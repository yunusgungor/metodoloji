"""Stop logic for Stop hook."""

import json
import pathlib
import re
import time

from .guard import find_approved
from .utils import is_code_target, is_free, rel_to_root


def _check_story_status(root: str, intent: str = "") -> tuple[bool, str]:
    """Check if a story is in-progress but incomplete.

    When `intent` names a story (e.g. "S-003'ü bitir" → S-003), only that
    story is checked — other stale in-progress stories don't block. Without
    intent, every in-progress story blocks (legacy behavior).

    Returns (should_block, reason).
    """
    target_key = ""
    if intent:
        from .utils import _story_key_from_intent
        target_key = _story_key_from_intent(intent)

    # Look for sprint-status.yaml. Canonical path is bmad-output/ (config.toml);
    # _bmad-output kept only as a legacy fallback for pre-migration projects.
    for candidate in [
        pathlib.Path(root) / "bmad-output" / "implementation-artifacts" / "sprint-status.yaml",
        pathlib.Path(root) / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml",
        pathlib.Path(root) / ".metodoloji" / "sprint-status.yaml",
    ]:
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
                # Check for in-progress stories
                in_progress = re.findall(r"^\s+(\d+-\d+-[a-z][a-z0-9-]+):\s+in-progress", content, re.MULTILINE)
                if target_key:
                    # Intent names a specific story: only block if it's in-progress.
                    if any(target_key == k for k in in_progress):
                        return True, (
                            f"Story {target_key} is in-progress but stop requested. "
                            f"Complete it before stopping."
                        )
                elif in_progress:
                    return True, (
                        f"Story in-progress but stop requested: {', '.join(in_progress)}. "
                        f"Complete the story before stopping."
                    )
            except OSError:
                pass
    return False, ""


def _latest_session_start(root: str) -> float:
    """Newest session_start marker timestamp in the audit log (0.0 = none).

    Scans from the TAIL: the newest marker is almost always near the end, so
    a bounded tail read replaces the full-file parse. Falls back to the full
    file only when the tail holds no marker.
    """
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return 0.0
    for line in reversed(tail):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == _SESSION_MARKER_TYPE:
            try:
                return float(rec.get("timestamp", 0) or 0)
            except (TypeError, ValueError):
                return 0.0
    # No marker in tail — full scan (old logs predate the tail window).
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0.0
    newest = 0.0
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == _SESSION_MARKER_TYPE:
            try:
                newest = max(newest, float(rec.get("timestamp", 0) or 0))
            except (TypeError, ValueError):
                pass
    return newest


def _story_status_is_stale(root: str, intent: str) -> bool:
    """True when the sprint-status file predates this session's start.

    A leftover in-progress story from a previous session must not wedge a new
    one; the intent-named story still blocks (explicit user focus wins).
    No session marker (old bootstrap) → not stale, legacy blocking behavior.
    """
    from .utils import _story_key_from_intent
    if intent and _story_key_from_intent(intent):
        return False
    session_start = _latest_session_start(root)
    if not session_start:
        return False
    newest = 0.0
    for candidate in [
        pathlib.Path(root) / "bmad-output" / "implementation-artifacts" / "sprint-status.yaml",
        pathlib.Path(root) / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml",
        pathlib.Path(root) / ".metodoloji" / "sprint-status.yaml",
    ]:
        try:
            if candidate.is_file():
                newest = max(newest, candidate.stat().st_mtime)
        except OSError:
            pass
    if not newest:
        return False
    return newest < session_start


# Cap on session lines read per stop: a bounded tail covers any realistic
# session; unbounded growth would make stop O(history).
_SESSION_TAIL_LINES = 20000


def _read_session_lines(root: str) -> list[str]:
    """Audit lines after the newest session_start marker (all lines if none).

    Single reader shared by touched-set + deny-budget (one file read per
    stop, not one per helper). Bounded to the newest _SESSION_TAIL_LINES so
    stop stays O(session), never O(history).
    """
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    lines = lines[-_SESSION_TAIL_LINES:]
    offset = 0
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == _SESSION_MARKER_TYPE:
            offset = i + 1
    return lines[offset:]


def _session_touched_code(root: str) -> list[str]:
    """Code files this session actually wrote (from the audit trail).

    Only lines after the newest session_start marker count; no marker (fresh
    session / logging disabled) → whole log counts once, then the marker is
    written. Pre-existing brownfield files are never listed: only PostToolUse
    records this session wrote count.
    """
    from .bash_targets import extract_bash_targets

    lines = _read_session_lines(root)
    touched: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or "tool" not in rec:
            continue  # session_start / stop_deny markers carry no tool input
        tool = str(rec.get("tool", ""))
        tool_input = rec.get("input", {})
        if not isinstance(tool_input, dict):
            continue
        if tool in ("file_editor", "notebook_editor"):
            path = tool_input.get("path", "") or tool_input.get("file_path", "")
            if path and "$" not in str(path):
                rel = rel_to_root(root, str(path))
                if rel and is_code_target(rel):
                    touched.add(rel)
        elif tool == "terminal":
            command = tool_input.get("command", "") or tool_input.get("cmd", "")
            if command and "$" not in str(command):
                for target in extract_bash_targets(str(command)):
                    rel = rel_to_root(root, str(target))
                    if rel and is_code_target(rel):
                        touched.add(rel)
    return sorted(touched)


# Marker the audit log carries per session start; stop only counts lines
# after the newest marker, so yesterday's unapproved touches never block
# today's session.
_SESSION_MARKER_TYPE = "session_start"

# stop_hook_active re-fires (Claude re-invokes Stop after a deny) let the
# session close: one push-back per stretch of work, never a wedge.
_MAX_STOP_DENIES_PER_SESSION = 1


def _stop_denies_so_far(root: str) -> int:
    """Count stop denies already recorded this session (after the marker)."""
    denies = 0
    for line in _read_session_lines(root):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == "stop_deny":
            denies += 1
    return denies


def record_session_start(root: str) -> None:
    """Append a session_start marker (called by the audit hook on SessionStart).

    Carries a timestamp so stop can tell stale sprint-status leftovers from
    this session's stories, and so the touched-set starts after this line.
    """
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": _SESSION_MARKER_TYPE,
                                "timestamp": time.time()},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass


def _record_stop_deny(root: str, reason: str) -> None:
    """Append a stop_deny marker so the next re-fire knows its deny budget."""
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "stop_deny", "reason": reason[:200]},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass


def _session_start_offset(root: str) -> int:
    """Index of the first audit line after the newest session_start marker (0 = none)."""
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    offset = 0
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == _SESSION_MARKER_TYPE:
            offset = i + 1
    return offset


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes or incomplete stories exist."""
    from .utils import repo_root
    root = repo_root(json_in)

    # 0. Loop breaker: stop_hook_active means Claude re-invoked Stop after a
    #    previous deny — honor the deny budget instead of wedging the session.
    if json_in.get("stop_hook_active"):
        return {"decision": "allow"}
    from .config import hook_gate_mode
    if hook_gate_mode("stop_guard") == "soft":
        return {"decision": "allow"}
    if _stop_denies_so_far(root) >= _MAX_STOP_DENIES_PER_SESSION:
        return {"decision": "allow"}

    # 1. Check for incomplete stories (intent-aware: if the session intent
    #    names a specific story, only that story blocks stop). A memlog whose
    #    status is 'complete' means the session's work is done — no story check.
    #    A stale sprint-status older than the session start never blocks
    #    (brownfield leftover), unless the intent names that story.
    from .utils import _active_intent, _active_progress
    intent = _active_intent(root)
    progress = _active_progress(root)
    if progress and progress.lower() in ("complete", "done", "completed"):
        intent = ""  # work finished — don't block on in-progress stories
    should_block, reason = _check_story_status(root, intent=intent)
    if should_block and not _story_status_is_stale(root, intent):
        _record_stop_deny(root, reason)
        return {"decision": "deny", "reason": reason}

    # 2. Check for unapproved code changes — SESSION-TOUCHED files only.
    # ponytail: audit log is the touched set; whole-tree scan false-blocks
    # brownfield projects (pre-existing code ≠ this session did it).
    # find_approved caches verify results by record mtime, so stop stays fast.
    for rel in _session_touched_code(root):
        if is_free(rel):
            continue
        approved, _ = find_approved(rel, root=root)
        if not approved:
            reason = (f"Unapproved code changes detected: {rel}. "
                      f"Complete experiment record before stopping.")
            _record_stop_deny(root, reason)
            return {"decision": "deny", "reason": reason}

    # 3. Surface pending code-docs so the agent sees unfinished work at session end.
    result = {"decision": "allow"}
    try:
        from .code_docs import load_pending_docs
        pending = load_pending_docs()
        if pending:
            result["pending_docs"] = pending
    except Exception:
        pass

    return result
