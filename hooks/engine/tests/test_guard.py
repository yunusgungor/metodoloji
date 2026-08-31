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
