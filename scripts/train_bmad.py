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
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"

# Load .env so AZURE_OPENAI_* vars are available to SkillOpt
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

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
    # docs/bmad meta benchmarks
    "bmad-meta-mod",
    "bmad-meta-chain",
    "bmad-meta-guard",
    "bmad-meta-root",
    "bmad-meta-path",
    # Research methodology benchmark
    "bmad-research-experiment",
    # Code docs benchmark
    "bmad-code-docs",
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
    # docs/bmad meta benchmarks
    "bmad-meta-mod": ("bmad_benchmarks.envs.bmad_meta_mod.adapter", "BmadMetaModAdapter"),
    "bmad-meta-chain": ("bmad_benchmarks.envs.bmad_meta_chain.adapter", "BmadMetaChainAdapter"),
    "bmad-meta-guard": ("bmad_benchmarks.envs.bmad_meta_guard.adapter", "BmadMetaGuardAdapter"),
    "bmad-meta-root": ("bmad_benchmarks.envs.bmad_meta_root.adapter", "BmadMetaRootAdapter"),
    "bmad-meta-path": ("bmad_benchmarks.envs.bmad_meta_path.adapter", "BmadMetaPathAdapter"),
    # Research methodology benchmark
    "bmad-research-experiment": ("bmad_benchmarks.envs.bmad_research_experiment.adapter", "BmadResearchExperimentAdapter"),
    # Code docs benchmark
    "bmad-code-docs": ("bmad_benchmarks.envs.bmad_code_docs.adapter", "BmadCodeDocsAdapter"),
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
    import yaml as _yaml
    with open(config_path) as _f:
        _cfg = _yaml.safe_load(_f)
    # Set TARGET_DEPLOYMENT BEFORE SkillOpt modules load (they read it at import time)
    target = _cfg.get("model", {}).get("target", "")
    if target:
        os.environ["TARGET_DEPLOYMENT"] = target
    optimizer = _cfg.get("model", {}).get("optimizer", "")
    if optimizer:
        os.environ["OPTIMIZER_DEPLOYMENT"] = optimizer
    sys.argv = [
        "train.py",
        "--config", str(config_path),
        "--env", name,
    ]
    if _cfg.get("split_dir"):
        sys.argv.extend(["--split_dir", str(_cfg["split_dir"])])
    if _cfg.get("split_mode"):
        sys.argv.extend(["--split_mode", str(_cfg["split_mode"])])
    if _cfg.get("skill_init"):
        sys.argv.extend(["--skill_init", str(_cfg["skill_init"])])
    # Set TARGET_DEPLOYMENT so SkillOpt uses the correct model
    target = _cfg.get("model", {}).get("target", "")
    if target:
        os.environ["TARGET_DEPLOYMENT"] = target
    optimizer = _cfg.get("model", {}).get("optimizer", "")
    if optimizer:
        os.environ["OPTIMIZER_DEPLOYMENT"] = optimizer
    # Pass through fields that SkillOpt reads from CLI, not from config
    for key in ("seed", "workers", "limit", "out_root",
                "minibatch_size", "edit_budget"):
        val = _cfg.get(key)
        if val is not None:
            sys.argv.extend([f"--{key}", str(val)])
    # Pass through train.* fields
    train = _cfg.get("train", {})
    for key in ("batch_size", "num_epochs"):
        val = train.get(key)
        if val is not None:
            sys.argv.extend([f"--{key}", str(val)])
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
        # Re-register adapters after module reload (module init clears registry)
        _register_bmad_adapters()
        train_main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def main():
    # Resolve all relative config paths (split_dir, skill_init, out_root) against
    # the methodology root, regardless of the caller's cwd.
    os.chdir(REPO_ROOT)

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
