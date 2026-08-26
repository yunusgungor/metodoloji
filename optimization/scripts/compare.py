#!/usr/bin/env python3
"""SkillOpt before/after compare — diffs optimization/output/baseline.json
(before, written by baseline.py) against optimization/output/benchmark_results.json
(after, written by pipeline.py after SkillOpt eğitimi).

If no "after" file exists yet, prints the baseline snapshot only and exits 0.
This makes the script idempotent: it always tells you where you stand.

LLM is NOT required — this is purely a JSON diff tool.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "optimization" / "output"

BEFORE_PATH = OUT_DIR / "baseline.json"
AFTER_PATH = OUT_DIR / "benchmark_results.json"   # pipeline.py'nin canonical çıktısı


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_baseline(before: dict) -> None:
    print("=" * 60)
    print("  SkillOpt Baseline Snapshot (optimization/output/baseline.json)")
    print("=" * 60)
    print(f"\n  Genel: {before['passed']}/{before['total_tasks']} ({before['hard_accuracy']:.2%})")
    print(f"\n  Kategoriler:")
    for cat, rate in sorted(before.get("per_category", {}).items()):
        print(f"    {cat:10s} {rate:.0%}")
    print(f"\n  Skill dağılımı (hook-chain):")
    for skill, m in before.get("per_skill", {}).items():
        if m["total_tasks"]:
            print(f"    {skill:40s} {m['passed']:2d}/{m['total_tasks']:2d} ({m['hard_accuracy']:.0%})")


def _diff(before: dict, after: dict) -> None:
    print("\n" + "=" * 60)
    print("  Before / After Karşılaştırma")
    print("=" * 60)
    print(f"\n  {'Skill':40s}  {'Before':>10s}  {'After':>10s}  {'Δ':>10s}")
    print(f"  {'-'*40}  {'-'*10}  {'-'*10}  {'-'*10}")

    # pipeline.py sonrası "after" sözlüğü {skill_name: {hard_accuracy, ...}} formatında
    # baseline.py ise per_skill sözlüğü içinde tutuyor. İki formatı uzlaştır.
    after_per_skill = after.get("per_skill") if isinstance(after.get("per_skill"), dict) else after

    skills = set(before.get("per_skill", {}).keys()) | set(after_per_skill.keys())
    for skill in sorted(skills):
        b = before.get("per_skill", {}).get(skill, {})
        a = after_per_skill.get(skill, {}) if isinstance(after_per_skill.get(skill), dict) else {"hard_accuracy": after_per_skill.get(skill, 0)}
        b_hard = b.get("hard_accuracy", 0)
        a_hard = a.get("hard_accuracy", 0) if isinstance(a, dict) else a
        delta = a_hard - b_hard
        arrow = "↑" if delta > 0.001 else ("↓" if delta < -0.001 else "→")
        print(f"  {skill:40s}  {b_hard:9.2%}  {a_hard:9.2%}  {arrow}{delta:+9.2%}")


def main():
    before = _load(BEFORE_PATH)
    if before is None:
        print(f"[HATA] baseline.json bulunamadı: {BEFORE_PATH}")
        print("  Önce çalıştır: python optimization/scripts/baseline.py")
        sys.exit(1)

    _print_baseline(before)

    after = _load(AFTER_PATH)
    if after is None:
        print("\n  not: benchmark_results.json henüz yok (SkillOpt eğitimi koşturulmamış).")
        print("       İlk 'before' snapshot yukarıda — pipeline.py ile eğitim sonrası")
        print("       karşılaştırma otomatik görünecek.")
        return

    _diff(before, after)


if __name__ == "__main__":
    main()
