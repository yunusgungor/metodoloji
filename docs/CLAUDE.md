# metodoloji — BMAD Methodology Plugin

Claude Code plugin for BMAD methodology enforcement.

## What this does

- **Record chain**: E → IR → SP → S → QR → PR (experiment → implementation record → sprint plan → story → quality review → product record)
- **Mechanical gates**: guard (write/edit blocking), quality (bash validation), deploy (deployment checks), audit (post-write trail), stop (session-end validation)
- **123 skills** with **120 bridge TOMLs** linking native outputs to methodology records

## Hooks

All hooks run via `hooks/scripts/hook-entry.sh` which dispatches to the Python engine at `hooks/engine/main.py`.

Claude Code reads the hook config from `hooks/hooks.json` (auto-discovered). The OpenHands
runtime uses the same engine via `hooks/hooks.openhands.json` (referenced from `.plugin/plugin.json`).

| Hook | Matcher | Policy | Timeout |
|------|---------|--------|---------|
| SessionStart | — | fail-open (context injection) | 30s |
| PreToolUse guard | Write\|Edit\|MultiEdit | fail-closed | 10s |
| PreToolUse quality | Bash | fail-open | 10s |
| PreToolUse deploy | Bash | fail-open | 10s |
| PostToolUse audit | Write\|Edit\|MultiEdit\|Bash | fail-open (async) | 5s |
| Stop | — | fail-closed | 15s |

## Commands

- `/metodoloji:init` — install templates into workspace
- `/metodoloji:gate-setup` — generate `~/.bmad/gate-key` (machine-local, not committed)
- `/metodoloji:verify` — verify experiment approval chain
- `/metodoloji:audit` — run full audit trail check

## Installation (Claude Code)

The plugin ships a marketplace manifest at `.claude-plugin/marketplace.json` and a
`defaultEnabled: false` manifest flag: the fail-closed guard hooks are opt-in.

```sh
/plugin marketplace add ./      # or the GitHub repo URL
/plugin install metodoloji@metodoloji
claude plugin enable metodoloji # defaultEnabled: false → enable explicitly
```

On the first session: `/metodoloji:init` and `/metodoloji:gate-setup`.

## Requirements

- Python 3.6+ (python3, python, or py on Windows)
- Git Bash or POSIX-compatible shell (sh)

## Cross-platform notes

- Bootstrap auto-detects python via `python3 → python → py` fallback chain
- Windows paths are converted via `cygpath` when available under Git Bash
- `chmod 600` on gate-key is silently ignored on Windows (no POSIX permissions)
- `.sh` files are normalized to LF line endings via `.gitattributes`