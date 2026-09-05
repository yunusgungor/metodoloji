#!/bin/sh
# Orca hook — explicit Stop event script.
# Directly executable, or sourced by claude-hook.sh when invoked as
# `claude-hook.sh Stop`. Emits the v2 Stop schema and forwards.
ORCA_HOOK_EVENT="Stop"
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
