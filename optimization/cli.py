#!/usr/bin/env python3
"""BMAD SkillOpt CLI — unified interface for benchmark, optimize, compare, sleep.

Usage:
    python optimization/cli.py benchmark                    # Run all benchmarks
    python optimization/cli.py benchmark --skill bmad-dev-story  # Benchmark one skill
    python optimization/cli.py optimize --skill bmad-dev-story   # Optimize one skill
    python optimization/cli.py optimize --chain               # Optimize all hook-chain
    python optimization/cli.py compare                        # Compare before/after
    python optimization/cli.py status                         # Show optimization status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(OPT_DIR))

# Configure openai_compatible backend BEFORE any skillopt imports
os.environ.setdefault("REFLACT_MODEL_BACKEND", "openai_compatible")
os.environ.setdefault("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:20128/v1")
os.environ.setdefault("OPENAI_COMPATIBLE_API_KEY", "sk-2d3c99a72a01cbcc-smtwcf-24b76850")
os.environ.setdefault("OPENAI_COMPATIBLE_MODEL", "crof/deepseek-v4-flash-0731")


HOOK_CHAIN_SKILLS = [
    "bmad-research-experiment",
    "bmad-check-implementation-readiness",
    "bmad-sprint-planning",
    "bmad-create-story",
    "bmad-dev-story",
    "bmad-code-review",
]


def cmd_benchmark(args):
    """Run benchmark evaluation."""
    from train import run_benchmark, DEFAULT_CONFIG

    cfg = dict(DEFAULT_CONFIG)
    if args.epochs:
        cfg["num_epochs"] = args.epochs

    if args.skill:
        skills = [args.skill]
    elif args.chain:
        skills = HOOK_CHAIN_SKILLS
    else:
        # Benchmark all skills that have SKILL.md
        skills_dir = PROJECT_ROOT / "skills"
        skills = [d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

    results = {}
    for skill in skills:
        try:
            result = run_benchmark(skill, cfg)
            results[skill] = result
        except Exception as e:
            print(f"  ERROR benchmarking {skill}: {e}")
            results[skill] = {"error": str(e)}

    # Save results
    results_path = OPT_DIR / "output" / "benchmark_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Results saved to {results_path}")
    return results


def cmd_optimize(args):
    """Run SkillOpt training."""
    from train import run_training, DEFAULT_CONFIG

    cfg = dict(DEFAULT_CONFIG)
    if args.epochs:
        cfg["num_epochs"] = args.epochs
    if args.batch_size:
        cfg["batch_size"] = args.batch_size
    if args.edit_budget:
        cfg["edit_budget"] = args.edit_budget

    if args.skill:
        skills = [args.skill]
    elif args.chain:
        skills = HOOK_CHAIN_SKILLS
    else:
        parser.error("Specify --skill or --chain")
        return

    results = {}
    for skill in skills:
        try:
            result = run_training(skill, cfg)
            results[skill] = result
        except Exception as e:
            print(f"  ERROR optimizing {skill}: {e}")
            results[skill] = {"error": str(e)}

    results_path = OPT_DIR / "output" / "optimization_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Results saved to {results_path}")
    return results


def cmd_compare(args):
    """Compare benchmark results before and after optimization."""
    before_path = OPT_DIR / "output" / "benchmark_results.json"
    after_path = OPT_DIR / "output" / "benchmark_results_after.json"

    if not before_path.exists():
        print("  No benchmark results found. Run: python optimization/cli.py benchmark")
        return

    with open(before_path, encoding="utf-8") as f:
        before = json.load(f)

    after = {}
    if after_path.exists():
        with open(after_path, encoding="utf-8") as f:
            after = json.load(f)

    print(f"\n{'='*60}")
    print("  BMAD SkillOpt — Before/After Comparison")
    print(f"{'='*60}\n")

    for skill, b_data in before.items():
        if isinstance(b_data, dict) and "error" not in b_data:
            b_hard = b_data.get("hard_accuracy", 0)
            a_data = after.get(skill, {})
            a_hard = a_data.get("hard_accuracy", 0) if isinstance(a_data, dict) else 0
            delta = a_hard - b_hard
            arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            print(f"  {skill:40s}  {b_hard:.2%} → {a_hard:.2%}  {arrow} {delta:+.2%}")

    print()


def cmd_status(args):
    """Show optimization status."""
    output_dir = OPT_DIR / "output"
    if not output_dir.exists():
        print("  No optimization output found.")
        return

    print(f"\n{'='*60}")
    print("  BMAD SkillOpt — Status")
    print(f"{'='*60}\n")

    for skill_dir in sorted(output_dir.iterdir()):
        if skill_dir.is_dir() and skill_dir.name not in ("benchmark_results.json", "chain_summary.json"):
            best_skill = skill_dir / "best_skill.md"
            history = skill_dir / "history.json"
            config = skill_dir / "config.json"

            status = "trained" if best_skill.exists() else "pending"
            steps = 0
            best_score = 0

            if history.exists():
                with open(history, encoding="utf-8") as f:
                    h = json.load(f)
                steps = len(h)
                if h:
                    best_score = max(s.get("best_score", 0) for s in h)

            model = "?"
            if config.exists():
                with open(config, encoding="utf-8") as f:
                    c = json.load(f)
                model = c.get("optimizer_model", "?")

            print(f"  {skill_dir.name:40s}  {status:8s}  steps={steps:3d}  best={best_score:.4f}  model={model}")

    print()


def main():
    parser = argparse.ArgumentParser(description="BMAD SkillOpt CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Run benchmark evaluation")
    p_bench.add_argument("--skill", type=str, help="Specific skill to benchmark")
    p_bench.add_argument("--chain", action="store_true", help="Benchmark hook-chain skills")
    p_bench.add_argument("--epochs", type=int, default=3)

    # optimize
    p_opt = sub.add_parser("optimize", help="Run SkillOpt training")
    p_opt.add_argument("--skill", type=str, help="Specific skill to optimize")
    p_opt.add_argument("--chain", action="store_true", help="Optimize hook-chain skills")
    p_opt.add_argument("--epochs", type=int, default=3)
    p_opt.add_argument("--batch-size", type=int, default=10)
    p_opt.add_argument("--edit-budget", type=int, default=6)

    # compare
    sub.add_parser("compare", help="Compare before/after results")

    # status
    sub.add_parser("status", help="Show optimization status")

    args = parser.parse_args()

    if args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "optimize":
        cmd_optimize(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
