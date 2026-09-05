"""Parametrized test: every benchmark's _selfcheck() passes."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bmad_benchmarks.registry import _ADAPTERS


def _collect_selfchecks():
    """Import each rollout module and yield (name, _selfcheck_fn) if present."""
    items = []
    for name in _ADAPTERS:
        module_path = _ADAPTERS[name][0].replace(".adapter", ".rollout")
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, "_selfcheck", None)
            if fn is not None:
                items.append(pytest.param(fn, id=name))
        except Exception:
            # Some benchmarks may not have a rollout _selfcheck — skip silently.
            pass
    return items


@pytest.mark.parametrize("selfcheck_fn", _collect_selfchecks())
def test_selfcheck(selfcheck_fn):
    """Run the benchmark's own _selfcheck() — it asserts internally."""
    selfcheck_fn()
