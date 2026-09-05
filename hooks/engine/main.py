#!/usr/bin/env python3
"""BMAD hooks engine — main entry point.

This module provides the entry point for OpenHands hooks.
It delegates to the appropriate handler based on the hook type.
"""

import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.guard import guard, quality, deploy
from modules.audit import audit
from modules.stop import stop


def main():
    """Main entry point for hook execution."""
    # Read JSON input from stdin
    try:
        json_in = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        # If no valid JSON (including closed/empty stdin), allow by default
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": os.environ.get("HOOK_TYPE", "PreToolUse"),
                "permissionDecision": "allow",
            }
        }))
        return

    # Determine hook type from environment or arguments.
    # hook-entry.sh passes the mode via HOOK_TYPE env (invocation:
    #   python3 main.py --runtime=openhands  → sys.argv[1] is a FLAG, not a mode).
    # Direct calls may also pass the mode positionally:  main.py guard --runtime=openhands
    hook_type = os.environ.get("HOOK_TYPE", "")
    for arg in sys.argv[1:]:
        if arg.startswith("--runtime="):
            os.environ["METODOLOJI_RUNTIME"] = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            hook_type = arg

    # Execute appropriate handler
    if hook_type == "guard":
        result = guard(json_in)
    elif hook_type == "quality":
        result = quality(json_in)
    elif hook_type == "deploy":
        result = deploy(json_in)
    elif hook_type == "audit":
        result = audit(json_in)
    elif hook_type == "stop":
        result = stop(json_in)
    else:
        # Unknown hook type - allow
        result = {"decision": "allow"}

    # Intent bridge: surface the session intent + scope so consumers of the
    # hook result can see them. Reads via the shared helpers (env first, then
    # the active .memlog.md), so it works even when bootstrap's env export
    # can't cross process boundaries.
    if isinstance(result, dict):
        try:
            from modules.utils import _active_intent, _active_scope, repo_root
            root = repo_root(json_in)
            intent = _active_intent(root)
            if intent:
                result["intent"] = intent
            scope = _active_scope(root)
            if scope:
                result["scope"] = scope
        except Exception:
            pass

    # Output result — Claude Code v2 schema: hookSpecificOutput wrapper.
    # Schema differs per event type:
    #   PreToolUse (guard/quality/deploy) → permissionDecision
    #   PostToolUse (audit)               → additionalContext
    #   Stop (stop)                       → additionalContext
    event_name = hook_type or "PreToolUse"
    if hook_type in ("guard", "quality", "deploy"):
        # PreToolUse: permissionDecision controls allow/deny/ask
        hso = {
            "hookEventName": "PreToolUse",
            "permissionDecision": result.get("decision", "allow"),
        }
        reason = result.get("reason")
        if reason:
            hso["permissionDecisionReason"] = reason
        warnings = result.get("methodology_warnings")
        if warnings:
            hso["additionalContext"] = "\n".join(warnings)
    elif hook_type == "audit":
        # PostToolUse: additionalContext feeds info back to the model
        hso = {"hookEventName": "PostToolUse"}
        warnings = result.get("methodology_warnings")
        if warnings:
            hso["additionalContext"] = "\n".join(warnings)
    elif hook_type == "stop":
        # Stop: additionalContext gives feedback so the model can act on it
        hso = {"hookEventName": "Stop"}
        reason = result.get("reason")
        if reason:
            hso["additionalContext"] = reason
        pending = result.get("pending_docs")
        if pending:
            existing = hso.get("additionalContext", "")
            hso["additionalContext"] = (existing + "\n" + pending).strip() if existing else pending
    else:
        # Unknown hook type — flat allow
        hso = {"hookEventName": event_name, "permissionDecision": "allow"}

    print(json.dumps({"hookSpecificOutput": hso}, ensure_ascii=False))


if __name__ == "__main__":
    main()
