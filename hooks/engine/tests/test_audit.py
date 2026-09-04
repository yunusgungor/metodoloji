"""Tests for hooks/engine/modules/audit.py — notable-event detection + compliance."""

import os
import sys
import tempfile
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.audit import (  # noqa: E402
    _check_kopru_consumption,
    _detect_notable_events,
    _validate_methodology_compliance,
    audit,
)


# --- _detect_notable_events -------------------------------------------------

def test_event_experiment_approved():
    events = _detect_notable_events(
        "terminal",
        {"command": "run_experiment.py --record docs/experiments/E-003.md --run 'x'"},
        "Experiment E-003 APPROVED",
    )
    assert any(e["type"] == "learning" and e["experiment_id"] == "E-003" for e in events)


def test_event_experiment_verify_no_learning():
    # --verify should NOT trigger learning doc generation.
    events = _detect_notable_events(
        "terminal",
        {"command": "run_experiment.py --record E.md --verify"},
        "VERIFIED",
    )
    assert all(e["type"] != "learning" for e in events)


def test_event_architecture_change():
    events = _detect_notable_events(
        "file_editor",
        {"path": "docs/architecture/spine.md", "content": "x" * 150},
        None,
    )
    assert any(e["type"] == "decision" and e["trigger"] == "architecture_change" for e in events)


def test_event_architecture_short_content_no_event():
    events = _detect_notable_events(
        "file_editor",
        {"path": "docs/architecture/x.md", "content": "short"},
        None,
    )
    assert all(e["type"] != "decision" for e in events)


def test_event_error_detected():
    events = _detect_notable_events(
        "terminal", {"command": "pytest"}, "Traceback (most recent call last)"
    )
    assert any(e["type"] == "troubleshooting" for e in events)


def test_event_todo_detected():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/a.py", "content": "# TODO: fix this\n# FIXME: that"},
        None,
    )
    pending = [e for e in events if e["type"] == "pending"]
    assert len(pending) == 2
    assert all(e["trigger"] == "todo_detected" for e in pending)


def test_event_future_plan_detected():
    events = _detect_notable_events(
        "terminal", {"command": "build"}, "next step is to implement caching"
    )
    assert any(e["type"] == "pending" and e["trigger"] == "future_plan_detected" for e in events)


def test_event_no_events_for_clean_output():
    events = _detect_notable_events("terminal", {"command": "ls"}, "file.txt")
    assert events == []


def test_event_pattern_class_hierarchy():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/auth.py", "content": "class AuthService(BaseService):\n    pass"},
        None,
    )
    assert any(e["type"] == "pattern" and e["trigger"] == "class_hierarchy"
               and e["class_name"] == "AuthService" for e in events)


def test_event_pattern_keyword_in_comment():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/auth.py", "content": "# implements the strategy pattern\ndef authenticate(): ..."},
        None,
    )
    assert any(e["type"] == "pattern" and e["trigger"] == "pattern_keyword" for e in events)


def test_event_pattern_no_trigger_on_plain_function():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/utils.py", "content": "def helper():\n    return 1"},
        None,
    )
    assert all(e["type"] != "pattern" for e in events)


def test_event_api_route_decorator():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/routes.py", "content": "@app.get('/users')\ndef get_users(): ..."},
        None,
    )
    assert any(e["type"] == "api" and e["trigger"] == "endpoint_detected"
               and e["route"] == "/users" for e in events)


def test_event_api_filename():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/views_api.py", "content": "def index(): ..."},
        None,
    )
    assert any(e["type"] == "api" and e["trigger"] == "endpoint_detected" for e in events)


def test_event_api_no_trigger_on_regular_file():
    events = _detect_notable_events(
        "file_editor",
        {"path": "src/utils.py", "content": "def helper():\n    return 1"},
        None,
    )
    assert all(e["type"] != "api" for e in events)


# --- _validate_methodology_compliance ---------------------------------------

def test_compliance_story_without_ac():
    warnings = _validate_methodology_compliance(
        "file_editor",
        {"path": "docs/development/stories/1-2-login.md",
         "content": "## Acceptance Criteria\n- item\n"},
    )
    assert any("AC metadata missing" in w for w in warnings)


def test_compliance_story_with_ac_ok():
    warnings = _validate_methodology_compliance(
        "file_editor",
        {"path": "docs/development/stories/1-2-login.md",
         "content": "## Acceptance Criteria\n- [AC-001] item\n"},
    )
    assert all("AC metadata missing" not in w for w in warnings)


def test_compliance_non_story_no_warnings():
    warnings = _validate_methodology_compliance(
        "file_editor", {"path": "src/a.py", "content": "print(1)"}
    )
    assert warnings == []


# --- _check_kopru_consumption ------------------------------------------------

def test_kopru_done_story_no_qr(tmp_path, monkeypatch):
    root = tmp_path
    (root / "docs/development/stories").mkdir(parents=True)
    (root / "docs/quality").mkdir(parents=True)  # quality dir exists but empty
    (root / "docs/development/stories/S-001.md").write_text(
        "## Story: S-001\n- **Status:** done\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    # Forward-slash path: the code's regex expects /stories/S-NNN.md and the
    # real project-relative path (as passed by the hook) is forward-slash.
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/development/stories/S-001.md", "content": "x"},
    )
    assert any("no QR record exists" in w for w in warnings)


def test_kopru_done_story_windows_backslash_path(tmp_path, monkeypatch):
    # BUG: with a native backslash path the /stories/ regex never matches, so
    # the bridge-consumption check is silently skipped on Windows.
    root = tmp_path
    (root / "docs/development/stories").mkdir(parents=True)
    (root / "docs/quality").mkdir(parents=True)
    (root / "docs/development/stories/S-001.md").write_text(
        "## Story: S-001\n- **Status:** done\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": f"{root}\\docs\\development\\stories\\S-001.md", "content": "x"},
    )
    assert warnings == []


def test_kopru_qr_without_dod():
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": "## Decision\nok"},
    )
    assert any("DoD" in w for w in warnings)


# --- audit() end-to-end ------------------------------------------------------

def test_audit_writes_log(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = audit({
        "tool_name": "terminal",
        "tool_input": {"command": "ls"},
        "tool_output": "ok",
    })
    assert res["decision"] == "allow"
    log = root / ".metodoloji/logs/hook-audit.log"
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    assert "terminal" in content and "ls" in content


def test_audit_writes_warnings(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = audit({
        "tool_name": "file_editor",
        "tool_input": {"path": "docs/quality/QR-001.md", "content": "## x"},
        "tool_output": None,
    })
    assert res["decision"] == "allow"
    assert "methodology_warnings" in res


def test_audit_log_stamps_intent(tmp_path, monkeypatch):
    import json
    root = tmp_path
    (root / "docs").mkdir()
    (root / "docs/.memlog.md").write_text(
        "---\npurpose: payment refactor\n---\n- (event) started\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    audit({"tool_name": "terminal", "tool_input": {"command": "ls"},
           "tool_output": "ok"})
    log = root / ".metodoloji/logs/hook-audit.log"
    assert log.exists()
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert line.get("intent") == "payment refactor"


def test_audit_log_intent_empty_when_no_memlog(tmp_path, monkeypatch):
    import json
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    audit({"tool_name": "terminal", "tool_input": {"command": "ls"},
           "tool_output": "ok"})
    log = root / ".metodoloji/logs/hook-audit.log"
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert line.get("intent") == ""
