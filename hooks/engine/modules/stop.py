"""Stop logic for Stop hook."""

import json
import os
import pathlib

from .config import GATE_DIR
from .guard import find_approved


def stop(json_in: dict) -> dict:
    """Stop hook: block stop if unapproved code changes exist."""
    # Check for any unapproved code changes in the workspace
    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()

    # Look for modified code files
    for p in pathlib.Path(root).rglob("*"):
        if p.is_file() and p.suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"):
            rel = str(p.relative_to(root))
            approved, _ = find_approved(rel)
            if not approved:
                return {
                    "decision": "deny",
                    "reason": f"Unapproved code changes detected: {rel}. "
                              f"Complete experiment record before stopping."
                }

    return {"decision": "allow"}
