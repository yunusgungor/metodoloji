#!/bin/sh
# hook-entry.sh — single resolution point: find engine, pass to python, apply policy.
# Usage: sh hook-entry.sh <guard|quality|deploy|stop|audit|session_start> [runtime]
# Cross-platform: Windows/macOS/Linux.
# Policies (Claude parity):
#   guard/stop     fail-closed  (engine missing → deny + exit 2)
#   quality/deploy fail-open    (engine missing → silent pass)
#   audit          fail-open
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/../.." && pwd)
ENGINE="$PLUGIN_ROOT/hooks/engine/main.py"
MODE="$1"

# Find a working python interpreter (cross-platform)
PY=
for c in python3 python py; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done
if [ -z "$PY" ]; then
    # Last resort: try common Windows paths
    for p in "/c/Python3*/python.exe" "/c/Users/$USER/AppData/Local/Programs/Python/Python3*/python.exe"; do
        for f in $p; do
            [ -x "$f" ] && PY="$f" && break 2
        done
    done
fi

_fail() {
    case "$MODE" in
        # Stop uses the loop-safe envelope: decision block + exit 0. Exit 2 on
        # Stop re-triggers the hook and wedges the session (stop_hook_active
        # never propagates on a non-zero exit path).
        stop)
            printf '%s\n' '{"decision":"block","reason":"Methodology hook engine could not run (no python or missing engine) — fail-closed blocked.","hookSpecificOutput":{"hookEventName":"Stop"}}'
            exit 0
            ;;
        guard)
            printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"'"$MODE"'","permissionDecision":"deny","permissionDecisionReason":"Methodology hook engine could not run (no python or missing engine) — fail-closed blocked."}}'
            exit 2
            ;;
        *)  exit 0 ;;
    esac
}

if [ -z "$PY" ] || [ ! -f "$ENGINE" ]; then
    _fail
fi

# Set hook type environment variable
export HOOK_TYPE="$MODE"

# Runtime selection: 2nd arg > env > default openhands
RUNTIME="${2:-${METODOLOJI_RUNTIME:-openhands}}"

# Read stdin and pass to engine
exec "$PY" "$ENGINE" --runtime="$RUNTIME"
