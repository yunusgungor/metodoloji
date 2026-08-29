"""Data loader for bmad-meta-chain benchmark.

Items are stages requiring the correct record + path + status values.
Each item: {id, stage, expected_record, expected_path, expected_status, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "stage": raw.get("stage", ""),
        "expected_record": raw.get("expected_record", ""),
        "expected_path": raw.get("expected_path", ""),
        "expected_status": raw.get("expected_status", ""),
        "task_type": raw.get("task_type", "meta-chain"),
    }


class BmadMetaChainDataLoader(SplitDataLoader):
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
