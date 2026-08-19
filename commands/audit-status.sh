#!/bin/sh
# audit-status.sh — Periyodik denetim: metodoloji durumunu kontrol et
# Kullanım: sh audit-status.sh

echo "=== BMAD Metodolojisi Durum Raporu ==="
echo "Tarih: $(date)"
echo

# 1. Gate Key Durumu
echo "1. Gate Key:"
if [ -f "$HOME/.bmad/gate-key" ]; then
    echo "   ✓ Kurulu ($(wc -c < "$HOME/.bmad/gate-key") bayt)"
else
    echo "   ✗ Yok (python3 run_experiment.py --init-secret ile oluşturun)"
fi

# 2. Deney Kayıtları
echo "2. Deney Kayıtları:"
if [ -d "docs/experiments" ]; then
    COUNT=$(ls -1 docs/experiments/*.md 2>/dev/null | wc -l)
    echo "   $COUNT kayıt var"
    ls -1 docs/experiments/*.md 2>/dev/null | head -5
else
    echo "   ✗ docs/experiments/ dizini yok"
fi

# 3. Hook Log Durumu
echo "3. Hook Logları:"
if [ -f ".metodoloji/logs/hook-audit.log" ]; then
    LINES=$(wc -l < ".metodoloji/logs/hook-audit.log")
    echo "   $LINES satır log var"
else
    echo "   ✗ Log dosyası yok"
fi

# 4. Plugin Dizin Yapısı
echo "4. Plugin Yapısı:"
echo "   Skills: $(ls -1 skills/ 2>/dev/null | wc -l) adet"
echo "   Custom TOML: $(ls -1 custom/*.toml 2>/dev/null | wc -l) adet"
echo "   Commands: $(ls -1 commands/*.md 2>/dev/null | wc -l) adet"

# 5. Guard Hook Testi
echo "5. Guard Hook Testi:"
RESULT=$(echo '{"tool_name": "terminal", "tool_input": {"command": "ls"}}' | python3 hooks/engine/main.py guard 2>/dev/null)
if echo "$RESULT" | grep -q '"allow"'; then
    echo "   ✓ Guard hook çalışıyor"
else
    echo "   ✗ Guard hook sorunlu: $RESULT"
fi

echo
echo "=== Rapor Sonu ==="
