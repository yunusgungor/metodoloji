"""Stop logic for Stop hook."""

import json
import pathlib
import re

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


def _session_touched_code(root: str) -> list[str]:
    """Code files this session actually wrote (from the audit trail).

    No audit log (fresh session / logging disabled) → [] → allow.
    Pre-existing brownfield files are never listed: only PostToolUse
    records this session wrote count.
    """
    from .bash_targets import extract_bash_targets
    from .config import log_file

    log_path = pathlib.Path(root).absolute() / log_file()
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    touched: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        tool = str(rec.get("tool", ""))
        tool_input = rec.get("input", {})
        if not isinstance(tool_input, dict):
            continue
        if tool in ("file_editor", "notebook_editor"):
            path = tool_input.get("path", "") or tool_input.get("file_path", "")
            if path:
                rel = rel_to_root(root, str(path))
                if rel and is_code_target(rel):
                    touched.add(rel)
        elif tool == "terminal":
            command = tool_input.get("command", "") or tool_input.get("cmd", "")
            if command:
                for target in extract_bash_targets(str(command)):
                    rel = rel_to_root(root, str(target))
                    if rel and is_code_target(rel):
                        touched.add(rel)
    return sorted(touched)


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes or incomplete stories exist."""
    from .utils import repo_root
    root = repo_root(json_in)

    # 1. Check for incomplete stories (intent-aware: if the session intent
    #    names a specific story, only that story blocks stop). A memlog whose
    #    status is 'complete' means the session's work is done — no story check.
    from .utils import _active_intent, _active_progress
    intent = _active_intent(root)
    progress = _active_progress(root)
    if progress and progress.lower() in ("complete", "done", "completed"):
        intent = ""  # work finished — don't block on in-progress stories
    should_block, reason = _check_story_status(root, intent=intent)
    if should_block:
        return {"decision": "deny", "reason": reason}

    # 2. Check for unapproved code changes — SESSION-TOUCHED files only.
    # ponytail: audit log is the touched set; whole-tree scan false-blocks
    # brownfield projects (pre-existing code ≠ this session did it).
    for rel in _session_touched_code(root):
        if is_free(rel):
            continue
        approved, _ = find_approved(rel, root=root)
        if not approved:
            return {
                "decision": "deny",
                "reason": f"Unapproved code changes detected: {rel}. "
                          f"Complete experiment record before stopping."
            }

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
