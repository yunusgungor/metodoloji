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

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from bmad_benchmarks.registry import (
    BENCHMARKS, register_all_adapters, load_benchmark_config, build_eval_argv,
)


def eval_benchmark(name, skill_path=None, split="test"):
    os.chdir(REPO_ROOT)
    if not skill_path:
        skill_path = str(OUTPUTS_DIR / name / "best_skill.md")
    if not Path(skill_path).exists():
        print(f"[ERROR] Skill not found: {skill_path}")
        return False

    try:
        cfg = load_benchmark_config(name)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return False

    sys.argv = build_eval_argv(name, cfg, skill_path, split)

    print(f"\nEvaluating: {name} | skill: {skill_path} | split: {split}")
    try:
        for mod in list(sys.modules):
            if mod.startswith("scripts.eval_only"):
                del sys.modules[mod]
        register_all_adapters()
        from scripts.eval_only import main as eval_main
        eval_main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def main():
    os.chdir(REPO_ROOT)
    parser = argparse.ArgumentParser(description="Evaluate trained BMAD skills")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--skill", default=None, help="Path to skill .md file")
    parser.add_argument("--split", default="test", help="Data split to evaluate")
    args = parser.parse_args()

    print("Registering BMAD adapters...")
    register_all_adapters()

    benchmarks = BENCHMARKS if args.benchmark == "all" else [args.benchmark]
    results = {}
    for name in benchmarks:
        results[name] = eval_benchmark(name, skill_path=args.skill, split=args.split)

    print("\n" + "=" * 60 + "\nEVAL RESULTS\n" + "=" * 60)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
