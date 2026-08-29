"""Data loader for bmad-meta-mod benchmark.

Items are tasks requiring mode classification.
Each item: {id, task_desc, expected_mode, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "task_desc": raw.get("task_desc", ""),
        "expected_mode": raw.get("expected_mode", "A"),
        "task_type": raw.get("task_type", "meta-mod"),
    }


class BmadMetaModDataLoader(SplitDataLoader):
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
