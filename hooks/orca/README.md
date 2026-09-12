# hooks/orca — Orca app hook bridge

Optional, **additive** hook scripts that mirror methodology hook events to the
[Orca](https://orca.build) desktop app's local hook server. They never gate
anything: every script emits the Claude Code v2 `hookSpecificOutput` schema
(allow / empty additionalContext) and forwards the payload for observability.

## What's here

| File | Purpose |
|---|---|
| `lib.sh` | Shared plumbing: single stdin read, v2 schema emission, endpoint config, forward transports (form-encoded + raw-json-v1), offline spool fallback. |
| `claude-hook.sh` | Generic dispatcher — event from `$1`, `ORCA_HOOK_EVENT`, the payload's `hook_event_name` field, empty-stdin ⇒ SessionStart, else fail-open PreToolUse allow. |
| `claude-hook-<Event>.sh` | Dedicated entry per event (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`) — sets `ORCA_HOOK_EVENT` and sources `lib.sh`. |
| `antigravity-hook.sh` | Antigravity runtime variant — event via `ORCA_ANTIGRAVITY_EVENT`, PreToolUse emits `ask`. |

## Activation

These scripts are NOT wired into `hooks/hooks.json` (the methodology's
gating engine lives there). They activate only when a runtime is configured
to call them explicitly, e.g. in Claude Code settings:

```json
{
  "hooks": {
    "PreToolUse": [
      { "hooks": [ { "type": "command",
        "command": "sh \"$CLAUDE_PROJECT_DIR/hooks/orca/claude-hook-PreToolUse.sh\"" } ] }
    ]
  }
}
```

or by the Orca app itself when it launches an agent inside a worktree of this
repo. No activation ⇒ no effect on any session.

## Configuration (environment)

| Var | Meaning |
|---|---|
| `ORCA_AGENT_HOOK_PORT` | Local hook-server port (required — no default in lib.sh). |
| `ORCA_AGENT_HOOK_TOKEN` | Shared token, sent as `X-Orca-Agent-Hook-Token`. |
| `ORCA_AGENT_HOOK_ENDPOINT` | Optional file sourced for endpoint overrides. |
| `ORCA_HOOK_EVENT` | Explicit event name for the generic dispatcher. |
| `ORCA_PANE_KEY` / `ORCA_TAB_ID` / `ORCA_WORKTREE_ID` | Routing metadata for the server. |

Offline or unreachable server ⇒ payloads spool to
`$ORCA_AGENT_HOOK_ENDPOINT/../spool/pane-<key>.jsonl` (bounded, 7-day TTL,
PreToolUse/PostToolUse excluded) so the app can replay later. All forwarding
is best-effort with sub-2-second timeouts; failures are silent by design.
