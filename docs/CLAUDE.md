# metodoloji — BMAD Methodology Plugin

Claude Code plugin for BMAD methodology enforcement.

## What this does

- **Record chain**: E → IR → SP → S → QR → PR (experiment → implementation readiness → sprint planning → story → quality review → production readiness)
- **Mechanical gates**: guard (write/edit blocking, always fail-closed), quality (`git commit` chain check), deploy (deploy-command chain check), audit (post-write trail), stop (session-end validation, always fail-closed)
- **123 skills** with **120 customization TOMLs** (33 active BRIDGEs linking native outputs to methodology records)

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
| PreToolUse quality | Bash\|terminal | config-gated: soft (default) / hard | 10s |
| PreToolUse deploy | Bash\|terminal | config-gated: soft (default) / hard | 10s |
| PostToolUse audit | Write\|Edit\|MultiEdit\|Bash\|file_editor\|terminal | fail-open (async) | 5s |
| Stop | — | fail-closed | 15s |

### Gate strictness (soft/hard)

`custom/config.toml [hooks]` controls the commit/deploy gates. Values are read live
per-call, so config edits apply without a reload:

```toml
[hooks]
quality_gate = "soft"   # "soft" (default) | "hard"
deploy_guard = "soft"   # "soft" (default) | "hard"
code_guard = "hard"     # "hard" (default) | "soft" (brownfield adoption)
stop_guard = "hard"     # "hard" (default) | "soft" (brownfield adoption)
```

- **soft** (default for quality/deploy) — a missing IR/QR/SP (quality) or IR/QR/SP/PR (deploy) record
  becomes a warning: `allow` + `methodology_warnings`. Nothing blocks.
- **hard** — the same missing records cause `DENY`.
- **guard** and **stop** are fail-closed by default (mechanical): writing code and closing
  the session require an approved, scope-matching VERIFIED experiment record — but only
  for files **this session touched** (audit-log based, never a whole-tree scan).
  Brownfield projects set `code_guard` / `stop_guard = "soft"` until the first
  VERIFIED scope exists. The guard's story-metadata path also follows
  `quality_gate` (hard → deny, soft → warn-only) — except the `experiment_refs`
  check, which always denies.
- **Stop is loop-safe**: `stop_hook_active` re-fires allow, one deny per session
  max, stale sprint-status ignored. Never duplicate the Stop registration
  (plugin manifest + manual `settings.json` entry = "Ran 2 stop hooks").
- Two independent layers: the fail-open/fail-closed column above is what happens when
  the **engine cannot run** (guard/stop deny + exit 2; quality/deploy/audit pass
  silently), while soft/hard is what happens when the engine runs but the **record
  chain is incomplete**.

## Commands

- `/metodoloji:init` — install templates into workspace
- `/metodoloji:gate-setup` — generate `~/.bmad/gate-key` (machine-local, not committed)
- `/metodoloji:verify` — verify an experiment record. Outcomes (exit codes):
  `VERIFIED` (0 — APPROVED with genuine token; the guard opens the record's `Code Scope`),
  `FORGED` (1 — token does not match the record's claim/measured/measurement-command),
  `REJECTED` or undecided (1 — did not pass the gate),
  `ADVISORY-BLOCK` (2 — token genuine but does **not** unlock code: small sample
  (Wilson bound below threshold), `n unknown`, or metric MISMATCH)
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

- Python 3.11+ (python3, python, or py on Windows) — stdlib `tomllib` is required by the TOML merge
- Git Bash or POSIX-compatible shell (sh)

## Cross-platform notes

- Bootstrap auto-detects python via `python3 → python → py` fallback chain
- Windows paths are converted via `cygpath` when available under Git Bash
- `chmod 600` on gate-key is silently ignored on Windows (no POSIX permissions)
- `.sh` files are normalized to LF line endings via `.gitattributes`