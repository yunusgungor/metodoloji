#!/bin/sh
# Orca hook — explicit UserPromptSubmit event script.
# Directly executable, or sourced by claude-hook.sh when invoked as
# `claude-hook.sh UserPromptSubmit`. Emits the v2 UserPromptSubmit schema and forwards.
ORCA_HOOK_EVENT="UserPromptSubmit"
. "$(dirname "$0")/lib.sh"
orca_hook_lib_entry "$@"
