"""Tests for scripts/sync-hooks-json.py — canonical hooks.json locator generator.

Covers the canonical command builder, byte-exact --check drift detection, and
--write regeneration (structure-preserving, idempotent). Loaded via importlib
so no subprocess is involved.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "sync-hooks-json.py"


def _load():
    spec = importlib.util.spec_from_file_location("sync_hooks_json", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()

HOOKS = ["bootstrap", "guard", "quality", "deploy", "audit", "stop"]


def _canonical():
    return {h: mod.hook_command(h) for h in HOOKS}


def _hook_entry(commands: dict, name: str, extra: dict | None = None) -> list:
    """One node carrying the named hook's command (skipped if absent).

    extra (e.g. {"timeout": 10} or {"async": True}) proves regenerate keeps
    non-command fields — passed as a dict because `async` is a keyword."""
    if name not in commands:
        return []
    node = {"type": "command", "command": commands[name]}
    node.update(extra or {})
    return [node]


def _write_manifest(path: Path, commands: dict) -> dict:
    """Write a hooks.json-shaped fixture; extra keys prove structure survives.

    A hook key missing from `commands` simply drops that node (used to test
    missing-dispatch-hook detection)."""
    pre = []
    if "guard" in commands:
        pre.append({"matcher": "Write|Edit|MultiEdit|file_editor|terminal",
                    "hooks": _hook_entry(commands, "guard", {"timeout": 10})})
    if "quality" in commands:
        pre.append({"matcher": "Bash|terminal",
                    "hooks": _hook_entry(commands, "quality", {"timeout": 10})})
    if "deploy" in commands:
        pre.append({"matcher": "Bash|terminal",
                    "hooks": _hook_entry(commands, "deploy", {"timeout": 10})})
    data = {
        "hooks": {
            "SessionStart": [{"hooks": _hook_entry(commands, "bootstrap",
                                                     {"timeout": 30})}],
            "PreToolUse": pre,
            "PostToolUse": [{"matcher": "Write|Edit|MultiEdit|Bash|file_editor|terminal",
                              "hooks": _hook_entry(commands, "audit",
                                                    {"timeout": 5, "async": True})}],
            "Stop": [{"hooks": _hook_entry(commands, "stop", {"timeout": 15})}],
        }
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


# --- hook_command (canonical builder) ----------------------------------------

def test_hook_command_all_hooks_built():
    for hook in HOOKS:
        cmd = mod.hook_command(hook)
        assert cmd.startswith("sh -c 'for d in ")
        assert cmd.endswith("; done; exit 0'")
        assert 'exec sh "$d/hooks/scripts/run-hook.sh" ' + hook in cmd


def test_hook_command_candidates_in_canonical_order():
    cmd = mod.hook_command("guard")
    joined = " ".join(mod._CANDIDATES)
    assert joined in cmd
    # Order matters: the first resolvable root wins at runtime.
    assert cmd.index('"$CLAUDE_PLUGIN_ROOT"') < cmd.index('"$METODOLOJI_PLUGIN_ROOT"')
    assert cmd.index('"$METODOLOJI_PLUGIN_ROOT"') < cmd.index('"/workspace"')


def test_hook_command_only_bootstrap_omits_tool_arg():
    for hook in ("guard", "quality", "deploy", "audit", "stop"):
        assert '"$1"' in mod.hook_command(hook)
    assert '"$1"' not in mod.hook_command("bootstrap")


def test_hook_command_unknown_hook_raises():
    with pytest.raises(ValueError):
        mod.hook_command("session_start")  # not a dispatched hook


# --- check (byte-exact drift detection) --------------------------------------

def test_check_passes_when_in_sync(tmp_path, capsys):
    m = _write_manifest(tmp_path / "hooks.json", _canonical())
    assert mod.check(tmp_path / "hooks.json") == 0
    out = capsys.readouterr().out
    assert "byte-identical" in out
    assert len(json.loads((tmp_path / "hooks.json").read_text())) > 0  # untouched


def test_check_catches_hand_edited_command(tmp_path, capsys):
    cmds = _canonical()
    cmds["guard"] = cmds["guard"].replace("$PWD", "$BOGUS_ROOT", 1)
    _write_manifest(tmp_path / "hooks.json", cmds)
    assert mod.check(tmp_path / "hooks.json") == 1
    out = capsys.readouterr().out
    assert "guard" in out and "drifted" in out


def test_check_catches_missing_dispatch_hook(tmp_path, capsys):
    cmds = _canonical()
    del cmds["stop"]
    _write_manifest(tmp_path / "hooks.json", cmds)
    assert mod.check(tmp_path / "hooks.json") == 1
    out = capsys.readouterr().out
    assert "missing from hooks.json" in out


def test_check_catches_renamed_hook_without_crashing(tmp_path, capsys):
    cmds = _canonical()
    cmds["garud"] = cmds.pop("guard")  # dispatch-shaped but unknown name
    _write_manifest(tmp_path / "hooks.json", cmds)
    assert mod.check(tmp_path / "hooks.json") == 1  # graceful, no traceback
    assert "guard" in capsys.readouterr().out


def test_check_reports_multiple_drifted_commands(tmp_path, capsys):
    cmds = _canonical()
    cmds["guard"] = cmds["guard"].replace("$PWD", "$A_ROOT", 1)
    cmds["stop"] = cmds["stop"].replace("$PWD", "$B_ROOT", 1)
    _write_manifest(tmp_path / "hooks.json", cmds)
    assert mod.check(tmp_path / "hooks.json") == 1
    out = capsys.readouterr().out
    assert "guard" in out and "stop" in out


# --- regenerate (--write) -----------------------------------------------------

def test_regenerate_repairs_drift(tmp_path):
    cmds = _canonical()
    cmds["audit"] = cmds["audit"].replace("$PWD", "$DRIFT_ROOT", 1)
    _write_manifest(tmp_path / "hooks.json", cmds)
    mod.regenerate(tmp_path / "hooks.json")
    data = json.loads((tmp_path / "hooks.json").read_text(encoding="utf-8"))
    # Every dispatch command is exactly one of the six canonical commands.
    commands = [n["command"] for n in _walk(data)]
    assert sorted(commands) == sorted(_canonical().values())
    assert mod.check(tmp_path / "hooks.json") == 0


def _walk(obj):
    if isinstance(obj, dict):
        if "command" in obj:
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_regenerate_preserves_structure(tmp_path):
    m = _write_manifest(tmp_path / "hooks.json", _canonical())
    mod.regenerate(tmp_path / "hooks.json")
    data = json.loads((tmp_path / "hooks.json").read_text(encoding="utf-8"))
    # Extra keys (matcher/timeout/async) and event grouping must survive.
    assert data["hooks"]["PostToolUse"][0]["matcher"].startswith("Write")
    assert data["hooks"]["PreToolUse"][1]["hooks"][0]["timeout"] == 10
    assert data["hooks"]["PostToolUse"][0]["hooks"][0]["async"] is True
    assert data["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] == 30
    assert list(data["hooks"].keys()) == ["SessionStart", "PreToolUse",
                                          "PostToolUse", "Stop"]


def test_regenerate_idempotent(tmp_path):
    path = tmp_path / "hooks.json"
    _write_manifest(path, _canonical())
    mod.regenerate(path)
    first = path.read_bytes()
    mod.regenerate(path)
    assert path.read_bytes() == first


# --- main() CLI wiring ---------------------------------------------------------

def test_main_check_ok(tmp_path, monkeypatch, capsys):
    _write_manifest(tmp_path / "hooks.json", _canonical())
    monkeypatch.setattr(sys, "argv", ["sync-hooks-json.py", "--check",
                                      str(tmp_path / "hooks.json")])
    assert mod.main() == 0
    assert "[OK]" in capsys.readouterr().out


def test_main_check_drift_returns_1(tmp_path, monkeypatch):
    cmds = _canonical()
    cmds["deploy"] = cmds["deploy"].replace('"/workspace"', '"/bogus"', 1)
    _write_manifest(tmp_path / "hooks.json", cmds)
    monkeypatch.setattr(sys, "argv", ["sync-hooks-json.py", "--check",
                                      str(tmp_path / "hooks.json")])
    assert mod.main() == 1


def test_main_write_then_check(tmp_path, monkeypatch, capsys):
    cmds = _canonical()
    cmds["quality"] = cmds["quality"].replace("$PWD", "$OLD_ROOT", 1)
    path = tmp_path / "hooks.json"
    _write_manifest(path, cmds)
    monkeypatch.setattr(sys, "argv", ["sync-hooks-json.py", "--write", str(path)])
    assert mod.main() == 0
    assert "[OK]" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["sync-hooks-json.py", "--check", str(path)])
    assert mod.main() == 0


def test_main_missing_manifest_returns_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sync-hooks-json.py", "--check",
                                      str(tmp_path / "nope.json")])
    assert mod.main() == 1
    assert "ERROR" in capsys.readouterr().out
