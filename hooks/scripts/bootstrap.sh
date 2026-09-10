#!/bin/sh
# bootstrap.sh — SessionStart: check/create the gate-key and inject short context
# (additionalContext). Non-blocking (fail-open). Cross-platform: Windows/macOS/Linux.
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYNCED=$(CDPATH= cd -- "$SELF/../.." && pwd)

WS="${CLAUDE_PROJECT_DIR:-$OPENHANDS_PROJECT_DIR}"
[ -z "$WS" ] && WS=$(pwd)

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

if [ -z "$PY" ]; then
    printf '%s\n' '{"additionalContext":"METODOLOJI active but python not found — hooks disabled. Install Python 3."}'
    exit 0
fi

# Auto-setup: create gate-key if missing (atomic write — a crashed python
# must never leave a truncated zero-byte key behind).
if [ ! -f "$HOME/.bmad/gate-key" ]; then
    mkdir -p "$HOME/.bmad"
    if "$PY" -c "import secrets; print(secrets.token_hex(32))" > "$HOME/.bmad/gate-key.tmp"; then
        mv "$HOME/.bmad/gate-key.tmp" "$HOME/.bmad/gate-key"
        chmod 600 "$HOME/.bmad/gate-key" 2>/dev/null || true
    else
        rm -f "$HOME/.bmad/gate-key.tmp"
    fi
fi

# Create missing directories
mkdir -p "$WS/docs/experiments"
mkdir -p "$WS/.metodoloji/logs"

# Short context: gate-key status + record chain reminder.
if [ -f "$HOME/.bmad/gate-key" ]; then KEY="present"; else KEY="MISSING — python run_experiment.py --init-secret"; fi

# Intent bridge: read the blackboard's status (progress) and scope, export to
# env. Every hook process shares the same session focus. Fail-open
# (read error → empty). Only status + scope are bridged: stop skips story
# checks on status=complete and the guard warns outside scope. (The old
# purpose/topic/goal/idea intent mirror was removed — nothing read it.)
# ponytail: WS with quote/backslash exits early (kept raw for mkdir;
# PYWS passed to python via env is quote-safe normalized).
case "$WS" in
    *\'* | *\"* | *\`* | *\\* | *\$*)
        export METODOLOJI_SCOPE=""
        SCOPE_CTX=""
        SKIP_INTENT_READ=1
        ;;
esac
PYWS="$WS"
if command -v cygpath >/dev/null 2>&1; then
    PYWS=$(cygpath -w "$WS" 2>/dev/null || echo "$WS")
fi
PYWS=$(printf '%s' "$PYWS" | tr '\\' '/')
# ponytail: shell vars cross into python via env, never string interpolation
# (a quote in $WS/$SYNCED would break `python -c` and silently empty the scope).
export METODOLOJI_WS="$PYWS"
export METODOLOJI_SYNCED="$SYNCED"
if [ "$SKIP_INTENT_READ" = "1" ]; then
    SCOPE=$(printf '')
else
SCOPE=$("$PY" -c "
import sys, os, pathlib
ws = os.environ.get('METODOLOJI_WS', '')
try:
    plugin = pathlib.Path(os.environ.get('METODOLOJI_SYNCED', ''))
    sys.path.insert(0, str(plugin / 'hooks' / 'engine'))
    os.environ['CLAUDE_PROJECT_DIR'] = ws
    from modules.config import blackboard_enabled
    if not blackboard_enabled():
        print('')
    else:
        from modules import blackboard as bb
        board = bb.read_board(ws)
        keys = board.get('keys', {})
        scope_entry = keys.get('scope')
        scope = str(scope_entry.get('value', '')).strip() if scope_entry and isinstance(scope_entry, dict) else ''
        print(scope)
except Exception:
    print('')
" 2>/dev/null || printf '')
fi
export METODOLOJI_SCOPE="$SCOPE"
if [ -n "$SCOPE" ]; then SCOPE_CTX=" Active scope: $SCOPE."; else SCOPE_CTX=""; fi

# Build full context and output as proper JSON (Python handles escaping).
# ponytail: shell vars cross into python via env (see above) — $SYNCED/$PYWS
# stay shell-side (ctx template, export); python reads them from env.
export METODOLOJI_KEY="$KEY" METODOLOJI_SCOPE_CTX="$SCOPE_CTX"
"$PY" -c "
import json, sys, os, pathlib

plugin = pathlib.Path(os.environ.get('METODOLOJI_SYNCED', ''))
sys.path.insert(0, str(plugin / 'hooks' / 'engine'))
ws = os.environ.get('METODOLOJI_WS', '')
os.environ['CLAUDE_PROJECT_DIR'] = ws

ctx = ('METODOLOJI active (plugin: ' + os.environ.get('METODOLOJI_SYNCED', '') + '). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: ' + os.environ.get('METODOLOJI_KEY', '') + '.' + os.environ.get('METODOLOJI_SCOPE_CTX', '') + ' Record templates: /metodoloji:init')

try:
    # Reuse the engine's session_start (compact_context + consume session
    # channel + handoff warning); it stamps the marker itself. No dup logic here.
    from modules.audit import session_start as engine_session_start
    res = engine_session_start({'cwd': ws})
    extra = (res or {}).get('additionalContext', '')
    marker = ' Blackboard: '
    if marker in extra:
        ctx += marker + extra.split(marker, 1)[1]
    elif extra and extra not in ctx:
        ctx += ' ' + extra
except Exception:
    try:
        from modules.stop import record_session_start
        record_session_start(ws)
    except Exception:
        pass

print(json.dumps({'additionalContext': ctx}))
" 2>/dev/null || printf '%s\n' "{\"additionalContext\":\"METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY.$SCOPE_CTX Record templates: /metodoloji:init\"}"
exit 0
