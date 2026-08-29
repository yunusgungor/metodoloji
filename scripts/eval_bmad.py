#!/usr/bin/env python3
"""Evaluate a trained BMAD skill using SkillOpt's eval-only engine.

Wraps SkillOpt's eval_only.py by calling its main() directly (avoids the
repo-path subprocess issue). Adapters are registered like train_bmad.py.

Usage:
    python scripts/eval_bmad.py --benchmark bmad-code-review --split test
    python scripts/eval_bmad.py --benchmark all
"""

import argparse
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

sys.path.insert(0, str(REPO_ROOT))

BENCHMARKS = [
    "bmad-code-review",
    "bmad-create-story",
    "bmad-architecture",
    "bmad-prd",
    "bmad-test-design",
    # Custom TOML methodology benchmarks
    "bmad-custom-ir",
    "bmad-custom-sp",
    "bmad-custom-story",
    "bmad-custom-qr",
    "bmad-custom-pr",
    # docs/bmad meta benchmarks
    "bmad-meta-mod",
    "bmad-meta-chain",
    "bmad-meta-guard",
    "bmad-meta-root",
    "bmad-meta-path",
]

_ADAPTERS = {
    "bmad-code-review": ("bmad_benchmarks.envs.bmad_code_review.adapter", "BmadCodeReviewAdapter"),
    "bmad-create-story": ("bmad_benchmarks.envs.bmad_create_story.adapter", "BmadCreateStoryAdapter"),
    "bmad-architecture": ("bmad_benchmarks.envs.bmad_architecture.adapter", "BmadArchitectureAdapter"),
    "bmad-prd": ("bmad_benchmarks.envs.bmad_prd.adapter", "BmadPrdAdapter"),
    "bmad-test-design": ("bmad_benchmarks.envs.bmad_test_design.adapter", "BmadTestDesignAdapter"),
    # Custom TOML methodology benchmarks
    "bmad-custom-ir": ("bmad_benchmarks.envs.bmad_custom_ir.adapter", "BmadCustomIrAdapter"),
    "bmad-custom-sp": ("bmad_benchmarks.envs.bmad_custom_sp.adapter", "BmadCustomSpAdapter"),
    "bmad-custom-story": ("bmad_benchmarks.envs.bmad_custom_story.adapter", "BmadCustomStoryAdapter"),
    "bmad-custom-qr": ("bmad_benchmarks.envs.bmad_custom_qr.adapter", "BmadCustomQRAdapter"),
    "bmad-custom-pr": ("bmad_benchmarks.envs.bmad_custom_pr.adapter", "BmadCustomPrAdapter"),
    # docs/bmad meta benchmarks
    "bmad-meta-mod": ("bmad_benchmarks.envs.bmad_meta_mod.adapter", "BmadMetaModAdapter"),
    "bmad-meta-chain": ("bmad_benchmarks.envs.bmad_meta_chain.adapter", "BmadMetaChainAdapter"),
    "bmad-meta-guard": ("bmad_benchmarks.envs.bmad_meta_guard.adapter", "BmadMetaGuardAdapter"),
    "bmad-meta-root": ("bmad_benchmarks.envs.bmad_meta_root.adapter", "BmadMetaRootAdapter"),
    "bmad-meta-path": ("bmad_benchmarks.envs.bmad_meta_path.adapter", "BmadMetaPathAdapter"),
}


def _register_bmad_adapters():
    from scripts import train as skillopt_train
    for name, (module_path, class_name) in _ADAPTERS.items():
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            skillopt_train._ENV_REGISTRY[name] = cls
            print(f"  [registered] {name}")
        except Exception as exc:
            print(f"  [skip] {name}: {exc}")


def eval_benchmark(name: str, skill_path: str | None = None, split: str = "test"):
    config_path = CONFIGS_DIR / name / "default.yaml"
    if not skill_path:
        skill_path = OUTPUTS_DIR / name / "best_skill.md"

    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return False
    if not Path(skill_path).exists():
        print(f"[ERROR] Skill not found: {skill_path}")
        return False

    sys.argv = [
        "eval_only.py",
        "--config", str(config_path),
        "--skill", str(skill_path),
        "--split", split,
    ]

    print(f"\nEvaluating: {name} | skill: {skill_path} | split: {split}")
    try:
        # Re-import to pick up fresh sys.argv
        for mod in list(sys.modules):
            if mod.startswith("scripts.eval_only"):
                del sys.modules[mod]
        from scripts.eval_only import main as eval_main
        eval_main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained BMAD skills")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review")
    parser.add_argument("--skill", default=None, help="Path to skill .md file")
    parser.add_argument("--split", default="test", help="Data split to evaluate")
    args = parser.parse_args()

    print("Registering BMAD adapters...")
    _register_bmad_adapters()

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
