#!/usr/bin/env python3
"""Deterministic Hook Benchmark — runs the real methodology hook engine
(guard, quality, deploy, stop, audit) against benchmark scenarios and reports
pass/fail per category.

This measures the ACTUAL code behavior, not model recall. Fully deterministic.

Usage:
    python optimization/run_hook_benchmark.py          # run all 60 tasks
    python optimization/run_hook_benchmark.py --type guard   # only guard
    python optimization/run_hook_benchmark.py --json   # JSON output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(OPT_DIR))

from envs.bmad.dataloader import BmadLoader
from envs.bmad.rollout import _run_hook


def main():
    parser = argparse.ArgumentParser(description="Deterministic BMAD hook benchmark")
    parser.add_argument("--type", type=str, help="Filter by task type (guard, quality, deploy, stop, audit, bridge, chain)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--data", type=str, default="optimization/benchmarks/data/all_tasks.jsonl", help="Benchmark data path")
    args = parser.parse_args()

    loader = BmadLoader(data_path=args.data, split_mode="ratio", split_ratio="2:1:7")
    loader.setup({})
    all_items = loader.train_items + loader.val_items + loader.test_items

    if args.type:
        all_items = [i for i in all_items if i.get("task_type") == args.type]

    by_type = defaultdict(lambda: Counter())
    failures = []
    for item in all_items:
        predicted = _run_hook(item)
        exp = item.get("expected_action", "?")
        gt = item.get("ground_truth", "?")
        ok = predicted.lower() == exp or gt in predicted
        by_type[item["task_type"]]["pass" if ok else "fail"] += 1
        if not ok:
            failures.append({
                "id": item["id"],
                "type": item["task_type"],
                "expected": exp,
                "ground_truth": gt,
                "got": predicted,
            })

    if args.json:
        result = {
            "total_pass": sum(c["pass"] for c in by_type.values()),
            "total_fail": sum(c["fail"] for c in by_type.values()),
            "categories": {
                t: {"pass": c["pass"], "fail": c["fail"], "rate": c["pass"] / max(c["pass"] + c["fail"], 1)}
                for t, c in by_type.items()
            },
            "failures": failures,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"\n{'='*55}")
    print("  BMAD Hook Benchmark — deterministic (real hook engine)")
    print(f"{'='*55}\n")

    total_p = total_f = 0
    for t in sorted(by_type):
        c = by_type[t]
        total = c["pass"] + c["fail"]
        total_p += c["pass"]
        total_f += c["fail"]
        rate = c["pass"] / total if total else 0
        bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
        print(f"  {t:8s} [{bar}] {c['pass']:3d}/{total} ({rate:.0%})")

    total = total_p + total_f
    rate = total_p / total if total else 0
    bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
    print(f"\n  {'TOTAL':8s} [{bar}] {total_p:3d}/{total} ({rate:.2%})")

    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f in failures:
            print(f"    {f['id']:15s} exp={f['expected']:10s} got={f['got']:10s}")

    print()


if __name__ == "__main__":
    main()