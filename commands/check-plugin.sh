#!/bin/sh
# check-plugin.sh — methodology plugin health check (single command, plugin variant).
#
#   0. Is the gate key installed?            (run_experiment.py --check-secret)
#   1. Gate + hook engine selfcheck        (plugin copies, both)
#   2. Manifesto + project-context wiring (for EVERY surface) + bridge audit
#   2b. Are bridge instructions visible at runtime? (resolve_customization deep_merge)
#   3. Approved experiment inventory              (records where the guard opened code writing)
#   4. Documentary (B/C/D) record completeness  (run_experiment.py --validate)
#   5. Engine drift audit               (plugin engine == repo canonical, if repo reachable)
#   5b. Hard gate enforcement mode (soft/hard — custom/config.toml [hooks])
#   5c. custom/ bridge TOMLs static quality audit (commands/check-custom.sh)
#   6. Development records format check  (run_experiment.py --validate)
#
# Usage:  sh commands/check-plugin.sh   (from the plugin root or anywhere;
#            target project root is cwd or $OPENHANDS_PROJECT_DIR)
#            sh commands/check-plugin.sh --negtest
#            (negative-test only: break the KÖPRÜ marker → catch §2b MISS → restore)
# Output:    [OK] / [WARNING] / [ERROR] at the start of each line; overall status at the end.

set -u

if [ "${1:-}" = "--negtest" ]; then
    # Negative test (repo convention: break → catch MISS → restore).
    # Temporarily removes the KÖPRÜ line from custom/bmad-dev-story.toml,
    # verifies §2b logic produces a MISS, then restores the file.
    SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
    PY=
    for cand in python3 python py; do
        if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
    done
    if [ -z "$PY" ]; then
        echo "[ERROR] python3/python/py not found — negative test cannot run." >&2
        exit 1
    fi
    PLUGIN_ROOT="$PLUGIN_ROOT" "$PY" - <<'PY'
import json, os, subprocess, sys
from pathlib import Path

PLUGIN = Path(os.environ["PLUGIN_ROOT"])
check_script = PLUGIN / "commands" / "check-plugin.sh"
total_stages = 3

# Stage 1/3: .env.example deleted → §6a.2 should catch a WARNING
print(f"[1/{total_stages}] does §6a emit a WARNING when .env.example is deleted")
env_example = PLUGIN / ".env.example"
gitignore = PLUGIN / ".gitignore"
orig_example = env_example.read_text(encoding="utf-8") if env_example.exists() else None
orig_gitignore = gitignore.read_text(encoding="utf-8")
if orig_example is None:
    print("  [ERROR] test setup broken: .env.example already missing")
    sys.exit(1)
try:
    env_example.unlink()
    r = subprocess.run(
        ["sh", str(check_script)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        cwd=str(PLUGIN),
    )
    if ".env.example not found" in r.stdout and r.returncode == 1:
        print("  [OK] §6a.2 WARNING caught, exit=1")
    else:
        print(f"  [ERROR] §6a.2 WARNING expected, output: ...{r.stdout[-400:]!r}")
        sys.exit(1)
finally:
    env_example.write_text(orig_example, encoding="utf-8")

# Stage 2/3: .env line removed from .gitignore → §6a.3 should catch an ERROR
print(f"[2/{total_stages}] does §6a emit an ERROR when .env is removed from .gitignore")
broken = "\n".join(l for l in orig_gitignore.splitlines() if l.strip() != ".env")
try:
    gitignore.write_text(broken, encoding="utf-8")
    r = subprocess.run(
        ["sh", str(check_script)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        cwd=str(PLUGIN),
    )
    if ".env line missing in .gitignore" in r.stdout and r.returncode == 1:
        print("  [OK] §6a.3 ERROR caught, exit=1")
    else:
        print(f"  [ERROR] §6a.3 ERROR expected, output: ...{r.stdout[-400:]!r}")
        sys.exit(1)
finally:
    gitignore.write_text(orig_gitignore, encoding="utf-8")

# Stage 3/3: KÖPRÜ removed from custom/bmad-dev-story.toml → §2b should catch a MISS
print(f"[3/{total_stages}] does §2b emit a MISS when KÖPRÜ is removed from custom/bmad-dev-story.toml")
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

try:
    broken = "\n".join(l for l in orig.splitlines() if "KÖPRÜ" not in l)
    if not bridge_visible(orig):
        print("  [ERROR] KÖPRÜ not visible even in intact custom TOML — test setup broken")
        sys.exit(1)
    if bridge_visible(broken):
        print("  [ERROR] §2b MISS expected, KÖPRÜ still visible after removal")
        sys.exit(1)
    print("  [OK] §2b MISS caught, custom TOML restored")
finally:
    toml.write_text(orig, encoding="utf-8")

print(f"[OK] all {total_stages} negtest stages successful")
sys.exit(0)
PY
    exit $?
fi

# PLUGIN_ROOT: derived from this script's location (it lives under commands/).
SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
export PLUGIN_ROOT

# PROJECT_ROOT: the target project (where records live). OPENHANDS_PROJECT_DIR > cwd.
PROJECT_ROOT=${OPENHANDS_PROJECT_DIR:-$(pwd)}
# Dogfooding: if the script is invoked from within the repo and cwd is the methodology repo, cwd stays valid.
export PROJECT_ROOT

GATE="$PLUGIN_ROOT/skills/bmad-research-experiment/scripts/run_experiment.py"
PROBLEMS=0

# Python resolver: python3 -> python -> py (Windows Launcher). Without it we cannot run.
PY=
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "[ERROR] python3/python/py not found — check-plugin cannot run." >&2
    exit 1
fi

echo "== 0) Is the gate key installed? =="
if "$PY" "$GATE" --check-secret >/dev/null 2>&1; then
    echo "[OK]   gate key present (HMAC — tokens can be produced)"
else
    echo "[ERROR] gate key MISSING. Run: $PY $GATE --init-secret"
    echo "       (writes ~/.bmad/gate-key outside the repo; without a key no approval/token can be produced)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 1) Gate + hook engine selfcheck (plugin copies) =="
if "$PY" "$GATE" --selfcheck >/tmp/meth-selfcheck.$$.log 2>&1; then
    echo "[OK]   gate --selfcheck passed"
else
    echo "[ERROR] gate --selfcheck failed:"
    sed 's/^/       /' /tmp/meth-selfcheck.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-selfcheck.$$.log
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" guard --runtime=openhands >/tmp/meth-hooks.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-hooks.$$.log; then
        echo "[OK]   hook engine running (main.py guard → returned a decision)"
    else
        echo "[ERROR] hook engine returned no decision:"
        sed 's/^/       /' /tmp/meth-hooks.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[ERROR] hook engine guard test failed:"
    sed 's/^/       /' /tmp/meth-hooks.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-hooks.$$.log
# quality hook test (PreToolUse — terminalmatcher)
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" quality --runtime=openhands >/tmp/meth-quality.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-quality.$$.log; then
        echo "[OK]   hook engine running (main.py quality → returned a decision)"
    else
        echo "[ERROR] hook engine quality returned no decision:"
        sed 's/^/       /' /tmp/meth-quality.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[ERROR] hook engine quality test failed:"
    sed 's/^/       /' /tmp/meth-quality.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-quality.$$.log
# deploy hook test (PreToolUse — terminalmatcher)
if echo '{}' | "$PY" "$PLUGIN_ROOT/hooks/engine/main.py" deploy --runtime=openhands >/tmp/meth-deploy.$$.log 2>&1; then
    if grep -q '"decision"' /tmp/meth-deploy.$$.log; then
        echo "[OK]   hook engine running (main.py deploy → returned a decision)"
    else
        echo "[ERROR] hook engine deploy returned no decision:"
        sed 's/^/       /' /tmp/meth-deploy.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[ERROR] hook engine deploy test failed:"
    sed 's/^/       /' /tmp/meth-deploy.$$.log
    PROBLEMS=$((PROBLEMS + 1))
fi
rm -f /tmp/meth-deploy.$$.log

echo "== 2) Manifesto wired to all surfaces + bridge (native→record)? =="
"$PY" - <<'PY'
import glob, os, sys, tomllib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
PROJECT = os.environ.get("PROJECT_ROOT") or "."

# Non-methodology tool surfaces — explicitly excluded from the audit (outside the capability map).
EXCLUDED = {"graft", "memory", "sync"}

# Development wing surfaces (development-methodology.md §6 mapping + dev agents):
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
        # Customization line: root + team + personal — effective facts (merge additive)
        facts = []
        ok = True
        for p in (root, team, user):
            if not os.path.isfile(p):
                continue
            try:
                data = tomllib.load(open(p, "rb"))
            except Exception as e:
                print("  PARSE ERROR: %s: %s" % (p, e))
                missing.append("%s (parse)" % name)
                ok = False
                break
            for sec in ("agent", "workflow"):
                facts += data.get(sec, {}).get("persistent_facts", [])
        if not ok:
            continue
        if not any("research-methodology.md" in x for x in facts):
            missing.append("%s (no manifesto: root+team+user)" % name)
        elif not any("project-context.md" in x for x in facts):
            missing.append("%s (no project-context)" % name)
        if name in DEV_WING and not any("development-methodology.md" in x for x in facts):
            missing.append("%s (no development manifesto)" % name)
        # Consumption: facts must not just be configured — the surface must actually load them.
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
            missing.append("%s (cosmetic: does not call resolve_customization)" % name)
    else:
        # No customization line → SKILL.md pointer
        try:
            txt = open(os.path.join(d, "SKILL.md"), encoding="utf-8").read()
        except Exception as e:
            missing.append("%s (unreadable: %s)" % (name, e))
            continue
        if "research-methodology.md" not in txt:
            missing.append("%s (no SKILL.md pointer)" % name)
        if name in DEV_WING and "development-methodology.md" not in txt:
            missing.append("%s (no SKILL.md development manifesto pointer)" % name)

# Menu skill targets must exist (broken capability link class).
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
                missing.append("%s menu → %s (skill directory missing)" % (os.path.basename(cp), s))

# Development wing manifesto: must be installed in the target project (/metodoloji:init).
DEVWING = os.path.join(PROJECT, "docs", "bmad", "development-methodology.md")
if not os.path.isfile(DEVWING):
    # In dogfooding the plugin root may also be it (methodology repo = PROJECT).
    missing.append("%s (document missing — run /metodoloji:init in target project)" % DEVWING)

# --- Bridge audit: native skill output → methodology record translation ---
BRIDGE = os.path.join(PROJECT, "docs", "bmad", "dev-skill-to-methodology-bridge.md")
if not os.path.isfile(BRIDGE):
    missing.append("%s (bridge document missing — native output not translated to methodology record)" % BRIDGE)

# Phase-1 bridge skills: each must produce docs/development/<record>-*.md.
BRIDGE_SKILLS = {
    "bmad-check-implementation-readiness": ("IR", "docs/development/", "create"),
    "bmad-sprint-planning": ("SP", "docs/development/", "create"),
    "bmad-create-story": ("S", "docs/development/stories/", "create"),
    "bmad-code-review": ("QR", "docs/development/", "create"),
    "bmad-dev-story": ("S", "docs/development/stories/", "update"),
    "bmad-quick-dev": ("S", "docs/development/stories/", "update"),
    "bmad-dev-auto": ("S", "docs/development/stories/", "update"),
}
for skill, (rec_type, target, _) in BRIDGE_SKILLS.items():
    toml_path = os.path.join(PLUGIN, "custom", "%s.toml" % skill)
    if not os.path.isfile(toml_path):
        missing.append("%s (no bridge skill override)" % skill)
        continue
    try:
        txt = open(toml_path, encoding="utf-8").read()
    except OSError:
        missing.append("%s (unreadable)" % toml_path)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (no bridge reference — append step may have been removed)" % skill)
    if target not in txt:
        missing.append("%s (methodology record target %s missing)" % (skill, target))

# Phase-3 QR feeders — ones working through the "## Metodoloji" section of SKILL.md.
QR_FEEDERS_SKILLMD = ["bmad-review-adversarial-general", "bmad-review-edge-case-hunter", "bmad-eval-runner"]
for skill in QR_FEEDERS_SKILLMD:
    skill_md = os.path.join(PLUGIN, "skills", skill, "SKILL.md")
    if not os.path.isfile(skill_md):
        missing.append("%s (no SKILL.md)" % skill)
        continue
    try:
        txt = open(skill_md, encoding="utf-8").read()
    except OSError:
        missing.append("%s (unreadable)" % skill_md)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (no bridge reference in SKILL.md)" % skill)
    if "docs/development/QR" not in txt:
        missing.append("%s (no QR feed target in SKILL.md)" % skill)

# Phase-3 QR feeders — ones working via custom/{skill}.toml activation_steps_append.
QR_FEEDERS_TOML = [
    "bmad-qa-generate-e2e-tests",
    "bmad-testarch-atdd", "bmad-testarch-automate", "bmad-testarch-ci",
    "bmad-testarch-framework", "bmad-testarch-nfr", "bmad-testarch-test-design",
    "bmad-testarch-test-review", "bmad-testarch-trace",
]
for skill in QR_FEEDERS_TOML:
    toml_path = os.path.join(PLUGIN, "custom", "%s.toml" % skill)
    if not os.path.isfile(toml_path):
        missing.append("%s (no bridge skill override)" % skill)
        continue
    try:
        txt = open(toml_path, encoding="utf-8").read()
    except OSError:
        missing.append("%s (unreadable)" % toml_path)
        continue
    if "dev-skill-to-methodology-bridge" not in txt:
        missing.append("%s (no bridge reference in append)" % skill)
    if "docs/development/QR" not in txt:
        missing.append("%s (no QR feed target in append)" % skill)

print("  checked surfaces: %d, excluded (non-methodology tool): %d" % (checked, excluded))
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   manifesto wired to all methodology surfaces"
else
    echo "[WARNING] wiring incomplete (see above)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 2b) Bridge instructions visible at runtime? (resolve_customization merge) =="
# The KÖPRÜ step in custom/{skill}.toml must merge with the skill-root customize.toml
# via resolve_customization.py deep_merge (append). Append semantics are persistent.
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
            missing.append("%s (KÖPRÜ absent after merge — custom toml append not working)" % name)
    except Exception as e:
        missing.append("%s (resolve error: %s)" % (name, str(e)[:60]))
print("  checked toml skills (installed): %d" % checked)
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   KÖPRÜ instructions visible at runtime (deep_merge append persistent)"
else
    echo "[WARNING] KÖPRÜ merge problem (see above)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 2c) KÖPRÜ DOGRULAMA instructions present? =="
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
            missing.append("%s (no DOGRULAMA in KÖPRÜ — LLM may skip the record)" % name)
    except Exception as e:
        missing.append("%s (resolve error: %s)" % (name, str(e)[:60]))
print("  checked KÖPRÜ skills: %d" % checked)
for m in missing:
    print("  MISS: %s" % m)
print("  problems: %d" % len(missing))
raise SystemExit(1 if missing else 0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   KÖPRÜ DOGRULAMA instructions present (LLM will auto-verify)"
else
    echo "[WARNING] KÖPRÜ DOGRULAMA missing (see above)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 3) Approved experiment inventory (did guard open code writing?) =="
FOUND=0
for rec in "$PROJECT_ROOT"/docs/experiments/*.md; do
    [ -f "$rec" ] || continue
    case "$(basename "$rec")" in _template.md) continue ;; esac
    if grep -q "Karar:\*\*[[:space:]]*ONAYLANDI" "$rec"; then
        if "$PY" "$GATE" --verify --record "$rec" >/dev/null 2>&1; then
            echo "[OK]   $rec -> VERIFIED"
            FOUND=$((FOUND + 1))
        else
            echo "[ERROR] $rec -> ONAYLANDI but --verify failed (FORGED?)"
            PROBLEMS=$((PROBLEMS + 1))
        fi
    fi
done
if [ "$FOUND" -eq 0 ]; then
    echo "[WARNING] no approved experiment — guard keeps code writing closed. Start with bmad-research-experiment."
    echo "        scratch/ can be used for exploration/experimentation code."
fi

echo "== 4) Documentary (B/C/D) record completeness =="
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
        echo "[IGNORED] $rec (Mod A / unrecognized — not documentary)"
    else
        echo "[WARNING] $rec missing/integrity issue:"
        sed 's/^/        /' /tmp/meth-doc.$$.log
        DOCPROBLEMS=$((DOCPROBLEMS + 1))
    fi
done
rm -f /tmp/meth-doc.$$.log
if [ "$DOCCHECKED" -eq 0 ]; then
    echo "[OK]   no documentary records (docs/research/, docs/design/) — new records will be checked"
fi
PROBLEMS=$((PROBLEMS + DOCPROBLEMS))

echo "== 5) Engine integrity audit (modular engine: main.py + modules/) =="
# The canonical is this repo's hooks/engine/ tree; the plugin copy must match the repo.
# Drift = missing/broken engine file (the old single-file bmad-hooks.py is gone).
ENGINE_OK=1
for f in main.py memlog.py resolve_customization.py modules/__init__.py \
         modules/config.py modules/utils.py modules/archive.py modules/bash_targets.py \
         modules/guard.py modules/audit.py modules/stop.py; do
    if [ ! -f "$PLUGIN_ROOT/hooks/engine/$f" ]; then
        echo "[ERROR] engine file missing: hooks/engine/$f"
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
        echo "[OK]   modular engine complete and importable (main.py + modules/)"
    else
        echo "[ERROR] modular engine import test failed:"
        sed 's/^/       /' /tmp/meth-engine.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
    rm -f /tmp/meth-engine.$$.log
else
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 5b) Hard gate enforcement mode (soft/hard) =="
# quality-gate and deploy-guard hooks are config-gated: custom/config.toml [hooks].
"$PY" - <<'PY'
import tomllib, os, sys
PLUGIN = os.environ.get("PLUGIN_ROOT") or "."
PROJECT = os.environ.get("PROJECT_ROOT") or "."
cfg = os.path.join(PLUGIN, "custom", "config.toml")
mode_default = "soft"
qg, dg = mode_default, mode_default
src = "(no config — soft default)"
if os.path.isfile(cfg):
    try:
        d = tomllib.load(open(cfg, "rb"))
        h = d.get("hooks", {}) or {}
        qg = str(h.get("quality_gate", "soft")).strip().lower()
        dg = str(h.get("deploy_guard", "soft")).strip().lower()
        src = "config"
    except Exception as e:
        print("  [ERROR] config parse: %s" % e)
        sys.exit(1)
problems = []
for name, val in (("quality_gate", qg), ("deploy_guard", dg)):
    if val not in ("soft", "hard"):
        problems.append("%s = %r (invalid — must be soft|hard)" % (name, val))
print("  quality_gate: %s (%s)" % (qg, src))
print("  deploy_guard: %s (%s)" % (dg, src))
if qg == "hard" or dg == "hard":
    import glob as _glob
    _dev = os.path.join(PROJECT, "docs", "development")
    _real = [f for pat in ("IR-*.md", "SP-*.md", "QR-*.md", "PR-*.md")
             for f in _glob.glob(os.path.join(_dev, pat))
             if not os.path.basename(f).startswith("_")]
    if not _real:
        problems.append("hard mode active but no real record in docs/development/ "
                        "(IR-/SP-/QR-/PR-) — every commit/push/deploy is blocked; "
                        "switch to soft or produce a record first")
print("  note: quality/deploy hooks are ACTIVE in OpenHands runtime (hooks.json:")
print("       PreToolUse -> guard/quality/deploy, Stop -> stop, PostToolUse -> audit).")
print("       quality_gate/deploy_guard values are now enforced at the hook level;")
print("       quality: DENY git commit without IR/QR/SP; deploy: DENY deploy without IR/QR/SP/PR.")
if problems:
    for p in problems:
        print("  MISS: %s" % p)
    sys.exit(1)
sys.exit(0)
PY
if [ $? -eq 0 ]; then
    echo "[OK]   hard gate mode valid (config soft; guard/stop fail-closed active)"
else
    echo "[WARNING] hard gate mode issue (see above)"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo "== 5c) custom/ bridge TOMLs static quality audit =="
# check-custom.sh §0-§6: TOML parse, persistent_facts, depth, hard-gate
# keywords, DOGRULAMA pattern, gds Mod A bridge reference, config
# soft/hard contract. Independent script; same style, same [OK]/[WARNING]/[ERROR]
# output. Root output kept internal; only exit code added to PROBLEMS.
if [ -f "$SELF/check-custom.sh" ]; then
    if sh "$SELF/check-custom.sh" >/tmp/meth-custom.$$.log 2>&1; then
        echo "[OK]   custom/ static quality audit passed"
    else
        echo "[WARNING] custom/ static quality violation:"
        sed 's/^/       /' /tmp/meth-custom.$$.log
        PROBLEMS=$((PROBLEMS + 1))
    fi
    rm -f /tmp/meth-custom.$$.log
else
    echo "[WARNING] commands/check-custom.sh not found (skipped)"
fi

echo "== 6) Development records format check =="
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
        echo "[WARNING] $rec -> no Karar/Durum field"
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
        echo "[WARNING] $rec -> unexpected Karar/Durum: '$dec' (allowed: $ALLOWED)"
        DEVPROBLEMS=$((DEVPROBLEMS + 1))
        continue
    fi
    if ! grep -q '\*\*Tarih:\*\*' "$rec"; then
        echo "[WARNING] $rec -> no Tarih field"
        DEVPROBLEMS=$((DEVPROBLEMS + 1))
        continue
    fi
    echo "[OK]   $rec ($dec)"
done
if [ "$DEVCHECKED" -eq 0 ]; then
    echo "[OK]   no development records (docs/development/) — new records will be checked"
fi
PROBLEMS=$((PROBLEMS + DEVPROBLEMS))

echo "== 6a) .env inventory: any hard-coded API key leakage? =="
ENVPROBLEMS=0
# 6a.1) Is .env present in the repo? (should not be — only .env.example)
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "[ERROR]  .env found at repo root — don't rely on .gitignore, .env must not be committed"
    ENVPROBLEMS=$((ENVPROBLEMS + 1))
else
    echo "[OK]    .env not present (protected via .gitignore)"
fi
# 6a.2) Does .env.example exist? (template for new developers)
if [ -f "$PROJECT_ROOT/.env.example" ]; then
    echo "[OK]    .env.example present"
else
    echo "[WARNING] .env.example not found — developer onboarding documentation missing"
    ENVPROBLEMS=$((ENVPROBLEMS + 1))
fi
# 6a.3) Is .env in .gitignore?
if grep -qx '.env' "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
    echo "[OK]    .gitignore → .env present"
else
    echo "[ERROR]  .env line missing in .gitignore — local key leak risk"
    ENVPROBLEMS=$((ENVPROBLEMS + 1))
fi
PROBLEMS=$((PROBLEMS + ENVPROBLEMS))

echo "== 6b) Tech-debt inventory integrity (drift/ID/P0/orphan) =="
if [ -x "$SELF/check-techdebt.sh" ]; then
    sh "$SELF/check-techdebt.sh"
    TDEXIT=$?
    if [ "$TDEXIT" -ne 0 ]; then
        PROBLEMS=$((PROBLEMS + 1))
    fi
else
    echo "[WARNING] $SELF/check-techdebt.sh not found or not executable — §6b skipped"
    PROBLEMS=$((PROBLEMS + 1))
fi

echo
if [ "$PROBLEMS" -eq 0 ]; then
    echo "STATUS: HEALTHY (all checks passed)"
    exit 0
else
    echo "STATUS: $PROBLEMS problems found"
    exit 1
fi
