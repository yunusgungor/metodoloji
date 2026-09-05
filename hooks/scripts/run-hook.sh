#!/bin/sh
# run-hook.sh — Central hook dispatcher across Claude Code, OpenHands Canvas/Local, and CI
# Discovers the plugin root reliably and routes to bootstrap.sh or hook-entry.sh.
# Usage: sh run-hook.sh <bootstrap|guard|quality|deploy|audit|stop> [args...]

TARGET_HOOK="$1"
[ -n "$1" ] && shift

# 1. Resolve Candidate Locations
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd)
SCRIPT_PLUGIN_ROOT=""
if [ -n "$SCRIPT_DIR" ]; then
    SCRIPT_PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd)
fi

CANDIDATES="
  $CLAUDE_PLUGIN_ROOT
  $METODOLOJI_PLUGIN_ROOT
  $SCRIPT_PLUGIN_ROOT
  $OPENHANDS_PROJECT_DIR
  $WORKSPACE_BASE
  .
  $PWD
  $PWD/metodoloji
  /workspace
  /workspace/metodoloji
  /workspace/*
  $HOME/.claude/plugins/cache/yunusgungor/metodoloji/*
  $HOME/.openhands/plugins/installed/metodoloji
  $HOME/.openhands/plugins/cache/*
"

PLUGIN_ROOT=""
for dir in $CANDIDATES; do
    if [ -d "$dir" ] && [ -f "$dir/hooks/scripts/hook-entry.sh" ] && [ -f "$dir/hooks/scripts/bootstrap.sh" ]; then
        PLUGIN_ROOT=$(CDPATH= cd -- "$dir" 2>/dev/null && pwd)
        break
    fi
done

# If plugin root could not be located, fail-open (exit 0) so agent workflows are never blocked
if [ -z "$PLUGIN_ROOT" ]; then
    exit 0
fi

# Export resolved root so child processes inherit it immediately
export METODOLOJI_PLUGIN_ROOT="$PLUGIN_ROOT"
[ -z "$CLAUDE_PLUGIN_ROOT" ] && export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"

# 2. Dispatch to target script
if [ "$TARGET_HOOK" = "bootstrap" ]; then
    exec sh "$PLUGIN_ROOT/hooks/scripts/bootstrap.sh" "$@"
else
    exec sh "$PLUGIN_ROOT/hooks/scripts/hook-entry.sh" "$TARGET_HOOK" "$@"
fi
