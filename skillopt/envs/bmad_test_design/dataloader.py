"""Data loader for bmad-test-design benchmark.

Items: {id, story_text, architecture_text, expected_test_categories[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "story_text": raw.get("story_text", ""),
        "architecture_text": raw.get("architecture_text", ""),
        "expected_test_categories": raw.get("expected_test_categories", [
            "unit", "integration", "e2e", "edge-case", "negative"
        ]),
        "task_type": raw.get("task_type", "test-design"),
    }


class BmadTestDesignDataLoader(SplitDataLoader):
    def load_split_items(self, split_path: pathlib.Path) -> list[dict]:
        items = []
        for f in sorted(split_path.glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                items.extend(_normalize(r) for r in data)
            else:
                items.append(_normalize(data))
        return items
