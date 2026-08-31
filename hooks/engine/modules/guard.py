"""Guard logic for PreToolUse hook."""

import contextlib
import io
import os
import pathlib
import re
import sys

from .config import GATE_DIR, _BMD_DIR, _KEY_ACCESS_IN_CONTENT, _DONE_RE
from .utils import is_code_target, is_free, norm_path, rel_to_root, repo_root, extract_story_key_from_content
from .bash_targets import extract_bash_targets

# Import gate script — deferred: sys.exit at module level kills the entire process
# (including audit which doesn't need the gate). Instead, gate is loaded lazily
# and guard/quality/deploy fail-closed at call time if it's missing.
gate = None

def _load_gate():
    global gate
    if gate is not None:
        return True
    if GATE_DIR is None:
        sys.stderr.write("metodoloji-hooks: gate script not found — fail-closed\n")
        return False
    if str(GATE_DIR) not in sys.path:
        sys.path.insert(0, str(GATE_DIR))
    try:
        import run_experiment as _gate  # noqa: E402
        gate = _gate
        return True
    except ImportError as exc:
        sys.stderr.write(f"metodoloji-hooks: gate import failed — {exc}\n")
        return False


def _secret_ref(s: str) -> bool:
    """True if s contains a secret leak indicator."""
    low = s.lower()
    if "gate-key" in low or "bmad_gate_key" in low:
        return True
    return bool(_BMD_DIR.search(s))


def _notebook_content_to_text(content) -> str:
    """Normalize notebook content to text for scanning."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for cell in content:
        if isinstance(cell, dict):
            src = cell.get("source") or cell.get("code") or []
            if isinstance(src, list):
                parts.extend(src)
            elif isinstance(src, str):
                parts.append(src)
        elif isinstance(cell, str):
            parts.append(cell)
    return "\n".join(parts)


def verify_record(rec: str) -> tuple[int, str]:
    """Run gate verify on a record; return (rc, scope)."""
    if not _load_gate():
        return 1, ""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = gate.verify(rec)
        return rc, gate.record_scope(rec)
    except Exception:
        return 1, ""


# Matches native story files (1-2-user-auth.md) AND methodology story records (S-001.md)
_STORY_RE = re.compile(r"(?:\b\d+-\d+-[a-z][a-z0-9-]*\.md\b|\bS-\d+\.md\b)", re.IGNORECASE)


def _parse_experiment_refs(content: str) -> list[dict]:
    """Extract experiment_refs from YAML frontmatter of a story file.

    Returns a list of dicts with keys: id, scope, status.
    Returns empty list if no experiment_refs found or parsing fails.
    """
    # Look for YAML frontmatter between --- delimiters
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return []
    frontmatter = fm_match.group(1)

    # Find experiment_refs block — simple line-by-line parse
    refs: list[dict] = []
    in_refs = False
    current: dict = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("experiment_refs"):
            in_refs = True
            continue
        if in_refs:
            if stripped.startswith("- "):
                if current:
                    refs.append(current)
                current = {}
                inner = stripped[2:].strip()
                # Handle inline: - id: E-001
                kv = inner.split(":", 1)
                if len(kv) == 2:
                    current[kv[0].strip()] = kv[1].strip()
            elif ":" in stripped and current:
                kv = stripped.split(":", 1)
                current[kv[0].strip()] = kv[1].strip()
            elif stripped and not stripped.startswith("-") and not ":" in stripped:
                # End of experiment_refs block
                break
    if current:
        refs.append(current)
    return refs


def _validate_story_experiment_refs(content: str, root: str = "") -> tuple[bool, str]:
    """Validate that all experiment_refs in a story file point to approved records.

    Returns (is_valid, reason).
    """
    if not root:
        root = repo_root({})
    refs = _parse_experiment_refs(content)
    if not refs:
        # No experiment_refs — not a story with metadata, allow
        return True, ""

    recs_dir = pathlib.Path(root) / "docs" / "experiments"
    if not recs_dir.is_dir():
        return False, "experiment_refs found but docs/experiments/ directory missing"

    for ref in refs:
        exp_id = ref.get("id", "")
        status = ref.get("status", "")
        if not exp_id:
            continue
        if status in ("PENDING", "REJECTED"):
            return False, (
                f"Experiment {exp_id} has status '{status}' — "
                f"ACs linked to this experiment cannot be implemented. "
                f"Mark linked ACs as [HYPOTHESIS] or get experiment approval first."
            )
        # Check if the experiment record exists and is verified
        exp_file = recs_dir / f"{exp_id}.md"
        if not exp_file.exists():
            return False, (
                f"Experiment record {exp_id}.md not found in docs/experiments/. "
                f"Create the experiment record before implementing linked ACs."
            )
        rc, _ = verify_record(str(exp_file))
        if rc != 0:
            return False, (
                f"Experiment record {exp_id} is not verified (rc={rc}). "
                f"Run run_experiment.py --verify --record {exp_file} first."
            )
    return True, ""


# --- AC Metadata Validation ---

_AC_ID_RE = re.compile(r"\[AC-(\d+)\]")
_TASK_AC_RE = re.compile(r"AC:\s*(AC-\d+)")
_DOD_ID_RE = re.compile(r"[\[\(]?DoD-(\d+)[\]\)]?")
_HYPOTHESIS_RE = re.compile(r"\[HYPOTHESIS\]")
_EXPERIMENT_FIELD_RE = re.compile(r"Experiment:\s*(E-\d+|—|-)")
_MEASURED_FIELD_RE = re.compile(r"Measured:\s*(true|false)", re.IGNORECASE)
_TYPE_FIELD_RE = re.compile(r"Type:\s*(agent-verifiable|user-evaluable|hybrid)", re.IGNORECASE)
_VERIFY_FIELD_RE = re.compile(r"Verify:\s*(.+)")


def _parse_ac_metadata(content: str) -> list[dict]:
    """Parse Acceptance Criteria section and extract AC metadata.

    Returns list of dicts with keys: id, experiment, type, measured, verify, is_hypothesis.
    """
    acs = []
    # Find Acceptance Criteria section
    ac_match = re.search(r"##\s+Acceptance\s+Criteria\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not ac_match:
        return acs
    ac_section = ac_match.group(1)

    # Split by AC identifiers
    ac_blocks = re.split(r"(?=\[AC-\d+\])", ac_section)
    for block in ac_blocks:
        id_match = _AC_ID_RE.search(block)
        if not id_match:
            continue
        ac_id = f"AC-{id_match.group(1)}"
        experiment_m = _EXPERIMENT_FIELD_RE.search(block)
        type_m = _TYPE_FIELD_RE.search(block)
        measured_m = _MEASURED_FIELD_RE.search(block)
        verify_m = _VERIFY_FIELD_RE.search(block)
        is_hypothesis = bool(_HYPOTHESIS_RE.search(block))

        acs.append({
            "id": ac_id,
            "experiment": experiment_m.group(1) if experiment_m else "",
            "type": type_m.group(1) if type_m else "",
            "measured": measured_m.group(1).lower() if measured_m else "",
            "verify": verify_m.group(1).strip() if verify_m else "",
            "is_hypothesis": is_hypothesis,
        })
    return acs


def _parse_task_ac_refs(content: str) -> list[dict]:
    """Parse Technical Tasks section and extract AC references.

    Returns list of dicts with keys: task_text, ac_refs (list of AC IDs).
    """
    tasks = []
    # Find Technical Tasks section
    tt_match = re.search(r"##\s+Technical\s+Tasks\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not tt_match:
        return tasks
    tt_section = tt_match.group(1)

    for line in tt_section.splitlines():
        # Only capture top-level tasks (not indented subtasks)
        if line.startswith("- [ ]") or line.startswith("- [x]"):
            ac_refs = _TASK_AC_RE.findall(line)
            tasks.append({
                "task_text": line.strip(),
                "ac_refs": ac_refs,
            })
    return tasks


def _validate_story_metadata(content: str) -> tuple[bool, str]:
    """Validate AC metadata, Task↔AC mapping, and DoD structure.

    Returns (is_valid, reason).

    S-008 fix (D2 root cause):
    - (a) If story has no experiment_refs in frontmatter (empty refs list
          or no frontmatter), skip the AC 'missing Experiment field' check
          entirely. Per bench invariant: 'not a story with metadata' implies
          the AC's Experiment field is optional (the AC is testing the
          ref validation itself, not a real experiment).
    - (b) If AC is marked [HYPOTHESIS], skip both the 'missing Experiment
          field' and 'Experiment=— but no [HYPOTHESIS] tag' checks. The
          [HYPOTHESIS] tag is an explicit opt-out from the Experiment
          field requirement.
    """
    issues = []

    refs = _parse_experiment_refs(content)
    has_refs = bool(refs)

    # 1. Validate AC metadata
    acs = _parse_ac_metadata(content)
    for ac in acs:
        if has_refs and not ac["is_hypothesis"]:
            if not ac["experiment"]:
                issues.append(f"{ac['id']}: missing Experiment field")
            elif ac["experiment"] in ("—", "-"):
                issues.append(f"{ac['id']}: Experiment=— but no [HYPOTHESIS] tag")
        # When has_refs is False OR ac is HYPOTHESIS, Experiment field is optional.
        if not ac["type"]:
            issues.append(f"{ac['id']}: missing Type field")
        if not ac["measured"]:
            issues.append(f"{ac['id']}: missing Measured field")
        if not ac["verify"]:
            issues.append(f"{ac['id']}: missing Verify field")

    # 2. Validate Task↔AC mapping
    tasks = _parse_task_ac_refs(content)
    ac_ids = {ac["id"] for ac in acs}
    for task in tasks:
        if not task["ac_refs"]:
            issues.append(f"Task without AC reference: {task['task_text'][:60]}...")
        else:
            for ref in task["ac_refs"]:
                if ref not in ac_ids:
                    issues.append(f"Task references non-existent {ref}: {task['task_text'][:60]}...")

    # 3. Validate DoD structure
    dod_match = re.search(r"##\s+Definition\s+of\s+Done\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if dod_match:
        dod_section = dod_match.group(1)
        for line in dod_section.splitlines():
            line = line.strip()
            if line.startswith("- [ ]") or line.startswith("- [x]"):
                if not _DOD_ID_RE.search(line):
                    issues.append(f"DoD item without identifier: {line[:60]}...")
                if not _VERIFY_FIELD_RE.search(line) and "Verify:" not in line:
                    # Check next lines for Verify field
                    pass

    if issues:
        return False, "; ".join(issues[:5])  # Limit to 5 issues
    return True, ""


# --- Methodology Chain Validation ---

def _validate_methodology_chain(content: str, rel_path: str, root: str = "") -> tuple[bool, str]:
    """Validate that the methodology chain is intact for a story file.

    Checks:
    - If story status is 'done', QR record must exist
    - If story status is 'review', methodology record must exist
    - If story references SP-XXX, SP record must exist

    Returns (is_valid, reason).
    """
    issues = []
    if not root:
        root = repo_root({})
    root = os.path.abspath(root)

    # Extract story status (handles: 'Status: done', '- **Status:** done', etc.)
    _STATUS_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(.+)", re.IGNORECASE | re.MULTILINE)
    status_match = _STATUS_RE.search(content)
    if not status_match:
        return True, ""  # No status = not a story file
    status = status_match.group(1).strip().lower()

    # Extract story key from content (title) or filename
    story_key = extract_story_key_from_content(content)
    if not story_key:
        key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
        if key_match:
            story_key = key_match.group(1)
    if not story_key:
        # Fallback: extract from filename
        key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", rel_path, re.IGNORECASE)
        if key_match:
            story_key = key_match.group(1)
    if not story_key:
        return True, ""

    # Check 1: If status is 'done', QR record must exist
    if status == "done":
        qr_dir = pathlib.Path(root) / "docs" / "quality"
        if qr_dir.is_dir():
            # Look for QR record that references this story
            found_qr = False
            for qr_file in qr_dir.glob("QR-*.md"):
                try:
                    qr_content = qr_file.read_text(encoding="utf-8", errors="replace")
                    if story_key in qr_content:
                        found_qr = True
                        break
                except OSError:
                    pass
            if not found_qr:
                issues.append(
                    f"Story status is 'done' but no QR record found for {story_key}. "
                    f"Run: python3 scripts/create-qr-record.py --story {rel_path}"
                )

    # Check 2: If status is 'review', methodology record must exist
    if status in ("review", "done"):
        meth_dir = pathlib.Path(root) / "docs" / "development" / "stories"
        if meth_dir.is_dir():
            # S-014 fix (E-010, GATE-OK-E-010-44abfab68a12b8b4f46ba8984dfa3f89):
            # exclude the story file itself from the methodology search. The
            # story mentions its own key, so without this check, the glob
            # trivially matched and the methodology check false-positived.
            target_name = pathlib.Path(rel_path).name
            found_meth = False
            for meth_file in meth_dir.glob("S-*.md"):
                if meth_file.name == target_name:
                    continue
                try:
                    meth_content = meth_file.read_text(encoding="utf-8", errors="replace")
                    if story_key in meth_content:
                        found_meth = True
                        break
                except OSError:
                    pass
            if not found_meth:
                issues.append(
                    f"Story status is '{status}' but no methodology record found for {story_key}. "
                    f"Run: python3 scripts/create-methodology-record.py --story {rel_path}"
                )

    # Check 3: If story references SP-XXX, SP record must exist
    sprint_match = re.search(r"\bSP-(\d+)\b", content, re.IGNORECASE)
    if sprint_match:
        sp_id = sprint_match.group(0)  # e.g. SP-001
        dev_dir = pathlib.Path(root) / "docs" / "development"
        if dev_dir.is_dir():
            found_sp = False
            for sp_file in dev_dir.glob("SP-*.md"):
                try:
                    sp_content = sp_file.read_text(encoding="utf-8", errors="replace")
                    if story_key in sp_content or sp_id in sp_content:
                        found_sp = True
                        break
                except OSError:
                    pass
            if not found_sp:
                issues.append(
                    f"Story references {sp_id} but no SP record found for {story_key}. "
                    f"Run bmad-sprint-planning to create SP record."
                )

    if issues:
        return False, "; ".join(issues[:3])
    return True, ""


def find_approved(target: str, recs_dir: str | None = None, root: str = "") -> tuple[bool, str]:
    """Find a VERIFIED record whose scope matches target."""
    if not _load_gate():
        return False, "gate script not available"
    target_rel = norm_path(target).lstrip("/")
    if not root:
        root = repo_root({})
    recs_dir = recs_dir or "docs/experiments"
    base = pathlib.Path(root) / recs_dir
    if not base.is_dir():
        return False, "docs/experiments/ not found"
    key_missing = False
    best = None
    for rec in sorted(base.glob("*.md")):
        if rec.name == "_template.md":
            continue
        rc, scope = verify_record(str(rec))
        if rc == 3:
            key_missing = True
            continue
        if rc != 0:
            continue
        if gate.scope_matches(scope, target_rel):
            return True, f"record {rec} (scope matched)"
        if best is None:
            best = f"record {rec} scope not matched"
    if key_missing:
        return False, "gate key not configured (python3 run_experiment.py --init-secret)"
    return False, best or "no approved experiment record"


def guard(json_in: dict) -> dict:
    """PreToolUse guard: block code writes without approved experiment record."""
    tool_name = json_in.get("tool_name", "")
    tool_input = json_in.get("tool_input", {})

    # Determine targets based on tool
    targets: list[str] = []

    if tool_name == "terminal":
        command = tool_input.get("command", "")
        targets = extract_bash_targets(command)

        # Check for secret references in command
        if _secret_ref(command):
            return {
                "decision": "deny",
                "reason": "Gate key reference detected in command — blocked."
            }

    elif tool_name == "file_editor":
        path = tool_input.get("path", "")
        if path:
            targets = [path]

    elif tool_name == "notebook_editor":
        path = tool_input.get("path", "")
        if path:
            targets = [path]

    # Check each target
    root = repo_root(json_in)
    for target in targets:
        rel = rel_to_root(root, target)

        # --- Story file validation (runs BEFORE free/code checks) ---
        # Story files (S-NNN.md or N-N-slug.md) need metadata validation
        # regardless of being in a free zone or non-code target.
        if _STORY_RE.search(rel):
            try:
                story_content = ""
                if tool_name == "file_editor":
                    story_content = str(tool_input.get("content", ""))
                    # If content is empty, try reading from disk
                    if not story_content.strip():
                        target_path = pathlib.Path(target)
                        if target_path.is_file():
                            story_content = target_path.read_text(encoding="utf-8", errors="replace")
                elif tool_name == "terminal":
                    # For terminal commands that create story files, skip AC check
                    # (the file doesn't exist yet)
                    pass

                if story_content:
                    # 1. Validate experiment_refs in frontmatter
                    valid, reason = _validate_story_experiment_refs(story_content, root)
                    if not valid:
                        return {
                            "decision": "deny",
                            "reason": f"Story experiment validation failed for {rel}: {reason}"
                        }
                    # 2. Validate AC metadata + Task↔AC + DoD structure
                    valid, reason = _validate_story_metadata(story_content)
                    if not valid:
                        return {
                            "decision": "deny",
                            "reason": f"Story metadata validation failed for {rel}: {reason}"
                        }
                    # 3. Validate methodology chain (QR for done, methodology record for review/done, SP if referenced)
                    valid, reason = _validate_methodology_chain(story_content, rel, root)
                    if not valid:
                        return {
                            "decision": "deny",
                            "reason": f"Methodology chain validation failed for {rel}: {reason}"
                        }
            except Exception as exc:
                sys.stderr.write(f"metodoloji: story validation error for {rel}: {exc}\n")
            # Story validation passed — continue to next target
            # (story files don't need experiment approval check)
            continue

        # --- Non-story files: free zone and code target checks ---

        # D7 — Content secret scan (S-005 fix: moved BEFORE free-zone check)
        # Apply to all paths so agent-zone files (scratch/, tmp/) are also scanned.
        # Without this, free-zone files bypass _KEY_ACCESS_IN_CONTENT entirely.
        if tool_name in ("file_editor", "notebook_editor"):
            try:
                content = ""
                if tool_name == "file_editor":
                    content = str(tool_input.get("content", ""))
                elif tool_name == "notebook_editor":
                    content = _notebook_content_to_text(tool_input.get("content", []))
                if content and _KEY_ACCESS_IN_CONTENT.search(content):
                    return {
                        "decision": "deny",
                        "reason": f"Secret access pattern detected in {rel} — blocked."
                    }
            except Exception as exc:
                sys.stderr.write(f"metodoloji: secret check error for {rel}: {exc}\n")

        # Free zone — no approval needed
        if is_free(rel):
            continue

        # Check if it's a code target
        if not is_code_target(rel):
            continue

        # Find approved record
        approved, detail = find_approved(rel, root=root)
        if not approved:
            return {
                "decision": "deny",
                "reason": f"No approved experiment record for {rel}: {detail}. "
                          f"Create a hypothesis, measure, and get approval with "
                          f"run_experiment.py --record docs/experiments/E-XXX.md --run <cmd>"
            }

    # --- Intent-scope check (warn-only) ---
    # If the active scope (e.g. "scope: src/auth" in the memlog) exists, a
    # write outside that scope is a warning, never a deny — the
    # experiment-approval logic above stays authoritative.
    from .utils import _active_scope
    scope = _active_scope(root)
    intent_warnings = _intent_scope_warnings(scope=scope, targets=targets, root=root)
    if intent_warnings:
        return {"decision": "allow", "methodology_warnings": intent_warnings}

    return {"decision": "allow"}


def _intent_scope_warnings(scope: str, targets: list, root: str = "") -> list[str]:
    """Warn-only list of writes outside the active scope.

    scope is a path (e.g. "src/auth"). A target outside that path gets a
    warning. Never denies. Story keys (S-003, 1-2-login) and empty scope
    return [].
    """
    scope = (scope or "").strip()
    if not scope or scope.startswith("S-") or re.fullmatch(r"\d+-\d+-[a-z][\w-]*", scope):
        return []  # no path scope, or a story key — nothing to check
    if not root:
        from .utils import repo_root
        root = repo_root({})
    from .utils import rel_to_root, norm_path
    scope_norm = norm_path(scope).rstrip("/")
    warnings = []
    for t in targets:
        rel = rel_to_root(root, str(t))
        if rel and not (rel == scope_norm or rel.startswith(scope_norm + "/")):
            warnings.append(
                f"Write to {rel} is outside the active scope '{scope}'. "
                f"If this is a different task, update the memlog purpose."
            )
    return warnings


# --- Quality Gate (PreToolUse, terminal) ---

def _is_git_commit(command: str) -> bool:
    """True if command is a git commit (or git commit -am, etc.)."""
    return bool(re.search(r"\bgit\b.*\bcommit\b", command))


def _find_done_stories_without_record(root: str, record_glob: str, record_dir: str,
                                      require_sp_ref: bool = False) -> list[str]:
    """Find stories with Status: done that lack a record of the given type.

    Args:
        record_glob: glob for record files (e.g. 'QR-*.md', 'SP-*.md').
        record_dir: directory to scan (project-relative, e.g. 'docs/quality').
        require_sp_ref: only check stories that reference an SP record.

    Returns list of story keys (e.g. '1-2-user-auth' or 'S-001') missing the record.
    """
    stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    rec_dir = pathlib.Path(root) / record_dir
    if not stories_dir.is_dir():
        return []

    # Collect all record content to search for story references
    rec_content = ""
    if rec_dir.is_dir():
        for rec_file in rec_dir.glob(record_glob):
            try:
                rec_content += rec_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _DONE_RE.search(content):
            continue
        sp_ref = None
        if require_sp_ref:
            # Only check stories that reference an SP record
            sp_ref = re.search(r"\bSP-(\d+)\b", content, re.IGNORECASE)
            if not sp_ref:
                continue
        # Extract story key from content (title) or filename
        story_key = extract_story_key_from_content(content)
        if not story_key:
            # Fallback: extract from filename (S-NNN → try content for N-N-slug)
            key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
            if key_match:
                story_key = key_match.group(1)
        if not story_key:
            # Last resort: use filename without extension
            story_key = story_file.stem
        if story_key in rec_content:
            continue
        # SP records may be referenced by ID even when the story key isn't in content
        if sp_ref is not None and sp_ref.group(0) in rec_content:
            continue
        missing.append(story_key)
    return missing


def _find_done_stories_without_qr(root: str) -> list[str]:
    """Find stories with Status: done that lack a QR record."""
    return _find_done_stories_without_record(root, "QR-*.md", "docs/quality")


def _find_done_stories_without_sp(root: str) -> list[str]:
    """Find stories with Status: done that reference an SP but lack SP record."""
    return _find_done_stories_without_record(root, "SP-*.md", "docs/development",
                                             require_sp_ref=True)


def _find_done_stories_without_pr(root: str) -> list[str]:
    """Find stories with Status: done that lack a PR record."""
    return _find_done_stories_without_record(root, "PR-*.md", "docs/development")


def _find_done_stories_without_ir(root: str) -> list[str]:
    """Find done stories when no IR record exists (Kapi 1 gate bypassed).

    IR is a project-level readiness record — if ANY done stories exist but
    NO IR records exist in docs/development/, the readiness gate was skipped.
    Returns list of story keys if IR is missing, empty list if IR exists.
    """
    stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    dev_dir = pathlib.Path(root) / "docs" / "development"
    if not stories_dir.is_dir():
        return []

    # Check if ANY IR record exists
    has_ir = False
    if dev_dir.is_dir():
        for ir_file in dev_dir.glob("IR-*.md"):
            if ir_file.name.startswith("_"):
                continue
            has_ir = True
            break
    if has_ir:
        return []  # IR gate was evaluated — OK

    # No IR records exist — check if there are done stories
    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status_match = _DONE_RE.search(content)
        if not status_match:
            continue
        story_key = extract_story_key_from_content(content)
        if not story_key:
            key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
            if key_match:
                story_key = key_match.group(1)
        if not story_key:
            story_key = story_file.stem
        missing.append(story_key)
    return missing


def quality(json_in: dict) -> dict:
    """Quality gate: block git commit if done stories lack IR, QR, or SP records.

    This is the Gate 1+2+3 enforcement — stories marked 'done' must have:
    - An Implementation Readiness record (IR) in docs/development/ (Gate 1)
    - A corresponding Quality Record (QR) in docs/quality/ (Gate 3)
    - A Sprint Planning record (SP) in docs/development/ (if story references SP, Gate 2)
    """
    tool_name = json_in.get("tool_name", "")
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = json_in.get("tool_input", {}).get("command", "")
    if not _is_git_commit(command):
        return {"decision": "allow"}

    root = repo_root({})
    root = os.path.abspath(root)
    return _check_gate_records(root, "git commit blocked")


# --- Deploy Gate (PreToolUse, terminal) ---

_DEPLOY_CMD_RE = re.compile(
    r"(?i)(?:"
    r"\bterraform\s+(?:apply|destroy|plan)\b|"
    r"\bkubectl\s+(?:apply|rollout|deploy)\b|"
    r"\bdocker\s+(?:compose\s+)?(?:up|deploy)\b|"
    r"\bansible\s+(?:playbook|deploy)\b|"
    r"\bgit\s+push\s+(?:origin|upstream)\s+(?:main|master|production|prod)\b|"
    r"\b部署\b|"
    r"\bdeploy\b"
    r")"
)


def _check_gate_records(root: str, blocked_action: str, include_pr: bool = False) -> dict:
    """Run the record-chain gate checks (IR → QR → SP → [PR]).

    Shared by quality() and deploy(). Returns a deny dict with reason, or
    {"decision": "allow"} when all required records exist.
    """
    # Check IR (Gate 1 — project-level readiness)
    missing_ir = _find_done_stories_without_ir(root)
    if missing_ir:
        return {
            "decision": "deny",
            "reason": (
                f"{blocked_action}: {len(missing_ir)} done story(s) exist but no Implementation Readiness (IR) record. "
                f"Stories: {', '.join(missing_ir)}. "
                f"Run bmad-check-implementation-readiness to create IR record."
            ),
        }

    # Check QR (Gate 3)
    missing_qr = _find_done_stories_without_qr(root)
    if missing_qr:
        return {
            "decision": "deny",
            "reason": (
                f"{blocked_action}: {len(missing_qr)} story(s) marked 'done' lack Quality Record (QR). "
                f"Stories: {', '.join(missing_qr)}. "
                f"Create QR with: python3 scripts/create-qr-record.py --story docs/development/stories/S-XXX.md"
            ),
        }

    # Check SP (Gate 2)
    missing_sp = _find_done_stories_without_sp(root)
    if missing_sp:
        return {
            "decision": "deny",
            "reason": (
                f"{blocked_action}: {len(missing_sp)} story(s) reference SP but lack Sprint Planning record. "
                f"Stories: {', '.join(missing_sp)}. "
                f"Run bmad-sprint-planning to create SP record."
            ),
        }

    # Check PR (Gate 4 — deploy only)
    if include_pr:
        missing_pr = _find_done_stories_without_pr(root)
        if missing_pr:
            return {
                "decision": "deny",
                "reason": (
                    f"{blocked_action}: {len(missing_pr)} story(s) lack Production Readiness (PR) record. "
                    f"Stories: {', '.join(missing_pr)}. "
                    f"Create PR record before deploying."
                ),
            }

    return {"decision": "allow"}


def deploy(json_in: dict) -> dict:
    """Deploy gate: block deployment if done stories lack IR, QR, SP, or PR records.

    This is the Gate 1+2+3+4 enforcement — stories marked 'done' must have:
    - An Implementation Readiness record (IR) in docs/development/ (Gate 1)
    - A Sprint Planning record (SP) in docs/development/ (if story references SP, Gate 2)
    - A Quality Record (QR) in docs/quality/ (Gate 3)
    - A Production Readiness (PR) record in docs/development/ (Gate 4)
    """
    tool_name = json_in.get("tool_name", "")
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = json_in.get("tool_input", {}).get("command", "")
    if not command or not _DEPLOY_CMD_RE.search(command):
        return {"decision": "allow"}

    root = repo_root({})
    root = os.path.abspath(root)
    return _check_gate_records(root, "Deploy blocked", include_pr=True)
