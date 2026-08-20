"""Audit logic for PostToolUse hook."""

import json
import os
import pathlib
import re
import time

from .config import RUNTIME, log_file


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


def audit(json_in: dict) -> dict:
    """PostToolUse audit: write JSON audit trail + methodology validation."""
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

    # Methodology validation (non-blocking, just warnings)
    warnings = _validate_methodology_compliance(tool_name, tool_input)
    if warnings:
        record["methodology_warnings"] = warnings

    # Get log file path (use absolute path)
    log_path = pathlib.Path(log_file()).absolute()

    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append record
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"decision": "allow"}
