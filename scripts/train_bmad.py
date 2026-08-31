#!/usr/bin/env python3
"""Train BMAD skills using SkillOpt.

Usage:
    python scripts/train_bmad.py --benchmark bmad-code-review
    python scripts/train_bmad.py --benchmark all
    python scripts/train_bmad.py --benchmark bmad-code-review --epochs 5 --lr 4
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from bmad_benchmarks.registry import (
    BENCHMARKS, register_all_adapters, load_benchmark_config, build_train_argv,
)


def train_benchmark(name, extra_args=None):
    os.chdir(REPO_ROOT)
    try:
        cfg = load_benchmark_config(name)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return False

    sys.argv = build_train_argv(name, cfg, extra_args)

    print(f"\n{'='*60}\nTraining: {name}\n{'='*60}\n")
    try:
        if "scripts.train" in sys.modules:
            del sys.modules["scripts.train"]
        register_all_adapters()
        from scripts.train import main as train_main
        train_main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def main():
    os.chdir(REPO_ROOT)
    parser = argparse.ArgumentParser(description="Train BMAD skills with SkillOpt")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=int, default=3, help="Learning rate (max edits)")
    parser.add_argument("--batch-size", type=int, default=8)
    args, extra = parser.parse_known_args()

    print("Registering BMAD adapters...")
    register_all_adapters()

    benchmarks = BENCHMARKS if args.benchmark == "all" else [args.benchmark]
    extra_args = []
    if args.epochs != 3:
        extra_args.extend(["--num_epochs", str(args.epochs)])
    if args.lr != 3:
        extra_args.extend(["--learning_rate", str(args.lr)])
    if args.batch_size != 8:
        extra_args.extend(["--batch_size", str(args.batch_size)])
    extra_args.extend(extra)

    results = {}
    for name in benchmarks:
        results[name] = train_benchmark(name, extra_args=extra_args)

    print("\n" + "=" * 60 + "\nRESULTS\n" + "=" * 60)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
