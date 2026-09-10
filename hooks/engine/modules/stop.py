"""Stop logic for Stop hook."""

import json
import pathlib
import re
import time

from .guard import find_approved
from .utils import is_code_target, is_free, rel_to_root


def _check_story_status(root: str, focus: str = "") -> tuple[bool, str]:
    """Check if a story is in-progress but incomplete.

    focus-aware: when the session focus names a story (e.g. "1-2-login"
    or "S-003") only that story blocks. Without a focus, or one naming
    no story, every in-progress story blocks (legacy behavior).

    Returns (should_block, reason).
    """
    target_key = ""
    if focus:
        from .utils import _story_key_from_focus
        target_key = _story_key_from_focus(focus)

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
                    # Focus names one story: only that story blocks.
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


def _story_status_is_stale(root: str, focus: str = "") -> bool:
    """True when the sprint-status file predates this session's start.

    A leftover in-progress story from a previous session must not wedge a new
    one; the focus-named story still blocks (explicit user focus wins).
    No session marker (old bootstrap) → not stale, legacy blocking behavior.
    """
    from .utils import _story_key_from_focus
    if focus and _story_key_from_focus(focus):
        return False  # explicit story focus — never stale
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
    
    NEW: Also records hook_event type for state machine validation (HIGH #7 / ISSUE #58)
    NEW: Generates unique session_id for multi-session isolation (MEDIUM #6 / ISSUE #65)
    """
    from .config import log_file
    import uuid
    
    # Generate unique session_id (timestamp + uuid for collision avoidance)
    session_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": _SESSION_MARKER_TYPE,
                                "hook_event": "SessionStart",
                                "session_id": session_id,
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


def _check_methodology_chain_completion(root: str) -> tuple[bool, str]:
    """Check if methodology chain E→IR→SP→S→QR→PR is complete.
    
    Warns if chain is incomplete (signals waiting in handoff channels).
    Does not block stop, only informs operator about pending stages.
    """
    try:
        from . import blackboard as bb
        waiting = bb.pending_handoff_channels(root)
        
        # Check for methodology chain stages waiting
        methodology_stages = {
            "bmad-research-experiment",
            "bmad-check-implementation-readiness",
            "bmad-sprint-planning",
            "bmad-create-story",
            "bmad-quality-record",
            "bmad-production-readiness",
        }
        
        stuck = [(s, c) for s, c in waiting.items() if s in methodology_stages and c > 0]
        if stuck:
            msg = "Methodology chain incomplete: " + ", ".join(
                f"{s} ({c} signal(s))" for s, c in stuck
            )
            return False, msg
    except Exception:
        pass
    
    return True, ""


def _validate_hook_state_machine(root: str) -> tuple[bool, str]:
    """Validate that hook events follow SessionStart→PreToolUse→PostToolUse→Stop order.
    
    Reads audit log and checks hook_event sequence for violations.
    Returns (is_valid, reason). (HIGH #7 / ISSUE #58)
    
    NEW: Also recognizes session_stop marker as session end (MEDIUM #3 / ISSUE #62)
    """
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    if not log_path.exists():
        return True, ""  # No log yet, OK
    
    try:
        session_started = False
        last_event = None
        violations = []
        
        with open(log_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                
                entry_type = entry.get("type", "")
                hook_event = entry.get("hook_event", "")
                
                # SessionStart marker
                if entry_type == "session_marker":
                    if hook_event == "SessionStart":
                        session_started = True
                        last_event = "SessionStart"
                    continue
                
                # NEW: session_stop marker (explicit session-end event)
                if entry_type == "session_stop":
                    if hook_event == "Stop":
                        if session_started and last_event:
                            # Valid end: SessionStart/PreToolUse/PostToolUse → Stop
                            if last_event not in ("SessionStart", "PreToolUse", "PostToolUse"):
                                violations.append(
                                    f"Hook sequence violation: last event '{last_event}' "
                                    f"should not transition to Stop"
                                )
                        session_started = False
                        last_event = "Stop"
                    continue
                
                # Stop marker (end of session) - legacy
                if entry_type == "stop":
                    if session_started and last_event:
                        # Valid end: SessionStart/PreToolUse/PostToolUse → Stop
                        if last_event not in ("SessionStart", "PreToolUse", "PostToolUse", "Stop"):
                            violations.append(
                                f"Hook sequence violation: last event '{last_event}' "
                                f"should not transition to Stop"
                            )
                    session_started = False
                    last_event = "Stop"
                    continue
                
                # Tool events with hook_event
                if hook_event in ("PreToolUse", "PostToolUse"):
                    # Validate transitions
                    if hook_event == "PreToolUse":
                        # PreToolUse must come after SessionStart (or another PostToolUse)
                        if not session_started:
                            violations.append(
                                f"Hook sequence violation: PreToolUse at line {line_no} "
                                f"without SessionStart"
                            )
                        elif last_event not in ("SessionStart", "PostToolUse"):
                            violations.append(
                                f"Hook sequence violation: PreToolUse follows '{last_event}' "
                                f"(expected SessionStart or PostToolUse)"
                            )
                        last_event = "PreToolUse"
                    
                    elif hook_event == "PostToolUse":
                        # PostToolUse must follow PreToolUse
                        if last_event != "PreToolUse":
                            violations.append(
                                f"Hook sequence violation: PostToolUse at line {line_no} "
                                f"follows '{last_event}' (expected PreToolUse)"
                            )
                        last_event = "PostToolUse"
        
        if violations:
            # Return first 2 violations as summary
            return False, "; ".join(violations[:2])
        
        return True, ""
    
    except Exception as e:
        # Can't validate log, but don't block stop
        return True, f"(hook validation skipped: {str(e)[:100]})"
    """Append the board's hot-key state to a deny reason (fail-open, gated).

    The notice tells the model which working context is still hot before the
    session closes — a nudge to wrap it up, never a block on its own.
    """
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return reason
        from . import blackboard as bb
        ctx = bb.compact_context(root)
        bits = []
        if ctx.get("hot"):
            bits.append(f"Blackboard hot key '{ctx['hot']}' is still active — "
                        "clear it (blackboard.py hot --clear) or finalize its artifact.")
        if ctx.get("hot_canvas"):
            hc = ctx["hot_canvas"]
            bits.append(f"Canvas '{hc['name']}' is still focused ({hc['cells']} cells) — "
                        "finalize or clear focus (blackboard.py canvas focus --clear).")
        alerts = bb.pending_alerts(root, "stop")
        if alerts:
            msgs = "; ".join(a["text"] for a in alerts[-3:])
            bits.append(f"{len(alerts)} pending alert(s): {msgs}.")
        try:
            waiting = bb.pending_handoff_channels(root)
        except Exception:
            waiting = {}
        waiting.pop("bmad-help", None)  # help skill has its own routing
        if waiting:
            w = ", ".join(f"{s} ({n})" for s, n in sorted(waiting.items()))
            total = sum(waiting.values())
            bits.append(f"PROACTIVE — hand-off waiting: {w}: {total} unclaimed "
                        "signal(s) left by completed upstream runs; do not close "
                        "the loop empty-handed (diagnose: blackboard.py "
                        "chain-health; claim: handoffs --skill <downstream>, "
                        "then consume its handoff channel).")  # announce-only
        if bits:
            bb.consume_alerts(root, "stop")  # deliver-once
            return reason + " " + " ".join(bits)
    except Exception:
        pass
    return reason


def _record_session_stop_marker(root: str) -> None:
    """Append a session_stop marker to the audit log (explicit session-end marker).
    
    Called by the stop hook to record session end time and context.
    (MEDIUM #3 / ISSUE #62: Session stop event)
    
    NEW: Includes session_id for multi-session isolation (MEDIUM #6 / ISSUE #65)
    """
    from .config import log_file
    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract session_id from most recent session_start if available
        session_id = ""
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Scan backwards to find last session_start
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "session_marker" and entry.get("hook_event") == "SessionStart":
                        session_id = entry.get("session_id", "")
                        break
                except (json.JSONDecodeError, ValueError):
                    pass
        except OSError:
            pass
        
        with open(log_path, "a", encoding="utf-8") as f:
            event = {"type": "session_stop",
                    "hook_event": "Stop",
                    "session_id": session_id,
                    "timestamp": time.time()}
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _record_session_to_blackboard(root: str) -> None:
    """Record session end to blackboard with handoff check."""
    # NEW: Write explicit session_stop marker to audit log (MEDIUM #3)
    _record_session_stop_marker(root)
    
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return
        from . import blackboard as bb

        # Record session end timestamp
        bb.record_watcher(root, "session_stop")

        # Update status to "complete"
        board = bb.read_board(root)
        if board.get("keys", {}).get("status"):
            bb.write_key(root, "status", "complete", type_="session")

        # Check for pending handoffs and notify
        try:
            waiting = bb.pending_handoff_channels(root)
            if waiting:
                for skill, count in waiting.items():
                    if count > 0:
                        bb.post_alert(root, "session", "handoff",
                                      f"Skill '{skill}' has {count} pending handoff(s)")
        except Exception:
            pass

        # Ensure bridge canvas is clean (focus cleared)
        try:
            board = bb.read_board(root)
            if board.get("hot_canvas") == "bridge":
                bb.canvas_focus(root, None)
        except Exception:
            pass
    except Exception:
        pass  # fail-open


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes or incomplete stories exist."""
    from .utils import repo_root
    root = repo_root(json_in)

    # NEW: Validate hook state machine (SessionStart→PreToolUse→PostToolUse→Stop order)
    # This is a diagnostic check, doesn't block stop, but informs operator (HIGH #7)
    hook_ok, hook_msg = _validate_hook_state_machine(root)
    if not hook_ok:
        # Log hook violation but don't block stop (fail-open)
        # Operator will see in blackboard diagnostics
        try:
            from .config import blackboard_enabled
            if blackboard_enabled():
                from . import blackboard as bb
                bb.post_alert(root, "stop", "warn", f"Hook sequence issue: {hook_msg}")
        except Exception:
            pass

    # Record session end to blackboard (fire-and-forget)
    _record_session_to_blackboard(root)

    # 0. Loop breaker: stop_hook_active means Claude re-invoked Stop after a
    #    previous deny — honor the deny budget instead of wedging the session.
    if json_in.get("stop_hook_active"):
        return {"decision": "allow"}
    from .config import hook_gate_mode
    if hook_gate_mode("stop_guard") == "soft":
        return {"decision": "allow"}
    if _stop_denies_so_far(root) >= _MAX_STOP_DENIES_PER_SESSION:
        return {"decision": "allow"}

    # 1. Check for incomplete stories (focus-aware: if the session scope
    #    names a specific story, only that story blocks stop). A blackboard
    #    status of 'complete' means the session's work is done — no story check.
    #    A stale sprint-status older than the session start never blocks
    #    (brownfield leftover), unless the scope names that story.
    from .utils import _active_scope, _active_progress
    focus = _active_scope(root)
    progress = _active_progress(root)
    if progress and progress.lower() in ("complete", "done", "completed"):
        focus = ""  # work finished — don't block on in-progress stories
    should_block, reason = _check_story_status(root, focus=focus)
    if should_block and not _story_status_is_stale(root, focus):
        reason = _board_dirty_notice(root, reason)
        _record_stop_deny(root, reason)
        return {"decision": "deny", "reason": reason}

    # 2. Check for unapproved code changes — SESSION-TOUCHED files only.
    # ponytail: audit log is the touched set; whole-tree scan false-blocks
    # brownfield projects (pre-existing code ≠ this session did it).
    # find_approved caches verify results by record mtime, so stop stays fast.
    
    # Also check methodology chain completion (warn-only, doesn't block)
    chain_ok, chain_msg = _check_methodology_chain_completion(root)
    if not chain_ok:
        # Add to the dirty notice but don't block stop
        reason = _board_dirty_notice(root, chain_msg)
    
    for rel in _session_touched_code(root):
        if is_free(rel):
            continue
        approved, _ = find_approved(rel, root=root)
        if not approved:
            reason = (f"Unapproved code changes detected: {rel}. "
                      f"Complete experiment record before stopping.")
            reason = _board_dirty_notice(root, reason)
            _record_stop_deny(root, reason)
            return {"decision": "deny", "reason": reason}

    return {"decision": "allow"}
