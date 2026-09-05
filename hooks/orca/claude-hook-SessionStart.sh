#!/bin/sh
# Orca hook — explicit SessionStart event script.
# Directly executable, or sourced by claude-hook.sh when invoked as
# `claude-hook.sh SessionStart`. Emits the v2 SessionStart schema and forwards.
ORCA_HOOK_EVENT="SessionStart"
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
