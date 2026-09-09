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

# Intent bridge: blackboard'daki purpose (intent) ve scope'u oku, env'e export et.
# Her hook prosesi aynı session intent'ini paylaşır. Fail-open (okuma hatası → boş).
PYWS="$WS"
if command -v cygpath >/dev/null 2>&1; then
    PYWS=$(cygpath -w "$WS" 2>/dev/null || echo "$WS")
fi
PYWS=$(printf '%s' "$PYWS" | tr '\\' '/')
INTENT_AND_SCOPE=$("$PY" -c "
import sys, os, pathlib
sys.path.insert(0, str(pathlib.Path('$PYWS') / '..' / 'hooks' / 'engine') if False else '')
try:
    import json
    plugin = pathlib.Path('$SYNCED')
    sys.path.insert(0, str(plugin / 'hooks' / 'engine'))
    os.environ['CLAUDE_PROJECT_DIR'] = '$PYWS'
    from modules.config import blackboard_enabled
    if not blackboard_enabled():
        print(''); print('')
    else:
        from modules import blackboard as bb
        board = bb.read_board('$PYWS')
        keys = board.get('keys', {})
        intent = ''
        for field in ('purpose', 'topic', 'goal', 'idea'):
            entry = keys.get(field)
            if entry and isinstance(entry, dict):
                val = str(entry.get('value', '')).strip()
                if val:
                    intent = val
                    break
        scope_entry = keys.get('scope')
        scope = str(scope_entry.get('value', '')).strip() if scope_entry and isinstance(scope_entry, dict) else ''
        print(intent)
        print(scope)
except Exception:
    print(''); print('')
" 2>/dev/null || printf '\n\n')
INTENT=$(printf '%s\n' "$INTENT_AND_SCOPE" | sed -n '1p')
SCOPE=$(printf '%s\n' "$INTENT_AND_SCOPE" | sed -n '2p')
export METODOLOJI_INTENT="$INTENT"
export METODOLOJI_SCOPE="$SCOPE"
if [ -n "$INTENT" ]; then INTENT_CTX=" Active intent: $INTENT."; else INTENT_CTX=""; fi
if [ -n "$SCOPE" ]; then SCOPE_CTX=" Active scope: $SCOPE."; else SCOPE_CTX=""; fi

# Build full context and output as proper JSON (Python handles escaping).
"$PY" -c "
import json, sys, os, pathlib

plugin = pathlib.Path('$SYNCED')
sys.path.insert(0, str(plugin / 'hooks' / 'engine'))
os.environ['CLAUDE_PROJECT_DIR'] = '$PYWS'

ctx = 'METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY.$INTENT_CTX$SCOPE_CTX Record templates: /metodoloji:init'

try:
    from modules.stop import record_session_start
    record_session_start('$PYWS')
except Exception:
    pass

print(json.dumps({'additionalContext': ctx}))
" 2>/dev/null || printf '%s\n' "{\"additionalContext\":\"METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY.$INTENT_CTX$SCOPE_CTX Record templates: /metodoloji:init\"}"
exit 0
