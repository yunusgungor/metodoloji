"""Tests for hooks/engine/modules/guard.py — gate record checks + story validation."""

import importlib.util
import sys
import tempfile
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.guard import (  # noqa: E402
    _check_gate_records,
    _find_done_stories_without_qr,
    _parse_experiment_refs,
    _parse_ac_metadata,
)


def _make_project(stories=(), records=()):
    """Create a temp project tree with stories and records.

    records is a list of (record_key, story_key) tuples; each record's content
    references the story key it covers, matching how the gate's
    _find_done_stories_without_record searches record content for story keys.
    """
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "docs/development/stories").mkdir(parents=True)
    (root / "docs/quality").mkdir(parents=True)
    for key, status in stories:
        (root / "docs/development/stories" / f"{key}.md").write_text(
            f"## Story: {key}\n- **Status:** {status}\n", encoding="utf-8")
    for rec_key, story_key in records:
        (root / "docs/quality" / f"{rec_key}.md").write_text(
            f"# QR\nStory {story_key} approved\n", encoding="utf-8")
    return td, root


def test_gate_ir_missing_denies():
    td, root = _make_project(stories=[("S-001", "done")])
    try:
        res = _check_gate_records(td.name, "git commit blocked")
        assert res["decision"] == "deny"
        assert "Implementation Readiness" in res["reason"]
    finally:
        td.cleanup()


def test_gate_qr_missing_denies():
    td, root = _make_project(stories=[("S-001", "done")])
    try:
        (root / "docs/development/IR-001.md").write_text("# IR\nready", encoding="utf-8")
        res = _check_gate_records(td.name, "git commit blocked")
        assert res["decision"] == "deny"
        assert "Quality Record" in res["reason"]
    finally:
        td.cleanup()


def test_gate_allow_when_records_present():
    td, root = _make_project(stories=[("S-001", "done")],
                             records=[("QR-001", "S-001")])
    try:
        (root / "docs/development/IR-001.md").write_text("# IR\nready", encoding="utf-8")
        res = _check_gate_records(td.name, "git commit blocked")
        assert res["decision"] == "allow"
    finally:
        td.cleanup()


def test_deploy_requires_pr():
    td, root = _make_project(stories=[("S-001", "done")],
                             records=[("QR-001", "S-001")])
    try:
        (root / "docs/development/IR-001.md").write_text("# IR\nready", encoding="utf-8")
        res = _check_gate_records(td.name, "Deploy blocked", include_pr=True)
        assert res["decision"] == "deny"
        assert "Production Readiness" in res["reason"]
        # adding PR (referencing the story) makes deploy pass
        (root / "docs/development/PR-001.md").write_text(
            "# PR\nStory S-001 ready\n", encoding="utf-8")
        res2 = _check_gate_records(td.name, "Deploy blocked", include_pr=True)
        assert res2["decision"] == "allow"
    finally:
        td.cleanup()


def test_find_done_stories_without_qr():
    td, root = _make_project(stories=[("S-001", "done"), ("S-002", "in-progress")])
    try:
        missing = _find_done_stories_without_qr(td.name)
        assert "S-001" in missing
        assert "S-002" not in missing  # not done
    finally:
        td.cleanup()


def test_parse_experiment_refs():
    content = """---
id: S-001
experiment_refs:
  - id: E-001
    scope: src/**
    status: APPROVED
---
## Story
"""
    refs = _parse_experiment_refs(content)
    assert len(refs) == 1
    assert refs[0]["id"] == "E-001"
    assert refs[0]["status"] == "APPROVED"


def test_parse_experiment_refs_empty():
    assert _parse_experiment_refs("## Story\nNo frontmatter") == []


def test_parse_ac_metadata():
    content = """## Acceptance Criteria
- [AC-001] **Given** X **When** Y **Then** Z
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: curl http://x
- [AC-002] **Given** X **When** Y **Then** Z
  - Experiment: —
  - Type: user-evaluable
  - Measured: false
  - Verify: manual
  - [HYPOTHESIS]
"""
    acs = _parse_ac_metadata(content)
    assert len(acs) == 2
    assert acs[0]["id"] == "AC-001"
    assert acs[0]["experiment"] == "E-001"
    assert acs[0]["type"] == "agent-verifiable"
    assert acs[1]["is_hypothesis"] is True


def test_parse_ac_metadata_no_section():
    assert _parse_ac_metadata("no ac here") == []


def test_parse_task_ac_refs():
    from modules.guard import _parse_task_ac_refs
    content = """## Technical Tasks
- [ ] implement login AC: AC-001
- [x] fix bug AC: AC-002 AC: AC-003
  - nested subtask AC: AC-999 (not a top-level task)
"""
    tasks = _parse_task_ac_refs(content)
    # Only top-level '- [ ]' / '- [x]' lines are captured; indented subtasks are not.
    assert len(tasks) == 2
    assert tasks[0]["ac_refs"] == ["AC-001"]
    assert tasks[1]["ac_refs"] == ["AC-002", "AC-003"]


def test_validate_story_metadata_missing_fields():
    from modules.guard import _validate_story_metadata
    content = """## Story: S-001
## Acceptance Criteria
- [AC-001] Given X When Y Then Z
"""
    valid, reason = _validate_story_metadata(content)
    assert valid is False
    assert "missing Type field" in reason


def test_validate_story_metadata_ok():
    from modules.guard import _validate_story_metadata
    content = """## Story: S-001
---
experiment_refs:
  - id: E-001
    status: APPROVED
---
## Acceptance Criteria
- [AC-001] Given X When Y Then Z
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: curl http://x
## Technical Tasks
- [ ] do it AC: AC-001
## Definition of Done
- [ ] DoD-001 Verify: manual
"""
    valid, reason = _validate_story_metadata(content)
    assert valid is True, reason


def test_validate_story_metadata_hypothesis_skips_experiment():
    from modules.guard import _validate_story_metadata
    content = """## Acceptance Criteria
- [AC-001] Given X When Y Then Z
  - Experiment: —
  - Type: user-evaluable
  - Measured: false
  - Verify: manual
  - [HYPOTHESIS]
"""
    # With no experiment_refs and a [HYPOTHESIS] AC, the missing Experiment
    # field is not flagged.
    valid, reason = _validate_story_metadata(content)
    assert valid is True, reason


def test_is_git_commit():
    from modules.guard import _is_git_commit
    assert _is_git_commit("git commit -am 'x'") is True
    assert _is_git_commit("git commit --amend") is True
    assert _is_git_commit("git status") is False
    assert _is_git_commit("ls") is False


def test_find_done_stories_without_ir():
    from modules.guard import _find_done_stories_without_ir
    td, root = _make_project(stories=[("S-001", "done")])
    try:
        missing = _find_done_stories_without_ir(td.name)
        assert "S-001" in missing
        (root / "docs/development").mkdir(exist_ok=True)
        (root / "docs/development/IR-001.md").write_text("# IR\n", encoding="utf-8")
        assert _find_done_stories_without_ir(td.name) == []
    finally:
        td.cleanup()


def test_find_done_stories_without_qr_excludes_templates():
    from modules.guard import _find_done_stories_without_qr
    td, root = _make_project(stories=[("S-001", "done"), ("_template", "done")])
    try:
        # _template.md is not an S-NNN file; only real stories are checked.
        missing = _find_done_stories_without_qr(td.name)
        assert "S-001" in missing
        assert "_template" not in missing
    finally:
        td.cleanup()


def test_intent_scope_warnings_outside_scope():
    from modules.guard import _intent_scope_warnings
    w = _intent_scope_warnings("src/auth", ["src/auth/login.py", "docs/README.md"], "/proj")
    assert any("docs/README.md" in x for x in w)
    assert not any("src/auth/login.py" in x for x in w)


def test_intent_scope_warnings_no_scope():
    from modules.guard import _intent_scope_warnings
    assert _intent_scope_warnings("", ["docs/x.md"], "/proj") == []
    assert _intent_scope_warnings("S-003", ["docs/other.md"], "/proj") == []


def test_guard_intent_scope_never_denies(tmp_path, monkeypatch):
    from modules.guard import guard
    # Scope outside → allow + warning, not deny.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.setenv("METODOLOJI_INTENT", "scope: src/auth")
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/x.md", "content": "hi"}})
    assert res["decision"] == "allow"
    assert any("outside the active scope" in w
               for w in res.get("methodology_warnings", []))
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
