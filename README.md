# metodoloji — dual-plugin (OpenHands + Claude Code)

BMAD methodology: 123 skills + 120 bridge TOMLs + mechanical gates
(guard/stop/quality/deploy) + record chain (E → IR → SP → S → QR → PR).
Shared `hooks/engine/` core, runtime-specific manifest layers.

## What it does

| Part | Function |
|---|---|
| `skills/` | 123 BMAD skills (native body) |
| `custom/` | 120 bridge TOMLs (`activation_steps_append` links native outputs to methodology records) + `config.toml` (soft/hard) |
| `hooks/` | PreToolUse/PostToolUse/Stop/SessionStart hooks; modular engine structure |
| `hooks/engine/` | Python engine: `main.py` (entry point), `modules/` (guard, audit, stop, utils, config) |
| `bmad/` | legacy `_bmad/` module data (bmm, cis, gds, wds, tea, core, bmb) |
| `templates/` | IR/SP/QR/PR/S/E/README/tech-debt record templates |
| `commands/` | `/metodoloji:init`, `/metodoloji:gate-setup`, `/metodoloji:verify`, `/metodoloji:audit` |

## Installation — OpenHands

```python
from openhands.sdk.plugin import Plugin
p = Plugin.load("github:yunusgungor/metodoloji", repo_path="openhands/metodoloji")
```

or local: `Plugin.load("<repo>/openhands/metodoloji")`.

On the first session: `/metodoloji:init` (installs templates) and `/metodoloji:gate-setup`
(generates `~/.bmad/gate-key` — machine-local, not committed).

## Installation — Claude Code

**Plugin marketplace** (ships a manifest at `.claude-plugin/marketplace.json`):
```
/plugin marketplace add https://github.com/yunusgungor/metodoloji
/plugin install metodoloji@metodoloji
```

The manifest sets `defaultEnabled: false` (fail-closed guard hooks are opt-in) — after
installing, enable the plugin explicitly:
```
claude plugin enable metodoloji
```

**Manual install** — clone the repo and reference in `.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/bootstrap.sh" }] }],
    "PreToolUse": [
      { "matcher": "Write|Edit|MultiEdit", "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/hook-entry.sh guard claude" }] },
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/hook-entry.sh quality claude" }] },
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/hook-entry.sh deploy claude" }] }
    ],
    "PostToolUse": [{ "matcher": "Write|Edit|MultiEdit|Bash", "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/hook-entry.sh audit claude", "async": true }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "sh /path/to/metodoloji/hooks/scripts/hook-entry.sh stop claude" }] }]
  }
}
```

On the first session: `/metodoloji:init` and `/metodoloji:gate-setup`.

## Hook tool mapping

The shared engine normalizes both runtimes to a common schema:

| Hook | OpenHands tool | Claude Code tool | Engine mode |
|------|---------------|-----------------|-------------|
| **guard** | `file_editor` | `Write`, `Edit`, `MultiEdit` | `guard` |
| **quality** | `terminal` (git commit) | `Bash` (git commit) | `quality` |
| **deploy** | `terminal` (deploy cmd) | `Bash` (deploy cmd) | `deploy` |
| **audit** | `file_editor`, `terminal` | `Write`, `Edit`, `MultiEdit`, `Bash` | `audit` |
| **stop** | — | — | `stop` |

Runtime is selected by `hook-entry.sh` via: `RUNTIME=${2:-${METODOLOJI_RUNTIME:-openhands}}`.
The engine reads `METODOLOJI_RUNTIME` env and `normalize_hook_input()` in `utils.py`
maps Claude tool names (`Write`→`file_editor`, `Bash`→`terminal`) transparently.

## Path variables

- `{project-root}` — target project root (`$OPENHANDS_PROJECT_DIR` or `$CLAUDE_PROJECT_DIR`) — methodology outputs go here
- `{metodoloji-root}` — this plugin's root (OpenHands: `~/.openhands/plugins/installed/metodoloji`, Claude Code: `${CLAUDE_PLUGIN_ROOT}` or repo clone path) — read-only source

**Rule:** All methodology outputs (records, bmad-output, artifacts) are created under `{project-root}` — never `{metodoloji-root}`.

## Modular Engine Structure

```
hooks/engine/
├── main.py              # Main entry point
├── modules/
│   ├── __init__.py      # Module exports
│   ├── config.py        # Constant configuration
│   ├── utils.py         # Helper functions
│   ├── archive.py       # Archive handling (tar/zip)
│   ├── bash_targets.py  # Bash command target detection
│   ├── guard.py         # PreToolUse logic
│   ├── audit.py         # PostToolUse audit trail
│   └── stop.py          # Stop logic
└── resolve_customization.py  # Skill TOML deep_merge bridge resolver
```

## Health check

```sh
sh scripts/check-plugin.sh            # full audit (§0–§6 + §2b + §5b + §5c + drift)
sh scripts/check-plugin.sh --negtest  # negative test: BREAK bridge → catch → restore
sh scripts/check-custom.sh            # custom/ static quality audit only (§0–§6)
```

## Source of truth and drift

The hook engine's canonical copy is this repo's `hooks/engine/` tree (modular engine:
`main.py` + `modules/`). The installed plugin copy must match the repo — `check-plugin.sh`
§5 audits integrity. Changes are always made in the repo; the installed plugin is updated
with `git pull` (the old single-file `bmad-hooks.py` is removed; do not reference it).

## Hard gate

In the OpenHands runtime the audit chain runs from **five** hook points (hooks.json):

| Hook | Mode | Matcher | Threshold | Behavior |
|------|-----|---------|----------|----------|
| **guard** | PreToolUse | file_editor, terminal | — | Code writing without an approved experiment → DENY (fail-closed) |
| **quality** | PreToolUse | terminal | — | `git commit` with done stories lacking IR/QR/SP → DENY when hard |
| **deploy** | PreToolUse | terminal | — | Deploy command + missing IR/QR/SP/PR → DENY when hard |
| **stop** | Stop | — | — | Incomplete story/unapproved code → DENY (fail-closed) |
| **audit** | PostToolUse | file_editor, terminal | — | Logs every call (fail-open) |

The `quality_gate`/`deploy_guard` values (`"soft"` default | `"hard"`) under
`custom/config.toml [hooks]` are enforced at hook level. In `"soft"` (default) the
commit/deploy gates warn (allow + `methodology_warnings`) instead of blocking;
`"hard"` turns them into mechanical DENY. guard/stop always fail-closed.

## Status

The installation/path layer is merged. The full E→IR→SP→S→QR chain has been
**produced mechanically** — E-005 went through the mechanical gate (measured
0.98, APPROVED, `--verify` → VERIFIED) and IR-001/SP-001/S-001/QR-001 were
generated from the record templates and pass `check-plugin.sh` §3/§6. What
remains unproven is the same chain produced live by a real LLM session invoking
those BRIDGE steps end to end; that live-session production is the closing gate
and is not yet merged.
