"""Data loader for bmad-code-docs benchmark.

Items are scenarios requiring code-doc detection and generation.
Each item: {id, scenario, expected_type, expected_tags, expected_sections,
            context, task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "scenario": raw.get("scenario", ""),
        "expected_type": raw.get("expected_type", "P"),
        "expected_tags": raw.get("expected_tags", []),
        "expected_sections": raw.get("expected_sections", ["## Kalıp", "## Kullanım Senaryosu"]),
        "context": raw.get("context", {}),
        "task_type": raw.get("task_type", "code-docs"),
    }


class BmadCodeDocsDataLoader(SplitDataLoader):
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
