#!/bin/sh
# check-techdebt.sh — docs/development/tech-debt.md ve templates/tech-debt.md
# envanterinin statik kalite denetimi. TD-002 false-positive monitörün kök
# nedenini mekanik hale getirir: şablon ↔ canlı envanter drift, ID çakışması,
# orphan TODO, P0 limit, ödenmiş/aktif çakışması.
#
#   1. Şablon özdeşliği (templates/tech-debt.md ↔ docs/development/tech-debt.md)
#   2. Aktif borç tablosu: ID benzersiz + sıralı (TD-NNN)
#   3. Aktif P0 sayısı <= 5 (manifesto hard limit)
#   4. Ödenmiş/aktif ID çakışması yok
#   5. Orphan TODO: kayıttaki her TD-XXX için ya aktif tabloda ya da ödenmiş
#      tabloda referans var; comment'lerdeki [TD-XXX] her zaman envanterde
#
# Kullanım:  sh commands/check-techdebt.sh
#            sh commands/check-techdebt.sh --negtest
#            (yalnızca negatif test: ID çakışması + orphan TODO enjekte →
#             MISS yakala → geri yükle)
# Çıkış:     her satırın başında [OK] / [UYARI] / [HATA]; sonunda genel durum.
set -u

PROBLEMS=0

if [ "${1:-}" = "--negtest" ]; then
    SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
    PY=
    for cand in python3 python py; do
        if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
    done
    if [ -z "$PY" ]; then
        echo "[HATA] python3/python/py bulunamadı — negatif test çalışamaz." >&2
        exit 1
    fi
    PLUGIN_ROOT="$PLUGIN_ROOT" "$PY" - <<'PY'
import os, re, subprocess, sys
from pathlib import Path

PLUGIN = Path(os.environ["PLUGIN_ROOT"])
td = PLUGIN / "docs" / "development" / "tech-debt.md"
check_script = PLUGIN / "commands" / "check-techdebt.sh"
total_stages = 3

def run_check() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(check_script)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        cwd=str(PLUGIN),
    )

orig = td.read_text(encoding="utf-8")

# Aşama 1/3: Aktif tabloya duplicate ID (TD-010, hem aktif hem ödenmiş)
# ekleyince §4 çakışma UYARI + §3 P0 sınırı tetiklenir mi?
print(f"[1/{total_stages}] aktif tabloya duplicate TD-010 eklenince §4 çakışma yakalıyor mu")
# Aktif tabloya TD-010 satırı ekleyelim (P0 olarak), ödenmiş tabloda zaten var.
# Fallback zinciri: P0 placeholder → TD-003 (P2) → TD-001 (eski varsayım)
new_row = "| TD-010 | duplicate-test | test | 2026-08-26 | Test | @test | SP-001 |\n"
broken = re.sub(
    r"(\| —    \| —     \| —             \| —             \| —    \| —      \| —            \|\n)",
    r"\1" + new_row, orig, count=1)
if "TD-010 | duplicate-test" not in broken:
    broken = re.sub(r"(\| TD-003 \|[^\n]+\n)", r"\1" + new_row, orig, count=1)
if "TD-010 | duplicate-test" not in broken:
    broken = re.sub(r"(\| TD-001 \|[^\n]+\n)", r"\1" + new_row, orig, count=1)
td.write_text(broken, encoding="utf-8")
try:
    r = run_check()
    if "TD-010" in r.stdout and "hem aktif hem ödenmiş" in r.stdout and r.returncode == 1:
        print("  [OK] §4 çakışma yakalandı, exit=1")
    else:
        print(f"  [HATA] §4 çakışma bekleniyordu, çıktı sonu: ...{r.stdout[-400:]!r}")
        sys.exit(1)
finally:
    td.write_text(orig, encoding="utf-8")

# Aşama 2/3: Aktif P0 sayısı 6'ya çıkarıldığında §3 hard limit devreye giriyor mu?
print(f"[2/{total_stages}] P0 sayısı 6 olduğunda §3 hard limit devreye giriyor mu")
# P0 bölümünün "—    | —" placeholder satırını bul ve 5 yeni P0 satırı ekle.
# Eğer TD-001 gibi gerçek bir P0 satırı varsa ondan sonra ekler; yoksa
# placeholder'dan sonra ekler.
broken = re.sub(
    r"(\| —    \| —     \| —             \| —             \| —    \| —      \| —            \|\n)",
    r"\1| TD-101 | P0-test-1 | t | 2026-08-26 | Test | @t | SP-001 |\n"
    r"| TD-102 | P0-test-2 | t | 2026-08-26 | Test | @t | SP-001 |\n"
    r"| TD-103 | P0-test-3 | t | 2026-08-26 | Test | @t | SP-001 |\n"
    r"| TD-104 | P0-test-4 | t | 2026-08-26 | Test | @t | SP-001 |\n"
    r"| TD-105 | P0-test-5 | t | 2026-08-26 | Test | @t | SP-001 |\n"
    r"| TD-106 | P0-test-6 | t | 2026-08-26 | Test | @t | SP-001 |\n",
    orig, count=1)
# Eğer placeholder yoksa, TD-001 satırından sonra ekle (eski davranış).
if "P0-test-1" not in broken:
    broken = re.sub(
        r"(\| TD-001 \|[^\n]+\n)",
        r"\1| TD-101 | P0-test-1 | t | 2026-08-26 | Test | @t | SP-001 |\n"
        r"| TD-102 | P0-test-2 | t | 2026-08-26 | Test | @t | SP-001 |\n"
        r"| TD-103 | P0-test-3 | t | 2026-08-26 | Test | @t | SP-001 |\n"
        r"| TD-104 | P0-test-4 | t | 2026-08-26 | Test | @t | SP-001 |\n"
        r"| TD-105 | P0-test-5 | t | 2026-08-26 | Test | @t | SP-001 |\n"
        r"| TD-106 | P0-test-6 | t | 2026-08-26 | Test | @t | SP-001 |\n",
        orig, count=1)
td.write_text(broken, encoding="utf-8")
try:
    r = run_check()
    if "Aktif P0 sayısı 6 > 5" in r.stdout and r.returncode == 1:
        print("  [OK] §3 hard limit yakalandı, exit=1")
    else:
        print(f"  [HATA] §3 hard limit bekleniyordu, çıktı sonu: ...{r.stdout[-400:]!r}")
        sys.exit(1)
finally:
    td.write_text(orig, encoding="utf-8")

# Aşama 3/3: Orphan TODO: TD-999 scratch/ içine inject → §5 yakalıyor mu?
# (envanter dosyası §5 kapsamı dışında — oraya yazmak meşru referans olur)
print(f"[3/{total_stages}] orphan TODO [TD-999] scratch/ içine enjekte edildiğinde §5 yakalıyor mu")
negtest_artifact = PLUGIN / "scratch" / "_negtest_orphan.py"
artifact_orig = None
if negtest_artifact.exists():
    artifact_orig = negtest_artifact.read_text(encoding="utf-8")
try:
    negtest_artifact.write_text(
        "# TODO: [TD-999] orphan-test-comment (negtest artifact, silinecek)\n",
        encoding="utf-8")
    r = run_check()
    if "TD-999" in r.stdout and "orphan" in r.stdout and r.returncode == 1:
        print("  [OK] §5 orphan TODO yakalandı, exit=1")
    else:
        print(f"  [HATA] §5 orphan TODO bekleniyordu, çıktı sonu: ...{r.stdout[-400:]!r}")
        sys.exit(1)
finally:
    if artifact_orig is None:
        negtest_artifact.unlink(missing_ok=True)
    else:
        negtest_artifact.write_text(artifact_orig, encoding="utf-8")

print(f"[OK] tüm {total_stages} negtest aşaması başarılı")
sys.exit(0)
PY
    exit $?
fi

# Normal mod: PLUGIN_ROOT ve dosya yolları
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)

TEMPLATE="$PLUGIN_ROOT/templates/tech-debt.md"
LIVE="$PLUGIN_ROOT/docs/development/tech-debt.md"

echo "== 1) Şablon özdeşliği (templates/ ↔ docs/development/) =="
if [ ! -f "$TEMPLATE" ]; then
    echo "[HATA] $TEMPLATE bulunamadı"
    PROBLEMS=$((PROBLEMS + 1))
elif [ ! -f "$LIVE" ]; then
    echo "[HATA] $LIVE bulunamadı"
    PROBLEMS=$((PROBLEMS + 1))
elif diff -q "$TEMPLATE" "$LIVE" >/dev/null 2>&1; then
    echo "[OK]   templates/tech-debt.md ↔ docs/development/tech-debt.md özdeş"
else
    echo "[HATA] templates/tech-debt.md ↔ docs/development/tech-debt.md DRİFT (fark var)"
    PROBLEMS=$((PROBLEMS + 1))
fi

if [ ! -f "$LIVE" ]; then
    echo
    echo "DURUM: $PROBLEMS sorun bulundu (LIVE dosyası yok, sonraki bölümler atlandı)"
    [ "$PROBLEMS" -eq 0 ] && exit 0 || exit 1
fi

echo "== 2) Aktif borç tablosu: ID'ler benzersiz ve sıralı mı =="
# Aktif tablo: "## Aktif Teknik Borçlar" ile "## Ödenmiş Borçlar" arası
ACTIVE_IDS=$(awk '/^## Aktif Teknik Borçlar/{flag=1; next} /^## Ödenmiş Borçlar/{flag=0} flag && /^\| TD-/{print $2}' "$LIVE" | sed 's/|//g')
DUPES=$(echo "$ACTIVE_IDS" | sort | uniq -d)
if [ -n "$DUPES" ]; then
    echo "[HATA] aktif tabloda tekrar eden ID: $(echo $DUPES | tr '\n' ' ')"
    PROBLEMS=$((PROBLEMS + 1))
else
    echo "[OK]   aktif tabloda tekrar eden ID yok ($(echo "$ACTIVE_IDS" | wc -l | tr -d ' ') benzersiz)"
fi
# Sıralılık: TD-NNN numerik artan mı
SORTED=$(echo "$ACTIVE_IDS" | sort -t- -k2 -n)
if [ "$ACTIVE_IDS" = "$SORTED" ]; then
    echo "[OK]   aktif tablo ID'leri numerik sıralı"
else
    echo "[UYARI] aktif tablo ID'leri sıralı değil (beklenen artan TD-NNN)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 3) Aktif P0 sayısı hard limit (<= 5) =="
# P0 satırları: "### Kritik Öncelik (P0)" bölümü içindeki | TD-... | satırları
P0_COUNT=$(awk '/^### Kritik Öncelik/{flag=1; next} /^### /{flag=0} flag && /^\| TD-/{count++} END{print count+0}' "$LIVE")
if [ "$P0_COUNT" -le 5 ]; then
    echo "[OK]   aktif P0 = $P0_COUNT (<= 5 limit)"
else
    echo "[HATA] Aktif P0 sayısı $P0_COUNT > 5 — manifesto hard limiti aşıldı (yeni feature alınmaz)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 4) Aktif/Ödenmiş ID çakışması yok =="
PAID_IDS=$(awk '/^## Ödenmiş Borçlar/{flag=1; next} flag && /^\| TD-/{print $2}' "$LIVE" | sed 's/|//g')
# POSIX uyumlu kesişim: iki listeyi sırala, geçici dosyalardan comm ile
TMPA=$(mktemp); TMPB=$(mktemp)
trap 'rm -f "$TMPA" "$TMPB"' EXIT
echo "$ACTIVE_IDS" | sort -u > "$TMPA"
echo "$PAID_IDS"   | sort -u > "$TMPB"
OVERLAP=$(comm -12 "$TMPA" "$TMPB" | tr -d '[:space:]')
if [ -z "$OVERLAP" ]; then
    echo "[OK]   aktif ve ödenmiş tablolar ayrık (TD-XXX çakışması yok)"
else
    echo "[HATA] TD-XXX hem aktif hem ödenmiş: $(echo $OVERLAP | tr '\n' ' ')"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 5) Orphan TODO [TD-XXX] envanter dışında referans yok mu =="
# TODO comment standardı: "# TODO: [TD-XXX]" veya "<!-- TODO: [TD-XXX]"
# Envanterdeki tüm ID'ler
ALL_IDS=$(printf '%s\n%s\n' "$ACTIVE_IDS" "$PAID_IDS" | sort -u | grep -v '^$' || true)
# TODO'larda geçen ID'ler (derleme artifact'leri ve scratch dizinleri dışlanır)
TODO_IDS=$(grep -rhoE --binary-files=without-match \
    'TODO:[[:space:]]*\[TD-[0-9]+\]' \
    --exclude-dir=__pycache__ --exclude='*.pyc' \
    --exclude-dir=_generated_splits --exclude-dir=.metodoloji \
    "$PLUGIN_ROOT/scratch/" "$PLUGIN_ROOT/custom/" 2>/dev/null \
    | sed -E 's/.*\[(TD-[0-9]+)\].*/\1/' | sort -u)
if [ -z "$TODO_IDS" ]; then
    echo "[OK]   TODO comment taranan dizinlerde yok (scratch/, custom/)"
else
    TMPC=$(mktemp); TMPD=$(mktemp)
    trap 'rm -f "$TMPC" "$TMPD"' EXIT
    echo "$TODO_IDS" > "$TMPC"
    echo "$ALL_IDS"   > "$TMPD"
    ORPHANS=$(comm -23 "$TMPC" "$TMPD" | tr -d '[:space:]')
    if [ -n "$ORPHANS" ]; then
        echo "[HATA] orphan TODO (envanterde yok): $(echo $ORPHANS | tr '\n' ' ')"
        PROBLEMS=$((PROBLEMS + 1))
    else
        echo "[OK]   tüm TODO [TD-XXX] envanterde kayıtlı"
    fi
fi

echo
if [ "$PROBLEMS" -eq 0 ]; then
    echo "DURUM: SAĞLIKLI (tech-debt envanter bütün)"
    exit 0
else
    echo "DURUM: $PROBLEMS sorun bulundu"
    exit 1
fi
