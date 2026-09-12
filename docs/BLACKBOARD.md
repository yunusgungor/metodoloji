# Blackboard — Dynamic Working Context Network

The blackboard is the project's connective tissue — a network, not a notebook.
Every producer (skills) and consumer (hooks, CLI) pins into it: text keys,
ordered lists, live canvases, graph links, subscriptions and routed alerts.
One event-sourced store per project, read by hooks and written by both hooks
and skills.

## Why

code-docs auto-generated garbage docs (zero recall, constant token burn).
memlog carried intent but had a blind engine fallback, a drifted copy, and a
self-contradicting lifecycle. The blackboard keeps what worked (durable
cross-session context, hook-visible state) and drops what failed (auto doc
generation, deep recursive scans, split-brain storage). On top of that it adds
what the removed systems never had: structure (lists), live surfaces
(canvases), and a graph (links + alert routing) so context flows between
producers and consumers instead of sitting in one flat file.

## Core invariants

1. **One file.** All state lives in `<project-root>/.metodoloji/blackboard.json`.
2. **Event-sourced.** Every mutation is appended to
   `.metodoloji/logs/blackboard-events.log` as one JSON line. The snapshot is a
   cache — deleting it is always safe (rebuilt from the event log). Consumption
   (`consume`) is evented too, so delivered alerts never resurrect.
3. **Atomic + locked.** Reads and writes take an exclusive `fcntl`/`msvcrt`
   lock (`blackboard.json.lock`), serialized per-process by a thread mutex.
   A crashed writer can never truncate state. Mutations never nest: a mutator
   must not call another `_mutate` (deadlock).
4. **Bounded.** Everything has caps; oldest items expire first:
   128 keys, 32 tags, 64 contributions, 10k events, 100 items per list,
   8 canvases, 256 cells per canvas (32 auto cells), 4 watch paths per canvas,
   128 links, 16 subscriptions, 32 alerts, 80-char channel names (the
   `handoff.<skill>` channel must fit the longest skill name — 35 chars —
   so the old 40-char cap would have truncated some signals out of their
   own receiver's reach).
5. **Fail-open.** Every consumer (hooks, CLI) degrades to silence when the
   board is missing, corrupt, or locked. The blackboard never blocks work.
6. **Focus is single.** One `hot` key and one `hot_canvas` at a time; a
   dangling focus (expired target) is never surfaced.
7. **Bounded-context contract.** `read --context` emits a compact JSON summary
   designed to be injected by hooks — never a whole-board dump.
8. **No auto content generation** — except the explicit real-time feed: a
   canvas that *declares* `watch` paths receives audited tool touches as
   `auto` cells. Nothing else is ever written without a writer.

## The five content planes

### 1. Text keys (`write`)
Namespaced single values: `prd.acme-crm`, `ux.acme-crm`, `story.S-003`.
Type tag free-form (`note|decision|state|...`). One key may be `hot`.

### 2. Lists (`list-add`, `list-remove`)
Ordered items under one key (append-only, bounded to 100). Remove by exact
item text or index (0-based, oldest first). The hot key may be a list —
context injection then previews `list[N]`.

### 3. Canvases — dynamic surfaces (`canvas *`)
A canvas is a named set of cells, optionally grid-shaped (`--grid WxH`), that
any project actor mutates in real time:

- `canvas create --name map --grid 8x8 [--focus]` — grid or free-form.
- `canvas set/remove/move/resize/clear` — cell ops (content ≤ 500 chars,
  free-form `kind` such as `note|decision|risk|auto`, optional `x/y`
  coordinates on grid canvases).
- `canvas focus` — one canvas is the board's `hot_canvas` (surfaced by the
  engine at session start and stop).
- `canvas watch --path docs/` — **real-time feed**: every audited tool touch
  under the path lands as an `auto` cell (via `stamp_tool_event` in the
  PostToolUse hook), so a canvas can mirror the project's living filesystem.
  Un-watch with `--remove`.

Grid coordinates are advisory layout hints; free canvases (`grid = null`)
carry cells keyed by id only. Producers update cells mid-run; consumers read
the whole surface with `canvas-read` or just the focused summary in context.

### 4. Graph links (`link`, `unlink`, `neighbors`)
Directed edges between any two nodes (key names, canvas names) with a
relation (`informs`, `blocks`, `related`...). `neighbors` gives the one-hop
neighborhood in both directions, optionally filtered by relation. Links are
the static half of the wiring; subscriptions are the dynamic half.

### 5. Subscriptions & alerts (`subscribe`, `alerts`, `consume`, `notify`)
A subscription binds a watcher to a glob pattern (`prd.*`, `canvas:*`) and a
channel (`session` → injected at session start, `stop` → surfaced at stop, or
any custom channel). Matching mutations — key writes, list changes, canvas
mutations, live touches, link events — are routed as alerts into every
matching channel (deduplicated per channel+kind+text). Engine hooks consume
their channels deliver-once; `consume --channel C` does the same by hand;
`notify` posts a manual alert.

**Hand-off handshake.** Skill-to-skill signals ride the same alert plumbing:
`handoff --to <skill> --from-key <run-key> --note "..."` routes an alert into
the reserved `handoff.<skill>` channel (kind `handoff`). The signal waits
until the downstream skill consumes it — that consumption *is* the
handshake. Until then, session_start carries a proactive warning
(`PROACTIVE — hand-off waiting: <skill> (n): N unclaimed signal(s) from
completed upstream runs; a run finished its work but nobody picked up the
baton ...`) naming the diagnose path (`chain-health`) and the claim path
(`handoffs --skill <self>`, then consume its handoff channel).
Announce-only, never consumes; `bmad-help` is hidden from the warning —
it routes, it does not produce). The stop hook carries the same warning
into deny reasons (`... do not close the loop empty-handed ...`) when a
run tries to close with unclaimed hand-offs on the board. Chain example: a PRD run
closes with `handoff --to bmad-ux`; the UX run opens, reads
`handoffs --skill bmad-ux`, picks up the named artifact first, consumes
`handoff.bmad-ux`, and closes with `handoff --to bmad-architecture` — the
delivery relay in full: prd → ux → architecture → spec →
create-epics-and-stories → create-story → dev-story → code-review (each
sender is optional — a signal not sent just leaves that hop silent, never
broken; dev-story consumes upstream and signals the review run onward;
code-review terminates the tool chain: it consumes and reports, it does
not signal onward). The methodology chain rides the same protocol on its
own run keys: research-experiment → check-implementation-readiness →
sprint-planning → create-story → quality-record → production-readiness
(prefixes `E-`, `IR-`, `SP-`, `S-`, `QR-`, `PR-`). The E→IR→SP→story and
story→QR hops are wired in the stage skills (readiness signals the
verdict to sprint planning; sprint planning signals the queue to the
story run; the story run queues the QR record that will close it out);
stage skills may adopt remaining hops incrementally — a stage that
never sends just leaves its hop silent. Side entrances feed
the relay: brainstorming and forge-idea signal `bmad-product-brief`, and
the brief signals `bmad-prd`.

## Engine integration points (the octopus arms)

- **session_start** — stamps `watchers.session_start`, consumes the `session`
  channel (deliver-once) and injects: hot key with preview, live focused
  canvas (cells/auto counts), tags, last contribution, hot-key neighbors, and
  up to 3 routed alerts.
- **audit** (PostToolUse) — mirrors the last tool target into a bounded
  `last_tool.<tool>` key (never the content body), then pushes the touch into
  every watching canvas (`stamp_tool_event`) — the real-time plane.
- **stop** — deny reasons carry hot-key + focused-canvas notices and pending
  `stop`-channel alerts, consumed deliver-once; unclaimed hand-offs surface
  as the same proactive warning (announce-only — a nudge, never a block on
  its own; the addressed skill still completes the handshake).
- Engine writes are all guarded by the `[hooks] blackboard` switch.

## The relay at a glance

Both relays ride one handshake. The closing run posts
`handoff --to <downstream> --from-key <run-key> --note "..."` and the
signal waits in the reserved `handoff.<skill>` channel; the addressed
run opens with `handoffs --skill <self>`, reads the named artifact
first, and completes the handshake by consuming the channel:

    closing run                          opening run
    -----------                          -----------
    handoff --to bmad-ux                 handoffs --skill bmad-ux
         |                                    |  (note names the artifact)
         v                                    v
    handoff.bmad-ux  ======= waiting =======>  read the artifact first
    from-key: prd.<slug>                       |
         ^                                     v
         +======== consumed <=========  consume --channel handoff.bmad-ux
                                (that consumption IS the handshake)

`chain-health` reports every hop `idle`/`clear`/`waiting`; `doctor`
surfaces unclaimed signals at close-out; session_start/stop announce
waiting signals without ever consuming them. A hop whose sender never
fires stays silent — never broken.

    TOOL CHAIN (side entrances feed the relay)

      brainstorming --+
      forge-idea -----+--> brief --> prd --> ux --> architecture
                                                        |
                                                        v
                                                       spec
                                                        |
                                                        v
                                    create-epics-and-stories
                                                        |
                                                        v
      code-review <-- dev-story <-- create-story <-------+
         (terminal)      ^              |
                         |              +--> quality-record --> production-readiness
                         |                  (terminal)
          dev-story consumes story.<key>; the QR record is queued
          with story.<key> too — both hop edges carry story.<key>

      from-keys: brief.* prd.* ux.* architecture.* spec.* epics.* story.*

    METHODOLOGY CHAIN (create-story is the bridge between the relays)

      research-experiment --> check-implementation-readiness --> sprint-planning --> create-story
           E-<exp-id>                   IR-<date>                 SP-<date>      (bridge)

      create-story --(queue: story.<key>)--> quality-record --(QR-<id>)--> production-readiness
                                                                              PR-... (terminal)

## Chain health (`chain-health`)

Per-hop diagnostics for the delivery relay, sender-attributed from the event
log (signal text is `<from-key>: <note>`, so a run-key namespace prefix —
`prd.`, `ux.`, `architecture.`, `spec.`, `epics.`, `story.` on the tool
chain; `E-`, `IR-`, `SP-`, `S-`, `QR-`, `PR-` on the methodology chain —
names the sender; a from-key outside every known namespace attributes to
`unknown` and still surfaces under `extra`):

    python3 bmad/scripts/blackboard.py chain-health

Each of the 6 hops reports `waiting` (posted, downstream has not consumed —
the handshake is open), `consumed` (handshake completed) and a `status`:
`idle` (no signal ever sent), `clear` (all sent signals consumed), `waiting`
(at least one open). Signals addressed to skills outside the chain surface
in `extra` — the protocol is extensible, the diagnostic follows.
`total_waiting` is the one number to watch: a non-zero value means a run
finished its work but its hand-off was never picked up.

## Doctor (`doctor`)

One-glance diagnostic of the whole board:

    python3 bmad/scripts/blackboard.py doctor            # human panel
    python3 bmad/scripts/blackboard.py doctor --json     # raw report

Checks: config gate (on/off), snapshot version + age, event-log line and
garbage counts, per-plane cap usage (warns at ≥90% — oldest will expire
soon), focus (hot key / hot canvas), snapshot↔event-log drift (`last_tool.*`
tool-stamped keys are excluded — the audit hook folds them in by design),
leftover `.tmp` files (crash residue, safe to delete), chain health
(`total_waiting` with the waiting hops named), and canvas watch paths
(existence noted). Verdict: `HEALTHY` iff no warnings, else `NEEDS
ATTENTION` with a numbered list and remediation hints (rebuild on drift,
delete tmp, claim hand-offs via chain-health).

## Config

`custom/config.toml [hooks] blackboard = "on" | "off"` (default `on`, read
live per call like the other gates). `off` = all engine integration becomes a
no-op; the CLI still works (fail-open).

## CLI

`bmad/scripts/blackboard.py`:

    read    [--key K] [--context] [--project-root R]
    write   --key K --value V [--type T] [--hot]
    list-add    --key K --item X
    list-remove --key K (--item X | --index N)
    list-clear  --key K            (empty the list)
    canvas create|set|remove|move|resize|clear|focus|watch  (see --help)
    canvas-read --name N
    link      --a A --b B [--relation R]
    unlink    --a A --b B [--relation R]
    neighbors --node N [--relation R]
    subscribe   --watcher W --pattern P [--channel C]
    unsubscribe --watcher W --pattern P
    alerts   [--channel C]        (read-only peek)
    consume  --channel C          (take and clear)
    notify   --channel C --kind K --text X
    handoff  --to SKILL --from-key K [--note X]
    handoffs [--skill S]          (peek waiting signals)
    tag/untag --tag T
    contribute --who W --what X
    hot --key K | --clear
    stats

All commands accept `--project-root R` (default: cwd). Writes print a one-line
JSON ack `{"ok": true, ...}`. Fail-open: missing/corrupt state yields an empty
result and exit 0.

## Skill contract

Producing skills (brief, brainstorming, forge, PRD, UX, architecture,
spec, epics, story, dev-story)
run on three planes:

- **Focus (required)** — `write --hot` one state key at activation,
  `hot --clear` at close, milestone re-writes in between.
- **Intent bridge (required)** — mirror the session intent onto the global
  bridge keys so every hook process sees the run's focus: `write --key
  purpose --value "<one-line subject>"` at activation (plus `topic` / `goal`
  / `idea` in the skill's own vocabulary where the pre-memlog-removal text
  used those variants), `write --key scope --value "<path scope>"` when the
  work is path-scoped (guard warns on out-of-scope writes; bootstrap exports
  it as `METODOLOJI_SCOPE`), and `write --key status --value complete` at
  close (stop skips story checks and `bmad-help` routes to next steps once
  progress is `complete`). Last writer wins — concurrent runs overwrite each
  other, which is the correct semantic for "what is the session about now".
- **Run list (required where threads appear)** — unresolved threads ride
  `<run-key>.pending` (or `.open` / `.branches` / `.failing` / `.parked` by
  domain); resolved items come off, consciously-parked items stay as
  hand-off signal.
- **Chain handshake (producing skills that hand off downstream)** — at
  close, `handoff --to <downstream>` with a one-line note naming what the
  next run should pick up first; at activation, check
  `handoffs --skill <self>` and consume the channel only after binding the
  run, so an unrouted signal keeps waiting.
- **Close-out check (all producing skills)** — after clearing focus and
  lists but before posting the run's own hand-off, run
  `doctor --json` and surface `NEEDS ATTENTION` warnings to the user
  (headless: into the status output) — residual hot keys, expiring planes,
  tmp residue, or *earlier* runs' unclaimed signals get named before the
  session ends instead of silently rotting on the board.
- **Canvas (where a live picture helps)** — surface maps (ux), decision maps
  (architecture), idea boards (brainstorming);
  `watch` paths feed touches automatically; leave the canvas standing when
  downstream skills read it, clear focus at close.

That is the entire contract — no lifecycle status beyond the `status` bridge
key, no log schema, no resume machinery beyond the artifacts themselves
plus the run lists that back them.

## Guest skills (read + trace only)

Helpers that produce no methodology record of their own
(`bmad-advanced-elicitation`, `bmad-eval-runner`) stay off the planes above:
no focus key, no bridge writes, no run list, no hand-off, no canvas, no
`doctor` close-out — those stay owned by the invoking skill. They inherit
context read-only (`read --context`, plus targeted `read --key` peeks) and
leave exactly one trace: `contribute --who <skill> --what "<session>:
<one-line outcome>"`. Fail-open throughout — board errors never block the
return to the caller.
