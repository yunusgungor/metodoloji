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


def _check_kopru_consumption(tool_name: str, tool_input: dict) -> list[str]:
    """Check if KÖPRÜ outputs exist for recently modified files.

    When a story file or methodology record is modified, verify that
    the corresponding chain records exist. Non-blocking warnings.
    """
    warnings = []
    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    root = os.path.abspath(root)

    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        if not path:
            return warnings

        # Check: S-NNN.md modified → methodology record should exist
        if re.search(r"/stories/S-\d+\.md$", path, re.IGNORECASE):
            stories_dir = pathlib.Path(root) / "docs" / "development" / "stories"
            if stories_dir.is_dir():
                for s_file in stories_dir.glob("S-*.md"):
                    try:
                        content = s_file.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    # Check if done but no QR
                    if re.search(r"[-*]?\s*\*?\*?Status\s*:\s*\*?\*?\s*(done)", content, re.IGNORECASE):
                        qr_dir = pathlib.Path(root) / "docs" / "quality"
                        if qr_dir.is_dir():
                            qr_files = list(qr_dir.glob("QR-*.md"))
                            if not qr_files:
                                warnings.append(
                                    f"KÖPRÜ uyumsuzluğu: {s_file.name} durumu 'done' ama QR kaydı yok. "
                                    f"bmad-code-review veya bmad-dev-story KÖPRÜ'sü henüz çalışmadı."
                                )

        # Check: QR-NNN.md modified → should have DoD items
        if re.search(r"/QR-\d+\.md$", path, re.IGNORECASE):
            content = str(tool_input.get("content", ""))
            if content and "DoD Item" not in content and "DoD-" not in content:
                warnings.append(
                    f"KÖPRÜ uyumsuzluğu: {path} DoD item'ları içermiyor. "
                    f"QR kaydı eksik/yanlış oluşturulmuş olabilir."
                )

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

    # KÖPRÜ consumption check (non-blocking)
    kopru_warnings = _check_kopru_consumption(tool_name, tool_input)
    warnings.extend(kopru_warnings)

    if warnings:
        record["methodology_warnings"] = warnings

    # Get log file path anchored to the project root, not the process cwd
    # (cwd may differ under OpenHands; guard/quality/deploy resolve scopes
    # via OPENHANDS_PROJECT_DIR, so audit must too).
    root = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    log_path = pathlib.Path(root).absolute() / log_file()

    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append record
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    result = {"decision": "allow"}
    if warnings:
        result["methodology_warnings"] = warnings
    return result
