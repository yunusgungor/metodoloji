#!/usr/bin/env python3
"""Train BMAD skills using SkillOpt.

Wraps SkillOpt's train.py, registering BMAD adapters first.

Usage:
    python scripts/train_bmad.py --benchmark bmad-code-review
    python scripts/train_bmad.py --benchmark all
    python scripts/train_bmad.py --benchmark bmad-code-review --epochs 5 --lr 4
"""

import argparse
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"

# MUST add repo root before any local imports
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
    "bmad-custom-ideation",
]

# Adapter class mapping
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
    "bmad-custom-ideation": ("bmad_benchmarks.envs.bmad_custom_ideation.adapter", "BmadCustomIdeationAdapter"),
}


def _register_bmad_adapters():
    """Register BMAD adapters into SkillOpt's environment registry."""
    # Import SkillOpt's train module to access its registry
    from scripts import train as skillopt_train

    for name, (module_path, class_name) in _ADAPTERS.items():
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            skillopt_train._ENV_REGISTRY[name] = cls
            print(f"  [registered] {name}")
        except Exception as exc:
            print(f"  [skip] {name}: {exc}")


def train_benchmark(name: str, extra_args: list[str] | None = None):
    config_path = CONFIGS_DIR / name / "default.yaml"
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return False

    # out_root is set in the YAML config per benchmark
    sys.argv = [
        "train.py",
        "--config", str(config_path),
    ]
    if extra_args:
        sys.argv.extend(extra_args)

    print(f"\n{'='*60}")
    print(f"Training: {name}")
    print(f"Config:   {config_path}")
    print(f"{'='*60}\n")

    try:
        # Re-import to pick up the fresh sys.argv
        if "scripts.train" in sys.modules:
            del sys.modules["scripts.train"]
        from scripts.train import main as train_main
        train_main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Train BMAD skills with SkillOpt")
    parser.add_argument("--benchmark", choices=BENCHMARKS + ["all"],
                        default="bmad-code-review", help="Benchmark to train")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=int, default=3, help="Learning rate (max edits)")
    parser.add_argument("--batch-size", type=int, default=8)
    args, extra = parser.parse_known_args()

    print("Registering BMAD adapters...")
    _register_bmad_adapters()

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
        ok = train_benchmark(name, extra_args=extra_args)
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
