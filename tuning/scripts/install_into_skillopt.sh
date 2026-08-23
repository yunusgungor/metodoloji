#!/bin/sh
# metodoloji env'ini bir SkillOpt checkout'una bağlar (idempotent).
# Kullanım: sh tuning/scripts/install_into_skillopt.sh /path/to/SkillOpt
set -eu

SKILLOPT_DIR="${1:?kullanim: install_into_skillopt.sh /path/to/SkillOpt}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"   # tuning/ kökü

[ -d "$SKILLOPT_DIR/skillopt/envs" ] || { echo "SkillOpt checkout bulunamadi: $SKILLOPT_DIR"; exit 1; }

# 1) env paketi
ln -sfn "$SRC/skillopt_env/metodoloji" "$SKILLOPT_DIR/skillopt/envs/metodoloji"
# 2) veri seti
ln -sfn "$SRC/data/metodoloji_split" "$SKILLOPT_DIR/data/metodoloji_split"
# 3) config
mkdir -p "$SKILLOPT_DIR/configs/metodoloji"
ln -sfn "$SRC/configs/metodoloji/default.yaml" "$SKILLOPT_DIR/configs/metodoloji/default.yaml"

# 4) registry kayıtları (train.py + eval_only.py) — _register_builtins icindeki
#    son try/except blogunun ardina ekler.
for script in "$SKILLOPT_DIR/scripts/train.py" "$SKILLOPT_DIR/scripts/eval_only.py"; do
  if ! grep -q '"metodoloji"' "$script"; then
    python3 - "$script" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
block = (
    '    try:\n'
    '        from skillopt.envs.metodoloji.adapter import MetodolojiAdapter\n'
    '        _ENV_REGISTRY["metodoloji"] = MetodolojiAdapter\n'
    '    except ImportError:\n'
    '        pass\n'
)
idx = text.find("\ndef get_adapter")
if idx == -1:
    raise SystemExit(f"get_adapter bulunamadi: {path}")
head = text[:idx]
cut = head.rfind("        pass\n")
if cut == -1:
    raise SystemExit(f"registry blogu bulunamadi: {path}")
cut += len("        pass\n")
open(path, "w", encoding="utf-8").write(head[:cut] + block + head[cut:] + text[idx:])
print(f"patched: {path}")
PY
  fi
done

echo "OK — SkillOpt kokunden calistir:"
echo "  python scripts/train.py --config configs/metodoloji/default.yaml"
