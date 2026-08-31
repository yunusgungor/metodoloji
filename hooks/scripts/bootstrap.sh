#!/bin/sh
# bootstrap.sh — SessionStart: check/create the gate-key and inject short context
# (additionalContext). Non-blocking (fail-open).
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYNCED=$(CDPATH= cd -- "$SELF/../.." && pwd)

WS="$OPENHANDS_PROJECT_DIR"
[ -z "$WS" ] && WS=$(pwd)

# Auto-setup: create gate-key if missing
if [ ! -f "$HOME/.bmad/gate-key" ]; then
    mkdir -p "$HOME/.bmad"
    # Generate a simple gate key (sufficient for HMAC)
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$HOME/.bmad/gate-key"
    chmod 600 "$HOME/.bmad/gate-key"
fi

# Create missing directories
mkdir -p "$WS/docs/experiments"
mkdir -p "$WS/.metodoloji/logs"

# Short context: gate-key status + record chain reminder.
if [ -f "$HOME/.bmad/gate-key" ]; then KEY="present"; else KEY="MISSING — python3 run_experiment.py --init-secret"; fi
printf '%s\n' "{\"additionalContext\":\"METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY. Record templates: /metodoloji:init\"}"
exit 0
