"""Data loader for bmad-meta-path benchmark.

Items are path/operation classification tasks.
Each item: {id, operation, expected_path, expected_status, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "operation": raw.get("operation", ""),
        "expected_path": raw.get("expected_path", "project-root"),
        "expected_status": raw.get("expected_status", "output"),
        "task_type": raw.get("task_type", "meta-path"),
    }


class BmadMetaPathDataLoader(SplitDataLoader):
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
