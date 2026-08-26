#!/bin/sh
# check-plugin.sh — metodoloji plugin'i sağlık kontrolü (tek komut, plugin varyantı).
#
#   0. Kapı anahtarı kurulu mu            (run_experiment.py --check-secret)
#   1. Kapı + hook motoru selfcheck        (plugin kopyaları, her ikisi)
#   2. Manifesto + proje-bağlam kablolaması (HER yüzey için) + köprü denetimi
#   2b. Köprü talimatları runtime'da görünür mü (resolve_customization deep_merge)
#   3. Onaylı deney envanteri              (guard'ın kod yazımını açtığı kayıtlar)
#   4. Belgesel (B/C/D) kayıt eksiksizliği  (run_experiment.py --validate)
#   5. Engine drift denetimi               (plugin motoru == repo canonical, repo erişilebilirse)
#   5b. Hard gate enforcement modu (soft/hard — custom/config.toml [hooks])
#   6. Geliştirme kayıtları format kontrolü  (run_experiment.py --validate)
#
# Kullanım:  sh commands/check-plugin.sh   (plugin kökünden veya her yerden;
#            hedef proje kökü cwd veya $OPENHANDS_PROJECT_DIR)
#            sh commands/check-plugin.sh --negtest
#            (yalnızca negatif test: KÖPRÜ'yü boz → §2b MISS yakala → geri yükle)
# Çıkış:     her satırın başında [OK] / [UYARI] / [HATA]; sonunda genel durum.

set -u

if [ "${1:-}" = "--negtest" ]; then
    # Negatif test (repo geleneği: boz → MISS yakala → geri yükle).
    # custom/bmad-dev-story.toml içinden KÖPRÜ satırını geçici kaldırır,
    # §2b mantığının MISS ürettiğini doğrular, dosyayı geri yükler.
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
import json, os, subprocess, sys
from pathlib import Path

PLUGIN = Path(os.environ["PLUGIN_ROOT"])
toml = PLUGIN / "custom" / "bmad-dev-story.toml"
resolver = PLUGIN / "hooks" / "engine" / "resolve_customization.py"
skill = PLUGIN / "skills" / "bmad-dev-story"
orig = toml.read_text(encoding="utf-8")

def bridge_visible(text: str) -> bool:
    toml.write_text(text, encoding="utf-8")
    try:
        r = subprocess.run(
            [sys.executable, str(resolver), "-s", str(skill),
             "-k", "workflow.activation_steps_append"],
            capture_output=True, text=True, encoding="utf-8", timeout=15)
        d = json.loads(r.stdout)
        return any("KÖPRÜ" in s for s in d.get("workflow.activation_steps_append", []))
    finally:
        toml.write_text(orig, encoding="utf-8")

broken = "\n".join(l for l in orig.splitlines() if "KÖPRÜ" not in l)
if not bridge_visible(orig):
    print("[HATA] sağlam custom TOML'da bile KÖPRÜ görünmüyor — test kurulumu bozuk")
    sys.exit(1)
if bridge_visible(broken):
    print("[HATA] negatif test başarısız: KÖPRÜ silindiği halde §2b mantığı yakalamadı")
    sys.exit(1)
print("[OK]   negatif test: KÖPRÜ silindi → MISS yakalandı → custom TOML geri yüklendi")
sys.exit(0)
PY
    exit $?
fi

# PLUGIN_ROOT: bu betiğin konumundan türetilir (commands/ altındadır).
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
export PLUGIN_ROOT

# PROJECT_ROOT: hedef proje (kayıtların yaşadığı yer). OPENHANDS_PROJECT_DIR > cwd.
PROJECT_ROOT=${OPENHANDS_PROJECT_DIR:-$(pwd)}
# Dogfooding: betik repo içinden çağrılıp cwd metodoloji reposu ise cwd geçerli kalır.
export PROJECT_ROOT

GATE="$PLUGIN_ROOT/skills/bmad-research-experiment/scripts/run_experiment.py"
PROBLEMS=0

# Python çözücü: python3 -> python -> py (Windows Launcher). Yoksa çalışamayız.
PY=
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "[HATA] python3/python/py bulunamadı — check-plugin çalışamaz." >&2
    exit 1
fi

echo "== 0) Kapı anahtarı kurulu mu =="
if "$PY" "$GATE" --check-secret >/dev/null 2>&1; then
    echo "[OK]   kapı anahtarı mevcut (HMAC — jeton üretilebilir)"
else
    echo "[HATA] kapı anahtarı YOK. Çalıştır: $PY $GATE --init-secret"
    echo "       (repo dışına ~/.bmad/gate-key yazar; anahtarsız onay/jeton üretilemez)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 1) Kapı + hook motoru selfcheck (plugin kopyaları) =="
if "$PY" "$GATE" --selfcheck >/tmp/meth-selfcheck.$$.log 2>&1; then
    echo "[OK]   kapı --selfcheck geçti"
else
    echo "[HATA] kapı --selfcheck başarısız:"
    sed 's/^/       /' /tmp/meth-selfcheck.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-selfcheck.$$.log
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" guard --runtime=openhands >/tmp/meth-hooks.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-hooks.$$.log; then
        echo "[OK]   hook motoru çalışıyor (main.py guard → karar döndü)"
    else
        echo "[HATA] hook motoru karar döndürmedi:"
        sed 's/^/       /' /tmp/meth-hooks.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[HATA] hook motoru guard testi başarısız:"
    sed 's/^/       /' /tmp/meth-hooks.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-hooks.$$.log
# quality hook testi (PreToolUse — terminalmatcher)
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" quality --runtime=openhands >/tmp/meth-quality.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-quality.$$.log; then
        echo "[OK]   hook motoru çalışıyor (main.py quality → karar döndü)"
    else
        echo "[HATA] hook motoru quality karar döndürmedi:"
        sed 's/^/       /' /tmp/meth-quality.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[HATA] hook motoru quality testi başarısız:"
    sed 's/^/       /' /tmp/meth-quality.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-quality.$$.log
# deploy hook testi (PreToolUse — terminalmatcher)
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" deploy --runtime=openhands >/tmp/meth-deploy.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-deploy.$$.log; then
        echo "[OK]   hook motoru çalışıyor (main.py deploy → karar döndü)"
    else
        echo "[HATA] hook motoru deploy karar döndürmedi:"
        sed 's/^/       /' /tmp/meth-deploy.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[HATA] hook motoru deploy testi başarısız:"
    sed 's/^/       /' /tmp/meth-deploy.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-deploy.$$.log

echo "== 2) Manifesto tüm yüzeylere + köprü (native→kayıt) kablolanmış mı =="
"$PY" - <<'PY'
import glob, os, sys, tomllib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
PROJECT = os.environ.get("PROJECT_ROOT") or "."

# Non-metodoloji araç yüzeyleri — denetimden açıkça hariç (kapasite haritası dışı).
EXCLUDED = {"graft", "memory", "sync"}

# Geliştirme kanadı yüzeyleri (development-methodology.md §6 eşlemesi + dev ajanları):
DEV_WING = {
    "bmad-check-implementation-readiness", "bmad-prd", "bmad-ux",
    "bmad-create-architecture", "bmad-sprint-planning", "bmad-create-story",
    "bmad-create-epics-and-stories", "bmad-dev-story", "bmad-quick-dev",
    "bmad-dev-auto", "bmad-research-experiment",
    "bmad-testarch-atdd", "bmad-testarch-automate", "bmad-testarch-ci",
    "bmad-testarch-framework", "bmad-testarch-nfr", "bmad-testarch-test-design",
    "bmad-testarch-test-review", "bmad-testarch-trace",
    "bmad-code-review", "bmad-review-adversarial-general",
    "bmad-review-edge-case-hunter", "bmad-qa-generate-e2e-tests",
    "bmad-eval-runner", "gds-performance-test", "bmad-document-project",
    "bmad-retrospective", "bmad-correct-course", "bmad-sprint-status",
    "bmad-agent-dev", "bmad-agent-architect", "bmad-agent-pm",
    "bmad-agent-ux-designer", "bmad-agent-tech-writer", "bmad-tea",
}

missing = []
checked = 0
excluded = 0

skills = sorted(
    d for d in glob.glob(os.path.join(PLUGIN, "skills", "*"))
    if os.path.isdir(d) and os.path.isfile(os.path.join(d, "SKILL.md"))
)
for d in skills:
    name = os.path.basename(d)
    if name in EXCLUDED:
        excluded += 1
        continue
    checked += 1

    root = os.path.join(d, "customize.toml")
    team = os.path.join(PLUGIN, "custom", "%s.toml" % name)
    user = os.path.join(PLUGIN, "custom", "%s.user.toml" % name)

    if os.path.isfile(root):
        # Özelleştirme hattı: root + takım + kişisel — effective facts (merge eklemeli)
        facts = []
        ok = True
        for p in (root, team, user):
            if not os.path.isfile(p):
                continue
            try:
                data = tomllib.load(open(p, "rb"))
            except Exception as e:
                print("  PARSE HATA: %s: %s" % (p, e))
                missing.append("%s (parse)" % name)
                ok = False
                break
            for sec in ("agent", "workflow"):
                facts += data.get(sec, {}).get("persistent_facts", [])
        if not ok:
            continue
        if not any("research-methodology.md" in x for x in facts):
            missing.append("%s (manifesto yok: root+team+user)" % name)
        elif not any("project-context.md" in x for x in facts):
            missing.append("%s (proje-bağlam yok)" % name)
        if name in DEV_WING and not any("development-methodology.md" in x for x in facts):
            missing.append("%s (geliştirme manifestosu yok)" % name)
        # Tüketim: facts sadece yapılandırılmamalı, yüzey onları GERÇEKTEN yüklemeli.
        consumed = False
        for root2, _, files in os.walk(d):
            for f in files:
                if not f.endswith((".md", ".py", ".sh")):
                    continue
                try:
                    if "resolve_customization" in open(os.path.join(root2, f),
                                                       encoding="utf-8",
                                                       errors="replace").read():
                        consumed = True
                        break
                except OSError:
                    continue
            if consumed:
                break
        if not consumed:
            missing.append("%s (kozmetik: resolve_customization çağırmıyor)" % name)
    else:
        # Özelleştirme hattı yok → SKILL.md işaretçisi
        try:
            txt = open(os.path.join(d, "SKILL.md"), encoding="utf-8").read()
        except Exception as e:
            missing.append("%s (okunamadı: %s)" % (name, e))
            continue
        if "research-methodology.md" not in txt:
            missing.append("%s (SKILL.md işaretçisi yok)" % name)
        if name in DEV_WING and "development-methodology.md" not in txt:
            missing.append("%s (SKILL.md geliştirme manifestosu işaretçisi yok)" % name)

# Menü skill hedefleri var olmalı (kırık yetenek bağlantısı sınıfı).
for cp in sorted(set(glob.glob(os.path.join(PLUGIN, "skills", "*", "customize.toml")))
                 | set(glob.glob(os.path.join(PLUGIN, "custom", "*.toml")))):
    if os.path.basename(cp) == "config.toml":
        continue
    try:
        cd = tomllib.load(open(cp, "rb"))
    except Exception:
        continue
    for sec in ("agent", "workflow"):
        for it in cd.get(sec, {}).get("menu", []):
            s = it.get("skill")
            if s and not os.path.isdir(os.path.join(PLUGIN, "skills", s)):
                missing.append("%s menü → %s (skill dizini yok)" % (os.path.basename(cp), s))

# Geliştirme kanadı manifestosu: hedef projede kurulu olmalı (/metodoloji:init).
DEVWING = os.path.join(PROJECT, "docs", "bmad", "development-methodology.md")
if not os.path.isfile(DEVWING):
    # Plugin kökü dogfooding'de de olabilir (metodoloji reposu = PROJECT).
    missing.append("%s (doküman yok — hedef projede /metodoloji:init çalıştırın)" % DEVWING)

# --- Köprü denetimi: native skill çıktısı → metodoloji kaydı çevirisi ---
BRIDGE = os.path.join(PROJECT, "docs", "bmad", "dev-skill-to-methodology-bridge.md")
if not os.path.isfile(BRIDGE):
    missing.append("%s (köprü dokümanı yok — native çıktı metodoloji kaydına çevrilmiyor)" % BRIDGE)

# Faz-1 köprü skill'leri: her biri docs/development/<kayıt>-*.md üretmelidir.
BRIDGE_SKILLS = {
    "bmad-check-implementation-readiness": ("IR", "docs/development/", "uret"),
    "bmad-sprint-planning": ("SP", "docs/development/", "uret"),
    "bmad-create-story": ("S", "docs/development/stories/", "uret"),
    "bmad-code-review": ("QR", "docs/development/", "uret"),
    "bmad-dev-story": ("S", "docs/development/stories/", "guncelle"),
    "bmad-quick-dev": ("S", "docs/development/stories/", "guncelle"),
    "bmad-dev-auto": ("S", "docs/development/stories/", "guncelle"),
}
for skill, (rec_type, target, _) in BRIDGE_SKILLS.items():
    toml_path = os.path.join(PLUGIN, "custom", "%s.toml" % skill)
    if not os.path.isfile(toml_path):
        missing.append("%s (köprü skill override'ı yok)" % skill)
        continue
    try:
        txt = open(toml_path, encoding="utf-8").read()
    except OSError:
        missing.append("%s (okunamadı)" % toml_path)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (köprü referansı yok — append adımı silinmiş olabilir)" % skill)
    if target not in txt:
        missing.append("%s (metodoloji kayıt hedefi %s yok)" % (skill, target))

# Faz-3 QR besleyicileri — SKILL.md "## Metodoloji" bölümüyle çalışanlar.
QR_FEEDERS_SKILLMD = ["bmad-review-adversarial-general", "bmad-review-edge-case-hunter", "bmad-eval-runner"]
for skill in QR_FEEDERS_SKILLMD:
    skill_md = os.path.join(PLUGIN, "skills", skill, "SKILL.md")
    if not os.path.isfile(skill_md):
        missing.append("%s (SKILL.md yok)" % skill)
        continue
    try:
        txt = open(skill_md, encoding="utf-8").read()
    except OSError:
        missing.append("%s (okunamadı)" % skill_md)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (köprü referansı SKILL.md'de yok)" % skill)
    if "docs/development/QR" not in txt:
        missing.append("%s (QR besleme hedefi SKILL.md'de yok)" % skill)

# Faz-3 QR besleyicileri — custom/{skill}.toml activation_steps_append'iyle çalışanlar.
QR_FEEDERS_TOML = [
    "bmad-qa-generate-e2e-tests",
    "bmad-testarch-atdd", "bmad-testarch-automate", "bmad-testarch-ci",
    "bmad-testarch-framework", "bmad-testarch-nfr", "bmad-testarch-test-design",
    "bmad-testarch-test-review", "bmad-testarch-trace",
]
for skill in QR_FEEDERS_TOML:
    toml_path = os.path.join(PLUGIN, "custom", "%s.toml" % skill)
    if not os.path.isfile(toml_path):
        missing.append("%s (köprü skill override'ı yok)" % skill)
        continue
    try:
        txt = open(toml_path, encoding="utf-8").read()
    except OSError:
        missing.append("%s (okunamadı)" % toml_path)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (köprü referansı append'te yok)" % skill)
    if "docs/development/QR" not in txt:
        missing.append("%s (QR besleme hedefi append'te yok)" % skill)

print("  denetlenen yüzey: %d, hariç tutulan (non-metodoloji araç): %d" % (checked, excluded))
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   manifesto tüm metodoloji yüzeylerine kablolanmış"
else
    echo "[UYARI] kablolama eksik (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 2b) Köprü talimatları runtime'da görünür mü (resolve_customization merge) =="
# custom/{skill}.toml'daki KÖPRÜ adımı, resolve_customization.py deep_merge (append)
# ile skill-root customize.toml'la birleşmeli. Append semantiği kalıcıdır.
"$PY" - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
PLUGIN = Path(os.environ.get("PLUGIN_ROOT") or ".")
RESOLVER = PLUGIN / "hooks" / "engine" / "resolve_customization.py"
TOML_SKILLS = [
    "bmad-check-implementation-readiness", "bmad-sprint-planning",
    "bmad-create-story", "bmad-code-review",
    "bmad-dev-story", "bmad-quick-dev", "bmad-dev-auto",
    "bmad-qa-generate-e2e-tests",
    "bmad-testarch-atdd", "bmad-testarch-automate", "bmad-testarch-ci",
    "bmad-testarch-framework", "bmad-testarch-nfr", "bmad-testarch-test-design",
    "bmad-testarch-test-review", "bmad-testarch-trace",
    "gds-dev-story", "gds-quick-dev", "gds-code-review",
    "gds-check-implementation-readiness", "gds-sprint-planning", "gds-create-story",
    "gds-test-automate", "gds-test-design", "gds-test-framework",
    "gds-test-review", "gds-e2e-scaffold", "gds-performance-test", "gds-playtest-plan",
]
missing = []
checked = 0
for name in TOML_SKILLS:
    skill_dir = PLUGIN / "skills" / name
    if not skill_dir.is_dir():
        continue
    checked += 1
    try:
        r = subprocess.run(
            [sys.executable, str(RESOLVER), "-s", str(skill_dir),
             "-k", "workflow.activation_steps_append"],
            capture_output=True, text=True, encoding="utf-8", timeout=15)
        d = json.loads(r.stdout)
        asa = d.get("workflow.activation_steps_append", [])
        if not any("KÖPRÜ" in s or "KOPRU" in s for s in asa):
            missing.append("%s (KÖPRÜ merge sonucunda yok — custom toml append çalışmıyor)" % name)
    except Exception as e:
        missing.append("%s (resolve hatası: %s)" % (name, str(e)[:60]))
print("  denetlenen toml skill (yüklü): %d" % checked)
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   KÖPRÜ talimatları runtime'da görünür (deep_merge append kalıcı)"
else
    echo "[UYARI] KÖPRÜ merge sorunu (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 2c) KÖPRÜ DOGRULAMA talimatları mevcut mu =="
"$PY" - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
PLUGIN = Path(os.environ.get("PLUGIN_ROOT") or ".")
RESOLVER = PLUGIN / "hooks" / "engine" / "resolve_customization.py"
KOPRU_SKILLS = [
    "bmad-check-implementation-readiness", "bmad-sprint-planning",
    "bmad-create-story", "bmad-code-review",
    "bmad-dev-story", "bmad-quick-dev", "bmad-dev-auto",
    "gds-check-implementation-readiness", "gds-sprint-planning",
    "gds-create-story", "gds-code-review",
    "gds-dev-story", "gds-quick-dev",
]
missing = []
checked = 0
for name in KOPRU_SKILLS:
    skill_dir = PLUGIN / "skills" / name
    if not skill_dir.is_dir():
        continue
    checked += 1
    try:
        r = subprocess.run(
            [sys.executable, str(RESOLVER), "-s", str(skill_dir),
             "-k", "workflow.activation_steps_append"],
            capture_output=True, text=True, encoding="utf-8", timeout=15)
        d = json.loads(r.stdout)
        asa = d.get("workflow.activation_steps_append", [])
        has_verify = any("DOGRULAMA" in s for s in asa)
        if not has_verify:
            missing.append("%s (KÖPRÜ'de DOGRULAMA yok — LLM kaydı atlayabilir)" % name)
    except Exception as e:
        missing.append("%s (resolve hatası: %s)" % (name, str(e)[:60]))
print("  denetlenen KÖPRÜ skill: %d" % checked)
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   KÖPRÜ DOGRULAMA talimatları mevcut (LLM otomatik doğrulayacak)"
else
    echo "[UYARI] KÖPRÜ DOGRULAMA eksik (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 3) Onaylı deney envanteri (guard kod önü açtı mı) =="
FOUND=0
for rec in "$PROJECT_ROOT"/docs/experiments/*.md; do
    [ -f "$rec" ] || continue
    case "$(basename "$rec")" in _template.md) continue ;; esac
    if grep -q "Karar:\*\*[[:space:]]*ONAYLANDI" "$rec"; then
        if "$PY" "$GATE" --verify --record "$rec" >/dev/null 2>&1; then
            echo "[OK]   $rec -> VERIFIED"
            FOUND=$((FOUND + 1))
        else
            echo "[HATA] $rec -> ONAYLANDI ama --verify geçmedi (FORGED?)"
            PROBLEMS=$((PROBLEMS + 1))
        fi
    fi
done
if [ "$FOUND" -eq 0 ]; then
    echo "[UYARI] onaylı deney yok — guard kod yazımını kapalı tutuyor. bmad-research-experiment ile başla."
    echo "        Keşif/deneme kodu için scratch/ kullanılabilir."
fi

echo "== 4) Belgesel (B/C/D) kayıt eksiksizliği =="
DOCPROBLEMS=0
DOCCHECKED=0
for rec in "$PROJECT_ROOT"/docs/research/*.md "$PROJECT_ROOT"/docs/design/*.md; do
    [ -f "$rec" ] || continue
    case "$(basename "$rec")" in _template.md) continue ;; esac
    DOCCHECKED=$((DOCCHECKED + 1))
    "$PY" "$GATE" --validate "$rec" >/tmp/meth-doc.$$.log 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "[OK]   $rec"
    elif [ "$rc" -eq 2 ]; then
        echo "[GÖZARDI] $rec (Mod A / tanınmayan — belgesel değil)"
    else
        echo "[UYARI] $rec eksik/dürüstlük sorunu:"
        sed 's/^/        /' /tmp/meth-doc.$$.log
        DOCPROBLEMS=$((DOCPROBLEMS + 1))
    fi
done
rm -f /tmp/meth-doc.$$.log
if [ "$DOCCHECKED" -eq 0 ]; then
    echo "[OK]   belgesel kayıt yok (docs/research/, docs/design/) — eklenecek kayıt denetlenir"
fi
PROBLEMS=$((PROBLEMS + DOCPROBLEMS))

echo "== 5) Engine bütünlük denetimi (modüler motor: main.py + modules/) =="
# Canonical bu repo'nun hooks/engine/ ağacıdır; plugin kopyası repo ile aynı
# olmalı. Drift = eksik/bozuk engine dosyası (eski tek-dosya bmad-hooks.py yok).
ENGINE_OK=1
for f in main.py memlog.py resolve_customization.py modules/__init__.py \
         modules/config.py modules/utils.py modules/archive.py modules/bash_targets.py \
         modules/guard.py modules/audit.py modules/stop.py; do
    if [ ! -f "$PLUGIN_ROOT/hooks/engine/$f" ]; then
        echo "[HATA] engine dosyası eksik: hooks/engine/$f"
        ENGINE_OK=0
    fi
done
if [ "$ENGINE_OK" -eq 1 ]; then
    if "$PY" -c "
import py_compile, os, sys
engine=os.path.normpath(sys.argv[1])
files=['main.py','memlog.py','resolve_customization.py',
       'modules/__init__.py','modules/config.py','modules/utils.py',
       'modules/archive.py','modules/bash_targets.py','modules/guard.py',
       'modules/audit.py','modules/stop.py']
for f in files:
    py_compile.compile(os.path.join(engine, f), doraise=True)
print('import-ok')
" "$PLUGIN_ROOT/hooks/engine" >/tmp/meth-engine.$$.log 2>&1; then
        echo "[OK]   modüler motor eksiksiz ve import edilebilir (main.py + modules/)"
    else
        echo "[HATA] modüler motor import testi başarısız:"
        sed 's/^/       /' /tmp/meth-engine.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
    rm -f /tmp/meth-engine.$$.log
else
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 5b) Hard gate enforcement modu (soft/hard) =="
# quality-gate ve deploy-guard hook'ları config-gated: custom/config.toml [hooks].
"$PY" - <<'PY'
import tomllib, os, sys
PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
PROJECT = os.environ.get("PROJECT_ROOT") or "."
cfg = os.path.join(PLUGIN, "custom", "config.toml")
mode_default = "soft"
qg, dg = mode_default, mode_default
src = "(config yok — soft varsayılan)"
if os.path.isfile(cfg):
    try:
        d = tomllib.load(open(cfg, "rb"))
        h = d.get("hooks", {}) or {}
        qg = str(h.get("quality_gate", "soft")).strip().lower()
        dg = str(h.get("deploy_guard", "soft")).strip().lower()
        src = "config"
    except Exception as e:
        print("  [HATA] config parse: %s" % e)
        sys.exit(1)
problems = []
for name, val in (("quality_gate", qg), ("deploy_guard", dg)):
    if val not in ("soft", "hard"):
        problems.append("%s = %r (geçersiz — soft|hard olmalı)" % (name, val))
print("  quality_gate: %s (%s)" % (qg, src))
print("  deploy_guard: %s (%s)" % (dg, src))
if qg == "hard" or dg == "hard":
    import glob as _glob
    _dev = os.path.join(PROJECT, "docs", "development")
    _real = [f for pat in ("IR-*.md", "SP-*.md", "QR-*.md", "PR-*.md")
             for f in _glob.glob(os.path.join(_dev, pat))
             if not os.path.basename(f).startswith("_")]
    if not _real:
        problems.append("hard mod aktif ama docs/development/ gerçek kaydı yok "
                        "(IR-/SP-/QR-/PR-) — her commit/push/deploy bloklanır; "
                        "soft'a çevir veya önce kayıt üret")
print("  not: OpenHands runtime'da quality/deploy hook'ları AKTİFTİR (hooks.json:")
print("       PreToolUse -> guard/quality/deploy, Stop -> stop, PostToolUse -> audit).")
print("       quality_gate/deploy_guard değerleri artık hook seviyesinde zorlanır;")
print("       quality: git commit IR'siz/QR'siz/SP'sizse DENY; deploy: IR'siz/QR'siz/SP'siz/PR'sız deploy DENY.")
if problems:
    for p in problems:
        print("  MISS: %s" % p)
    sys.exit(1)
sys.exit(0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   hard gate modu geçerli (config soft; guard/stop fail-closed aktif)"
else
    echo "[UYARI] hard gate modu sorunu (yukarı bak)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 6) Geliştirme kayıtları format kontrolü =="
DEVPROBLEMS=0
DEVCHECKED=0
for rec in \
    "$PROJECT_ROOT"/docs/development/IR-*.md "$PROJECT_ROOT"/docs/development/SP-*.md \
    "$PROJECT_ROOT"/docs/development/QR-*.md "$PROJECT_ROOT"/docs/development/PR-*.md \
    "$PROJECT_ROOT"/docs/development/stories/S-*.md "$PROJECT_ROOT"/docs/development/incidents/PM-*.md; do
    [ -f "$rec" ] || continue
    DEVCHECKED=$((DEVCHECKED + 1))
    case "$(basename "$rec")" in
        IR-*) ALLOWED="HAZIR EKSİK" ;;
        QR-*) ALLOWED="ONAYLANDI REDDEDİLDİ REVİZE" ;;
        PR-*) ALLOWED="HAZIR BEKLİYOR" ;;
        SP-*) ALLOWED="planlandı devam ediyor tamamlandı iptal" ;;
        S-*)  ALLOWED="backlog sprint in-progress review done blocked" ;;
        PM-*) ALLOWED="açık investigation resolved closed" ;;
        *)    continue ;;
    esac
    line=$(grep -m1 '\*\*Karar:\*\*' "$rec")
    if [ -z "$line" ]; then
        line=$(grep -m1 '\*\*Durum:\*\*' "$rec")
    fi
    if [ -z "$line" ]; then
        echo "[UYARI] $rec -> Karar/Durum alanı yok"
        DEVPROBLEMS=$((DEVPROBLEMS + 1))
        continue
    fi
    dec=$(echo "$line" | sed 's/.*\*\*\(Karar\|Durum\):\*\* *//; s/[|→].*//' | sed 's/^ *//; s/ *$//')
    found=0
    case "$(basename "$rec")" in
        IR-*) case "$dec" in HAZIR|EKSİK) found=1 ;; esac ;;
        QR-*) case "$dec" in ONAYLANDI|REDDEDİLDİ|REVİZE) found=1 ;; esac ;;
        PR-*) case "$dec" in HAZIR|BEKLİYOR) found=1 ;; esac ;;
        SP-*) case "$dec" in planlandı|"devam ediyor"|tamamlandı|iptal) found=1 ;; esac ;;
        S-*)  case "$dec" in backlog|sprint|in-progress|review|done|blocked) found=1 ;; esac ;;
        PM-*) case "$dec" in açık|investigation|resolved|closed) found=1 ;; esac ;;
    esac
    if [ "$found" -eq 0 ]; then
        echo "[UYARI] $rec -> beklenmeyen Karar/Durum: '$dec' (izinli: $ALLOWED)"
        DEVPROBLEMS=$((DEVPROBLEMS + 1))
        continue
    fi
    if ! grep -q '\*\*Tarih:\*\*' "$rec"; then
        echo "[UYARI] $rec -> Tarih alanı yok"
        DEVPROBLEMS=$((DEVPROBLEMS + 1))
        continue
    fi
    echo "[OK]   $rec ($dec)"
done
if [ "$DEVCHECKED" -eq 0 ]; then
    echo "[OK]   geliştirme kaydı yok (docs/development/) — eklenecek kayıt denetlenir"
fi
PROBLEMS=$((PROBLEMS + DEVPROBLEMS))

echo
if [ "$PROBLEMS" -eq 0 ]; then
    echo "DURUM: SAĞLIKLI (tüm kontroller geçti)"
    exit 0
else
    echo "DURUM: $PROBLEMS sorun bulundu"
    exit 1
fi
