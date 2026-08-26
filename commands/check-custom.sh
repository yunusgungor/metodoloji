#!/bin/sh
# check-custom.sh — custom/ köprü TOML'lerinin statik kalite denetimi.
#
#   0. TOML parse + tablo varlığı
#   1. Persistent-facts üçlüsü  (research / development / project-context)
#   2. activation_steps_append derinliği
#        Gate uygulayıcılar (GATE_REQUIRED)  → >= 3 adım
#        Diğer workflow'lar (MOD_A_RECORD_ONLY + araçlar) → >= 1 adım
#   3. Hard-gate anahtar kelimeleri
#        GATE_REQUIRED    → ONAYLANDI/REDDEDİLDİ/FORGED/VERIFIED olmalı
#        GATE_REFERENCE_OK → referans olarak taşıyabilir (örn. bmad-tea)
#        Diğerleri → sızıntı (yanlış katmanda) → fail
#   4. Köprü DOGRULAMA kalıbı (gate uygulayıcılar: "ls -la ... HATA ver")
#   5. gds-* Mod A köprü referansı (dev-skill-to-methodology-bridge zorunlu)
#   6. config.toml [hooks] soft/hard sözleşmesi (DRY: §5b ile aynı parser)
#   7. Köprü belge §N.N referans drift denetimi (bridge.md bölümleriyle senkron)
#
# Kullanım:  sh commands/check-custom.sh
#            sh commands/check-custom.sh --negtest
#            (yalnızca negatif test: §3 hard-gate + §7 bridge drift → MISS
#             yakala → geri yükle)
# Çıkış:     her satırın başında [OK] / [UYARI] / [HATA]; sonunda genel durum.
set -u

PROBLEMS=0

if [ "${1:-}" = "--negtest" ]; then
    # Negatif test 1: §3 hard-gate — bmad-dev-story.toml'dan hard-gate
    # anahtar kelimelerini (ONAYLANDI / REDDEDİLDİ / FORGED / VERIFIED) geçici
    # kaldır, §3 mantığının MISS ürettiğini doğrula, dosyayı geri yükle.
    # Negatif test 2: §7 bridge drift — bridge.md'den "### §2.3" başlığını
    # geçici kaldır, custom/ dosyalarındaki §2.3 referanslarından dolayı §7
    # mantığının MISS ürettiğini doğrula, bridge'i geri yükle.
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
toml = PLUGIN / "custom" / "bmad-dev-story.toml"
bridge = PLUGIN / "docs" / "bmad" / "dev-skill-to-methodology-bridge.md"
KEYWORDS = ("ONAYLANDI", "REDDEDİLDİ", "FORGED", "VERIFIED")

orig_toml = toml.read_text(encoding="utf-8")
orig_bridge = bridge.read_text(encoding="utf-8")

# ---- Test 1: §3 hard-gate ----
def has_dev_story_gate_error(text: str) -> bool:
    toml.write_text(text, encoding="utf-8")
    try:
        r = subprocess.run(
            ["sh", str(PLUGIN / "commands" / "check-custom.sh")],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        out = r.stdout
        for line in out.splitlines():
            if "bmad-dev-story" in line and "hard-gate" in line:
                return True
        return False
    finally:
        toml.write_text(orig_toml, encoding="utf-8")

if has_dev_story_gate_error(orig_toml):
    print("[HATA] sağlam custom TOML'da bile hard-gate hatası görünüyor — test kurulumu bozuk")
    sys.exit(1)

broken_toml = "\n".join(
    l for l in orig_toml.splitlines()
    if not any(k in l for k in KEYWORDS)
)
removed = (orig_toml.count("ONAYLANDI") + orig_toml.count("REDDEDİLDİ")
           + orig_toml.count("FORGED") + orig_toml.count("VERIFIED"))
removed_after = (broken_toml.count("ONAYLANDI") + broken_toml.count("REDDEDİLDİ")
                 + broken_toml.count("FORGED") + broken_toml.count("VERIFIED"))
if removed == removed_after or removed == 0:
    print("[HATA] anahtar kelimeler bulunamadı veya temizlenemedi — test kurulumu bozuk")
    sys.exit(1)

if not has_dev_story_gate_error(broken_toml):
    print("[HATA] negatif test 1 başarısız: hard-gate silindiği halde §3 mantığı yakalamadı")
    sys.exit(1)
print("[OK]   negatif test 1/2: hard-gate anahtar kelimeleri silindi → §3 MISS yakalandı")

# ---- Test 2: §7 bridge drift ----
def has_bridge_drift_error(bridge_text: str) -> bool:
    """§7 drift: bridge'den §2.3 kaldırıldığında custom/ dosyalarındaki §2.3
    referanslarından dolayı 'köprü §N.N drift' UYARI satırı çıkmalı."""
    bridge.write_text(bridge_text, encoding="utf-8")
    try:
        r = subprocess.run(
            ["sh", str(PLUGIN / "commands" / "check-custom.sh")],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        out = r.stdout
        for line in out.splitlines():
            if "köprü §N.N drift" in line or "bridge'de olmayan" in line:
                return True
        return False
    finally:
        bridge.write_text(orig_bridge, encoding="utf-8")

if has_bridge_drift_error(orig_bridge):
    print("[HATA] sağlam bridge'de bile drift hatası görünüyor — test kurulumu bozuk")
    sys.exit(1)

# bridge'den "### §2.3" bloğunu satır-bazlı sil: başlık satırından sonraki
# `### ` veya `## ` başlığına kadar. Drift testinin minimum müdahalesi.
def remove_section_23(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out = []
    skip = False
    for line in lines:
        if line.startswith("### §2.3"):
            skip = True
            continue
        if skip and (line.startswith("### ") or line.startswith("## ")):
            skip = False
        if not skip:
            out.append(line)
    return "".join(out)

broken_bridge = remove_section_23(orig_bridge)
if "### §2.3" in broken_bridge or "§2.3" in broken_bridge:
    print("[HATA] bridge'den §2.3 silinemedi — başlık farklı veya eşleşmedi")
    sys.exit(1)

if not has_bridge_drift_error(broken_bridge):
    print("[HATA] negatif test 2 başarısız: §2.3 bridge'den silindiği halde §7 mantığı yakalamadı")
    sys.exit(1)
print("[OK]   negatif test 2/2: bridge §2.3 silindi → §7 MISS yakalandı → bridge geri yüklendi")
sys.exit(0)
PY
    exit $?
fi

# (Ana akış aşağıda)

SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
export PLUGIN_ROOT

# Python çözücü (check-plugin.sh ile aynı kural).
PY=
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "[HATA] python3/python/py bulunamadı — check-custom çalışamaz." >&2
    exit 1
fi

echo "== 0) TOML parse + tablo varlığı =="
"$PY" - <<'PY'
import glob, os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
problems = []
checked = 0
for path in sorted(glob.glob(os.path.join(PLUGIN, "custom", "*.toml"))):
    name = os.path.basename(path)
    if name == "config.toml":
        continue  # §6'da ayrı denetleniyor
    checked += 1
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception as e:
        problems.append("%s: parse hatası — %s" % (name, e))
        continue
    if not any(sec in data for sec in ("workflow", "agent")):
        problems.append("%s: [workflow] veya [agent] tablosu yok" % name)

print("  denetlenen custom dosyası: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   tüm custom TOML'leri parse ediyor ve tablo içeriyor"
else
    echo "[UYARI] parse/tablo sorunu (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 1) Persistent-facts üçlüsü (research / development / project-context) =="
"$PY" - <<'PY'
import glob, os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
# Geliştirme kanadı — bu listede olanlar üçlüyü (research + development +
# project-context) yüklemeli. Listede olmayanlar için tek zorunluluk
# project-context.md'dir; diğer manifesto işaretçileri opsiyonel kalır.
# Not: bmad-eval-runner / bmad-research-experiment / bmad-review-* bilinçli
# olarak listede değil — bunlar "kod yazmaz, ölçer/denetler" ve sadece
# research manifestosunu yükler (deney kaydı üretir).
DEV_WING = {
    "bmad-check-implementation-readiness", "bmad-prd", "bmad-ux",
    "bmad-create-architecture", "bmad-sprint-planning", "bmad-create-story",
    "bmad-create-epics-and-stories", "bmad-dev-story", "bmad-quick-dev",
    "bmad-dev-auto",
    "bmad-testarch-atdd", "bmad-testarch-automate", "bmad-testarch-ci",
    "bmad-testarch-framework", "bmad-testarch-nfr", "bmad-testarch-test-design",
    "bmad-testarch-test-review", "bmad-testarch-trace",
    "bmad-code-review",
    "bmad-qa-generate-e2e-tests",
    "bmad-document-project",
    "bmad-retrospective", "bmad-correct-course", "bmad-sprint-status",
    "bmad-agent-dev", "bmad-agent-architect", "bmad-agent-pm",
    "bmad-agent-ux-designer", "bmad-agent-tech-writer", "bmad-tea",
}

problems = []
checked = 0
for path in sorted(glob.glob(os.path.join(PLUGIN, "custom", "*.toml"))):
    name = os.path.basename(path)[:-5]  # strip .toml
    if name == "config":
        continue
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception:
        continue  # §0 zaten raporladı
    checked += 1
    facts = []
    for sec in ("workflow", "agent"):
        facts += data.get(sec, {}).get("persistent_facts", []) or []
    if not facts:
        problems.append("%s: persistent_facts yok" % name)
        continue
    if not any("project-context.md" in x for x in facts):
        problems.append("%s: project-context.md işaretçisi yok" % name)
    if name in DEV_WING:
        if not any("research-methodology.md" in x for x in facts):
            problems.append("%s: research-methodology.md işaretçisi yok (DEV kanat)" % name)
        if not any("development-methodology.md" in x for x in facts):
            problems.append("%s: development-methodology.md işaretçisi yok (DEV kanat)" % name)

print("  denetlenen: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   persistent_facts üçlüsü tüm yüzeylerde"
else
    echo "[UYARI] persistent_facts eksik (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 2) activation_steps_append derinliği =="
"$PY" - <<'PY'
import glob, os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
# Gate UYGULAYAN yüzeyler (kod yazar / merge denetler) — min 3 adım:
#   köprü talimatı + en az bir verify kalıbı + DOGRULAMA adımı
# Gate uygulamayan Mod A yüzeyler (kayıt üretir ama kod yazmaz) — min 1 adım.
# Bu ayrım, hard-gate sözleşmesinin fiilen kullanan dosyaları hedefler.
GATE_REQUIRED = {
    "bmad-dev-story", "bmad-dev-auto", "bmad-quick-dev",
    "bmad-code-review", "bmad-agent-dev",
    "bmad-create-story",   # AC'de experiment ONAYLANDI kontrolü = gate doğrulayıcısı
    "gds-dev-story", "gds-quick-dev", "gds-code-review",
    "gds-create-story",    # gds create-story de aynı şekilde doğrulayıcı
    "gds-agent-game-dev", "wds-agent-mimir-builder",
}
MOD_A_RECORD_ONLY = {
    "bmad-research-experiment", "bmad-check-implementation-readiness",
    "bmad-sprint-planning",
    "gds-check-implementation-readiness",
    "gds-sprint-planning",
}
MIN_RECORD = 1
MIN_GATE = 3

problems = []
checked = 0
for path in sorted(glob.glob(os.path.join(PLUGIN, "custom", "*.toml"))):
    name = os.path.basename(path)[:-5]
    if name == "config":
        continue
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception:
        continue
    checked += 1
    asa = data.get("workflow", {}).get("activation_steps_append", []) or []
    n = len(asa)
    if n == 0:
        # [agent] dosyaları boş olabilir (activation_steps_append yok, normal).
        if "agent" in data and "workflow" not in data:
            continue
        problems.append("%s: activation_steps_append boş (workflow dosyası)" % name)
        continue
    if name in GATE_REQUIRED:
        if n < MIN_GATE:
            problems.append("%s: gate uygulayıcısı ama derinlik=%d (>= %d olmalı)" %
                            (name, n, MIN_GATE))
    else:
        if n < MIN_RECORD:
            problems.append("%s: derinlik=%d (>= %d olmalı)" % (name, n, MIN_RECORD))

print("  denetlenen: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   activation_steps_append derinliği kurala uygun"
else
    echo "[UYARI] derinlik ihlali (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 3) Hard-gate anahtar kelimeleri (ONAYLANDI / REDDEDİLDİ / FORGED / VERIFIED) =="
"$PY" - <<'PY'
import glob, os, re, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
# Mod A: gate'i ÜRETEN veya UYGULAYAN yüzeyler — hard-gate kelimesi zorunlu.
# Bu set, hard-gate'in fiilen kullanıldığı (kod yazan / merge denetleyen /
# mekanik onaylayan) dosyaları kapsar. Belgesel üretim yapan (kayıt üreten
# ama gate uygulamayan) yüzeyler burada DEĞİLDİR.
GATE_REQUIRED = {
    "bmad-dev-story", "bmad-dev-auto", "bmad-quick-dev",
    "bmad-code-review", "bmad-agent-dev",
    "bmad-create-story",   # AC'de experiment ONAYLANDI kontrolü = gate doğrulayıcısı
    "gds-dev-story", "gds-quick-dev", "gds-code-review",
    "gds-create-story",    # gds create-story de aynı şekilde doğrulayıcı
    "gds-agent-game-dev", "wds-agent-mimir-builder",
}
# Gate'i referans olarak taşıyan ama uygulamayan yüzeyler (prensip bildirimi
# veya eğitim amaçlı). Bu listede olanlar için hard-gate kelimesi sızıntı
# sayılmaz; başka hiçbir yüzeyde görünürse hata olur.
GATE_REFERENCE_OK = {
    "bmad-tea",  # test stratejisi belgesel: "Mod A mekanik onayına bağlı" der
}
# Hem activation_steps_append'te hem principles'te geçebilir.
KEYWORDS = ("ONAYLANDI", "REDDEDİLDİ", "FORGED", "VERIFIED")

problems = []
checked = 0
for path in sorted(glob.glob(os.path.join(PLUGIN, "custom", "*.toml"))):
    name = os.path.basename(path)[:-5]
    if name == "config":
        continue
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception:
        continue
    checked += 1
    blob_parts = []
    for sec in ("workflow", "agent"):
        s = data.get(sec, {})
        blob_parts += s.get("activation_steps_append", []) or []
        blob_parts += s.get("principles", []) or []
    blob = "\n".join(blob_parts)
    has_gate = any(k in blob for k in KEYWORDS)
    if name in GATE_REQUIRED:
        if not has_gate:
            problems.append("%s: hard-gate uygulayıcısı ama anahtar kelime yok "
                            "(%s bekleniyordu)" % (name, "|".join(KEYWORDS)))
    elif name not in GATE_REFERENCE_OK and has_gate:
        problems.append("%s: Mod A dışı ama hard-gate anahtar kelimesi sızmış — "
                        "yanlış katmanda; kontrol et" % name)

print("  denetlenen: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   hard-gate anahtar kelimeleri doğru katmanda"
else
    echo "[UYARI] hard-gate sızıntısı veya eksikliği (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 4) Köprü DOGRULAMA kalıbı (Mod A) =="
"$PY" - <<'PY'
import glob, os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
# DOGRULAMA kalıbı: append içinde hem "DOGRULAMA" hem de "HATA ver" geçmeli.
# Bu, LLM'in dosyayı oluşturduktan sonra terminal ile doğrulamasını zorunlu kılar.
# Sadece gate uygulayan yüzeyler için (kod yazan / merge denetleyen / köprü
# üreten); belgesel kayıt üreticiler (research-experiment, sprint-planning
# vb.) kendi --validate hattına güvenir.
KOPRU = {
    "bmad-dev-story", "bmad-dev-auto", "bmad-quick-dev",
    "bmad-code-review", "bmad-create-story",
    "gds-dev-story", "gds-code-review", "gds-quick-dev",
}

problems = []
checked = 0
for name in sorted(KOPRU):
    path = os.path.join(PLUGIN, "custom", name + ".toml")
    if not os.path.isfile(path):
        continue
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception:
        continue
    checked += 1
    asa = data.get("workflow", {}).get("activation_steps_append", []) or []
    blob = "\n".join(asa)
    if "DOGRULAMA" not in blob or "HATA ver" not in blob:
        problems.append("%s: DOGRULAMA + 'HATA ver' kalıbı eksik" % name)

print("  denetlenen köprü skill: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   tüm köprü skill'lerinde DOGRULAMA+HATA kalıbı mevcut"
else
    echo "[UYARI] DOGRULAMA kalıbı eksik (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 5) gds-* Mod A köprü referansı (dev-skill-to-methodology-bridge) =="
# Not: hard-gate anahtar kelimesi denetimi §3'te yapılıyor; burada sadece
# bmm modülünün (gds) köprü dokümanına açık referans verip vermediğini
# kontrol ediyoruz — DRY (hard-gate çift raporu yok).
"$PY" - <<'PY'
import glob, os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
GDS_MOD_A = {
    "gds-dev-story", "gds-create-story",
    "gds-code-review", "gds-quick-dev",
}

problems = []
checked = 0
for name in sorted(GDS_MOD_A):
    path = os.path.join(PLUGIN, "custom", name + ".toml")
    if not os.path.isfile(path):
        continue
    try:
        data = tomllib.load(open(path, "rb"))
    except Exception:
        continue
    checked += 1
    blob_parts = []
    for sec in ("workflow", "agent"):
        s = data.get(sec, {})
        blob_parts += s.get("activation_steps_append", []) or []
        blob_parts += s.get("principles", []) or []
    blob = "\n".join(blob_parts)
    if "dev-skill-to-methodology-bridge" not in blob:
        problems.append("%s: köprü referansı yok (gds Mod A bmm sözleşmesi)" % name)

print("  denetlenen gds Mod A: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   gds Mod A köprü referansları mevcut"
else
    echo "[UYARI] gds Mod A köprü referansı eksik (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 6) config.toml [hooks] soft/hard sözleşmesi =="
"$PY" - <<'PY'
import os, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
cfg = os.path.join(PLUGIN, "custom", "config.toml")
if not os.path.isfile(cfg):
    print("  [HATA] %s yok" % cfg)
    sys.exit(1)
try:
    d = tomllib.load(open(cfg, "rb"))
except Exception as e:
    print("  [HATA] config parse: %s" % e)
    sys.exit(1)
h = d.get("hooks", {}) or {}
qg = str(h.get("quality_gate", "soft")).strip().lower()
dg = str(h.get("deploy_guard", "soft")).strip().lower()
print("  quality_gate: %s" % qg)
print("  deploy_guard: %s" % dg)
problems = []
for name, val in (("quality_gate", qg), ("deploy_guard", dg)):
    if val not in ("soft", "hard"):
        problems.append("%s = %r (geçersiz — soft|hard olmalı)" % (name, val))
if problems:
    for p in problems:
        print("  MISS: %s" % p)
    sys.exit(1)
sys.exit(0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   config soft/hard sözleşmesi geçerli"
else
    echo "[UYARI] config soft/hard sorunu (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 7) Köprü belge §N.N referans drift denetimi =="
# dev-skill-to-methodology-bridge referansı taşıyan custom/*.toml dosyalarında
# kullanılan §N.N bölüm referansları bridge.md'de gerçekten var olmalı.
# Bu, bridge belgesi güncellendiğinde custom/'un drift'ini yakalar (silinen/
# yeniden adlandırılan bölümlerden doğan yanlış referansları).
"$PY" - <<'PY'
import glob, os, re, sys, tomllib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
BRIDGE = os.path.join(PLUGIN, "docs", "bmad", "dev-skill-to-methodology-bridge.md")
if not os.path.isfile(BRIDGE):
    print("  [HATA] bridge belgesi yok: %s" % BRIDGE)
    sys.exit(1)

# Bridge bölümlerini çıkar: ## §N veya ### §N.N[a-z]?
bridge_secs = set()
with open(BRIDGE, encoding="utf-8") as f:
    for m in re.finditer(r'^(?:##|###) §([0-9]+(?:\.[0-9]+[a-z]?)?)', f.read(), re.M):
        bridge_secs.add(m.group(1))

problems = []
checked = 0
for path in sorted(glob.glob(os.path.join(PLUGIN, "custom", "*.toml"))):
    name = os.path.basename(path)[:-5]
    if name == "config":
        continue
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        continue
    # Bridge referansı taşımayan dosyalar muaf (farklı manifestolara atıf
    # yapıyor olabilir — sadece bridge kullananları denetle).
    if "dev-skill-to-methodology-bridge" not in text:
        continue
    checked += 1
    refs = set()
    for m in re.finditer(r'§([0-9]+(?:\.[0-9]+[a-z]?)?)', text):
        refs.add(m.group(1))
    unknown = sorted(refs - bridge_secs)
    if unknown:
        problems.append("%s: bridge'de olmayan §N.N → %s (yazım hatası veya "
                        "eski bölüm; bridge.md'den kontrol et)" %
                        (name, ", ".join(unknown)))

print("  denetlenen bridge kullanan: %d" % checked)
for p in problems:
    print("  MISS: %s" % p)
raise SystemExit(1 if problems else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   köprü §N.N referansları bridge ile senkron"
else
    echo "[UYARI] köprü §N.N drift (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo
if [ "${PROBLEMS:-0}" -eq 0 ]; then
    echo "DURUM: SAĞLIKLI (custom/ tüm statik kontrolleri geçti)"
    exit 0
else
    echo "DURUM: ${PROBLEMS} sorun bulundu"
    exit 1
fi
