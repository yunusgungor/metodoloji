"""Tests for hooks/engine/modules/code_docs.py — doc build/write/recall/load."""

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.code_docs import (  # noqa: E402
    _get_project_root,
    _next_id,
    _parse_frontmatter,
    _slugify,
    _write_doc,
    build_decision_doc,
    build_learning_doc,
    build_pattern_doc,
    build_pending_doc,
    build_troubleshooting_doc,
    create_decision,
    create_learning,
    create_pending,
    load_context_for_task,
    load_pending_docs,
    load_recent_docs,
    recall_all,
    recall_by_experiment,
    recall_by_tag,
    recall_by_type,
)


# --- _slugify / _next_id / _parse_frontmatter -------------------------------

def test_slugify():
    assert _slugify("Hello World!") == "hello-world"
    assert _slugify("  Spaces   Between  ") == "spaces-between"
    assert _slugify("a" * 60) == "a" * 40  # capped


def test_next_id_starts_at_001(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    assert _next_id("decision") == "D-001"


def test_next_id_increments(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-x.md").write_text("", encoding="utf-8")
    (d / "D-002-y.md").write_text("", encoding="utf-8")
    assert _next_id("decision") == "D-003"


def test_parse_frontmatter():
    content = "---\nid: D-1\ntype: decision\ntitle: \"T\"\ntags: [a, b]\n---\nbody"
    fm = _parse_frontmatter(content)
    assert fm["id"] == "D-1"
    assert fm["tags"] == ["a", "b"]


def test_parse_frontmatter_no_frontmatter():
    assert _parse_frontmatter("no fm") == {}


# --- build_*_doc content shape ----------------------------------------------

def test_build_decision_doc_fields():
    doc = build_decision_doc("Pick Go", "Go it is", "team pref",
                             related_experiments=["E-001"],
                             related_stories=["S-002"])
    assert "D-NEW-pick-go" in doc
    assert "## Decision" in doc and "Go it is" in doc
    assert "E-001" in doc and "S-002" in doc


def test_build_learning_doc_parses_record(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    rec = tmp_path / "E-001.md"
    rec.write_text(
        "**Theory:** T\n**Hypothesis:** H-001: \"x >= 0.9\"\n"
        "**Measurement Metrics:** x\n**Decision:** APPROVED\n",
        encoding="utf-8",
    )
    doc = build_learning_doc("E-001", str(rec))
    assert "Experiment E-001" in doc
    assert "T" in doc and "H-001" in doc


def test_build_pending_doc_defaults():
    doc = build_pending_doc("Fix bug", "desc", priority="high")
    assert "X-NEW-fix-bug" in doc
    assert "priority: high" in doc
    assert "Not yet determined." in doc


def test_build_troubleshooting_doc_prevention_default():
    doc = build_troubleshooting_doc("Err", "e", "cause", "fix")
    assert "Not specified." in doc


def test_build_pattern_doc_example_default():
    doc = build_pattern_doc("Pat", "p", "usage")
    assert "# Example to be added" in doc


# --- create_* + recall round-trip -------------------------------------------

def test_create_and_recall_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    path = create_decision("Choose X", "X", "because", tags=["auth"],
                           related_experiments=["E-005"])
    assert path.exists()
    # recall by tag
    by_tag = recall_by_tag("auth")
    assert any(d["title"] == "Choose X" for d in by_tag)
    # recall by experiment
    by_exp = recall_by_experiment("E-005")
    assert any(d["title"] == "Choose X" for d in by_exp)
    # recall by type
    by_type = recall_by_type("decision")
    assert len(by_type) == 1
    # recall all groups
    all_docs = recall_all()
    assert all_docs["decision"] == by_type


def test_recall_by_tag_no_match(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    assert recall_by_tag("nonexistent-tag") == []


def test_recall_by_type_unknown():
    assert recall_by_type("bogus") == []


# --- index generation -------------------------------------------------------

def test_create_decision_writes_index(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    create_decision("Idx", "d", "r")
    index = tmp_path / "docs/code-docs/index.md"
    assert index.exists()
    assert "## Categories" in index.read_text(encoding="utf-8")


# --- load_context_for_task --------------------------------------------------

def test_load_context_keyword(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    create_decision("Auth flow", "d", "r", tags=["auth"])
    ctx = load_context_for_task("implement the auth login flow")
    assert "Related Code Docs" in ctx
    assert "Auth flow" in ctx


def test_load_context_experiment(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    create_learning("E-010", str(tmp_path / "E-010.md"))  # missing record: defaults
    ctx = load_context_for_task("task mentioning E-010")
    assert "E-010" in ctx or "Related Code Docs" in ctx


def test_load_context_pending_always(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    create_pending("Todo thing", "desc")
    ctx = load_context_for_task("unrelated task")
    assert "Todo thing" in ctx


def test_load_context_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    assert load_context_for_task("nothing here") == ""


def test_load_recent_docs(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    create_decision("A", "d", "r")
    create_decision("B", "d", "r")
    ctx = load_recent_docs(n=5)
    assert "Related Code Docs" in ctx


def test_load_pending_docs(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    assert load_pending_docs() == ""
    create_pending("P1", "desc")
    assert "P1" in load_pending_docs()


def test_write_doc_replaces_placeholder_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    content = "id: D-NEW-some-slug\ntype: decision\n"
    path = _write_doc("decision", "slug", content)
    written = path.read_text(encoding="utf-8")
    assert "D-NEW-some-slug" not in written
    assert written.startswith("id: D-")
