#!/usr/bin/env python3
"""sync-hooks-json.py — single source of truth for the hooks.json dispatch locator.

hooks/hooks.json embeds one plugin-root locator loop per hook command because
neither runtime injects a guaranteed plugin-root env var into hook commands.
Those commands were historically copy-pasted by hand (six copies that could
drift silently). THIS script is now the single source: the locator candidates
below are the ONLY place an install path is edited, and `--write` regenerates
every hook command in hooks/hooks.json from them.

    python3 scripts/sync-hooks-json.py --write   # regenerate hooks/hooks.json
    python3 scripts/sync-hooks-json.py --check   # verify hooks.json is in sync (CI)

Usage: python3 sync-hooks-json.py (--write|--check) [hooks.json]

The candidate list is cross-checked against hooks/scripts/run-hook.sh by
scripts/check-plugin.sh §1b — run-hook.sh remains the authoritative DISCOVERY
logic (two-phase, glob-newest-first), while this file owns the DISPATCH list
that has to be reachable from static JSON.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# --- Canonical dispatch locators (SINGLE SOURCE OF TRUTH) ---------------------
# Tokens are the shell candidate roots the hook command loop searches, in the
# exact order hooks.json must embed them. Edit here, then run --write.
_CANDIDATES = (
    '"$CLAUDE_PLUGIN_ROOT"',
    '"$METODOLOJI_PLUGIN_ROOT"',
    '"."',
    '"$PWD"',
    '"/workspace"',
    '"/workspace/metodoloji"',
    '"$HOME/.claude/plugins/cache/yunusgungor/metodoloji/"*',
    '"$HOME/.openhands/plugins/installed/metodoloji"',
)

# Hook name -> whether the command forwards the runtime tool name as "$1".
# bootstrap needs no tool name; every PreToolUse/PostToolUse/Stop hook forwards
# the tool name it was fired for (unused by hook-entry.sh, kept for parity).
_HOOKS = {
    "bootstrap": False,
    "guard": True,
    "quality": True,
    "deploy": True,
    "audit": True,
    "stop": True,
}

_HOOK_RE = re.compile(r'run-hook\.sh"\s+([a-z_]+)')

_DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "hooks" / "hooks.json"


def hook_command(hook: str) -> str:
    """Build the canonical hook command for `hook` from _CANDIDATES."""
    if hook not in _HOOKS:
        raise ValueError(f"unknown hook {hook!r} (expected one of {sorted(_HOOKS)})")
    arg = ' "$1"' if _HOOKS[hook] else ""
    return (
        "sh -c 'for d in "
        + " ".join(_CANDIDATES)
        + '; do [ -f "$d/hooks/scripts/run-hook.sh" ] && exec sh '
        + '"$d/hooks/scripts/run-hook.sh" '
        + hook
        + arg
        + "; done; exit 0'"
    )


def _walk_command_nodes(obj):
    """Yield every dict node that carries a hook "command" string."""
    if isinstance(obj, dict):
        if "command" in obj:
            yield obj
        for v in obj.values():
            yield from _walk_command_nodes(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_command_nodes(v)


def _expected(node: dict) -> tuple[str, str] | None:
    """Return (hook, canonical command) for a command node, or None when the
    node isn't a run-hook.sh dispatch command. A dispatch-shaped command whose
    hook name is unknown (hand-renamed) also reads as non-canonical — callers
    surface it as drift/missing instead of crashing."""
    m = _HOOK_RE.search(node["command"])
    if not m:
        return None
    hook = m.group(1)
    try:
        return hook, hook_command(hook)
    except ValueError:
        return None


def regenerate(manifest: Path) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    seen = set()
    for node in _walk_command_nodes(data):
        got = _expected(node)
        if got is None:
            print(f"  skip non-dispatch command: {node['command'][:60]!r}")
            continue
        hook, canonical = got
        node["command"] = canonical
        seen.add(hook)
    missing = set(_HOOKS) - seen
    if missing:
        print(f"  ERROR: dispatch commands for {sorted(missing)} not found in hooks.json")
        sys.exit(1)
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] hooks.json regenerated from canonical locator: {manifest}")


def check(manifest: Path) -> int:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    problems = 0
    seen = set()
    drifted = []
    for node in _walk_command_nodes(data):
        got = _expected(node)
        if got is None:
            continue
        hook, canonical = got
        seen.add(hook)
        if node["command"] != canonical:
            drifted.append(hook)
    if drifted:
        problems += 1
        print(f"  MISS: hook command(s) {sorted(drifted)} drifted from the canonical locator")
        print("        run: python3 scripts/sync-hooks-json.py --write")
    missing = set(_HOOKS) - seen
    if missing:
        problems += 1
        print(f"  MISS: dispatch commands for {sorted(missing)} missing from hooks.json")
    if not problems:
        print(f"[OK] hooks.json dispatch commands byte-identical to canonical locator ({len(seen)} hooks)")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate/verify hooks.json dispatch commands")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="rewrite hooks.json from the canonical locator")
    g.add_argument("--check", action="store_true", help="verify hooks.json matches the canonical locator")
    ap.add_argument("manifest", nargs="?", type=Path, default=_DEFAULT_MANIFEST,
                    help="path to hooks.json (default: alongside this script's repo)")
    args = ap.parse_args()

    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}")
        return 1
    if args.write:
        regenerate(args.manifest)
        return 0
    return check(args.manifest)


if __name__ == "__main__":
    sys.exit(main())
