"""Stop logic for Stop hook."""

import json
import os
import pathlib
import re

from .config import _DONE_RE
from .guard import find_approved
from .utils import is_free, norm_path

# ponytail: directory-level prune — skip known-non-code dirs entirely
_CODE_SUFFIXES = frozenset({".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"})
_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".metodoloji", "scratch",
    "tmp", "temp", "docs", "templates", "commands", ".plugin", "bmad",
})


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


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes or incomplete stories exist."""
    from .utils import repo_root
    root = repo_root(json_in)

    # 1. Check for incomplete stories (intent-aware: if the session intent
    #    names a specific story, only that story blocks stop).
    from .utils import _active_intent
    intent = _active_intent(root)
    should_block, reason = _check_story_status(root, intent=intent)
    if should_block:
        return {"decision": "deny", "reason": reason}

    # 2. Check for unapproved code changes (directory-level prune for speed)
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune known non-code directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            ext = pathlib.PurePosixPath(fname).suffix.lower()
            if ext not in _CODE_SUFFIXES:
                continue
            full = pathlib.Path(dirpath) / fname
            rel = norm_path(str(full.relative_to(root)))
            if is_free(rel):
                continue
            approved, _ = find_approved(rel)
            if not approved:
                return {
                    "decision": "deny",
                    "reason": f"Unapproved code changes detected: {rel}. "
                              f"Complete experiment record before stopping."
                }

    return {"decision": "allow"}
