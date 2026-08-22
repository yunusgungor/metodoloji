"""Stop logic for Stop hook."""

import json
import os
import pathlib
import re

from .config import GATE_DIR, RUNTIME
from .guard import find_approved
from .utils import is_free


def _check_story_status(root: str) -> tuple[bool, str]:
    """Check if any story is in-progress but incomplete.

    Returns (should_block, reason).
    """
    # Look for sprint-status.yaml
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
                if in_progress:
                    return True, (
                        f"Story in-progress but stop requested: {', '.join(in_progress)}. "
                        f"Complete the story before stopping."
                    )
            except OSError:
                pass
    return False, ""


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes or incomplete stories exist."""
    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()

    # 1. Check for incomplete stories
    should_block, reason = _check_story_status(root)
    if should_block:
        return {"decision": "deny", "reason": reason}

    # 2. Check for unapproved code changes
    for p in pathlib.Path(root).rglob("*"):
        if p.is_file() and p.suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"):
            rel = str(p.relative_to(root))
            # Skip free zones (scratch/, .metodoloji/, plugin root, tmp/, temp/...):
            # the manifesto declares these exempt from experiment approval. Also skip
            # git-ignored files: only tracked (or new) source in protected areas is
            # meant to block stop. guard.py already applies is_free()/is_code_target()
            # to writes; this keeps stop consistent with it.
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
