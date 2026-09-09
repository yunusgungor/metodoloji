# Blackboard — Dynamic Working Context

The blackboard is the replacement for the removed code-docs and memlog systems:
a single event-sourced working context per project, read by hooks and written
by both hooks and skills.

## Why

code-docs auto-generated garbage docs (zero recall, constant token burn).
memlog carried intent but had a blind engine fallback, a drifted copy, and a
self-contradicting lifecycle. The blackboard keeps what worked (durable
cross-session context, hook-visible state) and drops what failed (auto doc
generation, deep recursive scans, split-brain storage).

## Core invariants

1. **One file.** All state lives in `<project-root>/.metodoloji/blackboard.json`.
2. **Event-sourced.** Every mutation is appended to
   `.metodoloji/logs/blackboard-events.log` as one JSON line. The snapshot is a
   cache — deleting it is always safe (rebuilt from the event log).
3. **Atomic + locked.** Reads and writes take an exclusive `fcntl`/`msvcrt`
   lock (`blackboard.json.lock`). A crashed writer can never truncate state.
4. **Bounded.** Keys, tags, contributions, and events have caps (default:
   128 keys, 32 tags, 64 contributions, 10k events). Oldest items expire.
5. **Fail-open.** Every consumer (hooks, CLI) degrades to silence when the
   board is missing, corrupt, or locked. The blackboard never blocks work.
6. **Hotkey wins.** Only one key can be `hot` at a time. Write events on a hot
   key emit a `dirty` notice so every reader knows the context may have moved.
7. **Bounded-context contract.** `read --context` emits a compact JSON summary
   (hot key, tags, watchers, contributions) designed to be injected by hooks,
   not dumped wholesale.

## On the board

- `hot` — the key currently in focus (e.g. `prd.acme-crm`), at most one.
- `keys` — namespaced values: `prd.acme-crm`, `ux.acme-crm`, `story.S-003`...
- `tags` — project-level labels for lightweight retrieval.
- `contributions` — who did what, most recent first (bounded).
- `watchers` — which hooks subscribe (populated by the engine).

## Config

`custom/config.toml [hooks] blackboard = "on" | "off"` (default `on`, read
live per call like the other gates). `off` = all engine integration becomes a
no-op; the CLI still works (fail-open).

## CLI

`bmad/scripts/blackboard.py`:

    read   [--key K] [--context] [--project-root R]
    write  --key K --value V [--type T] [--hot] [--project-root R]
    tag    --tag T | --clear-tag T [--project-root R]
    contribute --who W --what X [--project-root R]
    hot    --key K | --clear [--project-root R]
    stats  [--project-root R]

Writes print a one-line JSON ack `{"ok": true, ...}`; `read --context` prints
compact JSON. The command is idempotent, atomic, and never exits non-zero for
missing state (exit 0, empty result).

## Engine integration points

- **session_start** — injects the compact context into `additionalContext`
  and stamps `watchers.session_start`.
- **audit** (PostToolUse) — appends a bounded `tool` event per audited call.
- **stop** — deny reasons carry `dirty` hot-key notices.
- Engine writes are all guarded by the `[hooks] blackboard` switch.
