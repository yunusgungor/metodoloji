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
os.chdir(REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from bmad_benchmarks.registry import (
    BENCHMARKS, register_all_adapters, build_train_argv, run_benchmarks,
)


def main():
    parser = argparse.ArgumentParser(description="Train BMAD skills with SkillOpt")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=int, default=3, help="Learning rate (max edits)")
    parser.add_argument("--batch-size", type=int, default=8)
    args, extra = parser.parse_known_args()

    register_all_adapters()

    names = BENCHMARKS if args.benchmark == "all" else [args.benchmark]
    extra_args = []
    if args.epochs != 3:
        extra_args.extend(["--num_epochs", str(args.epochs)])
    if args.lr != 3:
        extra_args.extend(["--learning_rate", str(args.lr)])
    if args.batch_size != 8:
        extra_args.extend(["--batch_size", str(args.batch_size)])
    extra_args.extend(extra)

    def build_argv(name, cfg):
        return build_train_argv(name, cfg, extra_args)

    ok = run_benchmarks(names, build_argv, "scripts.train", "TRAINING RESULTS")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
