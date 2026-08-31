#!/usr/bin/env python3
"""Evaluate a trained BMAD skill using SkillOpt.

Usage:
    python scripts/eval_bmad.py --benchmark bmad-code-review --split test
    python scripts/eval_bmad.py --benchmark all
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs"
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from bmad_benchmarks.registry import (
    BENCHMARKS, register_all_adapters, build_eval_argv, run_benchmarks,
)


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained BMAD skills")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--skill", default=None, help="Path to skill .md file")
    parser.add_argument("--split", default="test", help="Data split to evaluate")
    args = parser.parse_args()

    register_all_adapters()

    names = BENCHMARKS if args.benchmark == "all" else [args.benchmark]
    if args.skill:
        skill_path = args.skill
        if not Path(skill_path).exists():
            print(f"[ERROR] Skill not found: {skill_path}")
            raise SystemExit(1)
    else:
        skill_path = None  # each benchmark falls back to its own best_skill.md

    def build_argv(name, cfg):
        chosen = skill_path or str(OUTPUTS_DIR / name / "best_skill.md")
        return build_eval_argv(name, cfg, chosen, args.split)

    ok = run_benchmarks(names, build_argv, "scripts.eval_only", "EVAL RESULTS")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
