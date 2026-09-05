"""Validate JSON data files across all benchmarks have required fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

ENVS_DIR = _REPO / "bmad_benchmarks" / "envs"


def _collect_json_files():
    """Yield (benchmark_name, split, file_path) for every data JSON."""
    for bench_dir in sorted(ENVS_DIR.iterdir()):
        if not bench_dir.is_dir() or bench_dir.name.startswith("_"):
            continue
        data_dir = bench_dir / "data"
        if not data_dir.is_dir():
            continue
        for split in ("train", "val", "test"):
            split_dir = data_dir / split
            if not split_dir.is_dir():
                continue
            for f in sorted(split_dir.glob("*.json")):
                yield (bench_dir.name, split, f)


# Minimal schema: every item must be a dict with "id" and "task_type".
# Benchmarks add their own expected_* fields, but id+task_type are universal.
def _validate_item(item: dict, bench_name: str, filepath: Path) -> list[str]:
    errors = []
    if not isinstance(item, dict):
        errors.append(f"{filepath}: item is {type(item).__name__}, expected dict")
        return errors
    if "id" not in item:
        errors.append(f"{filepath}: missing 'id' field")
    if "task_type" not in item:
        errors.append(f"{filepath}: missing 'task_type' field")
    return errors


@pytest.mark.parametrize(
    "bench_name,split,filepath",
    [(b, s, f) for b, s, f in _collect_json_files()],
    ids=lambda x: str(x) if not isinstance(x, str) else x,
)
def test_json_schema(bench_name, split, filepath):
    """Each JSON file is a list of dicts with 'id' and 'task_type'."""
    with open(filepath, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = [data]
    assert isinstance(data, list), f"{filepath}: expected list, got {type(data).__name__}"
    if len(data) == 0:
        pytest.skip(f"{filepath}: empty list (placeholder)")
    all_errors = []
    for i, item in enumerate(data):
        errs = _validate_item(item, bench_name, filepath)
        for e in errs:
            all_errors.append(f"  item[{i}]: {e}")
    assert not all_errors, f"Schema errors in {filepath}:\n" + "\n".join(all_errors)
