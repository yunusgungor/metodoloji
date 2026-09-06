#!/bin/sh
# run-hook.sh — Central hook dispatcher across Claude Code, OpenHands Canvas/Local, and CI
# Discovers the plugin root reliably and routes to bootstrap.sh or hook-entry.sh.
# Usage: sh run-hook.sh <bootstrap|guard|quality|deploy|audit|stop> [args...]

TARGET_HOOK="$1"
[ -n "$1" ] && shift

# 1. Resolve Candidate Locations. Explicit roots first, then the script's own
# location (always correct for a checkout), then workspace globs, then
# versioned caches LAST — a stale cache must never shadow a live checkout.
# Glob candidates are expanded newest-first so parallel installs resolve to
# the freshest copy, not the alphabetically first.
_join_newest_first() {
    # $1 = glob pattern; prints existing dirs newest mtime first.
    for d in $1; do
        [ -d "$d" ] && printf '%s %s\n' "$(stat -c %Y "$d" 2>/dev/null || stat -f %m "$d" 2>/dev/null || echo 0)" "$d"
    done | sort -rn | cut -d' ' -f2-
}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd)
SCRIPT_PLUGIN_ROOT=""
if [ -n "$SCRIPT_DIR" ]; then
    SCRIPT_PLUGIN_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd)
fi

PLUGIN_ROOT=""
_try_candidate() {
    [ -d "$1" ] && [ -f "$1/hooks/scripts/hook-entry.sh" ] && [ -f "$1/hooks/scripts/bootstrap.sh" ] || return 1
    PLUGIN_ROOT=$(CDPATH= cd -- "$1" 2>/dev/null && pwd)
    return 0
}

for dir in "$CLAUDE_PLUGIN_ROOT" "$METODOLOJI_PLUGIN_ROOT" "$SCRIPT_PLUGIN_ROOT" \
           "$OPENHANDS_PROJECT_DIR" "$WORKSPACE_BASE" "." "$PWD" "$PWD/metodoloji" \
           "/workspace" "/workspace/metodoloji"; do
    [ -n "$dir" ] && _try_candidate "$dir" && break
done
if [ -z "$PLUGIN_ROOT" ]; then
    for dir in $(_join_newest_first "/workspace/*") \
               $(_join_newest_first "$HOME/.claude/plugins/cache/yunusgungor/metodoloji/*") \
               $(_join_newest_first "$HOME/.openhands/plugins/cache/*"); do
        _try_candidate "$dir" && break
    done
    [ -z "$PLUGIN_ROOT" ] && _try_candidate "$HOME/.openhands/plugins/installed/metodoloji"
fi

# Plugin root not located: guard/stop stay fail-closed (deny), everything
# else fails open. Stop uses the loop-safe envelope (block + exit 0).
if [ -z "$PLUGIN_ROOT" ]; then
    case "$TARGET_HOOK" in
        guard)
            printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Methodology plugin root not found — fail-closed blocked."}}'
            exit 2
            ;;
        stop)
            printf '%s\n' '{"decision":"block","reason":"Methodology plugin root not found — fail-closed blocked.","hookSpecificOutput":{"hookEventName":"Stop"}}'
            exit 0
            ;;
        *)  exit 0 ;;
    esac
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
