# metodoloji — BMAD Methodology Plugin

Claude Code plugin for BMAD methodology enforcement.

## What this does

- **Record chain**: E → IR → SP → S → QR → PR (experiment → implementation record → sprint plan → story → quality review → product record)
- **Mechanical gates**: guard (write/edit blocking), quality (bash validation), deploy (deployment checks), audit (post-write trail), stop (session-end validation)
- **125 skills** with 74 bridge TOMLs linking native outputs to methodology records

## Hooks

All hooks run via `hooks/scripts/hook-entry.sh` which dispatches to the Python engine at `hooks/engine/main.py`.

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

## Requirements

- Python 3.6+ (python3, python, or py on Windows)
- Git Bash or POSIX-compatible shell (sh)

## Cross-platform notes

- Bootstrap auto-detects python via `python3 → python → py` fallback chain
- Windows paths are converted via `cygpath` when available under Git Bash
- `chmod 600` on gate-key is silently ignored on Windows (no POSIX permissions)
