"""Data loader for bmad_custom_sp benchmark.

Items are scenarios that must produce a Sprint (SP) methodology record.
Each item: {id, sprint_scope, capacity, tech_debt, expected_fields[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        sprint_scope: raw.get("sprint_scope", ""),
        capacity: raw.get("capacity", ""),
        tech_debt: raw.get("tech_debt", ""),
        "expected_fields": raw.get("expected_fields", ['Tarih', 'Durum', 'Sprint hedefi', "Story'ler", 'Kapasite', 'Teknik borç', 'Blokerler', 'Bağımlılıklar']),
        "task_type": raw.get("task_type", "custom-sp"),
    }


class BmadCustomSpDataLoader(SplitDataLoader):
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
