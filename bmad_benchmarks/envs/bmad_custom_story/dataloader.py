"""Data loader for bmad_custom_story benchmark.

Items are scenarios that must produce a Story (S) methodology record.
Each item: {id, epic, experiments, architecture, expected_fields[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "epic": raw.get("epic", ""),
        "experiments": raw.get("experiments", ""),
        "architecture": raw.get("architecture", ""),
        "expected_fields": raw.get("expected_fields", ['Tarih', 'Durum', 'Sprint', 'User Story', 'Acceptance Criteria', 'Technical Tasks', 'Definition of Done', 'Bağımlılıklar', 'Araştırma Girdileri']),
        "task_type": raw.get("task_type", "custom-story"),
    }


class BmadCustomStoryDataLoader(SplitDataLoader):
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
