#!/bin/sh
# bootstrap.sh — SessionStart: check/create the gate-key and inject short context
# (additionalContext). Non-blocking (fail-open).
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYNCED=$(CDPATH= cd -- "$SELF/../.." && pwd)

WS="${CLAUDE_PROJECT_DIR:-$OPENHANDS_PROJECT_DIR}"
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

# Intent bridge: read the active .memlog.md purpose (if any) and export it so
# every hook process in this session shares the same intent. Parses frontmatter
# inline (no memlog import); converts the workspace path to a Windows-native
# form when cygpath is available so Python resolves it under Git Bash.
PYWS="$WS"
if command -v cygpath >/dev/null 2>&1; then
    PYWS=$(cygpath -w "$WS" 2>/dev/null || echo "$WS")
fi
# Forward-slash form: Windows Python accepts both, but backslashes would be
# escaped as unicode sequences in the inline string literal below.
PYWS=$(printf '%s' "$PYWS" | tr '\\' '/')
INTENT_AND_SCOPE=$(python3 -c "
import pathlib, os, sys
def _fields(root):
    cands = []
    for base in ('bmad-output', '.metodoloji', 'docs', ''):
        p = pathlib.Path(root) / base / '.memlog.md'
        if p.is_file(): cands.append(p)
    if not cands:
        try:
            cands = list(pathlib.Path(root).rglob('.memlog.md'))[:5]
        except OSError:
            cands = []
    if not cands: return '', ''
    newest = max(cands, key=lambda p: p.stat().st_mtime)
    text = newest.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    if not lines or lines[0] != '---': return '', ''
    purpose = scope = ''
    for ln in lines[1:]:
        if ln == '---': break
        if ln.startswith('purpose:'):
            purpose = ln.split(':', 1)[1].strip()
        elif ln.startswith('scope:'):
            scope = ln.split(':', 1)[1].strip()
    return purpose, scope
try:
    p, s = _fields('$PYWS')
    print(p)
    print(s)
except Exception:
    print(''); print('')
" 2>/dev/null || printf '\n\n')
INTENT=$(printf '%s\n' "$INTENT_AND_SCOPE" | sed -n '1p')
SCOPE=$(printf '%s\n' "$INTENT_AND_SCOPE" | sed -n '2p')
export METODOLOJI_INTENT="$INTENT"
export METODOLOJI_SCOPE="$SCOPE"

# Short context: gate-key status + record chain reminder + active intent + code docs.
if [ -f "$HOME/.bmad/gate-key" ]; then KEY="present"; else KEY="MISSING — python3 run_experiment.py --init-secret"; fi
if [ -n "$INTENT" ]; then INTENT_CTX=" Active intent: $INTENT."; else INTENT_CTX=""; fi
if [ -n "$SCOPE" ]; then SCOPE_CTX=" Active scope: $SCOPE."; else SCOPE_CTX=""; fi

# Build full context and output as proper JSON (Python handles escaping).
python3 -c "
import json, sys, os, pathlib

plugin = pathlib.Path('$SYNCED')
sys.path.insert(0, str(plugin / 'hooks' / 'engine'))
os.environ['CLAUDE_PROJECT_DIR'] = '$PYWS'

ctx = 'METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY.$INTENT_CTX$SCOPE_CTX Record templates: /metodoloji:init'

try:
    from modules.code_docs import load_pending_docs, load_recent_docs
    pending = load_pending_docs()
    recent = load_recent_docs(n=5)
    if pending or recent:
        ctx += '\n\n'
    if pending:
        ctx += pending
    if recent:
        if pending:
            ctx += '\n'
        ctx += recent
except Exception:
    pass

print(json.dumps({'additionalContext': ctx}))
" 2>/dev/null || printf '%s\n' "{\"additionalContext\":\"METODOLOJI active (plugin: $SYNCED). Record chain: E → IR → SP → S → QR → PR. Before writing code you need a scope-matching VERIFIED experiment approval; gate key: $KEY.$INTENT_CTX$SCOPE_CTX Record templates: /metodoloji:init\"}"
exit 0
