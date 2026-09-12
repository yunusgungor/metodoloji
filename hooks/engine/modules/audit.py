"""Audit logic for PostToolUse hook."""

import json
import pathlib
import re
import sys
import time

from .config import log_file
from .utils import dod_issues, has_dod_content, scan_dod_items


# Preview caps for the audit trail: bodies never land whole in the log.
_INPUT_PREVIEW_LEN = 300
_OUTPUT_PREVIEW_LEN = 500
# Keys whose values are file/command bodies, not metadata — preview only.
_BODY_KEYS = frozenset({"content", "code", "source", "text", "body", "output"})


def _redacted_input(tool_input: dict) -> dict:
    """Copy tool input with body values reduced to preview + length.

    Paths, commands and flags stay whole (stop/guard need them); only
    potentially large or sensitive bodies are cut.
    """
    redacted = {}
    for key, value in tool_input.items():
        if key in _BODY_KEYS and isinstance(value, str) and len(value) > _INPUT_PREVIEW_LEN:
            redacted[key] = value[:_INPUT_PREVIEW_LEN] + f"... [truncated {len(value)} chars]"
        elif key in _BODY_KEYS and isinstance(value, list):
            joined = "\n".join(str(v) for v in value)
            if len(joined) > _INPUT_PREVIEW_LEN:
                redacted[key] = joined[:_INPUT_PREVIEW_LEN] + f"... [truncated {len(joined)} chars]"
            else:
                redacted[key] = value
        else:
            redacted[key] = value
    return redacted


def _check_kopru_consumption(tool_name: str, tool_input: dict) -> list[str]:
    """Check if bridge outputs exist for recently modified files.

    Scoped to the modified file only (never a directory scan): a QR edit
    without structurally sound DoD items warns; the done-story→QR chain check
    lives in check-plugin.sh (static audit), not on the per-write hot path.
    QR DoD content is validated with the SAME rules and parser the guard
    applies to a story's Definition of Done (.utils.dod_issues) — identifier
    on every item plus a recorded verification — so the two layers can never
    disagree about what "valid DoD" means.
    """
    warnings = []

    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        if not path:
            return warnings

        # Check: QR-NNN.md modified → should carry DoD verification items
        if re.search(r"/QR-\d+\.md$", path, re.IGNORECASE):
            content = str(tool_input.get("content", ""))
            if not content:
                return warnings
            if not has_dod_content(content):
                warnings.append(
                    f"Bridge inconsistency: {path} does not contain DoD items. "
                    f"The QR record may be missing or incorrectly created."
                )
                return warnings
            # DoD content is referenced but no bullet/table item parsed → the
            # QR only repeats the words, it does not record the verification.
            if not scan_dod_items(content, qr=True):
                warnings.append(
                    f"Bridge inconsistency: {path} mentions DoD but has no DoD items "
                    f"(expected '- DoD-NNN …' bullets or a '| DoD-NNN | … |' table)."
                )
            # Structural defects — the guard's DoD rules applied to QR content.
            for issue in dod_issues(content, qr=True):
                warnings.append(f"Bridge inconsistency: {path} — {issue}")

    return warnings


def _ensure_bridge_canvases(root: str) -> None:
    """Ensure bridge tracking canvases exist and watch the right paths.
    
    Creates canvases for:
    1. Story→QR→PR→IR chain (tool workflow)
    2. E→IR→SP→S→QR→PR chain (methodology workflow)
    """
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return
        from . import blackboard as bb
        
        board = bb.read_board(root)
        
        # Ensure tool workflow bridge canvas exists
        if "bridge" not in board.get("canvases", {}):
            bb.canvas_create(root, "bridge", grid="16x8", focus=False)
            # Watch tool workflow paths (Story/QR/PR/IR in docs/)
            bb.canvas_watch(root, "bridge", "docs/development/stories")
            bb.canvas_watch(root, "bridge", "docs/quality")
            bb.canvas_watch(root, "bridge", "docs/development")
        
        # Ensure methodology chain canvas exists (E→IR→SP→S→QR→PR)
        if "methodology-chain" not in board.get("canvases", {}):
            bb.canvas_create(root, "methodology-chain", grid="6x3", focus=False)
            # Watch methodology workflow paths
            bb.canvas_watch(root, "methodology-chain", "docs/experiments")
            bb.canvas_watch(root, "methodology-chain", "docs/development")
            bb.canvas_watch(root, "methodology-chain", "docs/quality")
    except (ImportError, AttributeError, OSError):
        # Specific exceptions from blackboard (MEDIUM #7 / ISSUE #66)
        pass  # fail-open
    except Exception:
        # Unknown exceptions: log to stderr but fail-open
        try:
            import traceback
            sys.stderr.write(f"metodoloji: bridge canvas setup error: {traceback.format_exc()[:200]}\n")
        except Exception:
            pass


def _update_bridge_status(root: str, tool_name: str, tool_input: dict) -> None:
    """Update bridge status in blackboard when story/QR/PR files are modified.
    
    Also tracks full methodology chain E→IR→SP→S→QR→PR artifacts.
    """
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return
        from . import blackboard as bb

        # Ensure bridge canvas exists
        _ensure_bridge_canvases(root)

        if tool_name == "file_editor":
            path = tool_input.get("path", "")
            if not path:
                return

            # Experiment (E) record created/updated
            if re.search(r"/E-\d+\.md$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_experiment", path.split("/")[-1],
                            type_="state")
                bb.post_alert(root, "session", "bridge",
                             f"Experiment updated: {path.split('/')[-1]}")

            # Implementation Readiness (IR) record created/updated
            # (matches both IR-NNN.md records and the workflow's
            # implementation-readiness-report-<date>.md output)
            elif re.search(r"/(?:IR-\d+|implementation-readiness-report[^/\\]*)\.md$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_ir", path.split("/")[-1],
                            type_="state")
                # Link E→IR
                exp_match = re.search(r"E-\d+", path)
                if exp_match:
                    bb.link(root, f"exp:{exp_match.group()}", f"ir:{path.split('/')[-1]}",
                           relation="ready_for_implementation")
                bb.post_alert(root, "session", "bridge",
                             f"IR record updated: {path.split('/')[-1]}")

            # Sprint Planning (SP) record created/updated
            # (matches both SP-NNN.md records and the workflow's
            # sprint-status.yaml status file)
            elif re.search(r"/(?:SP-\d+\.md|sprint-status\.yaml)$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_sp", path.split("/")[-1],
                            type_="state")
                # Link IR→SP
                ir_match = re.search(r"IR-\d+", path)
                if ir_match:
                    bb.link(root, f"ir:{ir_match.group()}", f"sp:{path.split('/')[-1]}",
                           relation="sprint_planned")
                bb.post_alert(root, "session", "bridge",
                             f"SP record updated: {path.split('/')[-1]}")

            # Story (S) file created/updated
            elif re.search(r"/S-\d+\.md$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_story", path.split("/")[-1],
                            type_="state")
                bb.set_hot(root, path.split("/")[-1].replace(".md", ""))
                # Link SP→S
                sp_match = re.search(r"SP-\d+", path)
                if sp_match:
                    bb.link(root, f"sp:{sp_match.group()}", f"story:{path.split('/')[-1]}",
                           relation="implemented_in_story")
                bb.post_alert(root, "session", "bridge",
                             f"Story updated: {path.split('/')[-1]}")

            # Quality Record (QR) record created/updated
            elif re.search(r"/QR-\d+\.md$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_qr", path.split("/")[-1],
                            type_="state")
                # Link story→QR
                story_match = re.search(r"S-\d+", path)
                if story_match:
                    bb.link(root, f"story:{story_match.group()}", f"qr:{path.split('/')[-1]}",
                           relation="quality_verified")
                bb.post_alert(root, "session", "bridge",
                             f"QR record updated: {path.split('/')[-1]}")

            # Production Readiness (PR) record created/updated
            elif re.search(r"/PR-\d+\.md$", path, re.IGNORECASE):
                bb.write_key(root, "methodology.last_pr", path.split("/")[-1],
                            type_="state")
                # Link QR→PR
                qr_match = re.search(r"QR-\d+", path)
                if qr_match:
                    bb.link(root, f"qr:{qr_match.group()}", f"pr:{path.split('/')[-1]}",
                           relation="production_ready")
                bb.post_alert(root, "session", "bridge",
                             f"PR record updated: {path.split('/')[-1]}")
    except Exception:
        pass  # fail-open


def session_start(json_in: dict) -> dict:
    """SessionStart: stamp a session_start marker into the audit trail.

    Stop counts touched files and deny budget only after the newest marker,
    so previous sessions' unapproved touches and stale sprint-status
    leftovers never wedge a new session. Fail-open (never blocks startup).
    Returns additionalContext so the SessionStart event can inject it.
    """
    from .utils import repo_root
    root = repo_root(json_in)
    try:
        from .stop import record_session_start
        record_session_start(root)
    except Exception:
        pass
    
    # Initialize session progress keys if not set
    try:
        from .config import blackboard_enabled
        if blackboard_enabled():
            from . import blackboard as bb
            board = bb.read_board(root)
            # Initialize scope and status if empty
            if not board.get("keys", {}).get("scope"):
                bb.write_key(root, "scope", "docs", type_="session")
            if not board.get("keys", {}).get("status"):
                bb.write_key(root, "status", "active", type_="session")
    except Exception:
        pass
    
    ctx = "METODOLOJI session started. Record chain: E → IR → SP → S → QR → PR."
    try:
        from .config import blackboard_enabled
        if blackboard_enabled():
            from . import blackboard as bb
            bb.record_watcher(root, "session_start")
            # Proactive alert delivery: take this session's routed alerts now.
            delivered = bb.consume_alerts(root, "session")
            board_ctx = bb.compact_context(root)
            parts = []
            if board_ctx.get("hot"):
                hm = board_ctx.get("hot_meta") or {}
                preview = hm.get("preview")
                parts.append(f"hot: {board_ctx['hot']}"
                             + (f" = {preview}" if preview else ""))
            if board_ctx.get("hot_canvas"):
                hc = board_ctx["hot_canvas"]
                parts.append(f"canvas '{hc['name']}' live ({hc['cells']} cells"
                             + (f", {hc['auto']} auto" if hc.get("auto") else "")
                             + (f", latest: {hc['latest']}" if hc.get("latest") else "")
                             + ")")
            if board_ctx.get("tags"):
                parts.append("tags: " + ", ".join(board_ctx["tags"]))
            if board_ctx.get("contributions"):
                last = board_ctx["contributions"][-1]
                parts.append(f"last: {last['who']} — {last['what']}")
            if board_ctx.get("neighbors"):
                parts.append("neighbors: " + ", ".join(board_ctx["neighbors"]))
            if delivered:
                msgs = "; ".join(f"[{a['kind']}] {a['text']}" for a in delivered[-3:])
                parts.append(f"alerts: {msgs}" +
                             (f" (+{len(delivered) - 3} more)" if len(delivered) > 3 else ""))
            try:
                waiting = bb.pending_handoff_channels(root)
            except Exception:
                waiting = {}
            if waiting:
                waiting.pop("bmad-help", None)  # help skill has its own routing
                if waiting:
                    w = ", ".join(f"{s} ({n})" for s, n in sorted(waiting.items()))
                    total = sum(waiting.values())
                    parts.append(
                        f"PROACTIVE — hand-off waiting: {w}: {total} unclaimed "
                        "signal(s) from completed upstream runs; a run finished "
                        "its work but nobody picked up the baton (diagnose: "
                        "blackboard.py chain-health; claim: handoffs --skill "
                        "<this skill>, then consume its handoff channel)")
            if parts:
                ctx += " Blackboard: " + "; ".join(parts) + "."
    except Exception:
        pass
    return {"decision": "allow", "additionalContext": ctx}


def audit(json_in: dict) -> dict:
    """PostToolUse audit: write JSON audit trail + methodology validation."""
    from .utils import normalize_hook_input
    norm = normalize_hook_input(json_in)
    tool_name = norm["tool_name"]
    tool_input = norm["tool_input"]
    tool_output = json_in.get("tool_output", {})

    # Project root anchored like guard/quality/deploy (cwd may differ under
    # OpenHands; repo_root resolves via OPENHANDS_PROJECT_DIR).
    from .utils import repo_root
    root = repo_root(json_in)

    # Build audit record. File content is NEVER logged whole: large or
    # sensitive bodies stay out of the trail (preview + length only).
    # Session progress is stamped so the log answers "who did what, at what
    # stage" (stop reads it back to skip story checks on completion).
    # Fail-open — the helper returns '' when the board is empty.
    from .utils import _active_progress
    record = {
        "timestamp": time.time(),
        "tool": tool_name,
        "input": _redacted_input(tool_input),
        "output_summary": str(tool_output)[:500] if tool_output else None,
        "progress": _active_progress(root),
    }

    # Bridge consumption check (non-blocking, just warnings). Story-file AC /
    # experiment_refs validation lives in the guard (deny-or-warn by gate
    # mode) — auditing it again here would double-report the same defect.
    warnings = _check_kopru_consumption(tool_name, tool_input)

    if warnings:
        record["methodology_warnings"] = warnings

    log_path = pathlib.Path(root).absolute() / log_file()

    try:
        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append record
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        import sys
        print(f"audit log write failed: {exc}", file=sys.stderr)

    try:
        from .config import blackboard_enabled
        if blackboard_enabled():
            from . import blackboard as bb
            target = tool_input.get("path") or tool_input.get("file_path") or tool_name
            bb.stamp_tool_event(root, tool_name, str(target), hook_event="PostToolUse")  # NEW: Track hook sequence (HIGH #7)
            # Update bridge status (story→QR→PR chain)
            _update_bridge_status(root, tool_name, tool_input)
    except Exception:
        pass

    result = {"decision": "allow"}
    if warnings:
        result["methodology_warnings"] = warnings
    return result
