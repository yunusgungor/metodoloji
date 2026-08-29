#!/usr/bin/env python3
"""Train BMAD skills using SkillOpt.

Usage:
    python scripts/train_bmad.py --benchmark bmad-code-review
    python scripts/train_bmad.py --benchmark all
    python scripts/train_bmad.py --benchmark bmad-code-review --epochs 5 --lr 4
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"

BENCHMARKS = [
    "bmad-code-review",
    "bmad-create-story",
    "bmad-architecture",
    "bmad-prd",
    "bmad-test-design",
]


def train_benchmark(name: str, epochs: int = 3, lr: int = 3, batch_size: int = 8):
    config_path = CONFIGS_DIR / name / "default.yaml"
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return False

    out_root = REPO_ROOT / "outputs" / name
    cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "train.py"),
        "--config", str(config_path),
        "--out_root", str(out_root),
    ]

    print(f"\n{'='*60}")
    print(f"Training: {name}")
    print(f"Config:   {config_path}")
    print(f"Output:   {out_root}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Train BMAD skills with SkillOpt")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review", help="Benchmark to train")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=int, default=3, help="Learning rate (max edits)")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    benchmarks = BENCHMARKS if args.benchmark == "all" else [args.benchmark]

    results = {}
    for name in benchmarks:
        ok = train_benchmark(name, epochs=args.epochs, lr=args.lr,
                             batch_size=args.batch_size)
        results[name] = ok

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    all_pass = all(results.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
