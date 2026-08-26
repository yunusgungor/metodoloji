#!/usr/bin/env python3
"""SkillOpt baseline — runs the deterministic hook benchmark against all
benchmark task categories (incl. techdebt) and writes a pipeline-compatible
summary to optimization/output/baseline.json.

The summary uses SkillOpt's `run_benchmark` return shape so the
`compare.py` script can diff before/after in a single format.

  - hard_accuracy: passed / total (float in [0, 1])
  - soft_accuracy: passed / total (same proxy here; no LLM-graded soft)
  - passed: int
  - total_tasks: int
  - per_category: {name: {pass, fail, rate}}

No LLM calls; reads .env only if you also need SkillOpt eğitimi (this
script is benchmark-only, so .env is NOT required).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OPT_DIR = PROJECT_ROOT / "optimization"
DATA_DIR = OPT_DIR / "benchmarks" / "data"
OUT_DIR = OPT_DIR / "output"

HOOK_CHAIN_SKILLS = [
    "bmad-research-experiment",
    "bmad-check-implementation-readiness",
    "bmad-sprint-planning",
    "bmad-create-story",
    "bmad-dev-story",
    "bmad-code-review",
]


def _combine_benchmark_data() -> Path:
    """Concatenate all_tasks.jsonl + techdebt_tasks.jsonl into a single
    baseline input. Idempotent: re-writes each invocation.
    """
    combined = DATA_DIR / "_baseline_combined.jsonl"
    with open(combined, "w", encoding="utf-8") as out:
        for src in ("all_tasks.jsonl", "techdebt_tasks.jsonl"):
            p = DATA_DIR / src
            if not p.exists():
                continue
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        out.write(line)
    return combined


def _run_combined(combined: Path) -> dict:
    """Invoke run_hook_benchmark.py --json and parse the JSON object."""
    r = subprocess.run(
        [sys.executable, str(OPT_DIR / "run_hook_benchmark.py"),
         "--data", str(combined), "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        cwd=str(PROJECT_ROOT),
    )
    idx = r.stdout.find("{")
    if idx < 0:
        raise RuntimeError(f"benchmark JSON bulunamadı. stdout:\n{r.stdout[:500]}")
    return json.loads(r.stdout[idx:])


def _per_skill_breakdown(combined: Path) -> dict:
    """Group benchmark results by task.skill_target → rate per hook-chain skill."""
    # Re-run hook engine and tally per task.skill_target
    sys.path.insert(0, str(OPT_DIR))
    from envs.bmad.dataloader import BmadLoader
    from envs.bmad.rollout import _run_hook
    loader = BmadLoader(data_path=str(combined), split_mode="ratio", split_ratio="2:1:7")
    loader.setup({})
    items = loader.train_items + loader.val_items + loader.test_items

    per_skill = defaultdict(lambda: {"pass": 0, "fail": 0, "task_ids": []})
    for it in items:
        target = it.get("skill_target", "")
        # skill_target="skills/bmad-xxx/SKILL.md" → "bmad-xxx"
        skill = target.split("/")[1] if target.startswith("skills/") else target
        pred = _run_hook(it)
        exp = it.get("expected_action", "?")
        gt = it.get("ground_truth", "?")
        ok = pred.lower() == exp or gt in pred
        bucket = per_skill[skill]
        bucket["pass" if ok else "fail"] += 1
        bucket["task_ids"].append(it["id"])

    return dict(per_skill)


def main():
    print("=" * 60)
    print("  SkillOpt Baseline — deterministic hook benchmark")
    print("=" * 60)

    combined = _combine_benchmark_data()
    print(f"  Birleşik veri: {combined.name} (all_tasks + techdebt)")

    overall = _run_combined(combined)
    per_skill = _per_skill_breakdown(combined)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "skill": "<all>",
        "total_tasks": overall["total_pass"] + overall["total_fail"],
        "hard_accuracy": round(overall["total_pass"] / max(overall["total_pass"] + overall["total_fail"], 1), 4),
        "soft_accuracy": round(overall["total_pass"] / max(overall["total_pass"] + overall["total_fail"], 1), 4),
        "passed": overall["total_pass"],
        "per_category": {k: v["pass"] / max(v["pass"] + v["fail"], 1) for k, v in overall["categories"].items()},
        "per_skill": {
            skill: {
                "total_tasks": per_skill.get(skill, {}).get("pass", 0) + per_skill.get(skill, {}).get("fail", 0),
                "passed": per_skill.get(skill, {}).get("pass", 0),
                "failed": per_skill.get(skill, {}).get("fail", 0),
                "hard_accuracy": round(
                    per_skill.get(skill, {}).get("pass", 0) / max(
                        per_skill.get(skill, {}).get("pass", 0) + per_skill.get(skill, {}).get("fail", 0), 1), 4),
            }
            for skill in HOOK_CHAIN_SKILLS
        },
    }

    out_path = OUT_DIR / "baseline.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n  Genel: {summary['passed']}/{summary['total_tasks']} ({summary['hard_accuracy']:.2%})")
    print(f"  Kategoriler: {len(summary['per_category'])}")
    print(f"  Skill dağılımı:")
    for skill, m in summary["per_skill"].items():
        if m["total_tasks"]:
            print(f"    {skill:40s} {m['passed']:2d}/{m['total_tasks']:2d} ({m['hard_accuracy']:.0%})")
    print(f"\n  Kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
