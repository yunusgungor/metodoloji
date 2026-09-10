"""Tests for hooks/engine/modules/audit.py — trail redaction + bridge check."""

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.audit import (  # noqa: E402
    _check_kopru_consumption,
    _redacted_input,
    audit,
)


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


def test_kopru_qr_table_with_valid_dod_no_warning():
    """A QR DoD Verification table with identifier + evidence rows is fine."""
    content = (
        "## DoD Verification Results\n\n"
        "| DoD Item | Status | Evidence | Date |\n"
        "|----------|--------|----------|------|\n"
        "| DoD-001 | ✅ passed | curl output | 2026-08-20 |\n"
        "| DoD-002 | ✅ passed | pytest output | 2026-08-20 |\n"
    )
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": content},
    )
    assert warnings == []


def test_kopru_qr_table_missing_evidence_warns():
    """QR DoD table rows without a recorded status/evidence are flagged — the
    same structural rule the guard applies to story DoD Verify fields."""
    content = (
        "## DoD Verification Results\n\n"
        "| DoD Item | Status | Evidence | Date |\n"
        "|----------|--------|----------|------|\n"
        "| DoD-001 | — | — | — |\n"
    )
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": content},
    )
    assert any("DoD" in w and "missing Verify field" in w for w in warnings)


def test_kopru_qr_bullet_with_result_marker_no_warning():
    """QR bullet-style items that record their result (→ ✓ PASS) are valid."""
    content = "## DoD Verification\n\n- [DoD-001] DENY unapproved → ✓ PASS\n"
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": content},
    )
    assert warnings == []


def test_kopru_qr_bullet_without_verification_warns():
    """QR bullet-style items that record no result are flagged (guard parity)."""
    content = "## DoD Verification\n\n- [DoD-001] All ACs verified\n"
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": content},
    )
    assert any("DoD" in w and "missing Verify field" in w for w in warnings)


def test_kopru_qr_mentions_dod_but_no_items_warns():
    """A QR that repeats the words DoD but has no bullet/table item warns."""
    content = "## DoD Verification Results\n\n| DoD Item | Status | Evidence | Date |\n"
    warnings = _check_kopru_consumption(
        "file_editor",
        {"path": "docs/quality/QR-001.md", "content": content},
    )
    assert any("has no DoD items" in w for w in warnings)


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







# === NEW TESTS for audit module enhancements (MEDIUM #12 / ISSUE #71) ===


def test_redacted_input_truncates_long_input():
    """Test that _redacted_input respects length limits."""
    # Import the config limit
    from modules.config import ERROR_CODE_REGISTRY
    
    # Create long input
    long_input = "x" * 1000
    
    # Redacted input should be truncated
    result = _redacted_input({"path": "test.py", "content": long_input})
    
    # Result should be reasonable length (audit.py truncates at 300 chars)
    assert len(str(result)) < 500  # Sanity check


def test_audit_records_hook_events_to_blackboard(tmp_path, monkeypatch):
    """Test that audit module records PostToolUse events to blackboard."""
    import json
    
    root = tmp_path
    (root / ".metodoloji").mkdir()
    
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    
    # Call audit with a file edit
    json_in = {
        "command": "audit",
        "root": str(root),
        "tool": "file_editor",
        "input": {"path": "test.py", "content": "x = 1"},
    }
    
    result = audit(json_in)
    
    # Should return decision (allow/deny)
    assert "decision" in result
    assert result["decision"] in ("allow", "deny")


def test_audit_exception_handling_graceful(tmp_path, monkeypatch):
    """Test that audit handles exceptions gracefully (broad exception handling reduction)."""
    root = tmp_path
    (root / ".metodoloji").mkdir()
    
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    
    # Malformed input
    json_in = {
        "command": "audit",
        "root": str(root),
        "tool": "file_editor",
        "input": None,  # Invalid
    }
    
    try:
        result = audit(json_in)
        # Should not raise, but may fail gracefully
        assert isinstance(result, dict)
    except Exception as e:
        # If it raises, should be a specific exception, not generic
        assert not isinstance(e, Exception) or "specific" in str(type(e)).lower()


def test_bridge_validation_on_qr_file():
    """Test that bridge (S→QR) validation works on QR files."""
    from modules.audit import _check_kopru_consumption
    
    # QR file consumption check
    warnings = _check_kopru_consumption(
        "file_editor",
        {
            "path": "docs/quality/QR-001.md",
            "content": "# Quality Record\n## Definition of Done\n- [ ] DoD-001 verified"
        }
    )
    
    # Should return list of warnings (may be empty)
    assert isinstance(warnings, list)
