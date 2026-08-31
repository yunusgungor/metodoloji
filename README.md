# metodoloji (OpenHands plugin)

The OpenHands SDK plugin implementation of the BMAD methodology: 125 skills + 74 bridge
TOMLs + mechanical gates (guard/stop/quality/deploy) + record chain
(E → IR → SP → S → QR → PR).

## What it does

| Part | Function |
|---|---|
| `skills/` | 122 BMAD skills (native body) |
| `custom/` | 74 bridge TOMLs (`activation_steps_append` links native outputs to methodology records) + `config.toml` (soft/hard) |
| `hooks/` | PreToolUse/PostToolUse/Stop/SessionStart hooks; modular engine structure |
| `hooks/engine/` | Python engine: `main.py` (entry point), `modules/` (guard, audit, stop, utils, config) |
| `bmad/` | legacy `_bmad/` module data (bmm, cis, gds, wds, tea, core, bmb) |
| `templates/` | IR/SP/QR/PR/S/E/README/tech-debt record templates |
| `commands/` | `/metodoloji:init`, `/metodoloji:gate-setup`, `/metodoloji:verify`, `/metodoloji:audit` |

## Installation

```python
from openhands.sdk.plugin import Plugin
p = Plugin.load("github:yunusgungor/metodoloji", repo_path="openhands/metodoloji")
```

or local: `Plugin.load("<repo>/openhands/metodoloji")`.

On the first session: `/metodoloji:init` (installs templates) and `/metodoloji:gate-setup`
(generates `~/.bmad/gate-key` — machine-local, not committed).

## Path variables

- `{project-root}` — target project root (`$OPENHANDS_PROJECT_DIR`) — methodology outputs go here
- `{metodoloji-root}` — this plugin's root (install root `~/.openhands/plugins/installed/metodoloji`) — read-only source

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
sh commands/check-plugin.sh            # full audit (§0–§6 + §2b + §5b + §5c + drift)
sh commands/check-plugin.sh --negtest  # negative test: BREAK bridge → catch → restore
sh commands/check-custom.sh            # custom/ static quality audit only (§0–§6)
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
| **quality** | PreToolUse | terminal | — | `git commit` with done stories lacking IR/QR/SP → DENY (fail-closed) |
| **deploy** | PreToolUse | terminal | — | Deploy command + missing IR/QR/SP/PR → DENY (fail-closed) |
| **stop** | Stop | — | — | Incomplete story/unapproved code → DENY (fail-closed) |
| **audit** | PostToolUse | file_editor, terminal | — | Logs every call (fail-open) |

The `quality_gate`/`deploy_guard` values (`"soft"` default | `"hard"`) under
`custom/config.toml [hooks]` are now enforced at hook level: guard/stop mechanically
block low-quality commits/deploys.

## Status

The installation/path layer is merged; the live flow (first E→IR→SP→S→QR production in
a real LLM session) is not proven, so it cannot be called "fully merged". Closing gate:
Phase 8.
