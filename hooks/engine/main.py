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
        print(json.dumps({"decision": "allow"}))
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

    # Output result
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
