"""Data loader for bmad-meta-root benchmark.

Items are path/operation classification tasks.
Each item: {id, operation, expected_root, expected_direction, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "operation": raw.get("operation", ""),
        "expected_root": raw.get("expected_root", "project-root"),
        "expected_direction": raw.get("expected_direction", "output"),
        "task_type": raw.get("task_type", "meta-root"),
    }


class BmadMetaRootDataLoader(SplitDataLoader):
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
