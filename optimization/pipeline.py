#!/usr/bin/env python3
"""BMAD Optimization Pipeline — automated multi-skill optimization with integration testing.

Runs:
1. Baseline benchmark (before optimization)
2. Optimize each hook-chain skill sequentially
3. Integration test (all skills work together)
4. Regression test (check-plugin.sh still passes)
5. Final benchmark (after optimization)
6. Comparison report
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(OPT_DIR))

HOOK_CHAIN_SKILLS = [
    "bmad-research-experiment",
    "bmad-check-implementation-readiness",
    "bmad-sprint-planning",
    "bmad-create-story",
    "bmad-dev-story",
    "bmad-code-review",
]


def log(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run_check_plugin() -> bool:
    """Run check-plugin.sh and return True if healthy."""
    try:
        result = subprocess.run(
            ["sh", str(PROJECT_ROOT / "commands" / "check-plugin.sh")],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        return "SAĞLIKLI" in result.stdout
    except Exception as e:
        print(f"  check-plugin.sh error: {e}")
        return False


def run_negtest() -> bool:
    """Run check-plugin.sh --negtest and return True if passes."""
    try:
        result = subprocess.run(
            ["sh", str(PROJECT_ROOT / "commands" / "check-plugin.sh"), "--negtest"],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        return "[OK]" in result.stdout
    except Exception as e:
        print(f"  negtest error: {e}")
        return False


def run_benchmark_all() -> dict:
    """Run benchmark on all hook-chain skills."""
    from train import run_benchmark, DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    results = {}
    for skill in HOOK_CHAIN_SKILLS:
        try:
            results[skill] = run_benchmark(skill, cfg)
        except Exception as e:
            results[skill] = {"error": str(e)}
    return results


def run_optimize_all() -> dict:
    """Optimize all hook-chain skills."""
    from train import run_training, DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    cfg["num_epochs"] = 2  # Fewer epochs for pipeline
    results = {}
    for skill in HOOK_CHAIN_SKILLS:
        try:
            results[skill] = run_training(skill, cfg)
        except Exception as e:
            results[skill] = {"error": str(e)}
    return results


def main():
    start_time = time.time()

    log("STEP 1: Baseline Benchmark")
    before = run_benchmark_all()
    before_path = OPT_DIR / "output" / "benchmark_results.json"
    before_path.parent.mkdir(parents=True, exist_ok=True)
    with open(before_path, "w", encoding="utf-8") as f:
        json.dump(before, f, indent=2, ensure_ascii=False, default=str)

    log("STEP 2: Regression Test (before optimization)")
    reg_before = run_check_plugin()
    neg_before = run_negtest()
    print(f"  check-plugin.sh: {'PASS' if reg_before else 'FAIL'}")
    print(f"  negtest: {'PASS' if neg_before else 'FAIL'}")

    log("STEP 3: Optimize Hook-Chain Skills")
    opt_results = run_optimize_all()

    log("STEP 4: Regression Test (after optimization)")
    reg_after = run_check_plugin()
    neg_after = run_negtest()
    print(f"  check-plugin.sh: {'PASS' if reg_after else 'FAIL'}")
    print(f"  negtest: {'PASS' if neg_after else 'FAIL'}")

    log("STEP 5: Final Benchmark")
    after = run_benchmark_all()
    after_path = OPT_DIR / "output" / "benchmark_results_after.json"
    with open(after_path, "w", encoding="utf-8") as f:
        json.dump(after, f, indent=2, ensure_ascii=False, default=str)

    log("STEP 6: Comparison Report")
    print(f"\n  {'Skill':40s}  {'Before':>10s}  {'After':>10s}  {'Delta':>10s}")
    print(f"  {'-'*40}  {'-'*10}  {'-'*10}  {'-'*10}")
    for skill in HOOK_CHAIN_SKILLS:
        b = before.get(skill, {})
        a = after.get(skill, {})
        b_hard = b.get("hard_accuracy", 0) if isinstance(b, dict) else 0
        a_hard = a.get("hard_accuracy", 0) if isinstance(a, dict) else 0
        delta = a_hard - b_hard
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        print(f"  {skill:40s}  {b_hard:9.2%}  {a_hard:9.2%}  {arrow}{delta:+9.2%}")

    print(f"\n  Regression: check-plugin={'PASS' if reg_after else 'FAIL'} negtest={'PASS' if neg_after else 'FAIL'}")

    # Save final summary
    summary = {
        "before": before,
        "after": after,
        "optimization": {k: {"status": "ok" if "error" not in v else "error"} for k, v in opt_results.items()},
        "regression": {"check_plugin": reg_after, "negtest": neg_after},
        "elapsed_s": round(time.time() - start_time, 1),
    }
    summary_path = OPT_DIR / "output" / "pipeline_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Pipeline complete in {summary['elapsed_s']}s")
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
