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


def test_stamp_tool_event_survives_snapshot_rebuild(tmp_path, monkeypatch):
    # Event-sourced: last_tool.* returns from replay and survives a deleted
    # snapshot (regression guard for the old snapshot-only fold).
    import importlib.util, sys as _sys
    _engine(monkeypatch, str(tmp_path))
    bb.stamp_tool_event(str(tmp_path), "file_editor", "docs/a.md")
    board = bb.read_board(str(tmp_path))
    assert board["keys"]["last_tool.file_editor"]["value"] == "docs/a.md"
    os.remove(bb.board_paths(str(tmp_path))["snapshot"])  # force rebuild
    board2 = bb.read_board(str(tmp_path))
    assert board2["keys"]["last_tool.file_editor"]["value"] == "docs/a.md"


def test_stamp_tool_event_no_tool_ok(tmp_path):
    out = bb.stamp_tool_event(str(tmp_path), "", "x")
    assert out["ok"] is True


def test_watch_matches_normalizes_rel_abs(tmp_path):
    assert bb._watch_matches("docs/", "docs/a.md") is True
    assert bb._watch_matches("docs", "docs/a.md") is True
    assert bb._watch_matches("docs/", "skills/x.md") is False
    assert bb._watch_matches("./docs/", "docs/a.md") is True
    assert bb._watch_matches("docs/", "docs\\a.md") is True  # backslash equalized


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


# ==============================================================================
# v2 — lists
# ==============================================================================
def test_list_add_creates_and_appends(root):
    assert bb.list_add(root, "todos", "first")["count"] == 1
    ack = bb.list_add(root, "todos", "second")
    assert ack["count"] == 2
    board = bb.read_board(root)
    assert board["keys"]["todos"]["value"] == ["first", "second"]
    assert board["keys"]["todos"]["type"] == "list"


def test_list_remove_by_item_and_index(root):
    for it in ("a", "b", "c"):
        bb.list_add(root, "L", it)
    assert bb.list_remove(root, "L", item="b")["count"] == 2
    assert bb.list_remove(root, "L", index=0)["count"] == 1
    assert bb.read_board(root)["keys"]["L"]["value"] == ["c"]


def test_list_remove_missing_ok(root):
    bb.list_add(root, "L", "a")
    assert bb.list_remove(root, "L", item="zz")["removed"] == 0
    assert bb.list_remove(root, "absent", item="a")["ok"] is True


def test_list_remove_requires_selector(root):
    assert bb.list_remove(root, "L")["ok"] is False


def test_list_items_capped(root):
    for i in range(bb.MAX_LIST_ITEMS + 5):
        bb.list_add(root, "L", f"i{i:03d}")
    val = bb.read_board(root)["keys"]["L"]["value"]
    assert len(val) == bb.MAX_LIST_ITEMS
    assert val[0] == "i005"  # oldest expired


def test_list_empty_key_or_item_rejected(root):
    assert bb.list_add(root, " ", "x")["ok"] is False
    assert bb.list_add(root, "k", " ")["ok"] is False


def test_list_clear_empties_and_keeps_key(root):
    for it in ("a", "b", "c"):
        bb.list_add(root, "L", it)
    ack = bb.list_clear(root, "L")
    assert ack == {"ok": True, "key": "L", "cleared": 3}
    board = bb.read_board(root)
    assert board["keys"]["L"]["value"] == []
    assert board["keys"]["L"]["type"] == "list"


def test_list_clear_reusable_after(root):
    bb.list_add(root, "L", "a")
    bb.list_clear(root, "L")
    assert bb.list_add(root, "L", "b")["count"] == 1


def test_list_clear_missing_or_text_key_ok(root):
    assert bb.list_clear(root, "absent")["cleared"] == 0
    bb.write_key(root, "t", "text")
    assert bb.list_clear(root, "t")["cleared"] == 0  # text key untouched


def test_list_clear_survives_rebuild(root):
    bb.list_add(root, "L", "a")
    bb.list_clear(root, "L")
    os.remove(bb.board_paths(root)["snapshot"])
    assert bb.read_board(root)["keys"]["L"]["value"] == []


def test_cli_list_clear(tmp_path):
    _run_cli(str(tmp_path), "list-add", "--key", "t", "--item", "x")
    r = _run_cli(str(tmp_path), "list-clear", "--key", "t")
    assert json.loads(r.stdout)["cleared"] == 1
    r = _run_cli(str(tmp_path), "read", "--key", "t")
    assert json.loads(r.stdout)["value"] == []


def test_write_over_list_key_replaces_with_text(root):
    bb.list_add(root, "k", "a")
    bb.write_key(root, "k", "text now")
    board = bb.read_board(root)
    assert board["keys"]["k"]["value"] == "text now"


def test_list_survives_snapshot_rebuild(root):
    bb.list_add(root, "L", "one")
    bb.list_add(root, "L", "two")
    os.remove(bb.board_paths(root)["snapshot"])
    board = bb.read_board(root)
    assert board["keys"]["L"]["value"] == ["one", "two"]


def test_cli_list_roundtrip(tmp_path):
    _run_cli(str(tmp_path), "list-add", "--key", "t", "--item", "x1")
    _run_cli(str(tmp_path), "list-add", "--key", "t", "--item", "x2")
    r = _run_cli(str(tmp_path), "list-remove", "--key", "t", "--index", "0")
    assert json.loads(r.stdout)["count"] == 1
    r = _run_cli(str(tmp_path), "read", "--key", "t")
    assert json.loads(r.stdout)["value"] == ["x2"]


# ==============================================================================
# v2 — canvases (dynamic surfaces)
# ==============================================================================
def test_canvas_create_free_and_grid(root):
    a = bb.canvas_create(root, "free-one")
    assert a["ok"] and a["grid"] is None
    b = bb.canvas_create(root, "grid-one", grid="8x4")
    assert b["grid"] == [8, 4]
    assert set(bb.read_board(root)["canvases"]) == {"free-one", "grid-one"}


def test_canvas_create_duplicate_is_idempotent(root):
    bb.canvas_create(root, "c")
    ack = bb.canvas_create(root, "c", grid="3x3")
    assert ack["existed"] is True
    assert len(bb.read_board(root)["canvases"]) == 1


def test_canvas_set_and_read(root):
    bb.canvas_create(root, "map")
    ack = bb.canvas_set(root, "map", "A1", "nucleus", kind="decision", x=0, y=0)
    assert ack["cells"] == 1
    cv = bb.read_canvas(root, "map")
    cell = cv["cells"]["A1"]
    assert cell["content"] == "nucleus" and cell["kind"] == "decision"
    assert cell["x"] == 0 and cell["y"] == 0


def test_canvas_set_missing_canvas_is_noop(root):
    assert bb.canvas_set(root, "ghost", "A1", "x")["ok"] is True
    assert bb.read_board(root)["canvases"] == {}


def test_canvas_requires_name_and_cell(root):
    assert bb.canvas_set(root, "", "A1", "x")["ok"] is False
    assert bb.canvas_set(root, "c", "", "x")["ok"] is False


def test_canvas_cell_cap_expires_oldest(root):
    bb.canvas_create(root, "c")
    for i in range(bb.MAX_CELLS + 5):
        bb.canvas_set(root, "c", f"cell{i:04d}", str(i))
    cells = bb.read_canvas(root, "c")["cells"]
    assert len(cells) == bb.MAX_CELLS
    assert "cell0000" not in cells  # oldest expired


def test_canvas_auto_cells_capped_separately(root):
    bb.canvas_create(root, "c")
    for i in range(bb.MAX_AUTO_CELLS + 5):
        bb.canvas_touch(root, "c", f"docs/f{i}.md", content="auto")
    cv = bb.read_canvas(root, "c")
    autos = [c for c, v in cv["cells"].items() if v["kind"] == "auto"]
    assert len(autos) == bb.MAX_AUTO_CELLS


def test_canvas_remove_move_resize_clear(root):
    bb.canvas_create(root, "c")
    bb.canvas_set(root, "c", "A", "1")
    assert bb.canvas_remove(root, "c", "A")["ok"]
    assert "A" not in bb.read_canvas(root, "c")["cells"]
    bb.canvas_set(root, "c", "A", "1")
    m = bb.canvas_move(root, "c", "A", "B")
    assert m["moved"] is True
    cv = bb.read_canvas(root, "c")["cells"]
    assert "A" not in cv and cv["B"]["content"] == "1"
    assert bb.canvas_resize(root, "c", "10x10")["grid"] == [10, 10]
    assert bb.canvas_clear(root, "c")["cleared"] == 1
    assert bb.read_canvas(root, "c")["cells"] == {}


def test_canvas_focus_and_dangling_never_surfaces(root):
    bb.canvas_create(root, "c")
    assert bb.canvas_focus(root, "c")["hot_canvas"] == "c"
    assert bb.read_board(root)["hot_canvas"] == "c"
    bb.canvas_focus(root, None)
    assert bb.read_board(root)["hot_canvas"] is None
    # dangling: focus an unknown canvas → read clears it
    bb.canvas_focus(root, "ghost")
    assert bb.read_board(root)["hot_canvas"] is None


def test_canvas_focus_requires_name_or_clear(root):
    r = _run_cli(str(root), "canvas", "focus")  # no --name, no --clear
    assert r.returncode == 1


def test_canvas_watch_registers_and_unregisters(root):
    bb.canvas_create(root, "c")
    ack = bb.canvas_watch(root, "c", "docs/")
    assert ack["watch"] == ["docs/"]
    ack = bb.canvas_watch(root, "c", "skills/")
    assert ack["watch"] == ["docs/", "skills/"]
    ack = bb.canvas_watch(root, "c", "docs/", remove=True)
    assert ack["watch"] == ["skills/"]


def test_canvas_watch_requires_path(root):
    assert bb.canvas_watch(root, "c", " ")["ok"] is False


def test_watch_touch_lands_auto_cells(root):
    bb.canvas_create(root, "c")
    bb.canvas_watch(root, "c", "docs/")
    out = bb.watch_touch(root, "file_editor", "docs/a.md")
    assert out["touched"] == 1 and out["canvases"] == ["c"]
    cell = bb.read_canvas(root, "c")["cells"]["docs/a.md"]
    assert cell["kind"] == "auto" and "a.md" in cell["content"]
    # outside prefix → no touch
    assert bb.watch_touch(root, "file_editor", "skills/x/SKILL.md")["touched"] == 0


def test_watch_touch_empty_board_ok(root):
    out = bb.watch_touch(root, "bash", "anything.txt")
    assert out["ok"] and out["touched"] == 0


def test_canvas_survives_snapshot_rebuild(root):
    bb.canvas_create(root, "c", grid="4x4")
    bb.canvas_set(root, "c", "A1", "payload")
    bb.canvas_watch(root, "c", "docs/")
    os.remove(bb.board_paths(root)["snapshot"])
    cv = bb.read_canvas(root, "c")
    assert cv["grid"] == [4, 4]
    assert cv["cells"]["A1"]["content"] == "payload"
    assert cv["watch"] == ["docs/"]


def test_canvas_concurrent_sets_all_persist(root):
    bb.canvas_create(root, "c")

    def set_chunk(n):
        for i in range(5):
            bb.canvas_set(root, "c", f"w{n}.c{i}", f"v{n}-{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(set_chunk, range(6)))
    cells = bb.read_canvas(root, "c")["cells"]
    assert len(cells) == 30  # nothing lost under concurrent mutation


def test_canvases_cap_evicts_oldest_not_focused(root):
    for i in range(bb.MAX_CANVASES):
        bb.canvas_create(root, f"c{i:02d}")
        bb.canvas_set(root, f"c{i:02d}", "tick", str(i))
    bb.canvas_focus(root, "c00")  # protect the focused one
    bb.canvas_create(root, "new-one")
    names = set(bb.read_board(root)["canvases"])
    assert len(names) <= bb.MAX_CANVASES
    assert "c00" in names  # focused survivor
    assert "new-one" in names


def test_cli_canvas_lifecycle(tmp_path):
    _run_cli(str(tmp_path), "canvas", "create", "--name", "m", "--grid", "4x4")
    _run_cli(str(tmp_path), "canvas", "set", "--name", "m", "--cell", "A1",
             "--content", "core", "--kind", "decision")
    _run_cli(str(tmp_path), "canvas", "watch", "--name", "m", "--path", "docs/")
    r = _run_cli(str(tmp_path), "canvas-read", "--name", "m")
    cv = json.loads(r.stdout)
    assert cv["grid"] == [4, 4] and cv["cells"]["A1"]["content"] == "core"
    assert cv["watch"] == ["docs/"]
    r = _run_cli(str(tmp_path), "canvas", "move", "--name", "m", "--cell", "A1", "--to", "B2")
    assert json.loads(r.stdout)["moved"] is True
    _run_cli(str(tmp_path), "canvas", "focus", "--name", "m")
    r = _run_cli(str(tmp_path), "read", "--context")
    ctx = json.loads(r.stdout)
    assert ctx["hot_canvas"]["name"] == "m"
    _run_cli(str(tmp_path), "canvas", "focus", "--clear")
    r = _run_cli(str(tmp_path), "stats")
    s = json.loads(r.stdout)
    assert s["canvases"] == 1 and s["cells"] == 1


# ==============================================================================
# v2 — graph links
# ==============================================================================
def test_link_and_neighbors_both_directions(root):
    assert bb.link(root, "prd.x", "arch.y", relation="informs")["ok"]
    out = bb.neighbors(root, "prd.x")
    assert out == [{"node": "arch.y", "relation": "informs", "direction": "out"}]
    out = bb.neighbors(root, "arch.y")
    assert out == [{"node": "prd.x", "relation": "informs", "direction": "in"}]


def test_link_duplicate_ignored(root):
    bb.link(root, "a", "b")
    bb.link(root, "a", "b")
    assert len(bb.read_board(root)["links"]) == 1


def test_link_self_rejected(root):
    assert bb.link(root, "a", "a")["ok"] is False
    assert bb.link(root, "", "b")["ok"] is False


def test_unlink_specific_relation_or_all(root):
    bb.link(root, "a", "b", relation="r1")
    bb.link(root, "a", "b", relation="r2")
    ack = bb.unlink(root, "a", "b", relation="r1")
    assert ack["removed"] == 1
    ack = bb.unlink(root, "a", "b")
    assert ack["removed"] == 1
    assert bb.read_board(root)["links"] == []


def test_neighbors_relation_filter(root):
    bb.link(root, "a", "b", "x")
    bb.link(root, "a", "c", "y")
    out = bb.neighbors(root, "a", relation="y")
    assert [n["node"] for n in out] == ["c"]


def test_links_capped(root):
    for i in range(bb.MAX_LINKS + 5):
        bb.link(root, f"k{i:04d}", f"j{i:04d}")
    assert len(bb.read_board(root)["links"]) == bb.MAX_LINKS


def test_links_survive_snapshot_rebuild(root):
    bb.link(root, "a", "b", "rel")
    os.remove(bb.board_paths(root)["snapshot"])
    assert bb.read_board(root)["links"][0]["relation"] == "rel"


def test_cli_link_roundtrip(tmp_path):
    _run_cli(str(tmp_path), "link", "--a", "p", "--b", "q", "--relation", "blocks")
    r = _run_cli(str(tmp_path), "neighbors", "--node", "p")
    out = json.loads(r.stdout)
    assert out["neighbors"][0]["node"] == "q"
    _run_cli(str(tmp_path), "unlink", "--a", "p", "--b", "q")
    r = _run_cli(str(tmp_path), "neighbors", "--node", "p")
    assert json.loads(r.stdout)["neighbors"] == []


# ==============================================================================
# v2 — subscriptions & alerts (proactive routing)
# ==============================================================================
def test_subscription_routes_matching_key_update(root):
    bb.subscribe(root, "watcher1", "prd.*", channel="stop")
    bb.write_key(root, "prd.acme", "v")
    alerts = bb.pending_alerts(root, "stop")
    assert len(alerts) == 1
    assert "prd.acme" in alerts[0]["text"]


def test_subscription_nonmatching_no_alert(root):
    bb.subscribe(root, "w", "prd.*", channel="stop")
    bb.write_key(root, "ux.flow", "v")
    assert bb.pending_alerts(root, "stop") == []


def test_alert_dedup_identical(root):
    bb.subscribe(root, "w", "prd.*")
    bb.write_key(root, "prd.x", "v1")
    bb.write_key(root, "prd.x", "v2")  # same channel+kind+text → dedup
    assert len(bb.pending_alerts(root, "session")) == 1


def test_unsubscribe_stops_routing(root):
    bb.subscribe(root, "w", "prd.*")
    bb.unsubscribe(root, "w", "prd.*")
    bb.write_key(root, "prd.x", "v")
    assert bb.pending_alerts(root) == []


def test_consume_clears_only_target_channel(root):
    bb.subscribe(root, "w", "prd.*", channel="stop")
    bb.subscribe(root, "w2", "prd.*", channel="deploy")
    bb.write_key(root, "prd.x", "v")
    take = bb.consume_alerts(root, "stop")
    assert len(take) == 1
    assert bb.pending_alerts(root, "deploy")  # untouched
    assert bb.pending_alerts(root, "stop") == []


def test_canvas_subscription_routes_canvas_alerts(root):
    bb.subscribe(root, "w", "canvas:*")
    bb.canvas_create(root, "map")
    bb.canvas_set(root, "map", "A1", "x")
    alerts = bb.pending_alerts(root, "session")
    assert any("canvas 'map'" in a["text"] for a in alerts)


def test_alerts_capped(root):
    for i in range(bb.MAX_ALERTS + 10):
        bb.post_alert(root, "session", "info", f"m{i:03d}")
    alerts = bb.pending_alerts(root, "session")
    assert len(alerts) == bb.MAX_ALERTS
    assert alerts[0]["text"] == "m010"  # oldest expired


def test_post_alert_requires_text(root):
    assert bb.post_alert(root, "session", "info", "  ")["ok"] is False


def test_alerts_survive_snapshot_rebuild(root):
    bb.post_alert(root, "stop", "warn", "pending risk")
    os.remove(bb.board_paths(root)["snapshot"])
    alerts = bb.pending_alerts(root, "stop")
    assert alerts[0]["text"] == "pending risk"


def test_cli_alert_flow(tmp_path):
    _run_cli(str(tmp_path), "notify", "--channel", "stop", "--kind", "risk",
             "--text", "danger ahead")
    r = _run_cli(str(tmp_path), "alerts", "--channel", "stop")
    assert "danger ahead" in r.stdout
    r = _run_cli(str(tmp_path), "consume", "--channel", "stop")
    out = json.loads(r.stdout)
    assert out["alerts"][0]["text"] == "danger ahead"
    r = _run_cli(str(tmp_path), "alerts")
    assert json.loads(r.stdout)["alerts"] == []


def test_cli_subscribe_roundtrip(tmp_path):
    r = _run_cli(str(tmp_path), "subscribe", "--watcher", "w", "--pattern", "prd.*")
    assert json.loads(r.stdout)["ok"] is True
    _run_cli(str(tmp_path), "write", "--key", "prd.z", "--value", "1")
    r = _run_cli(str(tmp_path), "alerts")
    assert "prd.z" in r.stdout
    _run_cli(str(tmp_path), "unsubscribe", "--watcher", "w", "--pattern", "prd.*")
    _run_cli(str(tmp_path), "consume", "--channel", "session")
    _run_cli(str(tmp_path), "write", "--key", "prd.z2", "--value", "1")
    r = _run_cli(str(tmp_path), "alerts")
    assert json.loads(r.stdout)["alerts"] == []


# ==============================================================================
# v2 — compact context & stats enrichment
# ==============================================================================
def test_compact_context_lists_preview_and_graph_counts(root):
    bb.write_key(root, "prd.x", "A" * 200, hot=True)
    bb.list_add(root, "L", "i")
    bb.canvas_create(root, "c")
    bb.canvas_set(root, "c", "A1", "x")
    bb.link(root, "prd.x", "arch.y")
    bb.subscribe(root, "w", "prd.*")
    ctx = bb.compact_context(root)
    assert ctx["hot_meta"]["preview"] == "A" * 120  # bounded preview
    assert ctx["canvas_count"] == 1 and ctx["links"] == 1
    assert ctx["subscriptions"] == 1 and ctx["neighbors"] == ["arch.y"]
    assert ctx["key_count"] == 2


def test_compact_context_hot_list_preview(root):
    bb.list_add(root, "L", "a")
    bb.set_hot(root, "L")
    ctx = bb.compact_context(root)
    assert ctx["hot_meta"]["preview"] == "list[1]"


def test_compact_context_hot_canvas_summary(root):
    bb.canvas_create(root, "m", grid="2x2", focus=True)
    bb.canvas_set(root, "m", "A1", "x")
    bb.canvas_watch(root, "m", "docs/")
    bb.watch_touch(root, "file_editor", "docs/z.md")
    ctx = bb.compact_context(root)
    hc = ctx["hot_canvas"]
    assert hc["name"] == "m" and hc["cells"] == 2 and hc["auto"] == 1
    assert hc["grid"] == [2, 2] and hc["watch"] == ["docs/"]


def test_stats_counts_lists_and_cells(root):
    bb.list_add(root, "L", "a")
    bb.canvas_create(root, "c")
    bb.canvas_set(root, "c", "A1", "x")
    bb.canvas_set(root, "c", "A2", "y")
    s = bb.stats(root)
    assert s["lists"] == 1 and s["canvases"] == 1 and s["cells"] == 2
    assert s["hot_canvas"] is None


# ==============================================================================
# v2 — engine arms: proactive session injection, real-time touch, stop alerts
# ==============================================================================
def test_session_start_delivers_session_alerts(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_alert(str(tmp_path), "session", "risk", "deadline slipping")
    bb.post_alert(str(tmp_path), "session", "info", "second one")
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    ctx = out["additionalContext"]
    assert "[risk] deadline slipping" in ctx
    assert "second one" in ctx
    # delivered-once: a second start sees no alert section
    out2 = audit_mod.session_start({"cwd": str(tmp_path)})
    assert "[risk]" not in out2["additionalContext"]


def test_session_start_surfaces_hot_canvas(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.canvas_create(str(tmp_path), "live-map", grid="4x4", focus=True)
    bb.canvas_set(str(tmp_path), "live-map", "A1", "hub")
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    assert "canvas 'live-map' live (1 cells" in out["additionalContext"]


def test_audit_watch_touch_feeds_watching_canvas(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.canvas_create(str(tmp_path), "doc-map")
    bb.canvas_watch(str(tmp_path), "doc-map", "docs/")
    audit_mod.audit({"cwd": str(tmp_path), "hook_event_name": "PostToolUse",
                     "tool_name": "Write",
                     "tool_input": {"file_path": "docs/new-page.md", "content": "x"}})
    cell = bb.read_canvas(str(tmp_path), "doc-map")["cells"]["docs/new-page.md"]
    assert cell["kind"] == "auto" and "new-page.md" in cell["content"]


def test_stop_deny_reports_canvas_and_stop_alerts(tmp_path, monkeypatch):
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    sprint = tmp_path / "bmad-output" / "implementation-artifacts"
    sprint.mkdir(parents=True)
    (sprint / "sprint-status.yaml").write_text(
        "stories:\n  1-1-alpha: in-progress\n", encoding="utf-8")
    bb.canvas_create(str(tmp_path), "wip-map", focus=True)
    bb.post_alert(str(tmp_path), "stop", "risk", "unresolved conflict")
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "deny"
    assert "wip-map" in out["reason"]
    assert "unresolved conflict" in out["reason"]
    # deliver-once: alerts consumed
    assert bb.pending_alerts(str(tmp_path), "stop") == []


def _seed_block_story(tmp_path):
    """Seed an in-progress story that makes stop deny (hard gate)."""
    sprint = tmp_path / "bmad-output" / "implementation-artifacts"
    sprint.mkdir(parents=True, exist_ok=True)
    (sprint / "sprint-status.yaml").write_text(
        "stories:\n  1-1-alpha: in-progress\n", encoding="utf-8")


def test_stop_deny_carries_proactive_handoff_warning(tmp_path, monkeypatch):
    """A run closing with unclaimed handoffs is warned at stop — announce-only."""
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    _seed_block_story(tmp_path)
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "deny"
    assert "PROACTIVE — hand-off waiting: bmad-ux (1)" in out["reason"]
    assert "do not close the loop empty-handed" in out["reason"]
    assert "chain-health" in out["reason"]
    # announce-only: the signal still waits for its addressed skill
    assert len(bb.pending_handoffs(str(tmp_path), "bmad-ux")) == 1


def test_stop_allow_when_handoffs_all_claimed(tmp_path, monkeypatch):
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "allow"
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    bb.consume_alerts(str(tmp_path), "handoff.bmad-ux")  # shake completed
    out2 = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert "PROACTIVE" not in out2.get("reason", "")


def test_stop_handoff_warning_excludes_bmad_help(tmp_path, monkeypatch):
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    _seed_block_story(tmp_path)
    bb.post_handoff(str(tmp_path), "bmad-help", "anything", "n")
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert "PROACTIVE" not in out["reason"]  # help-only waiting never warns


def test_stop_handoff_warning_does_not_block_alone(tmp_path, monkeypatch):
    """The warning is a nudge, never a block: allow stays allow with it."""
    audit_mod, stop_mod, config_mod = _engine(monkeypatch, str(tmp_path))
    monkeypatch.setattr(config_mod, "hook_gate_mode", lambda key: "hard")
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "allow"  # nothing else to deny on
    assert out.get("reason") is None


def test_stop_allow_no_canvas_notice(tmp_path, monkeypatch):
    audit_mod, stop_mod, _ = _engine(monkeypatch, str(tmp_path))
    bb.canvas_create(str(tmp_path), "quiet")  # exists but not focused
    out = stop_mod.stop({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert out["decision"] == "allow"
    assert "wip-map" not in out.get("reason", "")


# ==============================================================================
# v2 — fail-open hardening
# ==============================================================================
def test_watch_touch_missing_project_ok(root):
    ghost = os.path.join(root, "never")
    assert bb.watch_touch(ghost, "t", "p")["ok"] is True


def test_read_canvas_missing_project_ok(root):
    cv = bb.read_canvas(os.path.join(root, "never"), "c")
    assert cv["exists"] is False and cv["cells"] == {}


def test_pending_alerts_missing_project_ok(root):
    assert bb.pending_alerts(os.path.join(root, "never")) == []


def test_consume_alerts_never_raises(root):
    # even when the board lock/mutation path fails, consumption is a list
    assert bb.consume_alerts(os.path.join(root, "never"), "x") == []


def test_unicode_in_lists_and_canvas_cells(root):
    bb.list_add(root, "L", "Türkçe ✓ 中文")
    bb.canvas_create(root, "harita")
    bb.canvas_set(root, "harita", "hücre-1", "AMAÇ: ✓")
    board = bb.read_board(root)
    assert board["keys"]["L"]["value"] == ["Türkçe ✓ 中文"]
    assert bb.read_canvas(root, "harita")["cells"]["hücre-1"]["content"] == "AMAÇ: ✓"


# ==============================================================================
# v2.1 — hand-off chain handshake (prd → ux → architecture)
# ==============================================================================
def test_handoff_routes_to_skill_channel(root):
    ack = bb.post_handoff(root, "bmad-ux", "prd.acme",
                          note="PRD final — see prd.md")
    assert ack["ok"] is True
    pending = bb.pending_handoffs(root, "bmad-ux")
    assert len(pending) == 1
    assert pending[0]["kind"] == "handoff"
    assert pending[0]["text"].startswith("prd.acme:")
    assert "PRD final" in pending[0]["text"]


def test_handoff_channels_isolated_per_skill(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    bb.post_handoff(root, "bmad-architecture", "ux.acme", "n2")
    assert bb.pending_handoffs(root, "bmad-architecture")[0]["text"].startswith("ux.acme")
    assert bb.pending_handoffs(root, "bmad-ux")[0]["text"].startswith("prd.acme")
    assert bb.pending_handoffs(root, "bmad-dev-story") == []


def test_handoff_waiting_counts_and_consume_once(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n2")
    bb.post_handoff(root, "bmad-architecture", "ux.acme", "n3")
    waiting = bb.pending_handoff_channels(root)
    assert waiting == {"bmad-ux": 2, "bmad-architecture": 1}
    take = bb.consume_alerts(root, "handoff.bmad-ux")
    assert len(take) == 2
    assert bb.pending_handoff_channels(root) == {"bmad-architecture": 1}


def test_handoff_requires_to_and_from_key(root):
    assert bb.post_handoff(root, "", "k", "n")["ok"] is False
    assert bb.post_handoff(root, "bmad-ux", " ", "n")["ok"] is False


def test_handoff_survives_rebuild_and_does_not_resurrect(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    os.remove(bb.board_paths(root)["snapshot"])
    assert len(bb.pending_handoffs(root, "bmad-ux")) == 1  # rebuild keeps it
    bb.consume_alerts(root, "handoff.bmad-ux")
    os.remove(bb.board_paths(root)["snapshot"])
    assert bb.pending_handoffs(root, "bmad-ux") == []  # consumption evented


def test_chain_prd_to_arch_full_handshake(root):
    """The full prd→ux→arch relay on one board."""
    # prd run closes → signals ux
    bb.post_handoff(root, "bmad-ux", "prd.acme", "PRD final")
    # ux run opens, sees the signal, consumes it (shake 1)
    assert bb.pending_handoff_channels(root) == {"bmad-ux": 1}
    bb.consume_alerts(root, "handoff.bmad-ux")
    assert bb.pending_handoff_channels(root) == {}
    # ux run closes → signals architecture
    bb.post_handoff(root, "bmad-architecture", "ux.acme", "UX final")
    # arch run opens, sees it, consumes (shake 2)
    assert bb.pending_handoffs(root, "bmad-architecture")[0]["text"].startswith("ux.acme")
    bb.consume_alerts(root, "handoff.bmad-architecture")
    assert bb.pending_handoff_channels(root) == {}


def test_session_start_announces_waiting_handoffs_without_consuming(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    ctx = out["additionalContext"]
    assert "hand-off waiting: bmad-ux (1)" in ctx
    # announce-only: the signal still waits for the skill itself
    assert len(bb.pending_handoffs(str(tmp_path), "bmad-ux")) == 1


def test_session_start_hides_bmad_help_handoffs(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_handoff(str(tmp_path), "bmad-help", "anything", "n")
    out = audit_mod.session_start({"cwd": str(tmp_path)})
    assert "hand-off waiting" not in out["additionalContext"]


def test_session_start_proactive_warning_when_waiting(tmp_path, monkeypatch):
    """total_waiting > 0 → the injection carries an actionable warning."""
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    bb.post_handoff(str(tmp_path), "bmad-architecture", "ux.acme", "UX final")
    ctx = audit_mod.session_start({"cwd": str(tmp_path)})["additionalContext"]
    assert "PROACTIVE — hand-off waiting" in ctx
    assert "2 unclaimed signal(s)" in ctx
    assert "nobody picked up the baton" in ctx
    assert "chain-health" in ctx          # diagnose path
    assert "handoffs --skill" in ctx       # claim path


def test_session_start_no_proactive_warning_when_clear(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_handoff(str(tmp_path), "bmad-ux", "prd.acme", "PRD final")
    bb.consume_alerts(str(tmp_path), "handoff.bmad-ux")  # handshake completed
    ctx = audit_mod.session_start({"cwd": str(tmp_path)})["additionalContext"]
    assert "PROACTIVE" not in ctx
    assert "hand-off waiting" not in ctx


def test_session_start_proactive_warning_counts_exclude_bmad_help(tmp_path, monkeypatch):
    audit_mod, _, _ = _engine(monkeypatch, str(tmp_path))
    bb.post_handoff(str(tmp_path), "bmad-help", "anything", "n")
    ctx = audit_mod.session_start({"cwd": str(tmp_path)})["additionalContext"]
    assert "PROACTIVE" not in ctx  # help-only waiting never warns


def test_cli_handoff_roundtrip(tmp_path):
    r = _run_cli(str(tmp_path), "handoff", "--to", "bmad-ux",
                 "--from-key", "prd.acme", "--note", "PRD final")
    assert json.loads(r.stdout)["ok"] is True
    r = _run_cli(str(tmp_path), "handoffs")
    assert json.loads(r.stdout)["waiting"] == {"bmad-ux": 1}
    r = _run_cli(str(tmp_path), "handoffs", "--skill", "bmad-ux")
    assert "prd.acme" in r.stdout
    r = _run_cli(str(tmp_path), "consume", "--channel", "handoff.bmad-ux")
    assert len(json.loads(r.stdout)["alerts"]) == 1
    r = _run_cli(str(tmp_path), "handoffs")
    assert json.loads(r.stdout)["waiting"] == {}


def test_cli_handoff_requires_to_and_from_key(tmp_path):
    r = _run_cli(str(tmp_path), "handoff", "--to", "", "--from-key", "k")
    assert r.returncode == 1 and json.loads(r.stdout)["ok"] is False
    r = _run_cli(str(tmp_path), "handoff", "--to", "bmad-ux")  # missing --from-key
    assert r.returncode != 0  # argparse usage error (rc=2)
    assert not r.stdout.strip()  # no partial output


def test_chain_health_idle_when_no_signals(root):
    h = bb.chain_health(root)
    assert h["ok"] is True
    assert len(h["chain"]) == 6  # 7 skills -> 6 hops
    assert all(hop["waiting"] == 0 and hop["consumed"] == 0 and hop["status"] == "idle"
               for hop in h["chain"])
    assert h["extra"] == [] and h["total_waiting"] == 0


def test_chain_health_counts_waiting_and_consumed_per_hop(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    bb.consume_alerts(root, "handoff.bmad-ux")          # prd->ux consumed
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n2")
    bb.consume_alerts(root, "handoff.bmad-ux")
    bb.post_handoff(root, "bmad-ux", "prd.new", "n3")   # still waiting
    bb.post_handoff(root, "bmad-architecture", "ux.acme", "n4")  # ux->arch waiting
    h = bb.chain_health(root)
    hops = {(hop["from"], hop["to"]): hop for hop in h["chain"]}
    assert hops[("bmad-prd", "bmad-ux")]["consumed"] == 2
    assert hops[("bmad-prd", "bmad-ux")]["waiting"] == 1
    assert hops[("bmad-prd", "bmad-ux")]["status"] == "waiting"
    assert hops[("bmad-ux", "bmad-architecture")]["waiting"] == 1
    assert hops[("bmad-architecture", "bmad-spec")]["status"] == "idle"
    assert h["total_waiting"] == 2


def test_chain_health_clear_status_all_consumed(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    bb.consume_alerts(root, "handoff.bmad-ux")
    h = bb.chain_health(root)
    assert h["chain"][0]["status"] == "clear"
    assert h["chain"][0]["waiting"] == 0 and h["chain"][0]["consumed"] == 1
    assert h["total_waiting"] == 0


def test_chain_health_surfaces_unknown_receivers_as_extra(root):
    bb.post_handoff(root, "some-future-skill", "ux.acme", "n1")
    h = bb.chain_health(root)
    assert h["chain"][0]["waiting"] == 0  # ux->arch hop untouched
    assert len(h["extra"]) == 1
    assert h["extra"][0] == {"from": "bmad-ux", "to": "some-future-skill",
                             "waiting": 1, "consumed": 0, "status": "waiting"}
    assert h["total_waiting"] == 1


def test_chain_health_consumption_is_not_double_counted(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n1")
    bb.consume_alerts(root, "handoff.bmad-ux")
    bb.consume_alerts(root, "handoff.bmad-ux")  # second consume of empty channel
    h = bb.chain_health(root)
    assert h["chain"][0]["consumed"] == 1  # not 2


def test_cli_chain_health(tmp_path):
    r = _run_cli(str(tmp_path), "chain-health")
    h = json.loads(r.stdout)
    assert h["ok"] is True and len(h["chain"]) == 6
    _run_cli(str(tmp_path), "handoff", "--to", "bmad-ux",
             "--from-key", "prd.acme", "--note", "n")
    r = _run_cli(str(tmp_path), "chain-health")
    h = json.loads(r.stdout)
    assert h["chain"][0]["waiting"] == 1 and h["total_waiting"] == 1


# ==============================================================================
# v2.2 — doctor (one-glance diagnostic)
# ==============================================================================
def test_doctor_healthy_on_empty_board(root):
    d = bb.doctor(root)
    assert d["ok"] is True and d["verdict"] == "HEALTHY"
    assert d["warnings"] == []
    c = d["checks"]
    assert c["gate"]["on"] is True or c["gate"]["known"] is False
    assert c["snapshot"]["exists"] is False
    assert c["events"]["exists"] is False
    assert c["drift"]["in_sync"] is True
    assert c["chain"]["total_waiting"] == 0


def test_doctor_healthy_on_lived_in_board(root):
    bb.write_key(root, "prd.acme", "v", hot=True)
    bb.canvas_create(root, "m", grid="8x8", focus=True)
    bb.canvas_set(root, "m", "A1", "x")
    bb.list_add(root, "prd.acme.pending", "t")
    bb.link(root, "prd.acme", "arch.acme")
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n")
    bb.consume_alerts(root, "handoff.bmad-ux")  # complete the shake
    d = bb.doctor(root)
    assert d["verdict"] == "HEALTHY"
    assert d["checks"]["focus"]["hot"] == "prd.acme"
    assert d["checks"]["focus"]["hot_canvas"] == "m"
    assert d["checks"]["drift"]["in_sync"] is True


def test_doctor_warns_on_cap_pressure(root):
    for i in range(bb.MAX_KEYS):
        bb.write_key(root, f"k{i:03d}", "x")
    d = bb.doctor(root)
    assert d["verdict"] == "NEEDS ATTENTION"
    assert any("keys 128/128" in w for w in d["warnings"])


def test_doctor_warns_on_tmp_residue(root):
    bb.write_key(root, "k", "v")
    open(bb.board_paths(root)["snapshot"] + ".1.2.tmp", "w").write("junk")
    open(bb.board_paths(root)["events"] + ".3.4.tmp", "w").write("junk")
    d = bb.doctor(root)
    assert d["verdict"] == "NEEDS ATTENTION"
    assert any("2 leftover .tmp" in w for w in d["warnings"])


def test_doctor_warns_on_unclaimed_handoffs(root):
    bb.post_handoff(root, "bmad-ux", "prd.acme", "n")
    d = bb.doctor(root)
    assert d["verdict"] == "NEEDS ATTENTION"
    assert any("unclaimed hand-off" in w and "PROACTIVE" in w
               for w in d["warnings"])


def test_doctor_detects_snapshot_drift(root):
    bb.write_key(root, "k", "v")
    # tamper with the snapshot behind the event log's back
    paths = bb.board_paths(root)
    with open(paths["snapshot"], encoding="utf-8") as f:
        data = json.load(f)
    data["keys"]["ghost"] = {"value": "x", "type": "note", "updated": 1.0}
    with open(paths["snapshot"], "w", encoding="utf-8") as f:
        json.dump(data, f)
    d = bb.doctor(root)
    assert d["checks"]["drift"]["in_sync"] is False
    assert d["verdict"] == "NEEDS ATTENTION"
    assert any("drift" in w and "rebuild" in w for w in d["warnings"])


def test_no_blackboard_set_command_in_source(root):
    """There is NO `blackboard.py set` command — the verb is `write`. A `set`
    in doc/comment/skill text makes the LLM emit an invalid command."""
    import pathlib
    repo = pathlib.Path(__file__).resolve().parent.parent.parent.parent
    self_file = pathlib.Path(__file__).resolve()
    offenders = []
    for pat in ("hooks/engine/**/*.py", "skills/**/*.md", "docs/*.md"):
        for p in pathlib.Path(repo).glob(pat):
            if p.resolve() == self_file:
                continue  # this guard text, not a real usage
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if "blackboard.py set " in line or "blackboard.py set --" in line:
                    offenders.append(f"{p.relative_to(repo)}:{i}: {line.strip()}")
    assert not offenders, "blackboard.py set komutu yok, write kullan:\n" + "\n".join(offenders)


def test_doctor_ignores_tool_stamped_keys_in_drift(root):
    """last_tool.* keys are folded from `tool` events and carry type "tool" —
    drift norm excludes them, so a tool stamp never reads as drift."""
    bb.write_key(root, "k", "v")
    paths = bb.board_paths(root)
    with open(paths["snapshot"], encoding="utf-8") as f:
        data = json.load(f)
    data["keys"]["last_tool.file_editor"] = {
        "value": "docs/a.md", "type": "tool", "updated": 1.0}
    with open(paths["snapshot"], "w", encoding="utf-8") as f:
        json.dump(data, f)
    d = bb.doctor(root)
    assert d["checks"]["drift"]["in_sync"] is True


def test_doctor_counts_garbage_event_lines(root):
    bb.write_key(root, "k", "v")
    with open(bb.board_paths(root)["events"], "a", encoding="utf-8") as f:
        f.write("GARBAGE\n")
    d = bb.doctor(root)
    assert d["checks"]["events"]["garbage"] == 1
    assert d["checks"]["events"]["status"] == "warn"
    assert d["verdict"] == "NEEDS ATTENTION"


def test_doctor_reports_watch_paths(root):
    bb.canvas_create(root, "m")
    bb.canvas_watch(root, "m", "docs/")
    d = bb.doctor(root)
    w = d["checks"]["watch"]["paths"]
    assert w == [{"canvas": "m", "path": "docs/", "exists": os.path.exists("docs/")}]


def test_cli_doctor_panel_and_json(tmp_path):
    _run_cli(str(tmp_path), "write", "--key", "k", "--value", "v", "--hot")
    r = _run_cli(str(tmp_path), "doctor")
    assert "blackboard doctor" in r.stdout
    assert "verdict: HEALTHY" in r.stdout
    assert "focus     hot: k" in r.stdout
    r = _run_cli(str(tmp_path), "doctor", "--json")
    j = json.loads(r.stdout)
    assert j["ok"] is True and j["checks"]["snapshot"]["version"] == 2


def test_v1_snapshot_upgrade_keeps_data(root):
    """A v1 snapshot (no graph sections) loads cleanly and gains defaults."""
    bb.write_key(root, "old", "data")
    paths = bb.board_paths(root)
    with open(paths["snapshot"], encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = 1
    for k in ("links", "canvases", "subscriptions", "alerts"):
        data.pop(k, None)
    with open(paths["snapshot"], "w", encoding="utf-8") as f:
        json.dump(data, f)
    board = bb.read_board(root)
    assert board["keys"]["old"]["value"] == "data"
    assert board["links"] == [] and board["canvases"] == {}
