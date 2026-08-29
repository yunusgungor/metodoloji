"""Data loader for bmad-architecture benchmark.

Items are project input scenarios (spec, codebase, or raw idea).
Each item: {id, input_text, input_type, expected_invariants[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "input_text": raw.get("input_text", ""),
        "input_type": raw.get("input_type", "raw-idea"),
        "expected_invariants": raw.get("expected_invariants", [
            "paradigm", "boundary", "dependency", "state", "ownership"
        ]),
        "task_type": raw.get("task_type", "architecture"),
    }


class BmadArchitectureDataLoader(SplitDataLoader):
    def load_split_items(self, split_path) -> list[dict]:
        items = []
        for f in sorted(pathlib.Path(split_path).glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                items.extend(_normalize(r) for r in data)
            else:
                items.append(_normalize(data))
        return items
