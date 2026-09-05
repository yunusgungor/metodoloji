#!/bin/sh
# Orca hook — explicit PostToolUse event script.
# Directly executable, or sourced by claude-hook.sh when invoked as
# `claude-hook.sh PostToolUse`. Emits the v2 PostToolUse schema and forwards.
ORCA_HOOK_EVENT="PostToolUse"
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
