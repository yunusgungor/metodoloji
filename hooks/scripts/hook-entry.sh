#!/bin/sh
# hook-entry.sh — single resolution point: find engine, pass to python, apply policy.
# Usage: sh hook-entry.sh <guard|quality|deploy|stop|audit>
# Policies (Claude parity):
#   guard/stop     fail-closed  (engine missing → deny + exit 2)
#   quality/deploy fail-open    (engine missing → silent pass)
#   audit          fail-open
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/../.." && pwd)
ENGINE="$PLUGIN_ROOT/hooks/engine/main.py"
MODE="$1"

PY=
for c in python3 python py; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done

_fail() {
    case "$MODE" in
        guard|stop)
            printf '%s\n' '{"decision":"deny","reason":"Methodology hook engine could not run (no python or missing engine) — fail-closed blocked."}'
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
exec "$PY" "$ENGINE" --runtime=$RUNTIME
