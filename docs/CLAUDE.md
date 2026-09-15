# metodoloji — BMAD Methodology Plugin

Claude Code plugin for BMAD methodology enforcement.

## What this does

- **Record chain**: E → IR → SP → S → QR → PR (experiment → implementation readiness → sprint planning → story → quality review → production readiness)
- **Mechanical gates**: guard (write/edit blocking, fail-closed at hard), quality (`git commit` chain check, config-gated), deploy (deploy-command chain check, config-gated), audit (post-write trail), stop (session-end validation, fail-closed at hard)
- **122 skills** with **118 customization TOMLs** + `config.toml` (33 active BRIDGEs linking native outputs to methodology records). `bmad-customize`, `bmad-help`, `memory`, `sync` are tool/meta skills with no bridge TOML by design (see check-plugin.sh §2 EXCLUDED / §6b pairing).

## Hooks

All hooks run via `hooks/scripts/hook-entry.sh` which dispatches to the Python engine at `hooks/engine/main.py` (`pre`/`guard`/`quality`/`deploy`/`audit`/`stop`/`session_start` modes; `hooks.json` dispatches the merged `pre` for PreToolUse).

One unified `hooks/hooks.json` serves both runtimes: Claude Code auto-discovers it from
its default hooks location (`./hooks/hooks.json`), and OpenHands auto-discovers the same
file. Matchers are regexes covering both tool vocabularies; hook commands self-locate the
plugin root and dispatch to the same `hooks/engine/` core.

| Hook | Matcher | Policy | Timeout |
|------|---------|--------|---------|
| SessionStart | — | fail-open (context injection) | 30s |
| PreToolUse `pre` | Write\|Edit\|MultiEdit\|Bash\|file_editor\|terminal | fail-closed (guard inside) | 20s |
| PostToolUse audit | Write\|Edit\|MultiEdit\|Bash\|file_editor\|terminal | fail-open (sync) | 5s |
| Stop | — | fail-closed | 15s |

> **One PreToolUse entry, three gates, one process.** `pre` runs
> guard → quality → deploy in order inside a single engine invocation; the
> first deny short-circuits and soft-gate warnings accumulate. Each gate keeps
> its own config key (`code_guard` / `quality_gate` / `deploy_guard`), so they
> remain independent policies — only the process is shared (it used to be
> three hook dispatches + three python cold-starts per tool call).
> The matcher is the union of both tool vocabularies, which also closes a gap:
> a Claude Code `Bash` call now reaches guard, so a shell write such as
> `echo x > src/a.py` can no longer sidestep the experiment gate (it previously
> matched quality/deploy only). That union also means guard's secret
> protection now applies to `Bash`: a command referencing the gate key
> (e.g. `cat ~/.bmad/gate-key`) is denied where the old per-gate dispatch
> allowed it to slip past guard.
>
> Measured engine latency (bench over direct `main.py` calls, Windows):
> simple calls ~198 ms → ~62 ms per tool call with the merged entry; a
> code-target write runs ~620 ms (dominated by HMAC verification of
> experiment records, ~15 ms each — same cost as the old three-process
> chain). Fixing that path also removed a Windows self-deadlock: guard's
> record lock plus `verify_record`'s blocking `msvcrt.LK_LOCK` on the same
> `.lock` file stalled code-target writes for ~100 s. Verify now takes a
> bounded non-blocking lock (`GATE_VERIFY_TIMEOUT_SECONDS = 15` stays below
> this hook's 20 s so a hung verify fails open inside the hook budget), and
> `find_approved` defers gate verification of records whose Code Scope
> cannot cover the target. Record `.lock` sidecars are runtime artifacts
> (gitignored), never committed.

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
  the **engine cannot run** (pre/guard/stop deny + exit 2; quality/deploy/audit pass
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