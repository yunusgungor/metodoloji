#!/bin/sh
# Orca hook — explicit dispatcher for Claude Code events.
#
# Event resolution order (no payload content sniffing):
#   1. $1 = explicit event name (SessionStart|UserPromptSubmit|PreToolUse|
#      PostToolUse|Stop) — e.g. `claude-hook.sh PreToolUse`
#   2. ORCA_HOOK_EVENT env (set by the dedicated claude-hook-<Event>.sh scripts)
#   3. a structured "hook_event_name" field inside the JSON payload
#   4. empty stdin => SessionStart (SessionStart hooks run without stdin)
#   5. anything else => fail-open PreToolUse allow
#
# Emits the Claude Code v2 hookSpecificOutput schema for the resolved event and
# forwards the payload to the Orca hook server (spool fallback when offline).
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
