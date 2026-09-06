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


def _seed_audit_log(root, records):
    import json
    log = root / ".metodoloji/logs/hook-audit.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_stop_allows_free_zone_code(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "explore.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "scratch/explore.py"}},
    ])
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_denies_unapproved_code(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/main.py"}},
    ])
    res = stop({})
    assert res["decision"] == "deny"
    assert "Unapproved code changes" in res["reason"]


def _seed_session_start(root):
    import json, time
    from modules.stop import _SESSION_MARKER_TYPE
    log = root / ".metodoloji/logs/hook-audit.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": _SESSION_MARKER_TYPE,
                            "timestamp": time.time()}) + "\n")


def test_stop_hook_active_allows(tmp_path, monkeypatch):
    # stop_hook_active=true (Claude re-fire after a deny) must never deny —
    # the loop breaker, even with unapproved touched code on disk.
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/main.py"}},
    ])
    res = stop({"stop_hook_active": True})
    assert res["decision"] == "allow"


def test_stop_deny_budget_allows_second_fire(tmp_path, monkeypatch):
    # First deny records stop_deny; the second fire (same session) allows.
    from modules.stop import _stop_denies_so_far
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/main.py"}},
    ])
    first = stop({})
    assert first["decision"] == "deny"
    assert _stop_denies_so_far(str(tmp_path)) == 1
    second = stop({})
    assert second["decision"] == "allow"


def test_stop_soft_guard_allows(tmp_path, monkeypatch):
    # stop_guard=soft (brownfield adoption) never blocks the session close.
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode",
                        lambda key: "soft" if key == "stop_guard" else "hard")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/main.py"}},
    ])
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_previous_session_touches_ignored(tmp_path, monkeypatch):
    # Touches before the session_start marker don't count: yesterday's
    # unapproved work must not wedge today's session.
    import time
    from modules.stop import _SESSION_MARKER_TYPE
    import json
    (tmp_path / "src").mkdir()
    (tmp_path / "src/old.py").write_text("x=1\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/old.py"}},
    ])
    log = tmp_path / ".metodoloji/logs/hook-audit.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": _SESSION_MARKER_TYPE,
                            "timestamp": time.time()}) + "\n")
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_stale_sprint_status_ignored(tmp_path, monkeypatch):
    # sprint-status older than the session marker never blocks (brownfield
    # leftover); without a marker, legacy blocking stays.
    import os, time
    cand = tmp_path / ".metodoloji"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  1-2-login: in-progress\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(cand / "sprint-status.yaml", (old, old))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    _seed_session_start(tmp_path)  # marker newer than the stale status
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_ignores_shell_variable_targets(tmp_path, monkeypatch):
    # Regression (live find): a heredoc rewrite command containing
    # "$spool_file" must not produce a literal "$spool_file" touched entry.
    from modules.stop import _session_touched_code
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "terminal", "input": {"command": "cat > $spool_file << 'EOF'\nx\nEOF"}},
        {"tool": "file_editor", "input": {"path": "$out/main.py"}},
    ])
    assert _session_touched_code(str(tmp_path)) == []


def test_stop_stale_sprint_status_blocks_without_marker(tmp_path, monkeypatch):
    # No session marker (old bootstrap) → legacy behavior preserved.
    cand = tmp_path / ".metodoloji"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  1-2-login: in-progress\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_INTENT", raising=False)
    res = stop({})
    assert res["decision"] == "deny"


def test_stop_allows_preexisting_brownfield_code(tmp_path, monkeypatch):
    # Regression: files that exist on disk but were NOT touched this session
    # (no audit-log record) must not block stop.
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "prisma.config.ts").write_text("export default {}\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "allow"


def test_stop_skips_non_code_dirs(tmp_path, monkeypatch):
    for d in ("docs", "templates", "commands", "bmad", ".metodoloji"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "docs/notes.py").write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    res = stop({})
    assert res["decision"] == "allow"


# --- main() dispatch --------------------------------------------------------
# ponytail: subprocess dispatch tests live here (engine entry contract),
# not in a new file — one place for "main.py speaks the hook schema".

def test_main_bad_stdin_stop_blocks(tmp_path):
    import subprocess
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["HOOK_TYPE"] = "stop"
    r = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        input="not-json",
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=env, cwd=str(_HOOKS.parent),
    )
    out = json.loads(r.stdout)
    assert out["decision"] == "block"


def test_main_bad_stdin_guard_denies(tmp_path):
    import subprocess
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["HOOK_TYPE"] = "guard"
    r = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        input="not-json",
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=env, cwd=str(_HOOKS.parent),
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_session_start_returns_context(tmp_path):
    import subprocess
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(MAIN_PY), "session_start"],
        input=json.dumps({}),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=env, cwd=str(_HOOKS.parent),
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "METODOLOJI" in out["hookSpecificOutput"].get("additionalContext", "")

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
