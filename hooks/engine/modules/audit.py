"""Audit logic for PostToolUse hook."""

import json
import pathlib
import re
import time

from .config import log_file
from .utils import dod_issues, has_dod_content, scan_dod_items


def _validate_methodology_compliance(tool_name: str, tool_input: dict) -> list[str]:
    """Check if the tool usage follows methodology rules.

    Returns list of warnings (non-blocking).
    """
    warnings = []

    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        # Check if writing to story file without proper metadata
        if path and re.search(r"\d+-\d+-[a-z][a-z0-9-]*\.md", path, re.IGNORECASE):
            content = str(tool_input.get("content", ""))
            if content:
                # Check for AC metadata
                if "[AC-" not in content and "Acceptance Criteria" in content:
                    warnings.append(f"Story file {path}: AC metadata missing (no [AC-XXX] identifiers)")
                # Check for experiment_refs
                if "experiment_refs" not in content and "---" in content:
                    warnings.append(f"Story file {path}: experiment_refs missing in frontmatter")

    return warnings


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
    record = {
        "timestamp": time.time(),
        "tool": tool_name,
        "input": _redacted_input(tool_input),
        "output_summary": str(tool_output)[:500] if tool_output else None,
    }

    # Methodology validation (non-blocking, just warnings)
    warnings = _validate_methodology_compliance(tool_name, tool_input)

    # Bridge consumption check (non-blocking)
    kopru_warnings = _check_kopru_consumption(tool_name, tool_input)
    warnings.extend(kopru_warnings)

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
            bb._mutate(root, lambda board: _stamp_tool_event(board, tool_name, target))
            # Real-time canvas push: watched canvases record the touch.
            bb.watch_touch(root, tool_name, str(target))
    except Exception:
        pass

    result = {"decision": "allow"}
    if warnings:
        result["methodology_warnings"] = warnings
    return result


def _stamp_tool_event(board: dict, tool_name: str, target: str) -> tuple[dict, None]:
    """Fold a bounded tool event into the board during the audit's mutation.

    Direct snapshot fold (no event-log append): the audit log itself is the
    durable record; the board copy is a bounded convenience for context reads.
    """
    from . import blackboard as bbmod
    key = f"last_tool.{tool_name}"
    board["keys"][key] = {"value": str(target)[:bbmod.MAX_TEXT_LEN],
                          "type": "tool", "updated": time.time()}
    while len(board["keys"]) > bbmod.MAX_KEYS:
        oldest = min(board["keys"], key=lambda k: board["keys"][k].get("updated", 0.0))
        board["keys"].pop(oldest)
    if board.get("hot") and board["hot"] not in board["keys"]:
        board["hot"] = None
    return board, None
