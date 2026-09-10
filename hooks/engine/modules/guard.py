"""Guard logic for PreToolUse hook."""

import contextlib
import io
import os
import pathlib
import re
import sys
import time

from .config import GATE_DIR, _BMD_DIR, _KEY_ACCESS_IN_CONTENT, _DONE_RE
from .utils import (is_code_target, is_free, norm_path, normalize_hook_input,
                    rel_to_root, repo_root, extract_story_key_from_content,
                    dod_issues, _VERIFY_FIELD_RE)
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
    except Exception as exc:
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
    """Run gate verify on a record; return (rc, scope).
    
    Acquires an advisory lock on the record file during verification to prevent
    concurrent deletion (TOCTOU race). (HIGH #5 / ISSUE #57)
    """
    if not _load_gate():
        return 1, ""
    
    # NEW: Acquire advisory lock to prevent TOCTOU race (HIGH #5)
    # If locking fails, continue anyway (fail-open) but note the risk
    lock_file = None
    try:
        rec_path = pathlib.Path(rec)
        if rec_path.exists():
            # Try to acquire shared advisory lock
            lock_file = open(str(rec_path) + ".lock", "a+")
            try:
                import fcntl
                fcntl.flock(lock_file, fcntl.LOCK_SH)  # Shared lock
            except ImportError:
                # Windows: msvcrt with exponential backoff (MEDIUM #10 / ISSUE #65)
                try:
                    import msvcrt
                    import time
                    max_retries = 10
                    retry_interval_ms = 10  # Start with 10ms
                    max_interval_ms = 100   # Cap at 100ms
                    
                    for attempt in range(max_retries):
                        try:
                            lock_file.seek(0)
                            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)  # Blocking lock
                            break
                        except OSError:
                            if attempt < max_retries - 1:
                                # Exponential backoff: 10ms * 2^attempt, capped at 100ms
                                wait_ms = min(retry_interval_ms * (2 ** attempt), max_interval_ms)
                                time.sleep(wait_ms / 1000.0)
                            else:
                                # Last attempt failed, continue without lock (fail-open)
                                pass
                except (ImportError, OSError):
                    pass  # Lock failed, continue anyway (fail-open)
    except OSError:
        pass  # Lock file creation failed, continue anyway
    
    try:
        # NEW: Re-check file exists after lock acquired (HIGH #8 / ISSUE #63)
        # Prevents TOCTOU race where record is deleted between initial check and verify call
        if not rec_path.exists():
            return 1, ""  # Record deleted after we acquired lock
        
        # NEW: Add timeout to gate.verify() to prevent indefinite hangs (MEDIUM #14 / ISSUE #73)
        from .config import GATE_VERIFY_TIMEOUT_SECONDS
        import threading
        
        verify_result = [None]  # Mutable to capture result from thread
        verify_exception = [None]
        
        def run_verify():
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    verify_result[0] = gate.verify(rec)
            except Exception as e:
                verify_exception[0] = e
        
        verify_thread = threading.Thread(target=run_verify, daemon=True)
        verify_thread.start()
        verify_thread.join(timeout=GATE_VERIFY_TIMEOUT_SECONDS)
        
        # If thread still running after timeout, return error (fail-open)
        if verify_thread.is_alive():
            sys.stderr.write(f"metodoloji: verify_record({rec}) timeout after {GATE_VERIFY_TIMEOUT_SECONDS}s\n")
            return 1, ""  # Timeout = verification failed
        
        if verify_exception[0]:
            raise verify_exception[0]
        
        rc = verify_result[0]
        return rc, gate.record_scope(rec)
    except (AttributeError, TypeError, ValueError):
        # Specific exceptions: gate module errors (MEDIUM #7 / ISSUE #66)
        return 1, ""
    except Exception:
        # Unknown exceptions: log to stderr but fail-open
        try:
            import traceback
            sys.stderr.write(f"metodoloji: verify_record({rec}) unexpected error: {traceback.format_exc()[:200]}\n")
        except Exception:
            pass
        return 1, ""
    finally:
        # Release lock
        if lock_file:
            try:
                import fcntl
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            except (ImportError, AttributeError):
                try:
                    import msvcrt
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except (ImportError, OSError, AttributeError):
                    pass
            finally:
                try:
                    lock_file.close()
                except OSError:
                    pass


# Matches native story files (1-2-user-auth.md) AND methodology story records
# (S-001.md). Basename-anchored: notes-S-001.md or a/b-S-001.md/notes.md must
# NOT count as story files (substring match would drag ordinary files into
# the story metadata chain).
_STORY_BASENAME_RE = re.compile(r"^(?:\d+-\d+-[a-z][a-z0-9-]*\.md|S-\d+\.md)$", re.IGNORECASE)


def _is_story_file(rel: str) -> bool:
    """True when the path's basename is exactly a story filename."""
    base = rel.replace("\\", "/").rsplit("/", 1)[-1]
    return bool(_STORY_BASENAME_RE.match(base))


def _unchecked_story_write_warning(rel: str) -> str:
    """Warn-only notice when a terminal story write bypasses content checks."""
    return (
        f"{rel}: story write via terminal — its content is not visible to the "
        f"guard before the write, so AC/chain validation did not run here "
        f"(the PostToolUse audit enforces it after the fact)."
    )


def _story_heredoc_body(command: str, target: str) -> str | None:
    """Return the literal heredoc payload a terminal command writes to `target`.

    Best-effort parse of the canonical shell story-creation pattern
    (`cat <<'EOF' > docs/.../S-002.md` or `cat > docs/.../S-002.md <<'EOF'`).
    Returns None when the command does not write a plain heredoc to the story
    target — in that case the payload is unknowable at guard time.

    Note: callers only reach this for commands without `$` (variable targets
    are dropped before story detection), so no shell expansion is needed.
    """
    m = re.search(r"<<\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", command)
    if not m:
        return None
    marker = m.group(2)
    want = os.path.basename(target.replace("\\", "/"))
    matched = None
    for rm in re.finditer(r">\s*([^\s;|&'\"]+)", command):
        if os.path.basename(rm.group(1)) == want:
            matched = rm
            break
    if matched is None:
        return None
    # Everything after the heredoc marker's line, up to the bare terminator
    # line, is the literal payload. The tail of the opening line (which may
    # carry the `> file` redirect) is not payload.
    body: list[str] = []
    for line in command[m.end():].splitlines()[1:]:
        if line.strip() == marker:
            break
        body.append(line)
    return "\n".join(body) if body else None


def _frontmatter_block(content: str) -> str:
    """Return the YAML frontmatter body ('' when absent).

    The closing fence must sit alone on its line: a body rule (`---`) never
    ends the block early.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return ""


def _parse_experiment_refs(content: str) -> list[dict]:
    """Extract experiment_refs from YAML frontmatter of a story file.

    Returns a list of dicts with keys: id, scope, status.
    Returns empty list if no experiment_refs found or parsing fails.
    """
    frontmatter = _frontmatter_block(content)
    if not frontmatter:
        return []

    # Find experiment_refs block — indentation-aware line parse. Only lines
    # indented DEEPER than the experiment_refs key belong to the block; a
    # top-level key (status: draft) ends it instead of merging into the ref.
    refs: list[dict] = []
    refs_indent: int | None = None
    current: dict = {}
    current_indent = 0
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if refs_indent is None:
            if stripped.startswith("experiment_refs"):
                refs_indent = indent
            continue
        if indent <= refs_indent:
            break  # back at top level — block is over
        if stripped.startswith("- "):
            if current:
                refs.append(current)
            current = {}
            current_indent = indent
            inner = stripped[2:].strip()
            # Handle inline: - id: E-001
            kv = inner.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()
        elif ":" in stripped and current and indent > current_indent:
            kv = stripped.split(":", 1)
            current[kv[0].strip()] = kv[1].strip()
    if current:
        refs.append(current)
    return refs


def _validate_story_experiment_refs(content: str, root: str = "") -> tuple[bool, str]:
    """Validate that all experiment_refs in a story file point to approved records.

    Also validates that a story file has at least 1 AC with an experiment reference.
    
    NEW: Check if experiment records have been recently revised. If so, mark downstream
    as potentially stale (HIGH #6 / ISSUE #12: Rollback/cascade invalidation)

    Returns (is_valid, reason).
    """
    if not root:
        root = repo_root({})
    refs = _parse_experiment_refs(content)
    
    # NEW: Check for AC experiment references using regex to find AC-NNN with Experiment: E-NNN
    ac_exp_pattern = re.compile(r"\[AC-\d+\].*?Experiment:\s*(E-\d+|—|-)", re.DOTALL | re.IGNORECASE)
    ac_experiment_refs = ac_exp_pattern.findall(content)
    
    # Filter out dashes (—, -) to get actual experiment IDs
    actual_ac_exp_refs = [e for e in ac_experiment_refs if e not in ("—", "-")]
    
    # NEW: A story must have at least 1 AC with an experiment reference (not mandatory, but recommended)
    # For now, warn but don't block. Can be made mandatory later.
    if not actual_ac_exp_refs and not refs:
        # No experiment references found anywhere in story
        # This is a warning case (story can still proceed but should be linked to an experiment)
        pass  # Allow it to proceed (soft enforcement)
    
    if not refs:
        # No experiment_refs in frontmatter — allow, but if no ACs have experiments either, it's orphaned
        if not actual_ac_exp_refs:
            # Story has no link to any experiment — this is the orphan case
            return False, (
                "Story has no experiment reference: every acceptance criterion must reference "
                "an Experiment (E-NNN). Add 'Experiment: E-XXX' field to each AC to link this story "
                "to the experiment that validates it."
            )
        return True, ""

    recs_dir = pathlib.Path(root) / "docs" / "experiments"
    if not recs_dir.is_dir():
        return False, "experiment_refs found but docs/experiments/ directory missing"

    cascade_warnings = []  # NEW: Collect cascade invalidation warnings
    
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
        
        # NEW: Check if experiment was recently revised (HIGH #6 / ISSUE #12)
        # If E-NNN was modified recently, downstream records may be stale
        try:
            exp_mtime = exp_file.stat().st_mtime
            story_path = pathlib.Path(root) / content.split("\n")[0].replace("# Story: ", "").split(" — ")[0]
            # Very simple heuristic: if experiment is newer than 1 hour, warn about potential staleness
            # (In production, would compare with story's last-verified timestamp)
            import time
            if time.time() - exp_mtime < 3600:  # Modified in last hour
                cascade_warnings.append(
                    f"{exp_id} was recently modified (< 1 hour ago). "
                    f"Downstream records (IR/SP/S/QR/PR) may be stale — consider re-validation."
                )
        except (OSError, ValueError):
            pass  # Can't get mtime, continue
    
    # Also validate AC experiment references
    for ac_exp_ref in actual_ac_exp_refs:
        exp_id = ac_exp_ref
        exp_file = recs_dir / f"{exp_id}.md"
        if not exp_file.exists():
            return False, (
                f"AC references Experiment {exp_id} but record not found in docs/experiments/. "
                f"Create the experiment record before implementing this AC."
            )
        rc, _ = verify_record(str(exp_file))
        if rc != 0:
            return False, (
                f"AC references Experiment {exp_id} which is not verified (rc={rc}). "
                f"Get experiment approval first."
            )
    
    # NEW: If cascade warnings exist, return them as soft warnings (for hard gate only)
    if cascade_warnings:
        return False, "; ".join(cascade_warnings[:2])  # Return as validation failure in hard mode
    
    return True, ""


# --- AC Metadata Validation ---

_AC_ID_RE = re.compile(r"\[AC-(\d+)\]")
_TASK_AC_RE = re.compile(r"AC:\s*(AC-\d+)")
_HYPOTHESIS_RE = re.compile(r"\[HYPOTHESIS\]")
_EXPERIMENT_FIELD_RE = re.compile(r"Experiment:\s*(E-\d+|—|-)")
_MEASURED_FIELD_RE = re.compile(r"Measured:\s*(true|false)", re.IGNORECASE)
_TYPE_FIELD_RE = re.compile(r"Type:\s*(agent-verifiable|user-evaluable|hybrid)", re.IGNORECASE)
# _VERIFY_FIELD_RE and the DoD rules are shared with the audit's QR DoD check
# (single source of truth in .utils).


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


def _check_duplicate_record_ids(root: str, filename: str, record_type: str) -> tuple[bool, str]:
    """Check if a record ID is unique across all existing records of that type.
    
    Scans docs/experiments (E-NNN), docs/stories (S-NNN), docs/implementation-readiness (IR-NNN),
    docs/sprint-plans (SP-NNN), docs/quality-records (QR-NNN), docs/production-readiness (PR-NNN)
    for duplicate IDs. (MEDIUM #2 / ISSUE #61)
    
    Returns (is_unique, reason).
    """
    try:
        # Extract record ID from filename (e.g., "E-001.md" → "E-001")
        match = re.match(r"^([A-Z]+-\d+)\.md$", filename)
        if not match:
            return True, ""  # Not a record file, skip
        
        record_id = match.group(1)
        
        # Map record type to directory
        type_to_dir = {
            "E": "docs/experiments",
            "IR": "docs/implementation-readiness",
            "SP": "docs/sprint-plans",
            "S": "docs/stories",
            "QR": "docs/quality-records",
            "PR": "docs/production-readiness",
        }
        
        if record_type not in type_to_dir:
            return True, ""  # Unknown type, skip
        
        rec_dir = pathlib.Path(root) / type_to_dir[record_type]
        if not rec_dir.exists():
            return True, ""  # Directory doesn't exist yet
        
        # Count how many files have this record ID (with bounds check)
        # NEW: Limit glob iteration (MEDIUM #11 / ISSUE #70)
        from .config import MAX_DUPLICATE_CHECK_RECORDS
        matching_files = []
        count = 0
        for f in rec_dir.glob(f"{record_id}.md"):
            count += 1
            if count > MAX_DUPLICATE_CHECK_RECORDS:
                break
            matching_files.append(f)
        
        # If more than 1 file, it's a duplicate
        if len(matching_files) > 1:
            duplicates = [str(f.relative_to(root)) for f in matching_files]
            return False, (
                f"Duplicate record ID '{record_id}' detected: {', '.join(duplicates)}. "
                f"Record IDs must be unique within their type."
            )
        
        return True, ""
    
    except Exception as e:
        # Can't check, allow write (fail-open)
        return True, f"(duplicate check skipped: {str(e)[:100]})"


def _validate_story_metadata(content: str) -> tuple[bool, str]:
    """Validate AC metadata, Task↔AC mapping, DoD structure, and STATUS field state machine.

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
          
    NEW: Status field state machine validation (HIGH #3 / ISSUE #11)
    - Valid states: backlog, ready-for-dev, in-progress, review, done, blocked
    - Valid transitions: backlog → ready-for-dev → in-progress → review → done
    - blocked can transition from/to any state (exception for emergencies)
    """
    issues = []

    # NEW: Validate status field state machine (HIGH #3 / ISSUE #11)
    _STATUS_RE = re.compile(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(.+)", re.IGNORECASE | re.MULTILINE)
    status_match = _STATUS_RE.search(content)
    if status_match:
        current_status = status_match.group(1).strip().lower()
        # Valid states in the state machine
        valid_states = {"backlog", "ready-for-dev", "in-progress", "review", "done", "blocked"}
        if current_status not in valid_states:
            issues.append(f"Invalid status '{current_status}'. Valid: backlog, ready-for-dev, in-progress, review, done, blocked")
        # Note: Full transition validation (e.g., backlog→done not allowed) would require
        # knowing previous status. For now, we validate only that current status is legal.

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
    # Shared with the audit's QR DoD check (.utils.dod_issues) so guard and
    # audit enforce the identical DoD rules (identifier + Verify per item).
    dod_match = re.search(r"##\s+Definition\s+of\s+Done\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if dod_match:
        issues.extend(dod_issues(dod_match.group(1)))

    if issues:
        return False, "; ".join(issues[:5])  # Limit to 5 issues
    return True, ""


# --- Methodology Chain Validation ---

# Chain text cache: methodology-chain checks read whole record dirs per story
# write. Keyed (mtime_ns, size), bounded — unchanged records are not re-read.
_CHAIN_TEXT_CACHE: dict[str, tuple[tuple[int, int], str]] = {}


def _cached_text(path: "pathlib.Path") -> str:
    """Read a chain record, cached by (mtime_ns, size)."""
    s = str(path)
    try:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return path.read_text(encoding="utf-8", errors="replace")
    hit = _CHAIN_TEXT_CACHE.get(s)
    if hit is not None and hit[0] == key:
        return hit[1]
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(_CHAIN_TEXT_CACHE) >= 256:
        _CHAIN_TEXT_CACHE.pop(next(iter(_CHAIN_TEXT_CACHE)))
    _CHAIN_TEXT_CACHE[s] = (key, text)
    return text


def _validate_methodology_chain(content: str, rel_path: str, root: str = "") -> tuple[bool, str]:
    """Validate that the methodology chain is intact for a story file.

    Checks:
    - If story status is 'done', QR record must exist
    - If story status is 'review', methodology record must exist
    - If story references SP-XXX, SP record must exist
    - If story references SP-XXX, SP must reference IR which must reference E (backreference chain)
    - Every AC must reference an approved experiment E-NNN

    Returns (is_valid, reason).
    """
    from .config import MAX_CHAIN_DEPTH, MAX_DUPLICATE_CHECK_RECORDS, MAX_EXPERIMENTS_TO_CHECK, MAX_STORY_COUNT
    
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

    # Check 1: If status is 'done', QR record must exist.
    # ponytail: read each QR file at most once per story write — the chain
    # cache below keeps (mtime_ns, size) so repeated writes don't re-read
    # unchanged records.
    if status == "done":
        qr_dir = pathlib.Path(root) / "docs" / "quality"
        if qr_dir.is_dir():
            # Look for QR record that references this story
            found_qr = False
            count = 0
            for qr_file in qr_dir.glob("QR-*.md"):
                count += 1
                if count > MAX_DUPLICATE_CHECK_RECORDS:  # Bounds check (MEDIUM #11)
                    break
                try:
                    qr_content = _cached_text(qr_file)
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
            count = 0
            for meth_file in meth_dir.glob("S-*.md"):
                count += 1
                if count > MAX_STORY_COUNT:  # Bounds check (MEDIUM #11)
                    break
                if meth_file.name == target_name:
                    continue
                try:
                    meth_content = _cached_text(meth_file)
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

    # Check 3: If story references SP-XXX, SP record must exist AND backreference chain S→SP→IR→E
    sprint_match = re.search(r"\bSP-(\d+)\b", content, re.IGNORECASE)
    if sprint_match:
        sp_id = sprint_match.group(0)  # e.g. SP-001
        dev_dir = pathlib.Path(root) / "docs" / "development"
        if dev_dir.is_dir():
            found_sp = False
            sp_file_found = None
            for sp_file in dev_dir.glob("SP-*.md"):
                try:
                    sp_content = _cached_text(sp_file)
                    if story_key in sp_content or sp_id in sp_content:
                        found_sp = True
                        sp_file_found = sp_file
                        break
                except OSError:
                    pass
            if not found_sp:
                issues.append(
                    f"Story references {sp_id} but no SP record found for {story_key}. "
                    f"Run bmad-sprint-planning to create SP record."
                )
            else:
                # NEW: Check backreference chain S→SP→IR→E (HIGH #4 / HIGH #8)
                # SP must reference IR, IR must reference E
                if sp_file_found:
                    sp_content = _cached_text(sp_file_found)
                    # Look for IR-NNN reference in SP
                    ir_match = re.search(r"\bIR-(\d+)\b", sp_content, re.IGNORECASE)
                    if ir_match:
                        ir_id = ir_match.group(0)
                        # Find IR record
                        found_ir = False
                        ir_file_found = None
                        for ir_file in dev_dir.glob("IR-*.md"):
                            try:
                                ir_content = _cached_text(ir_file)
                                if ir_id in ir_content:
                                    found_ir = True
                                    ir_file_found = ir_file
                                    break
                            except OSError:
                                pass
                        if not found_ir:
                            issues.append(
                                f"SP {sp_id} references {ir_id} but IR record not found. "
                                f"Create IR record before sprint planning."
                            )
                        else:
                            # Check if IR references E
                            if ir_file_found:
                                ir_content = _cached_text(ir_file_found)
                                # Look for E-NNN reference in IR
                                e_match = re.search(r"\bE-(\d+)\b", ir_content, re.IGNORECASE)
                                if not e_match:
                                    issues.append(
                                        f"IR record {ir_id} does not reference any Experiment (E-NNN). "
                                        f"IR must trace back to an approved experiment."
                                    )
                    else:
                        # NEW: SP exists but does NOT reference any IR (HIGH #4 - orphaned detection)
                        issues.append(
                            f"SP record {sp_id} does not reference any Implementation Readiness (IR) record. "
                            f"Stories cannot be planned without IR. Create IR record first."
                        )

    if issues:
        return False, "; ".join(issues[:3])
    return True, ""


# Verified-scope cache: find_approved runs gate.verify (HMAC) over every
# record per call. Cache per (mtime_ns, size) so repeated writes in a session
# don't re-verify unchanged records. Bounded (128 entries); rc=3 (key
# missing) is never cached — it would stick after --init-secret.
# NEW: Time-based expiry to prevent TOCTOU issues (MEDIUM #8 / ISSUE #67)
_VERIFY_CACHE: dict[str, tuple[tuple[int, int], int, str, float]] = {}
_VERIFY_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cached_verify(rec: str) -> tuple[int, str]:
    """verify_record with a small mtime+size-keyed cache (5-min TTL).
    
    NEW: Includes timestamp for time-based cache expiry (MEDIUM #8 / ISSUE #67)
    Prevents stale verification in long-running sessions where files may be deleted/re-created.
    """
    import time
    try:
        st = pathlib.Path(rec).stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return verify_record(rec)
    
    hit = _VERIFY_CACHE.get(rec)
    now = time.time()
    
    # Check cache hit: key must match AND cache must not be stale (5 min TTL)
    if hit is not None and hit[0] == key and (now - hit[3]) < _VERIFY_CACHE_TTL_SECONDS:
        return hit[1], hit[2]
    
    rc, scope = verify_record(rec)
    if rc != 3:
        if len(_VERIFY_CACHE) >= 128:
            _VERIFY_CACHE.pop(next(iter(_VERIFY_CACHE)))
        _VERIFY_CACHE[rec] = (key, rc, scope, now)  # NEW: Include timestamp
    return rc, scope


def find_approved(target: str, recs_dir: str | None = None, root: str = "") -> tuple[bool, str]:
    """Find a VERIFIED record whose scope matches target.
    
    Acquires advisory locks on record files while reading to prevent concurrent
    deletion (TOCTOU race). (HIGH #5 / ISSUE #57)
    """
    if not _load_gate():
        return False, "gate script not available"
    target_rel = norm_path(target).lstrip("/")
    if not root:
        root = repo_root({})
    recs_dir = recs_dir or "docs/experiments"
    if pathlib.PurePosixPath(recs_dir).is_absolute():
        return False, "absolute recs_dir rejected"
    # rc=2 (ADVISORY-BLOCK) is genuine-but-locked: surface its reason instead
    # of lumping it with forged/undecided rc=1.
    base = pathlib.Path(root) / recs_dir
    if not base.is_dir():
        return False, "docs/experiments/ not found"
    key_missing = False
    best = None
    advisory = None
    for rec in sorted(base.glob("*.md")):
        if rec.name == "_template.md":
            continue
        
        # NEW: Acquire advisory lock while verifying (HIGH #5 / ISSUE #57)
        lock_file = None
        try:
            lock_file = open(str(rec) + ".lock", "a+")
            try:
                import fcntl
                fcntl.flock(lock_file, fcntl.LOCK_SH)  # Shared lock
            except ImportError:
                try:
                    import msvcrt
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except (ImportError, OSError):
                    pass  # Lock failed, continue anyway
        except OSError:
            pass
        
        try:
            rc, scope = _cached_verify(str(rec))
            if rc == 3:
                key_missing = True
                continue
            if rc == 2:
                # Genuine token but locked (small sample / n unknown / metric
                # mismatch) — remember why instead of reporting "no record".
                if advisory is None:
                    advisory = (f"record {rec} is ADVISORY-BLOCKED (genuine token, "
                                f"code stays closed: small sample, n unknown, or metric "
                                f"mismatch — re-measure in a new record)")
                continue
            if rc != 0:
                continue
            try:
                matched = gate.scope_matches(scope, target_rel)
            except (AttributeError, TypeError, ValueError):
                # Specific exceptions from gate module (MEDIUM #7 / ISSUE #66)
                continue
            except Exception:
                # Unknown exceptions: log to stderr but continue
                try:
                    import traceback
                    sys.stderr.write(f"metodoloji: scope_matches error: {traceback.format_exc()[:200]}\n")
                except Exception:
                    pass
                continue
            if matched:
                return True, f"record {rec} (scope matched)"
            if best is None:
                best = f"record {rec} scope not matched"
        finally:
            # Release lock
            if lock_file:
                try:
                    import fcntl
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                except (ImportError, AttributeError):
                    try:
                        import msvcrt
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except (ImportError, OSError, AttributeError):
                        pass
                finally:
                    try:
                        lock_file.close()
                    except OSError:
                        pass
    
    if key_missing:
        return False, "gate key not configured (python3 run_experiment.py --init-secret)"
    return False, advisory or best or "no approved experiment record"


def _stamp_guard_to_blackboard(root: str, tool_name: str, tool_input: dict, decision: str) -> None:
    """Write guard decision to blackboard for traceability."""
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return
        from . import blackboard as bb
        target = tool_input.get("path") or tool_input.get("file_path") or tool_name
        bb.stamp_tool_event(root, tool_name, str(target), hook_event="PreToolUse")  # NEW: Track hook sequence (HIGH #7)
        # Set hot key if this is a story file
        if tool_name in ("file_editor", "notebook_editor"):
            path = tool_input.get("path", "")
            if path and ("S-" in path or re.search(r"/\d+-\d+-[a-z]", path)):
                bb.set_hot(root, path.split("/")[-1].replace(".md", ""))
        # Route alerts for guard decisions
        if decision == "deny":
            bb.post_alert(root, "guard", "warn", f"Guard denied: {tool_name} → {target}")
    except (ImportError, AttributeError, OSError):
        # Specific exceptions from blackboard (MEDIUM #7 / ISSUE #66)
        pass  # fail-open
    except Exception:
        # Unknown exceptions: log to stderr but fail-open
        try:
            import traceback
            sys.stderr.write(f"metodoloji: blackboard stamp error: {traceback.format_exc()[:200]}\n")
        except Exception:
            pass


def guard(json_in: dict) -> dict:
    """PreToolUse guard: block code writes without approved experiment record."""
    norm = normalize_hook_input(json_in)
    tool_name = norm["tool_name"]
    tool_input = norm["tool_input"]
    _soft_warnings: list[str] = []  # warn-only findings when quality_gate=soft

    # Stamp to blackboard (fire-and-forget, fail-open)
    root = repo_root(json_in)
    _stamp_guard_to_blackboard(root, tool_name, tool_input, "allow")

    # Determine targets based on tool
    targets: list[str] = []

    if tool_name == "terminal":
        command = tool_input.get("command", "")
        targets = extract_bash_targets(command)

        # Check for secret references in command
        if _secret_ref(command):
            _stamp_guard_to_blackboard(root, tool_name, tool_input, "deny")
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

    elif tool_name == "unknown":
        # normalize_hook_input flagged a tool the gate doesn't understand —
        # warn (visible) instead of silently allowing a write we can't judge.
        return {
            "decision": "allow",
            "methodology_warnings": [
                f"Unrecognized tool '{norm['raw_tool_name']}' — guard skipped; "
                f"verify this write manually."
            ],
        }

    # Check each target
    root = repo_root(json_in)
    for target in targets:
        rel = rel_to_root(root, target)

        # --- Story file validation (runs BEFORE free/code checks) ---
        # Story files (S-NNN.md or N-N-slug.md) need metadata validation
        # regardless of being in a free zone or non-code target.
        # Basename-anchored: notes-S-001.md is NOT a story file.
        if _is_story_file(rel):
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
                    # Shell writes cannot be inspected byte-for-byte, so guard
                    # validates the strongest signal it has:
                    #  * target already exists → the command modifies a story;
                    #    validate its CURRENT on-disk content (a shell-created
                    #    story may never have passed a content check, and this
                    #    write is the last chance to catch that before more
                    #    edits land on top of it).
                    #  * target is new → validate the heredoc payload when the
                    #    command writes one (cat <<EOF > S-002.md). When the
                    #    payload is not visible, flag the write warn-only:
                    #    AC/chain checks did not run here.
                    target_path = pathlib.Path(target)
                    if target_path.is_file():
                        try:
                            story_content = target_path.read_text(encoding="utf-8", errors="replace")
                        except OSError:
                            # Unreadable (e.g. permissions) — content unknowable,
                            # same warn-only treatment as an opaque creation.
                            story_content = ""
                            _soft_warnings.append(_unchecked_story_write_warning(rel))
                    else:
                        heredoc = _story_heredoc_body(command, target)
                        if heredoc is not None:
                            story_content = heredoc
                        else:
                            _soft_warnings.append(_unchecked_story_write_warning(rel))

                if story_content:
                    # NEW: Check for duplicate record IDs (MEDIUM #2 / ISSUE #61)
                    # Extract record ID from filename
                    filename = pathlib.Path(rel).name
                    match = re.match(r"^([A-Z]+-\d+)\.md$", filename)
                    if match:
                        record_type = match.group(1).split("-")[0]
                        unique, dup_reason = _check_duplicate_record_ids(root, filename, record_type)
                        if not unique:
                            return {
                                "decision": "deny",
                                "reason": f"Duplicate record ID detected: {dup_reason}"
                            }
                    
                    # 1. Validate experiment_refs in frontmatter — ALWAYS deny:
                    #    a story referencing an unapproved experiment must not be
                    #    written, regardless of strictness.
                    valid, reason = _validate_story_experiment_refs(story_content, root)
                    if not valid:
                        return {
                            "decision": "deny",
                            "reason": f"Story experiment validation failed for {rel}: {reason}"
                        }
                    # 2+3. Metadata + chain validation. Strictness comes from
                    #      custom/config.toml [hooks] quality_gate ONLY:
                    #      hard → deny, soft → warn-only. deploy_guard must NOT
                    #      leak into story-edit strictness (a hard deploy_guard
                    #      governs deploy commands, not file writes).
                    #      Read live so config changes apply per-call.
                    from .config import hook_gate_mode
                    soft_gate = hook_gate_mode("quality_gate") != "hard"
                    if soft_gate:
                        warnings = []
                        valid, reason = _validate_story_metadata(story_content)
                        if not valid:
                            warnings.append(f"Story metadata: {reason}")
                        # NEW: Check for duplicate record IDs (CRITICAL #23 / ISSUE #62)
                        basename = pathlib.Path(rel).name
                        record_type = basename.split("-")[0] if "-" in basename else ""
                        is_unique, dup_reason = _check_duplicate_record_ids(root, basename, record_type)
                        if not is_unique:
                            warnings.append(f"Record ID duplicate: {dup_reason}")
                        valid, reason = _validate_methodology_chain(story_content, rel, root)
                        if not valid:
                            warnings.append(f"Methodology chain: {reason}")
                        if warnings:
                            _soft_warnings.extend(warnings)
                    else:
                        valid, reason = _validate_story_metadata(story_content)
                        if not valid:
                            return {
                                "decision": "deny",
                                "reason": f"Story metadata validation failed for {rel}: {reason}"
                            }
                        # NEW: Check for duplicate record IDs (CRITICAL #23 / ISSUE #62)
                        basename = pathlib.Path(rel).name
                        record_type = basename.split("-")[0] if "-" in basename else ""
                        is_unique, dup_reason = _check_duplicate_record_ids(root, basename, record_type)
                        if not is_unique:
                            return {
                                "decision": "deny",
                                "reason": f"Record ID duplicate detected for {rel}: {dup_reason}"
                            }
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

        # Find approved record. code_guard=soft (brownfield adoption in
        # custom/config.toml [hooks]) relaxes a missing approval to warn-only.
        approved, detail = find_approved(rel, root=root)
        if not approved:
            from .config import hook_gate_mode
            msg = (f"No approved experiment record for {rel}: {detail}. "
                   f"Create a hypothesis, measure, and get approval with "
                   f"run_experiment.py --record docs/experiments/E-XXX.md --run <cmd>")
            if hook_gate_mode("code_guard") == "soft":
                _soft_warnings.append(msg)
                continue
            return {"decision": "deny", "reason": msg}

    # --- Intent-scope check (warn-only) ---
    # When the blackboard holds a scope key (e.g. blackboard.py write --key
    # scope --value src/auth), an out-of-scope write produces a warn-only
    # notice, never a deny. Experiment-approval deny always takes precedence.
    from .utils import _active_scope
    scope = _active_scope(root)
    intent_warnings = _intent_scope_warnings(scope=scope, targets=targets, root=root)

    all_warnings = intent_warnings + _soft_warnings
    if all_warnings:
        return {"decision": "allow", "methodology_warnings": all_warnings}

    return {"decision": "allow"}


def _intent_scope_warnings(scope: str, targets: list, root: str = "") -> list[str]:
    """List writes outside the active scope as warn-only notices.

    scope is a path (e.g. "src/auth"): any target outside it warns. Story
    keys (S-003, 1-2-login) and empty scope return []. Never denies.
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
                f"If this is a different task, update the blackboard scope "
                f"(blackboard.py write --key scope --value <new-scope>)."
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


def _check_methodology_chain_readiness(root: str) -> tuple[bool, str]:
    """Verify that each stage in the methodology chain is ready.
    
    E → IR → SP → S → QR → PR chain validation.
    Used by quality/deploy gates to ensure no stage is skipped.
    """
    issues = []
    
    # Check E (Experiment) records exist for done stories
    exp_dir = pathlib.Path(root) / "docs" / "experiments"
    if not exp_dir.is_dir():
        issues.append("No docs/experiments/ directory — E stage setup incomplete")
    
    # Check IR (Implementation Readiness) records
    ir_dir = pathlib.Path(root) / "docs" / "development"
    if not ir_dir.is_dir():
        issues.append("No docs/development/ directory — IR stage setup incomplete")
    
    # Check SP (Sprint Planning) records
    sp_files = list((ir_dir / "SP-*.md" if ir_dir.is_dir() else pathlib.Path()).glob("SP-*.md"))
    if not sp_files:
        # Not critical, but warn if stories exist
        story_dir = pathlib.Path(root) / "docs" / "development" / "stories"
        if story_dir.is_dir() and list(story_dir.glob("S-*.md")):
            issues.append("Stories exist but no SP (Sprint Planning) records found")
    
    # Check S (Story) and S→QR chain
    story_dir = pathlib.Path(root) / "docs" / "development" / "stories"
    qr_dir = pathlib.Path(root) / "docs" / "quality"
    if story_dir.is_dir() and qr_dir.is_dir():
        for story_file in story_dir.glob("S-*.md"):
            try:
                content = story_file.read_text(encoding="utf-8", errors="replace")
                # Check if story is marked done
                if re.search(r"status.*done", content, re.IGNORECASE):
                    story_key = story_file.stem
                    # Find corresponding QR
                    qr_found = False
                    for qr_file in qr_dir.glob("QR-*.md"):
                        qr_content = qr_file.read_text(encoding="utf-8", errors="replace")
                        if story_key in qr_content:
                            qr_found = True
                            break
                    if not qr_found:
                        issues.append(f"Story {story_key} done but no QR (Quality Record) found — QR stage skipped")
            except OSError:
                pass
    
    if issues:
        return False, "; ".join(issues[:3])
    return True, ""


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
    
    Also verifies the methodology chain E→IR→SP→S→QR→PR is intact.
    """
    norm = normalize_hook_input(json_in)
    tool_name = norm["tool_name"]
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = norm["tool_input"].get("command", "")
    if not _is_git_commit(command):
        return {"decision": "allow"}

    root = repo_root(json_in)
    root = os.path.abspath(root)

    # Stamp quality check to blackboard
    try:
        from .config import blackboard_enabled
        if blackboard_enabled():
            from . import blackboard as bb
            bb.stamp_tool_event(root, "quality", "git commit")
    except Exception:
        pass

    # Check methodology chain readiness first
    chain_ok, chain_reason = _check_methodology_chain_readiness(root)
    if not chain_ok:
        from .config import hook_gate_mode
        msg = f"Methodology chain incomplete: {chain_reason}"
        if hook_gate_mode("quality_gate") != "hard":
            return {"decision": "allow", "methodology_warnings": [msg]}
        return {"decision": "deny", "reason": msg}

    return _apply_gate_strictness(_check_gate_records(root, "git commit blocked"),
                                  "quality_gate")


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


def _apply_gate_strictness(result: dict, gate_key: str) -> dict:
    """Soft mode → a gate deny becomes warn-only allow.

    gate_key is the config key that controls this gate (quality_gate or
    deploy_guard). Read live (per-call) so config changes apply without reload.
    """
    if result.get("decision") != "deny":
        return result
    from .config import hook_gate_mode
    if hook_gate_mode(gate_key) != "hard":
        return {"decision": "allow", "methodology_warnings": [result["reason"]]}
    return result


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
    
    Also verifies the methodology chain E→IR→SP→S→QR→PR is complete for production.
    """
    norm = normalize_hook_input(json_in)
    tool_name = norm["tool_name"]
    if tool_name != "terminal":
        return {"decision": "allow"}

    command = norm["tool_input"].get("command", "")
    if not command or not _DEPLOY_CMD_RE.search(command):
        return {"decision": "allow"}

    root = repo_root(json_in)
    root = os.path.abspath(root)

    # Stamp deploy check to blackboard
    try:
        from .config import blackboard_enabled
        if blackboard_enabled():
            from . import blackboard as bb
            bb.stamp_tool_event(root, "deploy", command[:100])
            # Post handoff notification to production-readiness check
            bb.post_alert(root, "deploy", "gate", "Deploy gate triggered - checking PR readiness")
    except Exception:
        pass

    # Check methodology chain readiness for production
    chain_ok, chain_reason = _check_methodology_chain_readiness(root)
    if not chain_ok:
        from .config import hook_gate_mode
        msg = f"Methodology chain incomplete for production: {chain_reason}"
        if hook_gate_mode("deploy_guard") != "hard":
            return {"decision": "allow", "methodology_warnings": [msg]}
        return {"decision": "deny", "reason": msg}

    return _apply_gate_strictness(_check_gate_records(root, "Deploy blocked", include_pr=True),
                                  "deploy_guard")
