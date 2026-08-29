#!/bin/sh
# bootstrap.sh — SessionStart: gate-key durumunu kontrol/oluşturur ve kısa bağlam
# enjekte eder (additionalContext). Bloklayıcı değildir (fail-open).
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SYNCED=$(CDPATH= cd -- "$SELF/../.." && pwd)

WS="$OPENHANDS_PROJECT_DIR"
[ -z "$WS" ] && WS=$(pwd)

# Otomatik kurulum: Gate key yoksa oluştur
if [ ! -f "$HOME/.bmad/gate-key" ]; then
    mkdir -p "$HOME/.bmad"
    # Basit bir gate key oluştur (HMAC için yeterli)
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$HOME/.bmad/gate-key"
    chmod 600 "$HOME/.bmad/gate-key"
fi

# Eksik dizinleri oluştur
mkdir -p "$WS/docs/experiments"
mkdir -p "$WS/.metodoloji/logs"

# Kısa bağlam: gate-key durumu + kayıt zinciri hatırlatması.
if [ -f "$HOME/.bmad/gate-key" ]; then KEY="kurulu"; else KEY="YOK — python3 run_experiment.py --init-secret"; fi
printf '%s\n' "{\"additionalContext\":\"METODOLOJI aktif (plugin: $SYNCED). Kayıt zinciri: E → IR → SP → S → QR → PR. Kod yazmadan önce kapsamı eşleşen VERIFIED deney onayı gerekir; kapı anahtarı: $KEY. Kayıt şablonları için: /metodoloji:init\"}"
exit 0
