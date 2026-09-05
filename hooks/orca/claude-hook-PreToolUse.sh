#!/bin/sh
# Orca hook — explicit PreToolUse event script.
# Directly executable, or sourced by claude-hook.sh when invoked as
# `claude-hook.sh PreToolUse`. Emits the v2 PreToolUse allow schema and forwards.
ORCA_HOOK_EVENT="PreToolUse"
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
