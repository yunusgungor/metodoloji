"""Guard logic for PreToolUse hook."""

import contextlib
import io
import json
import os
import pathlib
import re
import sys

from .config import GATE_DIR, _BMD_DIR, _KEY_ACCESS_IN_CONTENT, _AGENT_ZONES
from .utils import is_code_target, is_free, norm_path, rel_to_root, repo_root
from .bash_targets import extract_bash_targets

# Import gate script
if GATE_DIR is None:
    sys.stderr.write("bmad-hooks: gate script not found — fail-closed\n")
    sys.exit(2)

if str(GATE_DIR) not in sys.path:
    sys.path.insert(0, str(GATE_DIR))
import run_experiment as gate  # noqa: E402


def _secret_ref(s: str) -> bool:
    """True if s contains a secret leak indicator."""
    low = s.lower()
    if "gate-key" in low or "bmad_gate_key" in low:
        return True
    return bool(_BMD_DIR.search(s))


def _notebook_content_to_text(content) -> str:
    """Normalize notebook content to text for scanning."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for cell in content:
        if isinstance(cell, dict):
            src = cell.get("source") or cell.get("code") or []
            if isinstance(src, list):
                parts.extend(src)
            elif isinstance(src, str):
                parts.append(src)
        elif isinstance(cell, str):
            parts.append(cell)
    return "\n".join(parts)


def verify_record(rec: str) -> tuple[int, str]:
    """Run gate verify on a record; return (rc, scope)."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = gate.verify(rec)
        return rc, gate.record_scope(rec)
    except Exception:
        return 1, ""


def find_approved(target: str, recs_dir: str | None = None) -> tuple[bool, str]:
    """Find a VERIFIED record whose scope matches target."""
    target_rel = norm_path(target).lstrip("/")
    recs_dir = recs_dir or "docs/experiments"
    base = pathlib.Path(recs_dir)
    if not base.is_dir():
        return False, "docs/experiments/ not found"
    key_missing = False
    best = None
    for rec in sorted(base.glob("*.md")):
        if rec.name == "_template.md":
            continue
        rc, scope = verify_record(str(rec))
        if rc == 3:
            key_missing = True
            continue
        if rc != 0:
            continue
        if gate.scope_matches(scope, target_rel):
            return True, f"record {rec} (scope matched)"
        if best is None:
            best = f"record {rec} scope not matched"
    if key_missing:
        return False, "gate key not configured (python3 run_experiment.py --init-secret)"
    return False, best or "no approved experiment record"


def guard(json_in: dict) -> dict:
    """PreToolUse guard: block code writes without approved experiment record."""
    tool_name = json_in.get("tool_name", "")
    tool_input = json_in.get("tool_input", {})

    # Determine targets based on tool
    targets: list[str] = []

    if tool_name == "terminal":
        command = tool_input.get("command", "")
        targets = extract_bash_targets(command)

        # Check for secret references in command
        if _secret_ref(command):
            return {
                "decision": "deny",
                "reason": "Gate key reference detected in command — blocked."
            }

    elif tool_name == "file_editor":
        path = tool_input.get("path", "")
        if path:
            targets = [path]

    elif tool_name == "notebook_editor":
        path = tool_input.get("path", "")
        if path:
            targets = [path]

    # Check each target
    root = repo_root(json_in)
    for target in targets:
        rel = rel_to_root(root, target)

        # Free zone — no approval needed
        if is_free(rel):
            continue

        # Check if it's a code target
        if not is_code_target(rel):
            continue

        # Check for secret references in file content (for free zones)
        if any(rel.startswith(zone) for zone in _AGENT_ZONES):
            try:
                content = ""
                if tool_name == "file_editor":
                    content = str(tool_input.get("content", ""))
                elif tool_name == "notebook_editor":
                    content = _notebook_content_to_text(tool_input.get("content", []))
                if _KEY_ACCESS_IN_CONTENT.search(content):
                    return {
                        "decision": "deny",
                        "reason": f"Secret access pattern detected in {rel} — blocked."
                    }
            except Exception:
                pass

        # Find approved record
        approved, detail = find_approved(rel)
        if not approved:
            return {
                "decision": "deny",
                "reason": f"No approved experiment record for {rel}: {detail}. "
                          f"Create a hypothesis, measure, and get approval with "
                          f"run_experiment.py --record docs/experiments/E-XXX.md --run <cmd>"
            }

    return {"decision": "allow"}
