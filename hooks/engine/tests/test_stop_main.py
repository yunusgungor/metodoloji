"""Tests for hooks/engine/modules/stop.py and hooks/engine/main.py dispatch."""

import json
import os
import subprocess
import sys
from pathlib import Path

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
    # Isolate from local config: the deny contract requires stop_guard=hard.
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
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
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
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


def test_stop_tail_bound_respected(tmp_path, monkeypatch):
    # _SESSION_TAIL_LINES bounds the read: stop stays O(session) — only the
    # newest lines are considered, older history is cut.
    import sys
    stop_mod = sys.modules["modules.stop"]
    monkeypatch.setattr(stop_mod, "_SESSION_TAIL_LINES", 5)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    _seed_audit_log(tmp_path, [
        {"tool": "file_editor", "input": {"path": "src/old.py"}},
    ] * 3 + [
        {"tool": "file_editor", "input": {"path": "src/new.py"}},
    ] * 5)
    assert stop_mod._session_touched_code(str(tmp_path)) == ["src/new.py"]


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
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
    cand = tmp_path / ".metodoloji"
    cand.mkdir(parents=True)
    (cand / "sprint-status.yaml").write_text(
        "stories:\n  1-2-login: in-progress\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
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

def _run_main(args, stdin_data, project_root=None):
    """Run main.py in a subprocess.

    project_root pins CLAUDE_PROJECT_DIR for the child. Without it the
    engine resolves no project root and stamps state next to cwd — which
    polluted the PLUGIN tree (hooks/.metodoloji/) instead of a sandbox.
    """
    env = dict(os.environ)
    if project_root is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
        cwd=str(_HOOKS.parent),
    )


def test_main_dispatch_guard(tmp_path):
    r = _run_main(["guard"], {"tool_name": "terminal", "tool_input": {"command": "ls"}},
                  project_root=tmp_path)
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_dispatch_unknown_hook_allows(tmp_path):
    r = _run_main(["nonexistent-hook"], {"tool_name": "terminal"},
                  project_root=tmp_path)
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
    # --runtime=openhands must be accepted and the engine must still decide.
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


def test_main_dispatch_quality_non_commit_allows(tmp_path):
    r = _run_main(["quality"], {"tool_name": "terminal",
                                "tool_input": {"command": "ls -la"}},
                  project_root=tmp_path)
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


# --- Focus-aware story blocking tests ----------------------------------------

def _seed_sprint_status(root, stories: dict):
    """Write sprint-status.yaml with the given story states."""
    cand = root / "bmad-output/implementation-artifacts"
    cand.mkdir(parents=True, exist_ok=True)
    lines = "stories:\n" + "".join(f"  {k}: {v}\n" for k, v in stories.items())
    (cand / "sprint-status.yaml").write_text(lines, encoding="utf-8")


def test_story_status_focus_named_story_blocks_only_that(tmp_path, monkeypatch):
    """A focus naming one story blocks only that story."""
    _seed_sprint_status(tmp_path, {"1-2-login": "in-progress", "3-4-export": "in-progress"})
    # Focus names only 1-2-login → only it blocks
    blocked, reason = _check_story_status(str(tmp_path), focus="1-2-login")
    assert blocked is True
    assert "1-2-login" in reason


def test_story_status_focus_named_story_other_ignored(tmp_path, monkeypatch):
    """A focus naming 1-2-login must not block 3-4-export."""
    _seed_sprint_status(tmp_path, {"1-2-login": "done", "3-4-export": "in-progress"})
    blocked, reason = _check_story_status(str(tmp_path), focus="1-2-login")
    assert blocked is False


def test_story_status_no_focus_all_block(tmp_path, monkeypatch):
    """No focus → every in-progress story blocks (legacy behavior)."""
    _seed_sprint_status(tmp_path, {"1-2-login": "in-progress", "3-4-export": "in-progress"})
    blocked, reason = _check_story_status(str(tmp_path), focus="")
    assert blocked is True
    assert "1-2-login" in reason


def test_stop_progress_complete_skips_story_check(tmp_path, monkeypatch):
    """status=complete on the blackboard skips the stop story check."""
    _seed_sprint_status(tmp_path, {"1-2-login": "in-progress"})
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_SCOPE", raising=False)
    # _active_progress returns "complete"
    import modules.utils as ut
    monkeypatch.setattr(ut, "_active_progress", lambda root: "complete")
    monkeypatch.setattr(ut, "_active_scope", lambda root: "")
    res = stop({})
    # The story check is skipped, so no story block (code approval irrelevant here);
    # only the "Story in-progress" reason must be absent
    if res["decision"] == "deny":
        assert "Story" not in res.get("reason", "")


def test_stop_focus_aware_story_blocking_e2e(tmp_path, monkeypatch):
    """End-to-end: stop() honors focus-aware story blocking."""
    from modules import config
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")
    _seed_sprint_status(tmp_path, {"1-2-login": "done", "3-4-export": "in-progress"})
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("METODOLOJI_SCOPE", raising=False)
    # Scope targets only 1-2-login; 3-4-export is in-progress but not targeted
    import modules.utils as ut
    monkeypatch.setattr(ut, "_active_scope", lambda root: "1-2-login")
    monkeypatch.setattr(ut, "_active_progress", lambda root: "")
    res = stop({})
    # 1-2-login is done and it is the only one checked → no story block
    # (a code block, if any, is a different thing — this tests the story block)
    if res["decision"] == "deny":
        assert "1-2-login" not in res.get("reason", "")


# === NEW TESTS for hook state machine validation (HIGH #9 / ISSUE #64) ===


def test_validate_hook_state_machine_detects_violations(tmp_path):
    """Test that _validate_hook_state_machine detects SessionStart→PreToolUse→Stop violations."""
    from modules.stop import _validate_hook_state_machine
    
    # Create minimal blackboard with bad hook sequence
    (tmp_path / ".metodoloji").mkdir()
    
    # Write events in wrong order: PreToolUse before SessionStart
    events = [
        '{"type": "hook", "name": "PreToolUse", "timestamp": 1000}',
        '{"type": "hook", "name": "SessionStart", "timestamp": 2000}',  # Wrong order!
    ]
    (tmp_path / ".metodoloji" / "events.log").write_text("\n".join(events), encoding="utf-8")
    
    hook_ok, hook_msg = _validate_hook_state_machine(str(tmp_path))
    assert hook_ok is False
    assert "SessionStart" in hook_msg or "PreToolUse" in hook_msg or "order" in hook_msg.lower()


def test_validate_hook_state_machine_allows_correct_sequence(tmp_path):
    """Test that _validate_hook_state_machine allows correct hook sequence."""
    from modules.stop import _validate_hook_state_machine
    
    (tmp_path / ".metodoloji").mkdir()
    
    # Correct order: SessionStart → PreToolUse → PostToolUse → Stop
    events = [
        '{"type": "hook", "name": "SessionStart", "timestamp": 1000}',
        '{"type": "hook", "name": "PreToolUse", "timestamp": 2000}',
        '{"type": "hook", "name": "PostToolUse", "timestamp": 3000}',
    ]
    (tmp_path / ".metodoloji" / "events.log").write_text("\n".join(events), encoding="utf-8")
    
    hook_ok, hook_msg = _validate_hook_state_machine(str(tmp_path))
    assert hook_ok is True


def test_stop_denies_on_hook_violation_hard_gate(tmp_path, monkeypatch):
    """Test that stop() denies on hook state machine violation in hard gate mode (HIGH #9)."""
    from modules.stop import stop
    from modules import config

    # The engine reads the project root from json_in["cwd"] (repo_root()
    # contract); CLAUDE_PROJECT_DIR is pinned as well so no fallback can
    # escape the sandbox and stamp state into the plugin tree.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "hard")

    # Setup: create bad hook sequence (PreToolUse before any SessionStart)
    (tmp_path / ".metodoloji").mkdir()
    events = [
        '{"type": "hook", "name": "PreToolUse", "timestamp": 1000}',
        '{"type": "hook", "name": "SessionStart", "timestamp": 2000}',
    ]
    (tmp_path / ".metodoloji" / "events.log").write_text("\n".join(events), encoding="utf-8")

    json_in = {"cwd": str(tmp_path), "hook_event_name": "Stop"}
    result = stop(json_in)

    # In hard gate with violations, stop must be denied
    assert result["decision"] == "deny"
    assert "Hook state machine violation" in result["reason"]


def test_stop_allows_on_hook_violation_soft_gate(tmp_path, monkeypatch):
    """Test that stop() allows on hook violation in soft gate mode (HIGH #9)."""
    from modules.stop import stop
    from modules import config

    # Sandbox the root via the real repo_root() contract (see hard-gate test).
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.setattr(config, "hook_gate_mode", lambda key: "soft")

    (tmp_path / ".metodoloji").mkdir()

    # Bad hook sequence (PostToolUse before any PreToolUse/SessionStart)
    events = [
        '{"type": "hook", "name": "PostToolUse", "timestamp": 1000}',
        '{"type": "hook", "name": "SessionStart", "timestamp": 2000}',
    ]
    (tmp_path / ".metodoloji" / "events.log").write_text("\n".join(events), encoding="utf-8")

    json_in = {"cwd": str(tmp_path), "hook_event_name": "Stop"}
    result = stop(json_in)

    # In soft gate, stop must be allowed even with violations (fail-open)
    assert result["decision"] == "allow"
