"""Guard logic for PreToolUse hook."""

import contextlib
import io
import json
import os
import pathlib
import re
import sys
from typing import Optional

from .config import GATE_DIR, _BMD_DIR, _KEY_ACCESS_IN_CONTENT, _AGENT_ZONES
from .utils import is_code_target, is_free, norm_path, rel_to_root, repo_root
from .bash_targets import extract_bash_targets

# Import gate script
if GATE_DIR is None:
    sys.stderr.write("metodoloji-hooks: gate script not found — fail-closed\n")
    sys.exit(2)

if str(GATE_DIR) not in sys.path:
    sys.path.insert(0, str(GATE_DIR))
import run_experiment as gate  # noqa: E402


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
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = gate.verify(rec)
        return rc, gate.record_scope(rec)
    except Exception:
        return 1, ""


_STORY_RE = re.compile(r"\b\d+-\d+-[a-z][a-z0-9-]*\.md\b", re.IGNORECASE)


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


def _validate_story_experiment_refs(content: str) -> tuple[bool, str]:
    """Validate that all experiment_refs in a story file point to approved records.

    Returns (is_valid, reason).
    """
    refs = _parse_experiment_refs(content)
    if not refs:
        # No experiment_refs — not a story with metadata, allow
        return True, ""

    recs_dir = pathlib.Path("docs/experiments")
    if not recs_dir.is_dir():
        return False, "experiment_refs found but docs/experiments/ directory missing"

    for ref in refs:
        exp_id = ref.get("id", "")
        status = ref.get("status", "")
        if not exp_id:
            continue
        if status in ("BEKLİYOR", "REDDEDİLDİ", "PENDING", "REJECTED"):
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
_DOD_ID_RE = re.compile(r"\[?DoD-(\d+)\]?")
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
    """
    issues = []

    # 1. Validate AC metadata
    acs = _parse_ac_metadata(content)
    for ac in acs:
        if not ac["experiment"]:
            issues.append(f"{ac['id']}: missing Experiment field")
        elif ac["experiment"] in ("—", "-") and not ac["is_hypothesis"]:
            issues.append(f"{ac['id']}: Experiment=— but no [HYPOTHESIS] tag")
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
        root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    root = os.path.abspath(root)

    # Extract story status (handles: 'Status: done', '- **Status:** done', etc.)
    _STATUS_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(.+)", re.IGNORECASE | re.MULTILINE)
    status_match = _STATUS_RE.search(content)
    if not status_match:
        return True, ""  # No status = not a story file
    status = status_match.group(1).strip().lower()

    # Extract story key from content (title) or filename
    story_key = _extract_story_key_from_content(content)
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
            found_meth = False
            for meth_file in meth_dir.glob("S-*.md"):
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


def find_approved(target: str, recs_dir: str | None = None) -> tuple[bool, str]:
    """Find a VERIFIED record whose scope matches target."""
    target_rel = norm_path(target).lstrip("/")
    recs_dir = recs_dir or "docs/experiments"
    base = pathlib.Path(recs_dir)
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

        # Free zone — no approval needed
        if is_free(rel):
            continue

        # Check if it's a code target
        if not is_code_target(rel):
            continue

        # Check for secret references in file content (for free zones)
        if any(rel.startswith(zone) for zone in _AGENT_ZONES):
            try:
                content = ""
                if tool_name == "file_editor":
                    content = str(tool_input.get("content", ""))
                elif tool_name == "notebook_editor":
                    content = _notebook_content_to_text(tool_input.get("content", []))
                if _KEY_ACCESS_IN_CONTENT.search(content):
                    return {
                        "decision": "deny",
                        "reason": f"Secret access pattern detected in {rel} — blocked."
                    }
            except Exception:
                pass

        # Find approved record
        approved, detail = find_approved(rel)
        if not approved:
            return {
                "decision": "deny",
                "reason": f"No approved experiment record for {rel}: {detail}. "
                          f"Create a hypothesis, measure, and get approval with "
                          f"run_experiment.py --record docs/experiments/E-XXX.md --run <cmd>"
            }

        # Story file validation: check experiment_refs + AC metadata + Task↔AC + DoD
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
                    valid, reason = _validate_story_experiment_refs(story_content)
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
            except Exception:
                pass  # Best-effort — don't block on parse errors

    return {"decision": "allow"}


# --- Quality Gate (PreToolUse, terminal) ---

def _is_git_commit(command: str) -> bool:
    """True if command is a git commit (or git commit -am, etc.)."""
    return bool(re.search(r"\bgit\b.*\bcommit\b", command))


def _extract_story_key_from_content(content: str) -> str:
    """Extract story key from file content — matches 'S-XXX' in title or 'N-N-slug' pattern."""
    # Try '# Story: S-XXX' header first (handles space variations around colon)
    m = re.search(r"#\s+Story\s*:\s*(\S+)", content, re.IGNORECASE)
    if m:
        return m.group(1)
    # Try '# Story S-XXX' (no colon)
    m = re.search(r"#\s+Story\s+(\S+)", content, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def _find_done_stories_without_qr(root: str) -> list[str]:
    """Find stories with Status: done that lack a QR record.

    Returns list of story keys (e.g. '1-2-user-auth' or 'S-001') missing QR.
    """
    stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    qr_dir = pathlib.Path(root) / "docs" / "quality"
    if not stories_dir.is_dir():
        return []

    # Collect all QR content to search for story references
    qr_content = ""
    if qr_dir.is_dir():
        for qr_file in qr_dir.glob("QR-*.md"):
            try:
                qr_content += qr_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    # Regex: matches 'Status: done', '- **Status:** done', etc.
    _DONE_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status_match = _DONE_RE.search(content)
        if not status_match:
            continue
        # Extract story key from content (title) or filename
        story_key = _extract_story_key_from_content(content)
        if not story_key:
            # Fallback: extract from filename (S-NNN → try content for N-N-slug)
            key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
            if key_match:
                story_key = key_match.group(1)
        if not story_key:
            # Last resort: use filename without extension
            story_key = story_file.stem
        if story_key not in qr_content:
            missing.append(story_key)
    return missing


def _find_done_stories_without_sp(root: str) -> list[str]:
    """Find stories with Status: done that reference an SP but lack SP record.

    Returns list of story keys missing SP.
    """
    stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    dev_dir = pathlib.Path(root) / "docs" / "development"
    if not stories_dir.is_dir():
        return []

    # Collect all SP content
    sp_content = ""
    if dev_dir.is_dir():
        for sp_file in dev_dir.glob("SP-*.md"):
            try:
                sp_content += sp_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    _DONE_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status_match = _DONE_RE.search(content)
        if not status_match:
            continue
        # Check if story references an SP record
        sp_ref = re.search(r"\bSP-(\d+)\b", content, re.IGNORECASE)
        if not sp_ref:
            continue  # No SP reference = not checked
        story_key = _extract_story_key_from_content(content)
        if not story_key:
            key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
            if key_match:
                story_key = key_match.group(1)
        if not story_key:
            story_key = story_file.stem
        if story_key not in sp_content and sp_ref.group(0) not in sp_content:
            missing.append(story_key)
    return missing


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
    _DONE_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status_match = _DONE_RE.search(content)
        if not status_match:
            continue
        story_key = _extract_story_key_from_content(content)
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

    This is the Kapi 1+2+3 enforcement — stories marked 'done' must have:
    - An Implementation Readiness record (IR) in docs/development/ (Kapi 1)
    - A corresponding Quality Record (QR) in docs/quality/ (Kapi 3)
    - A Sprint Planning record (SP) in docs/development/ (if story references SP, Kapi 2)
    """
    tool_name = json_in.get("tool_name", "")
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = json_in.get("tool_input", {}).get("command", "")
    if not _is_git_commit(command):
        return {"decision": "allow"}

    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    root = os.path.abspath(root)

    # Check IR (Kapi 1 — project-level readiness)
    missing_ir = _find_done_stories_without_ir(root)
    if missing_ir:
        return {
            "decision": "deny",
            "reason": (
                f"git commit blocked: {len(missing_ir)} done story(s) exist but no Implementation Readiness (IR) record. "
                f"Stories: {', '.join(missing_ir)}. "
                f"Run bmad-check-implementation-readiness to create IR record."
            ),
        }

    # Check QR (Kapi 3)
    missing_qr = _find_done_stories_without_qr(root)
    if missing_qr:
        return {
            "decision": "deny",
            "reason": (
                f"git commit blocked: {len(missing_qr)} story(s) marked 'done' lack Quality Record (QR). "
                f"Stories: {', '.join(missing_qr)}. "
                f"Create QR with: python3 scripts/create-qr-record.py --story docs/development/stories/S-XXX.md"
            ),
        }

    # Check SP (Kapi 2)
    missing_sp = _find_done_stories_without_sp(root)
    if missing_sp:
        return {
            "decision": "deny",
            "reason": (
                f"git commit blocked: {len(missing_sp)} story(s) reference SP but lack Sprint Planning record. "
                f"Stories: {', '.join(missing_sp)}. "
                f"Run bmad-sprint-planning to create SP record."
            ),
        }

    return {"decision": "allow"}


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


def _find_done_stories_without_pr(root: str) -> list[str]:
    """Find stories with Status: done that lack a PR record.

    Returns list of story keys missing PR.
    """
    stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    if not stories_dir.is_dir():
        return []

    # Collect all PR content
    pr_content = ""
    dev_dir = pathlib.Path(root) / "docs" / "development"
    if dev_dir.is_dir():
        for pr_file in dev_dir.glob("PR-*.md"):
            try:
                pr_content += pr_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    # Regex: matches 'Status: done', '- **Status:** done', etc.
    _DONE_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", re.IGNORECASE | re.MULTILINE)

    missing: list[str] = []
    for story_file in stories_dir.glob("S-*.md"):
        try:
            content = story_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status_match = _DONE_RE.search(content)
        if not status_match:
            continue
        # Extract story key from content (title) or filename
        story_key = _extract_story_key_from_content(content)
        if not story_key:
            key_match = re.search(r"(\d+-\d+-[a-z][a-z0-9-]+)", content, re.IGNORECASE)
            if key_match:
                story_key = key_match.group(1)
        if not story_key:
            story_key = story_file.stem
        if story_key not in pr_content:
            missing.append(story_key)
    return missing


def deploy(json_in: dict) -> dict:
    """Deploy gate: block deployment if done stories lack IR, QR, SP, or PR records.

    This is the Kapi 1+2+3+4 enforcement — stories marked 'done' must have:
    - An Implementation Readiness record (IR) in docs/development/ (Kapi 1)
    - A Sprint Planning record (SP) in docs/development/ (if story references SP, Kapi 2)
    - A Quality Record (QR) in docs/quality/ (Kapi 3)
    - A Production Readiness (PR) record in docs/development/ (Kapi 4)
    """
    tool_name = json_in.get("tool_name", "")
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = json_in.get("tool_input", {}).get("command", "")
    if not command or not _DEPLOY_CMD_RE.search(command):
        return {"decision": "allow"}

    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    root = os.path.abspath(root)

    # Check IR (Kapi 1 — project-level readiness)
    missing_ir = _find_done_stories_without_ir(root)
    if missing_ir:
        return {
            "decision": "deny",
            "reason": (
                f"Deploy blocked: {len(missing_ir)} done story(s) exist but no Implementation Readiness (IR) record. "
                f"Stories: {', '.join(missing_ir)}. "
                f"Run bmad-check-implementation-readiness to create IR record."
            ),
        }

    # Check QR (Kapi 3)
    missing_qr = _find_done_stories_without_qr(root)
    if missing_qr:
        return {
            "decision": "deny",
            "reason": (
                f"Deploy blocked: {len(missing_qr)} story(s) lack Quality Record (QR). "
                f"Stories: {', '.join(missing_qr)}. "
                f"Create QR first, then PR."
            ),
        }

    # Check SP (Kapi 2)
    missing_sp = _find_done_stories_without_sp(root)
    if missing_sp:
        return {
            "decision": "deny",
            "reason": (
                f"Deploy blocked: {len(missing_sp)} story(s) reference SP but lack Sprint Planning record. "
                f"Stories: {', '.join(missing_sp)}. "
                f"Run bmad-sprint-planning to create SP record."
            ),
        }

    # Check PR (Kapi 4)
    missing_pr = _find_done_stories_without_pr(root)
    if missing_pr:
        return {
            "decision": "deny",
            "reason": (
                f"Deploy blocked: {len(missing_pr)} story(s) lack Production Readiness (PR) record. "
                f"Stories: {', '.join(missing_pr)}. "
                f"Create PR record before deploying."
            ),
        }

    return {"decision": "allow"}
