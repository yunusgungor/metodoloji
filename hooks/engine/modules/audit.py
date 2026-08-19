"""Audit logic for PostToolUse hook."""

import json
import os
import pathlib
import time

from .config import RUNTIME, log_file


def audit(json_in: dict) -> dict:
    """PostToolUse audit: write JSON audit trail."""
    tool_name = json_in.get("tool_name", "")
    tool_input = json_in.get("tool_input", {})
    tool_output = json_in.get("tool_output", {})

    # Build audit record
    record = {
        "timestamp": time.time(),
        "tool": tool_name,
        "input": tool_input,
        "output_summary": str(tool_output)[:500] if tool_output else None,
    }

    # Get log file path
    log_path = pathlib.Path(log_file())

    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append record
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"decision": "allow"}
