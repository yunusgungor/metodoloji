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
    _redacted_input,
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

def test_kopru_done_story_check_moved_to_static_audit(tmp_path, monkeypatch):
    # The done-story→QR directory scan moved to check-plugin.sh (static
    # audit); the per-write hot path only checks the edited QR file itself.
    root = tmp_path
    (root / "docs/development/stories").mkdir(parents=True)
    (root / "docs/quality").mkdir(parents=True)  # quality dir exists but empty
    (root / "docs/development/stories/S-001.md").write_text(
        "## Story: S-001\n- **Status:** done\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/development/stories/S-001.md", "content": "x"},
    )
    assert warnings == []


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


def test_redacted_input_truncates_bodies_keeps_paths():
    big = "x" * 5000
    out = _redacted_input({"path": "src/main.py", "content": big,
                           "command": "echo hi"})
    assert out["path"] == "src/main.py"
    assert out["command"] == "echo hi"
    assert len(out["content"]) < len(big)
    assert "truncated 5000 chars" in out["content"]


def test_redacted_input_short_bodies_untouched():
    out = _redacted_input({"path": "src/a.py", "content": "print(1)"})
    assert out == {"path": "src/a.py", "content": "print(1)"}


def test_audit_log_redacts_content(tmp_path, monkeypatch):
    import json
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    big = "SECRET-DATA " * 500
    audit({"tool_name": "file_editor",
           "tool_input": {"path": "src/main.py", "content": big},
           "tool_output": None})
    log = root / ".metodoloji/logs/hook-audit.log"
    logged = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert logged["input"]["path"] == "src/main.py"
    assert len(logged["input"]["content"]) < len(big)
    assert "truncated 6000 chars" in logged["input"]["content"]


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


# ---------------------------------------------------------------------------
# New tests for fixes applied 2026-09-06
# ---------------------------------------------------------------------------

# --- _try_generate_code_doc error stamping ----------------------------------

def test_try_generate_code_doc_stamps_error_on_failure(tmp_path, monkeypatch):
    """On failure, _try_generate_code_doc stamps code_doc_errors into audit_record."""
    import sys
    from modules.audit import _try_generate_code_doc

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    # Make the directory read-only so create_pending will fail
    docs_dir = tmp_path / "docs/code-docs/pending"
    docs_dir.mkdir(parents=True)
    docs_dir.chmod(0o444)

    audit_record = {}
    try:
        _try_generate_code_doc(
            {"type": "pending", "trigger": "todo_detected",
             "path": "src/x.py", "description": "fix me"},
            audit_record=audit_record,
        )
    finally:
        docs_dir.chmod(0o755)  # restore for cleanup

    assert "code_doc_errors" in audit_record
    assert audit_record["code_doc_errors"][0]["event_type"] == "pending"


def test_try_generate_code_doc_no_stamp_on_success(tmp_path, monkeypatch):
    """On success, no code_doc_errors key is added to audit_record."""
    from modules.audit import _try_generate_code_doc

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    audit_record = {}
    _try_generate_code_doc(
        {"type": "pending", "trigger": "todo_detected",
         "path": "src/x.py", "description": "something to fix"},
        audit_record=audit_record,
    )
    assert "code_doc_errors" not in audit_record


def test_try_generate_code_doc_error_printed_to_stderr(tmp_path, monkeypatch, capsys):
    """Failure message is printed to stderr regardless of audit_record."""
    from modules.audit import _try_generate_code_doc

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    docs_dir = tmp_path / "docs/code-docs/pending"
    docs_dir.mkdir(parents=True)
    docs_dir.chmod(0o444)

    try:
        _try_generate_code_doc(
            {"type": "pending", "trigger": "todo_detected",
             "path": "src/x.py", "description": "fix me"},
        )
    finally:
        docs_dir.chmod(0o755)

    captured = capsys.readouterr()
    assert "code-docs generation warning" in captured.err


def test_audit_stamps_code_doc_errors_in_log(tmp_path, monkeypatch):
    """When code-doc generation fails, the error shows up in the audit log record."""
    import json
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    # Create a read-only pending dir so auto-generation of pending docs fails
    pending_dir = root / "docs/code-docs/pending"
    pending_dir.mkdir(parents=True)
    pending_dir.chmod(0o444)

    try:
        audit({
            "tool_name": "file_editor",
            "tool_input": {"path": "src/main.py", "content": "# TODO: fix this"},
            "tool_output": None,
        })
    finally:
        pending_dir.chmod(0o755)

    log = root / ".metodoloji/logs/hook-audit.log"
    assert log.exists()
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert "code_doc_errors" in record


# --- session_start root propagation -----------------------------------------

def test_session_start_uses_repo_root(tmp_path, monkeypatch):
    """session_start reads code-docs from the resolved repo root, not cwd."""
    import json
    from modules.audit import session_start

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    # Place a pending doc in the tmp_path code-docs
    pending_dir = tmp_path / "docs/code-docs/pending"
    pending_dir.mkdir(parents=True)
    (pending_dir / "X-001-pending.md").write_text(
        '---\nid: X-001\ntype: pending\ntitle: "Session pending"\n'
        'date: 06.09.2026\ntags: [pending]\npriority: normal\nstatus: pending\n---\n',
        encoding="utf-8",
    )

    result = session_start({"cwd": str(tmp_path)})
    assert result["decision"] == "allow"
    ctx = result.get("additionalContext", "")
    assert "Session pending" in ctx


def test_try_generate_code_doc_writes_to_given_root(tmp_path, monkeypatch):
    """_try_generate_code_doc(root=...) writes docs to the given root, not env root."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    from modules.audit import _try_generate_code_doc

    audit_record = {}
    _try_generate_code_doc(
        {"type": "pending", "trigger": "todo_detected",
         "path": "src/x.py", "description": "root prop test"},
        audit_record=audit_record,
        root=str(tmp_path),
    )
    assert "code_doc_errors" not in audit_record
    pending_dir = tmp_path / "docs/code-docs/pending"
    assert pending_dir.exists()
    docs = list(pending_dir.glob("X-*.md"))
    assert len(docs) == 1
    assert "root prop test" in docs[0].read_text(encoding="utf-8")


def test_audit_end_to_end_docs_in_correct_root(tmp_path, monkeypatch):
    """audit() end-to-end: TODO in file_editor content creates pending doc in project root."""
    import json
    root = tmp_path
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)

    audit({
        "tool_name": "file_editor",
        "tool_input": {"path": "src/main.py", "content": "# TODO: integrate billing"},
        "tool_output": None,
    })

    pending_dir = root / "docs/code-docs/pending"
    docs = list(pending_dir.glob("X-*.md")) if pending_dir.exists() else []
    assert len(docs) == 1
    assert "billing" in docs[0].read_text(encoding="utf-8")
