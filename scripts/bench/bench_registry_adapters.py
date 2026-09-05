#!/usr/bin/env python3
"""Bench: verify all 17 adapters register successfully.

Emits: adapter_register_rate=<value> (registered/total)
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bmad_benchmarks.registry import _ADAPTERS

total = len(_ADAPTERS)
registered = 0
failures = []

for name, (module_path, class_name) in _ADAPTERS.items():
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        assert cls is not None, f"{class_name} is None"
        registered += 1
    except Exception as e:
        failures.append(f"{name}: {e}")

rate = registered / total if total else 0.0
print(f"adapter_register_rate={rate:.3f} ({registered}/{total})")
for f in failures:
    print(f"  FAIL: {f}", file=sys.stderr)
