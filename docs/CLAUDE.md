# metodoloji — BMAD Methodology Plugin

Claude Code plugin for BMAD methodology enforcement.

## What this does

- **Record chain**: E → IR → SP → S → QR → PR (experiment → implementation record → sprint plan → story → quality review → product record)
- **Mechanical gates**: guard (write/edit blocking), quality (bash validation), deploy (deployment checks), audit (post-write trail), stop (session-end validation)
- **123 skills** with **120 bridge TOMLs** linking native outputs to methodology records

## Hooks

All hooks run via `hooks/scripts/hook-entry.sh` which dispatches to the Python engine at `hooks/engine/main.py`.

One unified `hooks/hooks.json` serves both runtimes: Claude Code auto-discovers it from
its default hooks location (`./hooks/hooks.json`), and OpenHands auto-discovers the same
file. Matchers are regexes covering both tool vocabularies; hook commands self-locate the
plugin root and dispatch to the same `hooks/engine/` core.

| Hook | Matcher | Policy | Timeout |
|------|---------|--------|---------|
| SessionStart | — | fail-open (context injection) | 30s |
| PreToolUse guard | Write\|Edit\|MultiEdit\|file_editor\|terminal | fail-closed | 10s |
| PreToolUse quality | Bash\|terminal | fail-open | 10s |
| PreToolUse deploy | Bash\|terminal | fail-open | 10s |
| PostToolUse audit | Write\|Edit\|MultiEdit\|Bash\|file_editor\|terminal | fail-open (async) | 5s |
| Stop | — | fail-closed | 15s |

## Commands

- `/metodoloji:init` — install templates into workspace
- `/metodoloji:gate-setup` — generate `~/.bmad/gate-key` (machine-local, not committed)
- `/metodoloji:verify` — verify experiment approval chain
- `/metodoloji:audit` — run full audit trail check

## Installation (Claude Code)

The plugin ships a marketplace manifest at `.claude-plugin/marketplace.json` with
`defaultEnabled: false` on the plugin entry (and the same flag in the plugin manifest):
the fail-closed guard hooks are opt-in.

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