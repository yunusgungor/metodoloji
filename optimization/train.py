#!/usr/bin/env python3
"""BMAD SkillOpt Training — runs the ReflACT training loop for BMAD skills.

Usage:
    python optimization/train.py --skill bmad-dev-story
    python optimization/train.py --skill bmad-code-review --epochs 5
    python optimization/train.py --chain  # optimize all hook-chain skills
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add optimization dir to path for env imports
OPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(OPT_DIR))

# Configure openai_compatible backend BEFORE any skillopt imports.
# Bu değerler artık hard-coded DEĞİL — sadece local geliştirmede hızlı bootstrap
# için default. Gerçek değerler .env'den (os.environ) gelir. Eğitim komutları
# `_require_llm_env()` ile zorunlu env'lerin dolu olduğunu denetler.
os.environ.setdefault("REFLACT_MODEL_BACKEND", "openai_compatible")
os.environ.setdefault("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:20128/v1")
# OPENAI_COMPATIBLE_API_KEY ve OPENAI_COMPATIBLE_MODEL setdefault YAPILMAZ —
# güvenlik: anahtar repo dışında kalmalı, model .env/.yaml'da bilinçli seçilmeli.

REQUIRED_LLM_ENV = ("OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_MODEL")


def _require_llm_env() -> None:
    """Eğitim/optimize çağrılarından önce zorunlu env'lerin varlığını denetle.

    API anahtarı setdefault ile asla koyulmaz: bu hem güvenlik borcudur (TD-012)
    hem de deterministik eğitimi bozar (anahtar değişirse sonuç değişir).
    """
    missing = [k for k in REQUIRED_LLM_ENV if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"[HATA] Eksik env değişkenleri: {', '.join(missing)}\n"
            f"  Çözüm: cp .env.example .env && değerleri doldur\n"
            f"  Veya:  export OPENAI_COMPATIBLE_API_KEY=... OPENAI_COMPATIBLE_MODEL=..."
        )


# Hook-chain skills to optimize in order
HOOK_CHAIN_SKILLS = [
    "bmad-research-experiment",
    "bmad-check-implementation-readiness",
    "bmad-sprint-planning",
    "bmad-create-story",
    "bmad-dev-story",
    "bmad-code-review",
]

DEFAULT_CONFIG = {
    "model_backend": "openai_compatible",
    "optimizer_model": "kgw/kilo-auto/free",
    "target_model": "kgw/kilo-auto/free",
    "optimizer_backend": "openai_compatible",
    "target_backend": "openai_compatible",
    "num_epochs": 3,
    "batch_size": 10,
    "accumulation": 2,
    "seed": 42,
    "edit_budget": 6,
    "min_edit_budget": 2,
    "merge_batch_size": 3,
    "analyst_workers": 2,
    "minibatch_size": 5,
    "failure_only": False,
    "lr_scheduler": "constant",
    "lr_control_mode": "fixed",
    "skill_update_mode": "patch",
    "use_gate": True,
    "gate_metric": "hard",
    "sel_env_num": 15,
    "test_env_num": 0,
    "eval_test": False,
    "force_accept": False,
    "split_mode": "ratio",
    "split_ratio": "2:1:7",
    "split_seed": 42,
    "workers": 4,
    "max_completion_tokens": 4096,
}


def load_skill_content(skill_name: str) -> str:
    """Load SKILL.md content for a given skill."""
    skill_path = PROJECT_ROOT / "skills" / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path}")
    return skill_path.read_text(encoding="utf-8")


def run_training(skill_name: str, cfg: dict) -> dict:
    """Run SkillOpt training for a single skill."""
    from skillopt.engine.trainer import ReflACTTrainer
    from envs.bmad.adapter import BmadAdapter

    out_root = str(PROJECT_ROOT / "optimization" / "output" / skill_name)
    os.makedirs(out_root, exist_ok=True)

    cfg["out_root"] = out_root
    cfg["skill_init"] = str(PROJECT_ROOT / "skills" / skill_name / "SKILL.md")
    cfg["data_path"] = str(PROJECT_ROOT / "optimization" / "benchmarks" / "data" / "all_tasks.jsonl")

    print(f"\n{'='*60}")
    print(f"  Training skill: {skill_name}")
    print(f"  Output: {out_root}")
    print(f"  Config: {json.dumps({k: v for k, v in cfg.items() if 'key' not in k.lower()}, indent=2)}")
    print(f"{'='*60}\n")

    adapter = BmadAdapter(
        split_dir=cfg.get("split_dir", ""),
        data_path=cfg["data_path"],
        split_mode=cfg.get("split_mode", "ratio"),
        split_ratio=cfg.get("split_ratio", "2:1:7"),
        split_seed=cfg.get("split_seed", 42),
        workers=cfg.get("workers", 4),
        analyst_workers=cfg.get("analyst_workers", 2),
        minibatch_size=cfg.get("minibatch_size", 5),
        edit_budget=cfg.get("edit_budget", 6),
        seed=cfg.get("seed", 42),
        max_completion_tokens=cfg.get("max_completion_tokens", 4096),
    )

    trainer = ReflACTTrainer(cfg, adapter)
    result = trainer.train()

    # Save summary
    summary_path = os.path.join(out_root, "training_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


def run_manifesto_training(cfg: dict) -> dict:
    """Run SkillOpt training on a manifesto document."""
    from skillopt.engine.trainer import ReflACTTrainer
    from envs.manifesto.adapter import ManifestoAdapter

    out_root = str(PROJECT_ROOT / "optimization" / "output" / "manifesto-research")
    os.makedirs(out_root, exist_ok=True)

    cfg["out_root"] = out_root
    cfg["skill_init"] = str(PROJECT_ROOT / "docs" / "bmad" / "research-methodology.md")
    cfg["data_path"] = str(PROJECT_ROOT / "optimization" / "benchmarks" / "data" / "manifesto_rules.jsonl")
    # Override model if env var is set
    if os.environ.get("OPENAI_COMPATIBLE_MODEL"):
        cfg["optimizer_model"] = os.environ["OPENAI_COMPATIBLE_MODEL"]
        cfg["target_model"] = os.environ["OPENAI_COMPATIBLE_MODEL"]

    print(f"\n{'='*60}")
    print(f"  Training manifesto: research-methodology.md")
    print(f"  Output: {out_root}")
    print(f"{'='*60}\n")

    adapter = ManifestoAdapter(
        data_path=cfg["data_path"],
        split_mode=cfg.get("split_mode", "ratio"),
        split_ratio=cfg.get("split_ratio", "2:1:7"),
        split_seed=cfg.get("split_seed", 42),
        workers=cfg.get("workers", 2),
        analyst_workers=cfg.get("analyst_workers", 2),
        minibatch_size=cfg.get("minibatch_size", 5),
        edit_budget=cfg.get("edit_budget", 4),
        seed=cfg.get("seed", 42),
        max_completion_tokens=cfg.get("max_completion_tokens", 2048),
    )

    trainer = ReflACTTrainer(cfg, adapter)
    result = trainer.train()

    summary_path = os.path.join(out_root, "training_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


def run_benchmark(skill_name: str, cfg: dict) -> dict:
    """Run evaluation only (no training)."""
    from envs.bmad.adapter import BmadAdapter

    out_root = str(PROJECT_ROOT / "optimization" / "output" / f"{skill_name}-eval")
    os.makedirs(out_root, exist_ok=True)

    cfg["out_root"] = out_root
    cfg["data_path"] = str(PROJECT_ROOT / "optimization" / "benchmarks" / "data" / "all_tasks.jsonl")

    adapter = BmadAdapter(
        data_path=cfg["data_path"],
        split_mode=cfg.get("split_mode", "ratio"),
        split_ratio=cfg.get("split_ratio", "2:1:7"),
        workers=cfg.get("workers", 4),
        max_completion_tokens=cfg.get("max_completion_tokens", 4096),
    )
    adapter.setup(cfg)

    # Load initial skill
    skill_content = load_skill_content(skill_name)

    # Build eval env
    eval_env = adapter.build_eval_env(env_num=cfg.get("sel_env_num", 15), split="valid_seen", seed=cfg.get("seed", 42))

    # Run rollout
    results = adapter.rollout(eval_env, skill_content, out_root)

    # Compute scores
    hard_scores = [r.get("hard", 0) for r in results]
    soft_scores = [r.get("soft", 0.0) for r in results]
    hard = sum(hard_scores) / max(len(hard_scores), 1)
    soft = sum(soft_scores) / max(len(soft_scores), 1)

    summary = {
        "skill": skill_name,
        "total_tasks": len(results),
        "hard_accuracy": round(hard, 4),
        "soft_accuracy": round(soft, 4),
        "passed": sum(hard_scores),
        "failed": len(hard_scores) - sum(hard_scores),
    }

    print(f"\n  Benchmark results for {skill_name}:")
    print(f"    Total: {summary['total_tasks']}")
    print(f"    Hard accuracy: {summary['hard_accuracy']:.2%}")
    print(f"    Soft accuracy: {summary['soft_accuracy']:.2%}")
    print(f"    Passed: {summary['passed']}/{summary['total_tasks']}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="BMAD SkillOpt Training")
    parser.add_argument("--skill", type=str, help="Skill name to optimize (e.g., bmad-dev-story)")
    parser.add_argument("--chain", action="store_true", help="Optimize all hook-chain skills")
    parser.add_argument("--benchmark", action="store_true", help="Run evaluation only")
    parser.add_argument("--epochs", type=int, default=None, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=None, help="Batch size")
    parser.add_argument("--edit-budget", type=int, default=None, help="Edit budget (learning rate)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--force-accept", action="store_true", help="Disable gate, accept all candidates")
    args = parser.parse_args()

    # Eğitim/optimize için LLM env'leri zorunlu. --benchmark sadece eval yapar
    # (LLM çağırmaz) → o yolda denetleme yapma.
    if not args.benchmark:
        _require_llm_env()

    cfg = dict(DEFAULT_CONFIG)
    if args.epochs is not None:
        cfg["num_epochs"] = args.epochs
    if args.batch_size is not None:
        cfg["batch_size"] = args.batch_size
    if args.edit_budget is not None:
        cfg["edit_budget"] = args.edit_budget
    if args.seed is not None:
        cfg["seed"] = args.seed
    if args.force_accept:
        cfg["use_gate"] = False

    if args.chain:
        results = {}
        for skill in HOOK_CHAIN_SKILLS:
            try:
                if args.benchmark:
                    result = run_benchmark(skill, cfg)
                else:
                    result = run_training(skill, cfg)
                results[skill] = result
            except Exception as e:
                print(f"  ERROR training {skill}: {e}")
                results[skill] = {"error": str(e)}

        # Save chain summary
        summary_path = PROJECT_ROOT / "optimization" / "output" / "chain_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  Chain summary saved to {summary_path}")

    elif args.skill:
        if args.benchmark:
            run_benchmark(args.skill, cfg)
        else:
            run_training(args.skill, cfg)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
