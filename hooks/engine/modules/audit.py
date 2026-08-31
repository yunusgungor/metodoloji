"""Audit logic for PostToolUse hook."""

import json
import os
import pathlib
import re
import time

from .config import log_file


def _detect_notable_events(tool_name: str, tool_input: dict, tool_output: dict) -> list[dict]:
    """Detect notable events that should trigger code doc generation.

    Returns list of events with type and context for doc creation.
    """
    events = []
    output_str = str(tool_output) if tool_output else ""

    # 1. Experiment approved → learning doc
    if tool_name == "terminal":
        cmd = str(tool_input.get("command", ""))
        if "run_experiment.py" in cmd and "--verify" not in cmd:
            if "APPROVED" in output_str or "VERIFIED" in output_str:
                # Extract experiment ID from command
                exp_match = re.search(r"E-\d+", cmd)
                record_match = re.search(r"--record\s+(\S+)", cmd)
                if exp_match and record_match:
                    events.append({
                        "type": "learning",
                        "trigger": "experiment_approved",
                        "experiment_id": exp_match.group(0),
                        "record_path": record_match.group(1),
                    })

    # 2. Architecture/design file changed → decision doc
    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        if any(p in path.lower() for p in ["architecture", "mimari", "design", "spine"]):
            content = str(tool_input.get("content", ""))
            if content and len(content) > 100:
                events.append({
                    "type": "decision",
                    "trigger": "architecture_change",
                    "path": path,
                    "content_preview": content[:200],
                })

    # 3. Error then success → troubleshooting doc
    if tool_name == "terminal":
        cmd = str(tool_input.get("command", ""))
        if "error" in output_str.lower() or "traceback" in output_str.lower():
            events.append({
                "type": "troubleshooting",
                "trigger": "error_detected",
                "command": cmd,
                "error_preview": output_str[:300],
            })

    # 4. Incomplete work / future plans → pending doc
    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        content = str(tool_input.get("content", ""))
        # Detect TODO/FIXME/HACK comments
        todo_matches = re.findall(r"(?:TODO|FIXME|HACK|XXX|OPTIMIZE)[:\s]*(.+)", content, re.IGNORECASE)
        for todo in todo_matches[:3]:  # Max 3 per file
            events.append({
                "type": "pending",
                "trigger": "todo_detected",
                "path": path,
                "description": todo.strip()[:200],
            })

    # 5. LLM output mentions future plans → pending doc
    if tool_name == "terminal":
        output_lower = output_str.lower()
        # Detect phrases indicating planned but unfinished work
        plan_patterns = [
            r"(?:next|following|upcoming)\s+(?:step|phase|iteration)",
            r"(?:planned|intended|considered)\s+(?:work|task|change)",
            r"(?:not yet (?:done|complete)|pending)",
            r"(?:needed|required|should be added|should be modified)",
        ]
        for pattern in plan_patterns:
            match = re.search(pattern, output_lower)
            if match:
                events.append({
                    "type": "pending",
                    "trigger": "future_plan_detected",
                    "description": match.group(0)[:200],
                    "context": output_str[max(0, match.start()-50):match.end()+50],
                })
                break  # Only one pending event per output

    return events


def _try_generate_code_doc(event: dict):
    """Try to generate a code doc from a detected event. Non-blocking."""
    try:
        from .code_docs import (create_learning, create_decision,
                                create_troubleshooting, create_pending)

        if event["type"] == "learning" and "experiment_id" in event:
            create_learning(
                experiment_id=event["experiment_id"],
                record_path=event["record_path"],
            )

        elif event["type"] == "decision" and "path" in event:
            create_decision(
                title=f"Architecture change: {os.path.basename(event['path'])}",
                decision=event.get("content_preview", "Architecture file modified"),
                rationale="Auto-detected by audit hook",
            )

        elif event["type"] == "troubleshooting" and "command" in event:
            create_troubleshooting(
                title=f"Error detected: {event['command'][:50]}",
                error=event.get("error_preview", "Error detected"),
                cause="Auto-detected by audit hook",
                solution="Fix not yet added — manual update needed",
            )

        elif event["type"] == "pending":
            desc = event.get("description", "Unfinished work")
            path = event.get("path", "")
            context = event.get("context", "")
            trigger = event.get("trigger", "")

            if trigger == "todo_detected":
                title = f"TODO: {desc[:50]}"
                context_info = f"File: {path}" if path else ""
            else:
                title = f"Pending work: {desc[:50]}"
                context_info = context[:200] if context else ""

            create_pending(
                title=title,
                description=desc,
                context=context_info,
                next_steps="Should be updated manually",
                priority="normal",
                tags=["pending", "auto-detected"],
            )
    except Exception as exc:
        import sys
        print(f"code-docs generation warning: {exc}", file=sys.stderr)  # Non-blocking, but visible for debugging


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
    """Check if bridge outputs exist for recently modified files.

    When a story file or methodology record is modified, verify that
    the corresponding chain records exist. Non-blocking warnings.
    """
    warnings = []
    from .utils import repo_root
    root = repo_root({})
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
                                    f"Bridge inconsistency: {s_file.name} status is 'done' but no QR record exists. "
                                    f"The bmad-code-review or bmad-dev-story bridge has not run yet."
                                )

        # Check: QR-NNN.md modified → should have DoD items
        if re.search(r"/QR-\d+\.md$", path, re.IGNORECASE):
            content = str(tool_input.get("content", ""))
            if content and "DoD Item" not in content and "DoD-" not in content:
                warnings.append(
                    f"Bridge inconsistency: {path} does not contain DoD items. "
                    f"The QR record may be missing or incorrectly created."
                )

    return warnings


def audit(json_in: dict) -> dict:
    """PostToolUse audit: write JSON audit trail + methodology validation."""
    tool_name = json_in.get("tool_name", "")
    tool_input = json_in.get("tool_input", {})
    tool_output = json_in.get("tool_output", {})

    # Project root anchored like guard/quality/deploy (cwd may differ under
    # OpenHands; repo_root resolves via OPENHANDS_PROJECT_DIR).
    from .utils import repo_root, _active_intent, _active_progress
    root = repo_root(json_in)

    # Build audit record
    record = {
        "timestamp": time.time(),
        "tool": tool_name,
        "input": tool_input,
        "output_summary": str(tool_output)[:500] if tool_output else None,
        # Intent bridge: stamp each record with the active session intent so
        # the log answers "who did what, under which intent".
        "intent": _active_intent(root),
        # Progress signal: the memlog status (set via memlog.py set --key status).
        "progress": _active_progress(root),
    }

    # Methodology validation (non-blocking, just warnings)
    warnings = _validate_methodology_compliance(tool_name, tool_input)

    # Bridge consumption check (non-blocking)
    kopru_warnings = _check_kopru_consumption(tool_name, tool_input)
    warnings.extend(kopru_warnings)

    # Detect notable events for code doc generation (non-blocking)
    notable_events = _detect_notable_events(tool_name, tool_input, tool_output)
    for event in notable_events:
        _try_generate_code_doc(event)

    if warnings:
        record["methodology_warnings"] = warnings

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
