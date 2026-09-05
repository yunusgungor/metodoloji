"""Tests for BENCHMARKS registry consistency and adapter config coverage."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so bmad_benchmarks is importable.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bmad_benchmarks.registry import BENCHMARKS, _ADAPTERS, CONFIGS_DIR


class TestRegistrySync:
    """BENCHMARKS list and _ADAPTERS dict must be in perfect sync."""

    def test_same_keys(self):
        bench_set = set(BENCHMARKS)
        adapter_set = set(_ADAPTERS.keys())
        assert bench_set == adapter_set, (
            f"In BENCHMARKS but not _ADAPTERS: {bench_set - adapter_set}\n"
            f"In _ADAPTERS but not BENCHMARKS: {adapter_set - bench_set}"
        )

    def test_same_length(self):
        assert len(BENCHMARKS) == len(_ADAPTERS) == 17, (
            f"Expected 17 benchmarks, got {len(BENCHMARKS)} benchmarks / "
            f"{len(_ADAPTERS)} adapters"
        )

    def test_no_duplicates(self):
        assert len(BENCHMARKS) == len(set(BENCHMARKS)), "Duplicate in BENCHMARKS"
        assert len(_ADAPTERS) == len(set(_ADAPTERS)), "Duplicate in _ADAPTERS"


class TestAdapterFormat:
    """Each adapter entry points to a valid (module_path, class_name) tuple."""

    def test_all_tuples(self):
        for name, val in _ADAPTERS.items():
            assert isinstance(val, tuple) and len(val) == 2, (
                f"{name}: expected (module_path, class_name), got {val!r}"
            )

    def test_module_paths_use_dots(self):
        for name, (module_path, _) in _ADAPTERS.items():
            assert "." in module_path, (
                f"{name}: module_path {module_path!r} doesn't look like a dotted import"
            )


class TestConfigCoverage:
    """Every benchmark must have a configs/<name>/default.yaml."""

    def test_all_configs_exist(self):
        missing = []
        for name in BENCHMARKS:
            cfg = CONFIGS_DIR / name / "default.yaml"
            if not cfg.exists():
                missing.append(name)
        assert not missing, f"Missing configs for: {missing}"


class TestAdapterModulesImportable:
    """Each adapter module can be imported (syntax + dependency check)."""

    def test_all_importable(self):
        import importlib
        failures = []
        for name, (module_path, class_name) in _ADAPTERS.items():
            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                assert cls is not None, f"{name}: {class_name} is None"
            except Exception as e:
                failures.append(f"{name}: {e}")
        assert not failures, "Import failures:\n" + "\n".join(failures)
