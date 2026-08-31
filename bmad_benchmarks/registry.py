"""Shared adapter registry and config loader for BMAD benchmarks.

Eliminates duplication between train_bmad.py and eval_bmad.py.
"""

import importlib
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"

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

# {benchmark_name: (module_path, class_name)}
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


def register_all_adapters():
    """Register all BMAD adapters into SkillOpt's environment registry."""
    from scripts import train as skillopt_train
    try:
        from scripts import eval_only as skillopt_eval
    except ImportError:
        skillopt_eval = None

    for name, (module_path, class_name) in _ADAPTERS.items():
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            skillopt_train._ENV_REGISTRY[name] = cls
            if skillopt_eval:
                skillopt_eval._ENV_REGISTRY[name] = cls
            print(f"  [registered] {name}")
        except Exception as exc:
            print(f"  [skip] {name}: {exc}")


def load_benchmark_config(name: str) -> dict:
    """Load YAML config and set model env vars (TARGET_DEPLOYMENT, etc.)."""
    config_path = CONFIGS_DIR / name / "default.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    target = cfg.get("model", {}).get("target", "")
    if target:
        os.environ["TARGET_DEPLOYMENT"] = target
    optimizer = cfg.get("model", {}).get("optimizer", "")
    if optimizer:
        os.environ["OPTIMIZER_DEPLOYMENT"] = optimizer
    return cfg


def build_train_argv(name: str, cfg: dict, extra_args: list[str] | None = None) -> list[str]:
    """Build sys.argv for SkillOpt's train.py."""
    config_path = str(CONFIGS_DIR / name / "default.yaml")
    argv = ["train.py", "--config", config_path, "--env", name]
    env = cfg.get("env", {}) if isinstance(cfg.get("env"), dict) else {}
    for key in ("split_dir", "split_mode", "skill_init"):
        val = env.get(key) or cfg.get(key)
        if val:
            argv.extend([f"--{key}", str(val)])
    for key in ("seed", "workers", "limit", "out_root", "minibatch_size", "edit_budget"):
        val = env.get(key) if isinstance(cfg.get("env"), dict) else None
        if val is None:
            val = cfg.get(key)
        if val is not None:
            argv.extend([f"--{key}", str(val)])
    train = cfg.get("train", {})
    for key in ("batch_size", "num_epochs"):
        val = train.get(key)
        if val is not None:
            argv.extend([f"--{key}", str(val)])
    if extra_args:
        argv.extend(extra_args)
    return argv


def build_eval_argv(name: str, cfg: dict, skill_path: str, split: str = "test") -> list[str]:
    """Build sys.argv for SkillOpt's eval_only.py."""
    config_path = str(CONFIGS_DIR / name / "default.yaml")
    argv = ["eval_only.py", "--config", config_path, "--skill", skill_path,
            "--split", split, "--env", name]
    env = cfg.get("env", {}) if isinstance(cfg.get("env"), dict) else {}
    for key in ("split_dir", "split_mode"):
        val = env.get(key) or cfg.get(key)
        if val:
            argv.extend([f"--{key}", str(val)])
    for key in ("seed", "workers", "out_root", "test_env_num"):
        val = cfg.get(key)
        if val is not None:
            argv.extend([f"--{key}", str(val)])
    return argv


def run_benchmark(name: str, build_argv, module_name: str, label: str) -> bool:
    """Load config, set argv, run one SkillOpt main under fresh module state.

    build_argv(name, cfg, ...) -> list[str]; module_name is the SkillOpt entry
    ('scripts.train' or 'scripts.eval_only'); label is the log line prefix.
    """
    try:
        cfg = load_benchmark_config(name)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return False
    sys.argv = build_argv(name, cfg)
    print(f"\n{label}: {name}")
    try:
        # Register adapters into the SAME module instance SkillOpt will use.
        # Deleting scripts.train from sys.modules and re-importing creates a
        # SECOND module object whose _ENV_REGISTRY starts empty — the adapters
        # registered on the first instance are lost and get_adapter raises
        # "Unknown environment". So import the entry ONCE, register onto it,
        # and call main() on that same instance. No delete.
        from importlib import import_module
        entry = import_module(module_name)
        register_all_adapters()
        entry.main()
        return True
    except SystemExit as exc:
        return exc.code == 0
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        return False


def run_benchmarks(names, build_argv, module_name, label) -> bool:
    """Run a list of benchmarks, printing a PASS/FAIL summary; True if all pass."""
    results = {name: run_benchmark(name, build_argv, module_name, label)
               for name in names}
    print("\n" + "=" * 60 + f"\n{label.upper()}\n" + "=" * 60)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return all(results.values())
