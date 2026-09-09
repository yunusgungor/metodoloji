"""Blackboard tests — full CLI/core combination matrix.

Covers: write/read/tag/untag/contribute/hot/stats, caps and expiry,
event-sourced snapshot rebuild, atomicity under concurrent writers,
unicode content, fail-open behavior (missing dir, corrupt JSON),
and the config gate (custom/config.toml [hooks] blackboard).
"""

import concurrent.futures
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import blackboard as bb  # noqa: E402

CLI = Path(__file__).resolve().parent.parent.parent.parent / "bmad" / "scripts" / "blackboard.py"


@pytest.fixture()
def root():
    with tempfile.TemporaryDirectory() as td:
        yield td


# --- basic lifecycle -----------------------------------------------------------
def test_write_and_read_key(root):
    ack = bb.write_key(root, "prd.acme", "v1", type_="state")
    assert ack == {"ok": True, "key": "prd.acme", "hot": False}
    board = bb.read_board(root)
    assert board["keys"]["prd.acme"]["value"] == "v1"
    assert board["keys"]["prd.acme"]["type"] == "state"


def test_write_overwrites_and_keeps_single_entry(root):
    bb.write_key(root, "k", "a")
    bb.write_key(root, "k", "b")
    board = bb.read_board(root)
    assert len(board["keys"]) == 1
    assert board["keys"]["k"]["value"] == "b"


def test_empty_key_rejected(root):
    ack = bb.write_key(root, "  ", "v")
    assert ack["ok"] is False
    assert "error" in ack


def test_value_length_capped(root):
    ack = bb.write_key(root, "k", "x" * (bb.MAX_VALUE_LEN + 100))
    assert ack["ok"] is True
    board = bb.read_board(root)
    assert len(board["keys"]["k"]["value"]) == bb.MAX_VALUE_LEN


def test_hot_set_and_clear(root):
    bb.write_key(root, "a", "1")
    ack = bb.set_hot(root, "a")
    assert ack == {"ok": True, "hot": "a"}
    assert bb.read_board(root)["hot"] == "a"
    bb.set_hot(root, None)
    assert bb.read_board(root)["hot"] is None


def test_only_one_hot_key(root):
    bb.write_key(root, "a", "1", hot=True)
    bb.write_key(root, "b", "2", hot=True)
    assert bb.read_board(root)["hot"] == "b"


def test_write_non_hot_on_hot_key_reports_dirty(root):
    bb.write_key(root, "a", "1", hot=True)
    ack = bb.write_key(root, "a", "2")
    assert ack.get("dirty_notice")


def test_tag_add_remove_and_duplicate(root):
    assert bb.add_tag(root, "crm") == {"ok": True, "tag": "crm"}
    assert bb.add_tag(root, "crm")["duplicate"] is True
    assert bb.remove_tag(root, "crm") == {"ok": True, "tag": "crm"}
    assert bb.remove_tag(root, "crm")["absent"] is True


def test_untag_missing_tag_is_ok(root):
    assert bb.remove_tag(root, "nope")["ok"] is True


def test_contribute_and_order(root):
    bb.add_contribution(root, "a", "did a")
    bb.add_contribution(root, "b", "did b")
    board = bb.read_board(root)
    assert [c["who"] for c in board["contributions"]] == ["a", "b"]


def test_contribute_requires_who(root):
    assert bb.add_contribution(root, " ", "x")["ok"] is False


def test_compact_context_shape(root):
    bb.write_key(root, "prd.acme", "v", type_="state", hot=True)
    bb.add_tag(root, "t")
    bb.add_contribution(root, "w", "what")
    ctx = bb.compact_context(root)
    assert ctx["hot"] == "prd.acme"
    assert ctx["hot_meta"]["type"] == "state"
    assert ctx["tags"] == ["t"]
    assert ctx["contributions"][-1]["who"] == "w"
    assert ctx["key_count"] == 1
    assert "keys" not in ctx  # bounded contract: never dumps all values


def test_stats(root):
    bb.write_key(root, "k", "v")
    s = bb.stats(root)
    assert s["keys"] == 1 and s["events"] >= 1 and s["hot"] is None


# --- caps & expiry -------------------------------------------------------------
def test_keys_cap_expires_oldest(root):
    for i in range(bb.MAX_KEYS + 10):
        bb.write_key(root, f"k{i:03d}", str(i))
    board = bb.read_board(root)
    assert len(board["keys"]) == bb.MAX_KEYS
    assert "k000" not in board["keys"]  # oldest expired
    assert f"k{bb.MAX_KEYS + 9:03d}" in board["keys"]


def test_keys_cap_expires_hot_never_dangles(root):
    bb.write_key(root, "hold", "x")
    for i in range(bb.MAX_KEYS):
        bb.write_key(root, f"fill{i:03d}", "x")
    # force 'hold' to be oldest + hot
    board = bb.read_board(root)
    bb.set_hot(root, "hold")
    bb.write_key(root, "zzz-newest", "x")
    # expire everything by flooding past cap
    for i in range(bb.MAX_KEYS + 5):
        bb.write_key(root, f"flood{i:03d}", "x", type_="flood")
    board = bb.read_board(root)
    if "hold" not in board["keys"]:
        assert board["hot"] != "hold"  # never dangles


def test_tags_cap(root):
    for i in range(bb.MAX_TAGS + 5):
        bb.add_tag(root, f"tag{i:03d}")
    assert len(bb.read_board(root)["tags"]) == bb.MAX_TAGS


def test_contributions_cap(root):
    for i in range(bb.MAX_CONTRIBUTIONS + 5):
        bb.add_contribution(root, f"w{i:03d}", "x")
    assert len(bb.read_board(root)["contributions"]) == bb.MAX_CONTRIBUTIONS


def test_events_log_capped(root):
    for i in range(60):
        bb.write_key(root, "same.key", f"v{i}")
    s = bb.stats(root)
    assert s["events"] <= bb.MAX_EVENTS


# --- event sourcing & rebuild --------------------------------------------------
def test_snapshot_rebuild_from_events(root):
    bb.write_key(root, "k", "v")
    bb.add_tag(root, "t")
    bb.add_contribution(root, "w", "x")
    bb.set_hot(root, "k")
    os.remove(bb.board_paths(root)["snapshot"])
    board = bb.read_board(root)  # triggers rebuild
    assert board["keys"]["k"]["value"] == "v"
    assert board["hot"] == "k"
    assert board["tags"] == ["t"]
    assert board["contributions"][0]["who"] == "w"
    assert os.path.exists(bb.board_paths(root)["snapshot"])


def test_corrupt_snapshot_rebuilds(root):
    bb.write_key(root, "k", "v")
    p = bb.board_paths(root)["snapshot"]
    Path(p).write_text("{corrupt json", encoding="utf-8")
    board = bb.read_board(root)
    assert board["keys"]["k"]["value"] == "v"


def test_event_log_survives_garbage_lines(root):
    ev = bb.board_paths(root)["events"]
    bb.write_key(root, "k", "v")
    with open(ev, "a", encoding="utf-8") as f:
        f.write("GARBAGE LINE\n\n")
    bb.write_key(root, "k2", "v2")
    board = bb.read_board(root)
    assert "k" in board["keys"] and "k2" in board["keys"]


def test_no_snapshot_write_when_no_mutation_on_read(root):
    bb.write_key(root, "k", "v")
    snap = bb.board_paths(root)["snapshot"]
    mtime1 = os.path.getmtime(snap)
    bb.read_board(root)
    mtime2 = os.path.getmtime(snap)
    assert mtime1 == mtime2  # reads do not rewrite the snapshot


# --- atomicity & concurrency ---------------------------------------------------
def test_concurrent_writers_all_persist(root):
    def write_chunk(n):
        for i in range(5):
            bb.write_key(root, f"w{n}.k{i}", f"v{n}-{i}")
        return n

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(write_chunk, range(6)))
    board = bb.read_board(root)
    assert len(board["keys"]) == 30


def test_snapshot_never_left_truncated(root):
    # Simulate a crash by killing mid-write is hard in-process; instead verify
    # every path a partial writer could leave behind is cleaned or ignored.
    bb.write_key(root, "k", "v")
    paths = bb.board_paths(root)
    Path(paths["snapshot"] + ".tmp").write_text("junk", encoding="utf-8")
    board = bb.read_board(root)  # tmp ignored
    assert board["keys"]["k"]["value"] == "v"


# --- fail-open -----------------------------------------------------------------
def test_missing_dir_returns_empty_board(root):
    board = bb.read_board(os.path.join(root, "no", "such", "dir"))
    assert board["keys"] == {} and board["hot"] is None


def test_compact_context_on_empty_project(root):
    ctx = bb.compact_context(os.path.join(root, "never-created"))
    assert ctx["hot"] is None and ctx["tags"] == [] and ctx["key_count"] == 0


def test_stats_on_missing_project(root):
    s = bb.stats(os.path.join(root, "never-created"))
    assert s["events"] == 0 and s["keys"] == 0


# --- unicode -------------------------------------------------------------------
def test_unicode_roundtrip(root):
    bb.write_key(root, "prd.ürün", "AMAÇ: Türkçe karakterler ✓ 中文")
    bb.add_contribution(root, "yazar", "taslak yazdı — karar: ✓")
    board = bb.read_board(root)
    assert board["keys"]["prd.ürün"]["value"].startswith("AMAÇ")
    assert board["contributions"][0]["what"].endswith("✓")


# --- CLI integration -----------------------------------------------------------
def _run_cli(root, *args):
    import subprocess
    return subprocess.run(
        [sys.executable, str(CLI), *args, "--project-root", root],
        capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def test_cli_full_lifecycle(tmp_path):
    r = _run_cli(str(tmp_path), "write", "--key", "prd.x", "--value", "V",
                 "--type", "state", "--hot")
    assert json.loads(r.stdout)["ok"] is True
    r = _run_cli(str(tmp_path), "tag", "--tag", "t")
    assert json.loads(r.stdout)["ok"] is True
    r = _run_cli(str(tmp_path), "contribute", "--who", "skill", "--what", "did")
    assert json.loads(r.stdout)["ok"] is True
    r = _run_cli(str(tmp_path), "read", "--context")
    ctx = json.loads(r.stdout)
    assert ctx["hot"] == "prd.x" and ctx["tags"] == ["t"] and ctx["key_count"] == 1
    r = _run_cli(str(tmp_path), "read", "--key", "prd.x")
    assert json.loads(r.stdout)["value"] == "V"
    r = _run_cli(str(tmp_path), "hot", "--clear")
    assert json.loads(r.stdout)["hot"] is None
    r = _run_cli(str(tmp_path), "untag", "--tag", "t")
    assert json.loads(r.stdout)["ok"] is True
    r = _run_cli(str(tmp_path), "stats")
    assert json.loads(r.stdout)["keys"] == 1


def test_cli_read_missing_key_ok(tmp_path):
    r = _run_cli(str(tmp_path), "read", "--key", "absent.key")
    out = json.loads(r.stdout)
    assert out["ok"] is True and out["value"] is None
    assert r.returncode == 0


def test_cli_empty_project_exit_zero(tmp_path):
    r = _run_cli(str(tmp_path), "read", "--context")
    assert r.returncode == 0
    assert json.loads(r.stdout)["hot"] is None


def test_cli_write_then_write_hot_dirty_notice(tmp_path):
    _run_cli(str(tmp_path), "write", "--key", "a", "--value", "1", "--hot")
    r = _run_cli(str(tmp_path), "write", "--key", "a", "--value", "2")
    assert "dirty_notice" in json.loads(r.stdout)


def test_cli_hot_requires_key_or_clear(tmp_path):
    r = _run_cli(str(tmp_path), "hot")
    assert r.returncode == 1
    assert json.loads(r.stdout)["ok"] is False


# --- engine integration ---------------------------------------------------------
def _engine(tmp_monkeypatch, root):
    """Import engine modules with the project root pinned."""
    import importlib
    tmp_monkeypatch.setenv("CLAUDE_PROJECT_DIR", root)
    audit_mod = importlib.import_module("modules.audit")
    stop_mod = importlib.import_module("modules.stop")
    config_mod = importlib.import_module("modules.config")
    return audit_mod, stop_mod, config_mod


def test_session_start_injects_board_context(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.write_key(str(tmp_path), "prd.acme", "v1", hot=True)
    bb.add_tag(str(tmp_path), "crm")
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    ctx = out["additionalContext"]
    assert "Blackboard:" in ctx
    assert "prd.acme" in ctx and "crm" in ctx
    board = bb.read_board(str(tmp_path))
    assert "session_start" in board["watchers"]


def test_session_start_empty_board_no_blackboard_section(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    assert "Blackboard:" not in out["additionalContext"]
    board = bb.read_board(str(tmp_path))
    assert "session_start" in board["watchers"]  # watcher stamped anyway


def test_audit_stamps_last_tool_key(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    audit_mod.audit({"cwd": str(tmp_path), "hook_event_name": "PostToolUse",
                     "tool_name": "Write",
                     "tool_input": {"file_path": "docs/a.md", "content": "x"}})
    board = bb.read_board(str(tmp_path))
    assert board["keys"]["last_tool.file_editor"]["type"] == "tool"
    assert board["keys"]["last_tool.file_editor"]["value"] == "docs/a.md"


def test_audit_stamp_gated_off(tmp_path, monkeypatch):
    audit_mod, _, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "blackboard_enabled", lambda: False)
    audit_mod.audit({"cwd": str(tmp_path), "hook_event_name": "PostToolUse",
                     "tool_name": "Write",
                     "tool_input": {"file_path": "docs/a.md", "content": "x"}})
    board = bb.read_board(str(tmp_path))
    assert "last_tool.file_editor" not in board["keys"]


def test_stop_deny_carries_hot_key_notice(tmp_path, monkeypatch):
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    # seed: in-progress story (fresh sprint-status) + hot board key
    sprint = tmp_path / "bmad-output" / "implementation-artifacts"
    sprint.mkdir(parents=True)
    (sprint / "sprint-status.yaml").write_text(
        "stories:\n  1-1-alpha: in-progress\n", encoding="utf-8")
    bb.write_key(str(tmp_path), "story.1-1-alpha", "wip", hot=True)
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "deny"
    assert "story.1-1-alpha" in out["reason"]  # board notice attached


def test_stop_allow_has_no_board_notice(tmp_path, monkeypatch):
    audit_mod, stop_mod, _ = _engine(monkeypatch, str(tmp_path))
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "allow"


def test_engine_smoke_no_memlog_regression(tmp_path, monkeypatch):
    """The removed systems stay removed under the new integration."""
    audit_mod, stop_mod, _ = _engine(monkeypatch, str(tmp_path))
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    assert "memlog" not in out["additionalContext"].lower()
    assert "intent" not in out and "scope" not in out
