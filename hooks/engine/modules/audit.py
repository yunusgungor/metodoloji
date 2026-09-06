"""Audit logic for PostToolUse hook."""

import json
import os
import pathlib
import re
import time

from .config import log_file


# Detection window: regexes run on the preview, never the whole body.
_DETECT_WINDOW = 8192


def _detect_notable_events(tool_name: str, tool_input: dict, tool_output: dict) -> list[dict]:
    """Detect notable events that should trigger code doc generation.

    Returns list of events with type and context for doc creation.
    """
    events = []
    output_str = str(tool_output)[:_DETECT_WINDOW] if tool_output else ""

    # 0. Code structure → pattern doc (class hierarchies, design-indicative comments)
    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        content = str(tool_input.get("content", ""))[:_DETECT_WINDOW]
        if path.endswith(".py") and content:
            # Class with inheritance or decorator = design pattern signal
            class_match = re.search(
                r"class\s+(\w+)\s*\([^)]+\)", content)
            if class_match:
                events.append({
                    "type": "pattern",
                    "trigger": "class_hierarchy",
                    "path": path,
                    "class_name": class_match.group(1),
                    "content_preview": content[:200],
                })
            else:
                # Explicit pattern mentions in comments
                if re.search(r"#.*(?:pattern|strategy|factory|adapter|decorator|observer|singleton|proxy)", content, re.IGNORECASE):
                    events.append({
                        "type": "pattern",
                        "trigger": "pattern_keyword",
                        "path": path,
                        "content_preview": content[:200],
                    })

    # 0b. API endpoint → api doc (route decorators, API file naming)
    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        content = str(tool_input.get("content", ""))[:_DETECT_WINDOW]
        if content:
            route_match = re.search(
                r"@(?:app|router|blueprint|api_view)\s*\.\s*(get|post|put|delete|patch|route)\s*\(",
                content)
            is_api_file = bool(re.search(r"(?:api|route|endpoint|view)s?\.py$", path, re.IGNORECASE))

            if route_match or is_api_file:
                route_path = ""
                if route_match:
                    after = content[route_match.end():]
                    rp = re.search(r"['\"]([^'\"]+)['\"]", after)
                    if rp:
                        route_path = rp.group(1)
                events.append({
                    "type": "api",
                    "trigger": "endpoint_detected",
                    "path": path,
                    "route": route_path,
                    "content_preview": content[:200],
                })

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
        content = str(tool_input.get("content", ""))[:_DETECT_WINDOW]
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
                                create_troubleshooting, create_pending,
                                create_pattern, create_api)

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

        elif event["type"] == "pattern" and "path" in event:
            class_name = event.get("class_name", "")
            if class_name:
                title = f"Pattern: {class_name}"
            else:
                title = f"Pattern: {os.path.basename(event['path'])}"
            create_pattern(
                title=title,
                pattern=event.get("content_preview", "Code structure detected"),
                usage=f"Observed in {event['path']}",
                tags=["pattern", "auto-detected"],
            )

        elif event["type"] == "api" and "path" in event:
            route = event.get("route", "")
            title = f"API: {route}" if route else f"API: {os.path.basename(event['path'])}"
            create_api(
                title=title,
                signature=route or event.get("path", ""),
                usage=event.get("content_preview", "Endpoint detected"),
                tags=["api", "auto-detected"],
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


# Preview caps for the audit trail: bodies never land whole in the log.
_INPUT_PREVIEW_LEN = 300
_OUTPUT_PREVIEW_LEN = 500
# Keys whose values are file/command bodies, not metadata — preview only.
_BODY_KEYS = frozenset({"content", "code", "source", "text", "body", "output"})


def _redacted_input(tool_input: dict) -> dict:
    """Copy tool input with body values reduced to preview + length.

    Paths, commands and flags stay whole (stop/guard need them); only
    potentially large or sensitive bodies are cut.
    """
    redacted = {}
    for key, value in tool_input.items():
        if key in _BODY_KEYS and isinstance(value, str) and len(value) > _INPUT_PREVIEW_LEN:
            redacted[key] = value[:_INPUT_PREVIEW_LEN] + f"... [truncated {len(value)} chars]"
        elif key in _BODY_KEYS and isinstance(value, list):
            joined = "\n".join(str(v) for v in value)
            if len(joined) > _INPUT_PREVIEW_LEN:
                redacted[key] = joined[:_INPUT_PREVIEW_LEN] + f"... [truncated {len(joined)} chars]"
            else:
                redacted[key] = value
        else:
            redacted[key] = value
    return redacted


def _check_kopru_consumption(tool_name: str, tool_input: dict) -> list[str]:
    """Check if bridge outputs exist for recently modified files.

    Scoped to the modified file only (never a directory scan): a QR edit
    without DoD items warns; the done-story→QR chain check lives in
    check-plugin.sh (static audit), not on the per-write hot path.
    """
    warnings = []

    if tool_name == "file_editor":
        path = tool_input.get("path", "")
        if not path:
            return warnings

        # Check: QR-NNN.md modified → should have DoD items
        if re.search(r"/QR-\d+\.md$", path, re.IGNORECASE):
            content = str(tool_input.get("content", ""))
            if content and "DoD Item" not in content and "DoD-" not in content:
                warnings.append(
                    f"Bridge inconsistency: {path} does not contain DoD items. "
                    f"The QR record may be missing or incorrectly created."
                )

    return warnings


def session_start(json_in: dict) -> dict:
    """SessionStart: stamp a session_start marker into the audit trail.

    Stop counts touched files and deny budget only after the newest marker,
    so previous sessions' unapproved touches and stale sprint-status
    leftovers never wedge a new session. Fail-open (never blocks startup).
    Returns additionalContext so the SessionStart event can inject it.
    """
    from .utils import repo_root
    try:
        from .stop import record_session_start
        record_session_start(repo_root(json_in))
    except Exception:
        pass
    try:
        from .code_docs import load_pending_docs, load_recent_docs
        ctx = "METODOLOJI session started. Record chain: E → IR → SP → S → QR → PR."
        pending = load_pending_docs()
        recent = load_recent_docs(n=5)
        if pending or recent:
            ctx += "\n\n"
        if pending:
            ctx += pending
        if recent:
            if pending:
                ctx += "\n"
            ctx += recent
        return {"decision": "allow", "additionalContext": ctx}
    except Exception:
        return {"decision": "allow"}


def audit(json_in: dict) -> dict:
    """PostToolUse audit: write JSON audit trail + methodology validation."""
    from .utils import normalize_hook_input
    norm = normalize_hook_input(json_in)
    tool_name = norm["tool_name"]
    tool_input = norm["tool_input"]
    tool_output = json_in.get("tool_output", {})

    # Project root anchored like guard/quality/deploy (cwd may differ under
    # OpenHands; repo_root resolves via OPENHANDS_PROJECT_DIR).
    from .utils import repo_root, _active_intent, _active_progress
    root = repo_root(json_in)

    # Build audit record. File content is NEVER logged whole: large or
    # sensitive bodies stay out of the trail (preview + length only).
    record = {
        "timestamp": time.time(),
        "tool": tool_name,
        "input": _redacted_input(tool_input),
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

    # Auto-load relevant code-docs for current task context (non-blocking).
    # Terminal-only: file_editor bodies already trigger doc generation above;
    # scanning the whole code-docs tree per write is the audit hot path.
    if tool_name == "terminal":
        try:
            from .code_docs import load_context_for_task
            task_desc = str(tool_input.get("command", ""))
            if tool_output:
                task_desc += " " + str(tool_output)[:200]
            if task_desc.strip():
                doc_context = load_context_for_task(task_desc)
                if doc_context:
                    record["related_docs"] = doc_context
        except Exception:
            pass

    if warnings:
        record["methodology_warnings"] = warnings

    log_path = pathlib.Path(root).absolute() / log_file()

    try:
        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append record
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        import sys
        print(f"audit log write failed: {exc}", file=sys.stderr)

    result = {"decision": "allow"}
    if warnings:
        result["methodology_warnings"] = warnings
    return result
