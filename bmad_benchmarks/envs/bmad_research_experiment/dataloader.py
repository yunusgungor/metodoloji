"""Data loader for bmad-research-experiment benchmark.

Items are scenarios requiring experiment record generation.
Each item: {id, task_desc, expected_fields, expected_hypothesis_format,
            expected_metric_type, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader

DEFAULT_FIELDS = ["Teori", "Hipotez", "Ölçüm metrikleri", "Deney tasarımı", "Kod kapsamı"]


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "task_desc": raw.get("task_desc", ""),
        "expected_fields": raw.get("expected_fields", DEFAULT_FIELDS),
        "expected_hypothesis_format": raw.get("expected_hypothesis_format", True),
        "expected_metric_type": raw.get("expected_metric_type", "accuracy"),
        "task_type": raw.get("task_type", "research-experiment"),
    }


class BmadResearchExperimentDataLoader(SplitDataLoader):
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
