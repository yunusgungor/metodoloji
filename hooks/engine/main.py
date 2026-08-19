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

from modules.guard import guard
from modules.audit import audit
from modules.stop import stop


def main():
    """Main entry point for hook execution."""
    # Read JSON input from stdin
    try:
        json_in = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If no valid JSON, allow by default
        print(json.dumps({"decision": "allow"}))
        return

    # Determine hook type from environment or arguments
    hook_type = os.environ.get("HOOK_TYPE", "")

    # Check command line arguments
    if len(sys.argv) > 1:
        hook_type = sys.argv[1]
        # Check for --runtime argument
        for arg in sys.argv[2:]:
            if arg.startswith("--runtime="):
                os.environ["METODOLOJI_RUNTIME"] = arg.split("=", 1)[1]

    # Execute appropriate handler
    if hook_type == "guard":
        result = guard(json_in)
    elif hook_type == "audit":
        result = audit(json_in)
    elif hook_type == "stop":
        result = stop(json_in)
    elif hook_type == "quality":
        # Quality gate - soft mode by default
        result = {"decision": "allow"}
    elif hook_type == "deploy":
        # Deploy guard - soft mode by default
        result = {"decision": "allow"}
    else:
        # Unknown hook type - allow
        result = {"decision": "allow"}

    # Output result
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
