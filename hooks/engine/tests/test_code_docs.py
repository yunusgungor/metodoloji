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


# ---------------------------------------------------------------------------
# New tests for fixes applied 2026-09-06
# ---------------------------------------------------------------------------

# --- root param on recall functions ----------------------------------------

def test_recall_by_tag_with_explicit_root(tmp_path, monkeypatch):
    """recall_by_tag(root=...) uses the given path, not env vars."""
    # Do NOT set CLAUDE_PROJECT_DIR — root param must win
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    # Pre-populate a decisions dir under tmp_path manually
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-test.md").write_text(
        '---\nid: D-001\ntype: decision\ntitle: "Root param test"\n'
        'date: 01.01.2026\ntags: [rootparam]\nstatus: active\n---\nbody',
        encoding="utf-8",
    )
    results = recall_by_tag("rootparam", root=str(tmp_path))
    assert len(results) == 1
    assert results[0]["title"] == "Root param test"


def test_recall_by_type_with_explicit_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-x.md").write_text(
        '---\nid: D-001\ntype: decision\ntitle: "T"\n'
        'date: 01.01.2026\ntags: [x]\nstatus: active\n---\n',
        encoding="utf-8",
    )
    results = recall_by_type("decision", root=str(tmp_path))
    assert len(results) == 1


def test_load_pending_docs_with_explicit_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    # Write a pending doc directly — bypass create_pending to avoid env lookup
    p = tmp_path / "docs/code-docs/pending"
    p.mkdir(parents=True)
    (p / "X-001-todo.md").write_text(
        '---\nid: X-001\ntype: pending\ntitle: "Pending root test"\n'
        'date: 01.01.2026\ntags: [pending]\npriority: normal\nstatus: pending\n---\n',
        encoding="utf-8",
    )
    result = load_pending_docs(root=str(tmp_path))
    assert "Pending root test" in result


def test_load_recent_docs_with_explicit_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-x.md").write_text(
        '---\nid: D-001\ntype: decision\ntitle: "Recent root"\n'
        'date: 06.09.2026\ntags: [x]\nstatus: active\n---\n',
        encoding="utf-8",
    )
    result = load_recent_docs(n=5, root=str(tmp_path))
    assert "Recent root" in result


def test_load_context_for_task_with_explicit_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-auth.md").write_text(
        '---\nid: D-001\ntype: decision\ntitle: "Auth decision"\n'
        'date: 06.09.2026\ntags: [auth]\nstatus: active\n---\n',
        encoding="utf-8",
    )
    ctx = load_context_for_task("implement the auth flow", root=str(tmp_path))
    assert "Auth decision" in ctx


# --- _get_project_root cwd fallback warning ---------------------------------

def test_get_project_root_cwd_fallback_emits_warning(monkeypatch, capsys):
    """_get_project_root() must print a warning to stderr when falling back to cwd."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    from modules.code_docs import _get_project_root
    _get_project_root()
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "cwd=" in captured.err


def test_get_project_root_no_warning_when_env_set(monkeypatch, capsys):
    """No warning when CLAUDE_PROJECT_DIR is set."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/project")
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    from modules.code_docs import _get_project_root
    _get_project_root()
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err

# --- root param write chain (end-to-end) ------------------------------------

def test_create_decision_with_explicit_root_no_env(tmp_path, monkeypatch):
    """create_decision(root=...) writes to given root even when no env var is set."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    path = create_decision("Root chain test", "d", "r", root=str(tmp_path))
    assert path.exists()
    assert str(tmp_path) in str(path)
    # index.md must also be created in the same root
    index = tmp_path / "docs/code-docs/index.md"
    assert index.exists()
    assert "Root chain test" in index.read_text(encoding="utf-8")


def test_create_pending_with_explicit_root_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    path = create_pending("Pending chain", "desc", root=str(tmp_path))
    assert path.exists()
    assert str(tmp_path) in str(path)


def test_next_id_uses_root_param(tmp_path, monkeypatch):
    """_next_id(root=...) counts existing docs under the given root, not env root."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    # Pre-create two decisions under tmp_path
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    (d / "D-001-x.md").touch()
    (d / "D-002-x.md").touch()
    assert _next_id("decision", root=str(tmp_path)) == "D-003"


def test_write_doc_uses_root_param(tmp_path, monkeypatch):
    """_write_doc(root=...) writes to the given root without touching env."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    content = "---\nid: D-NEW-test-slug\n---\n"
    path = _write_doc("decision", "test-slug", content, root=str(tmp_path))
    assert path.exists()
    assert str(tmp_path) in str(path)


def test_two_separate_roots_dont_cross_contaminate(tmp_path, monkeypatch):
    """create_decision with root=A and root=B each write only to their own root."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    root_a = tmp_path / "project_a"
    root_b = tmp_path / "project_b"
    root_a.mkdir()
    root_b.mkdir()
    create_decision("Decision A", "d", "r", root=str(root_a))
    create_decision("Decision B", "d", "r", root=str(root_b))
    # A only has Decision A
    docs_a = list((root_a / "docs/code-docs/decisions").glob("D-*.md"))
    assert len(docs_a) == 1
    assert "decision-a" in docs_a[0].name
    # B only has Decision B
    docs_b = list((root_b / "docs/code-docs/decisions").glob("D-*.md"))
    assert len(docs_b) == 1
    assert "decision-b" in docs_b[0].name


# --- CRLF handling (_parse_frontmatter + recall pipeline) --------------------

def test_parse_frontmatter_crlf():
    """CRLF line endings must parse identically to LF."""
    content_lf = "---\nid: D-1\ntype: decision\ntitle: \"CRLF\"\ntags: [a, b]\n---\nbody"
    content_crlf = content_lf.replace("\n", "\r\n")
    assert _parse_frontmatter(content_crlf) == _parse_frontmatter(content_lf)
    fm = _parse_frontmatter(content_crlf)
    assert fm["id"] == "D-1"
    assert fm["tags"] == ["a", "b"]


def test_parse_frontmatter_mixed_endings():
    """Mixed LF/CRLF/CR endings must still parse."""
    content = "---\r\nid: D-2\r\ntype: decision\ntitle: \"Mixed\"\r\ntags: [x]\n---\r\nbody"
    fm = _parse_frontmatter(content)
    assert fm["id"] == "D-2"
    assert fm["title"] == "Mixed"


def test_parse_frontmatter_bare_cr():
    """Bare CR (old Mac) endings must still parse."""
    content = "---\rid: D-3\rtype: decision\rtitle: \"BareCR\"\rtags: [y]\r---\rbody"
    fm = _parse_frontmatter(content)
    assert fm["id"] == "D-3"
    assert fm["tags"] == ["y"]


def test_parse_frontmatter_crlf_no_frontmatter():
    assert _parse_frontmatter("no fm\r\nsecond line") == {}


def test_recall_by_tag_with_crlf_file(tmp_path, monkeypatch):
    """Docs written with CRLF on disk must be recalled correctly."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    raw = (
        "---\r\n"
        'id: D-099\r\n'
        "type: decision\r\n"
        'title: "CRLF file"\r\n'
        "date: 06.09.2026\r\n"
        "tags: [crlftag]\r\n"
        "status: active\r\n"
        "---\r\n"
        "body\r\n"
    )
    # write with newline='' to preserve CRLF bytes exactly
    (d / "D-099-crlf.md").write_text(raw, encoding="utf-8", newline="")
    results = recall_by_tag("crlftag", root=str(tmp_path))
    assert len(results) == 1
    assert results[0]["id"] == "D-099"
    assert results[0]["title"] == "CRLF file"


def test_recall_by_type_with_crlf_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    d = tmp_path / "docs/code-docs/decisions"
    d.mkdir(parents=True)
    raw = "---\r\nid: D-100\r\ntype: decision\r\ntitle: \"T\"\r\ndate: 01.01.2026\r\ntags: [x]\r\nstatus: active\r\n---\r\n"
    (d / "D-100-x.md").write_text(raw, encoding="utf-8", newline="")
    results = recall_by_type("decision", root=str(tmp_path))
    assert any(r["id"] == "D-100" for r in results)


def test_load_context_with_crlf_pending(tmp_path, monkeypatch):
    """Pending docs stored CRLF must still be injected into task context."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    p = tmp_path / "docs/code-docs/pending"
    p.mkdir(parents=True)
    raw = (
        "---\r\n"
        "id: X-099\r\n"
        "type: pending\r\n"
        'title: "CRLF pending"\r\n'
        "date: 06.09.2026\r\n"
        "tags: [pending]\r\n"
        "priority: normal\r\n"
        "status: pending\r\n"
        "---\r\n"
    )
    (p / "X-099-pending.md").write_text(raw, encoding="utf-8", newline="")
    ctx = load_context_for_task("unrelated task", root=str(tmp_path))
    assert "CRLF pending" in ctx
