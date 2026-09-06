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


def test_guard_soft_gate_warns_not_denies(tmp_path, monkeypatch):
    """With quality_gate=soft, story metadata gaps are warn-only, not deny."""
    from modules.guard import guard
    from modules import config
    # Force the soft-gate branch regardless of custom/config.toml.
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "soft")
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"  # missing Type/Measured/Verify
        "## Technical Tasks\n"
        "- [ ] do it AC: AC-001\n"
        "## Definition of Done\n"
        "- [ ] DoD-001 Verify: manual\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    assert res["decision"] == "allow"
    assert any("missing Type field" in w
               for w in res.get("methodology_warnings", []))


# --- guard combination matrix -------------------------------------------------

def test_guard_hard_gate_denies_metadata(tmp_path, monkeypatch):
    """quality_gate=hard → story metadata gaps are deny, not warn."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"  # missing Type/Measured/Verify
        "## Technical Tasks\n"
        "- [ ] do it AC: AC-001\n"
        "## Definition of Done\n"
        "- [ ] DoD-001 Verify: manual\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    assert res["decision"] == "deny"
    assert "Story metadata validation failed" in res["reason"]


def test_guard_soft_gate_still_denies_missing_experiment(tmp_path, monkeypatch):
    """Even soft gate: a story whose frontmatter names a missing experiment is
    DENY — experiment_refs validity is strictness-independent."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "soft")
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "---\n"
        "experiment_refs:\n"
        "  - id: E-999\n"
        "    status: APPROVED\n"
        "---\n"
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"
        "  - Experiment: E-999\n"
        "  - Type: agent-verifiable\n"
        "  - Measured: true\n"
        "  - Verify: curl http://x\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    # E-999 record does not exist → experiment_refs invalid → DENY regardless
    # of the soft gate.
    assert res["decision"] == "deny"
    assert "Story experiment validation failed" in res["reason"]


def test_guard_soft_gate_combines_scope_and_metadata_warnings(tmp_path, monkeypatch):
    """soft gate + out-of-scope write → warnings from both, still allow."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "soft")
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"
        "## Technical Tasks\n"
        "- [ ] do it AC: AC-001\n"
        "## Definition of Done\n"
        "- [ ] DoD-001 Verify: manual\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.setenv("METODOLOJI_SCOPE", "src/auth")
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    assert res["decision"] == "allow"
    warns = res.get("methodology_warnings", [])
    # Both the metadata warning and the out-of-scope warning present.
    assert any("missing Type field" in w for w in warns)
    assert any("outside the active scope" in w for w in warns)
    monkeypatch.delenv("METODOLOJI_SCOPE", raising=False)


def test_guard_mixed_gate_config_story_edit_not_blocked_by_deploy_guard(
        tmp_path, monkeypatch):
    """Regression: deploy_guard=hard must NOT block story metadata edits when
    quality_gate=soft. The story path reads quality_gate ONLY — deploy_guard
    governs deploy commands, not file writes."""
    from modules.guard import guard
    from modules import config

    def mixed_mode(key):
        return "hard" if key == "deploy_guard" else "soft"

    monkeypatch.setattr(config, "hook_gate_mode", mixed_mode)
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"  # missing Type/Measured/Verify
        "## Technical Tasks\n"
        "- [ ] do it AC: AC-001\n"
        "## Definition of Done\n"
        "- [ ] DoD-001 Verify: manual\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    # quality_gate=soft → warn-only, allow despite deploy_guard=hard.
    assert res["decision"] == "allow"
    assert any("missing Type field" in w
               for w in res.get("methodology_warnings", []))


def test_guard_mixed_gate_config_hard_quality_still_denies(tmp_path, monkeypatch):
    """The mirror direction: quality_gate=hard denies story metadata gaps even
    when deploy_guard=soft — the story path follows quality_gate."""
    from modules.guard import guard
    from modules import config

    def mixed_mode(key):
        return "hard" if key == "quality_gate" else "soft"

    monkeypatch.setattr(config, "hook_gate_mode", mixed_mode)
    stories = tmp_path / "docs/development/stories"
    stories.mkdir(parents=True)
    content = (
        "## Story: S-001\n"
        "## Acceptance Criteria\n"
        "- [AC-001] Given X When Y Then Z\n"
        "## Technical Tasks\n"
        "- [ ] do it AC: AC-001\n"
        "## Definition of Done\n"
        "- [ ] DoD-001 Verify: manual\n"
    )
    (stories / "S-001.md").write_text(content, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/development/stories/S-001.md",
                                "content": content}})
    assert res["decision"] == "deny"
    assert "Story metadata validation failed" in res["reason"]


def _write_story(tmp_path, key="S-001", status="done"):
    """Write a done story into tmp_path's docs tree (no records)."""
    (tmp_path / "docs/development/stories").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/quality").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/development/stories" / f"{key}.md").write_text(
        f"## Story: {key}\n- **Status:** {status}\n", encoding="utf-8")


def test_quality_soft_gate_warns_not_denies(tmp_path, monkeypatch):
    """quality_gate=soft → git commit with missing IR/QR is warn-only."""
    from modules.guard import quality
    from modules import config
    monkeypatch.setattr(config, "_hook_gate_value",
                        lambda key: "soft")
    _write_story(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = quality({"tool_name": "terminal",
                   "tool_input": {"command": "git commit -m 'x'"}})
    assert res["decision"] == "allow"
    assert any("Implementation Readiness" in w
               for w in res.get("methodology_warnings", []))


def test_quality_hard_gate_denies(tmp_path, monkeypatch):
    """quality_gate=hard → git commit with missing IR/QR is DENY."""
    from modules.guard import quality
    from modules import config
    monkeypatch.setattr(config, "_hook_gate_value",
                        lambda key: "hard")
    _write_story(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = quality({"tool_name": "terminal",
                   "tool_input": {"command": "git commit -m 'x'"}})
    assert res["decision"] == "deny"


def test_deploy_soft_gate_warns_not_denies(tmp_path, monkeypatch):
    """deploy_guard=soft → deploy with missing PR is warn-only."""
    from modules.guard import deploy
    from modules import config
    monkeypatch.setattr(config, "_hook_gate_value",
                        lambda key: "soft")
    _write_story(tmp_path)
    (tmp_path / "docs/quality/QR-001.md").write_text(
        "# QR\nStory S-001 approved\n", encoding="utf-8")
    (tmp_path / "docs/development/IR-001.md").write_text("# IR\nready", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = deploy({"tool_name": "terminal",
                  "tool_input": {"command": "git push origin main"}})
    assert res["decision"] == "allow"
    assert any("Production Readiness" in w
               for w in res.get("methodology_warnings", []))


def test_deploy_hard_gate_denies(tmp_path, monkeypatch):
    """deploy_guard=hard → deploy with missing PR is DENY."""
    from modules.guard import deploy
    from modules import config
    monkeypatch.setattr(config, "_hook_gate_value",
                        lambda key: "hard")
    _write_story(tmp_path)
    (tmp_path / "docs/quality/QR-001.md").write_text(
        "# QR\nStory S-001 approved\n", encoding="utf-8")
    (tmp_path / "docs/development/IR-001.md").write_text("# IR\nready", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = deploy({"tool_name": "terminal",
                  "tool_input": {"command": "git push origin main"}})
    assert res["decision"] == "deny"


def test_gates_read_independent_keys(tmp_path, monkeypatch):
    """quality_gate and deploy_guard are read independently: deploy_guard=hard
    must not make the quality gate hard (and vice versa)."""
    from modules.guard import quality, deploy
    from modules import config
    # Only deploy_guard is hard.
    monkeypatch.setattr(config, "_hook_gate_value",
                        lambda key: "hard" if key == "deploy_guard" else "soft")
    _write_story(tmp_path)  # no IR record → both gates fail the IR check
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    # quality gate soft → allow + warning (never deny)
    q = quality({"tool_name": "terminal",
                 "tool_input": {"command": "git commit -m 'x'"}})
    assert q["decision"] == "allow"
    assert any("Implementation Readiness" in w
               for w in q.get("methodology_warnings", []))
    # deploy gate hard → deny on the same IR gap
    d = deploy({"tool_name": "terminal",
                "tool_input": {"command": "git push origin main"}})
    assert d["decision"] == "deny"
    assert "Implementation Readiness" in d["reason"]


def test_guard_notes_story_filename_not_story(tmp_path, monkeypatch):
    """notes-S-001.md is an ordinary file, not a story — no metadata gate."""
    from modules.guard import guard
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "docs/notes-S-001.md",
                                "content": "hello"}})
    assert res["decision"] == "allow"


def test_guard_frontmatter_body_rule_not_fence(tmp_path, monkeypatch):
    """A '---' rule inside the body must not truncate the frontmatter."""
    from modules.guard import _parse_experiment_refs
    content = ("---\n"
               "experiment_refs:\n"
               "  - id: E-001\n"
               "    status: APPROVED\n"
               "---\n"
               "## Body\n---\nrest\n")
    refs = _parse_experiment_refs(content)
    assert len(refs) == 1 and refs[0]["id"] == "E-001"


def test_guard_frontmatter_top_level_key_ends_refs():
    """status: draft after the refs is frontmatter, not part of the ref."""
    from modules.guard import _parse_experiment_refs
    content = ("---\n"
               "experiment_refs:\n"
               "  - id: E-001\n"
               "    status: APPROVED\n"
               "status: draft\n"
               "---\n")
    refs = _parse_experiment_refs(content)
    assert refs == [{"id": "E-001", "status": "APPROVED"}]


def test_guard_secret_context_still_denies(tmp_path, monkeypatch):
    """Access context (call/assign) still denies — narrowing only drops prose."""
    from modules.guard import guard
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "scratch/notes.md",
                                "content": "x = load_secret('k')"}})
    assert res["decision"] == "deny"


def test_guard_secret_prose_no_longer_denies(tmp_path, monkeypatch):
    """Bare 'secret_env' in prose is not an access — no deny."""
    from modules.guard import guard
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "scratch/notes.md",
                                "content": "the secret_env carries over"}})
    assert res["decision"] == "allow"


def test_guard_verify_cache_skips_reverify(tmp_path, monkeypatch):
    """Unchanged records verify once; second find_approved hits the cache."""
    import sys
    from modules.guard import find_approved, _VERIFY_CACHE
    guard_mod = sys.modules["modules.guard"]
    (tmp_path / "docs/experiments").mkdir(parents=True)
    (tmp_path / "docs/experiments/E-001.md").write_text("# E\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(guard_mod, "verify_record",
                        lambda rec: (calls.append(rec) or (0, "src/**")))
    monkeypatch.setattr(guard_mod, "_load_gate", lambda: True)
    monkeypatch.setattr(guard_mod, "gate",
                        type("G", (), {"scope_matches": staticmethod(lambda s, t: True)})(),
                        raising=False)
    _VERIFY_CACHE.clear()
    find_approved("src/a.py", root=str(tmp_path))
    find_approved("src/b.py", root=str(tmp_path))
    assert len(calls) == 1


def test_guard_code_guard_soft_warns_not_denies(tmp_path, monkeypatch):
    """code_guard=soft (brownfield): unapproved write warns, still allows."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode",
                        lambda key: "soft" if key == "code_guard" else "hard")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "src/main.py", "content": "print(1)"}})
    assert res["decision"] == "allow"
    assert any("No approved experiment record" in w
               for w in res.get("methodology_warnings", []))


def test_guard_code_guard_hard_still_denies(tmp_path, monkeypatch):
    """Default code_guard=hard: unapproved write still denies."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "src/main.py", "content": "print(1)"}})
    assert res["decision"] == "deny"


def test_guard_scope_inside_no_warning(tmp_path, monkeypatch):
    """A write inside the active scope gets no scope warning."""
    from modules.guard import guard
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "soft")
    (tmp_path / "src/auth").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.setenv("METODOLOJI_SCOPE", "src/auth")
    res = guard({"tool_name": "file_editor",
                 "tool_input": {"path": "src/auth/login.py", "content": "x"}})
    # Free-zone? src/ is not free → needs approval → deny (no experiment record).
    # The scope check itself must not add a scope warning when inside scope.
    warns = res.get("methodology_warnings", [])
    assert not any("outside the active scope" in w for w in warns)
    monkeypatch.delenv("METODOLOJI_SCOPE", raising=False)
