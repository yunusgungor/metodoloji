#!/usr/bin/env python3
"""Evaluate a trained BMAD skill.

Usage:
    python scripts/eval_bmad.py --benchmark bmad-code-review --skill outputs/bmad-code-review/best_skill.md
    python scripts/eval_bmad.py --benchmark all
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

BENCHMARKS = [
    "bmad-code-review",
    "bmad-create-story",
    "bmad-architecture",
    "bmad-prd",
    "bmad-test-design",
]


def eval_benchmark(name: str, skill_path: str = None, split: str = "valid"):
    config_path = CONFIGS_DIR / name / "default.yaml"
    if not skill_path:
        skill_path = OUTPUTS_DIR / name / "best_skill.md"

    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return False
    if not Path(skill_path).exists():
        print(f"[ERROR] Skill not found: {skill_path}")
        return False

    cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "eval_only.py"),
        "--config", str(config_path),
        "--skill", str(skill_path),
        "--split", split,
    ]

    print(f"\nEvaluating: {name} | skill: {skill_path} | split: {split}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained BMAD skills")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--skill", default=None, help="Path to skill .md file")
    parser.add_argument("--split", default="valid", help="Data split to evaluate")
    args = parser.parse_args()

    benchmarks = BENCHMARKS if args.benchmark == "all" else [args.benchmark]

    results = {}
    for name in benchmarks:
        ok = eval_benchmark(name, skill_path=args.skill, split=args.split)
        results[name] = ok

    print("\n" + "=" * 60)
    print("EVAL RESULTS")
    print("=" * 60)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
