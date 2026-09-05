"""Tests for hooks/engine/modules/stop.py and hooks/engine/main.py dispatch."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HOOKS))

from modules.stop import _check_story_status, stop  # noqa: E402

MAIN_PY = _HOOKS / "main.py"


# --- _check_story_status ----------------------------------------------------

def test_story_status_no_sprint_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    blocked, reason = _check_story_status(str(tmp_path))
    assert blocked is False and reason == ""


def test_story_status_in_progress_blocks(tmp_path, monkeypatch):
    cand = tmp_path / "bmad-output/implementation-artifacts"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  1-2-login: in-progress\n  3-4-export: done\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    blocked, reason = _check_story_status(str(tmp_path))
    assert blocked is True
    assert "1-2-login" in reason


def test_story_status_all_done_allows(tmp_path, monkeypatch):
    cand = tmp_path / "_bmad-output/implementation-artifacts"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  1-2-login: done\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    blocked, reason = _check_story_status(str(tmp_path))
    assert blocked is False


def test_story_status_metodoloji_fallback(tmp_path, monkeypatch):
    cand = tmp_path / ".metodoloji"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  5-6-auth: in-progress\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    blocked, reason = _check_story_status(str(tmp_path))
    assert blocked is True


# --- intent-aware story status ---------------------------------------------

def test_story_status_intent_target_in_progress_blocks():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cand = root / "bmad-output/implementation-artifacts"
        cand.mkdir(parents=True)
        (cand / "sprint-status.yaml").write_text(
            "stories:\n  1-2-login: in-progress\n  3-4-export: done\n",
            encoding="utf-8")
        blocked, reason = _check_story_status(str(root), intent="finish 1-2-login")
        assert blocked is True
        assert "1-2-login" in reason


def test_story_status_intent_target_done_allows():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cand = root / "bmad-output/implementation-artifacts"
        cand.mkdir(parents=True)
        (cand / "sprint-status.yaml").write_text(
            "stories:\n  1-2-login: in-progress\n  3-4-export: done\n",
            encoding="utf-8")
        blocked, _ = _check_story_status(str(root), intent="finish 3-4-export")
        assert blocked is False


def test_story_status_intent_unrelated_story_allows():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cand = root / "bmad-output/implementation-artifacts"
        cand.mkdir(parents=True)
        (cand / "sprint-status.yaml").write_text(
            "stories:\n  1-2-login: in-progress\n", encoding="utf-8")
        blocked, _ = _check_story_status(str(root), intent="finish 9-9-other")
        assert blocked is False


def test_story_status_no_intent_blocks_all():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cand = root / "bmad-output/implementation-artifacts"
        cand.mkdir(parents=True)
        (cand / "sprint-status.yaml").write_text(
            "stories:\n  1-2-login: in-progress\n", encoding="utf-8")
        blocked, reason = _check_story_status(str(root), intent="")
        assert blocked is True
        assert "1-2-login" in reason


# --- stop() -----------------------------------------------------------------

def test_stop_allows_clean_tree(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_allows_free_zone_code(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "explore.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_denies_unapproved_code(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "deny"
    assert "Unapproved code changes" in res["reason"]


def test_stop_skips_non_code_dirs(tmp_path, monkeypatch):
    for d in ("docs", "templates", "commands", "bmad", ".metodoloji"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "docs/notes.py").write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "allow"


# --- main() dispatch --------------------------------------------------------

def _run_main(args, stdin_data):
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        cwd=str(_HOOKS.parent),
    )


def test_main_dispatch_guard():
    r = _run_main(["guard"], {"tool_name": "terminal", "tool_input": {"command": "ls"}})
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_dispatch_unknown_hook_allows():
    r = _run_main(["nonexistent-hook"], {"tool_name": "terminal"})
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_dispatch_bad_stdin_allows():
    r = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        input="not-json",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        cwd=str(_HOOKS.parent),
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_dispatch_runtime_flag(tmp_path, monkeypatch):
    # --runtime=openhands should set METODOLOJI_RUNTIME (visible to config.RUNTIME).
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(MAIN_PY), "--runtime=openhands", "guard"],
        input=json.dumps({"tool_name": "terminal", "tool_input": {"command": "ls"}}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env=env,
        cwd=str(_HOOKS.parent),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_dispatch_quality_non_commit_allows(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    r = _run_main(["quality"], {"tool_name": "terminal",
                                "tool_input": {"command": "ls -la"}})
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
