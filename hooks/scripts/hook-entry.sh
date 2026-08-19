#!/bin/sh
# hook-entry.sh — tek çözümleme noktası: engine'i bul, python'a ver, politikayı uygula.
# Kullanım: sh hook-entry.sh <guard|quality|deploy|stop|audit>
# Politikalar (Claude parity):
#   guard/stop     fail-closed  (engine yoksa deny + exit 2)
#   quality/deploy fail-open    (engine yoksa sessiz geç)
#   audit          fail-open
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/../.." && pwd)
ENGINE="$PLUGIN_ROOT/hooks/engine/bmad-hooks.py"
MODE="$1"

PY=
for c in python3 python py; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done

_fail() {
    case "$MODE" in
        guard|stop)
            printf '%s\n' '{"decision":"deny","reason":"Metodoloji hook motoru çalışamadı (python yok ya da engine eksik) — fail-closed engellendi."}'
            exit 2
            ;;
        *)  exit 0 ;;
    esac
}

if [ -z "$PY" ] || [ ! -f "$ENGINE" ]; then
    _fail
fi

case "$MODE" in
    guard)   SUB=guard ;;
    quality) SUB=quality-gate ;;
    deploy)  SUB=deploy-guard ;;
    stop)    SUB=stop ;;
    audit)   SUB=audit ;;
    *)       _fail ;;
esac

exec "$PY" "$ENGINE" "$SUB" --runtime=openhands
