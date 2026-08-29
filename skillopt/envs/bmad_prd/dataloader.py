"""Data loader for bmad-prd benchmark.

Items: {id, idea_text, target_audience, expected_sections[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "idea_text": raw.get("idea_text", ""),
        "target_audience": raw.get("target_audience", ""),
        "expected_sections": raw.get("expected_sections", [
            "Overview", "Goals", "User Stories", "Requirements",
            "Success Metrics", "Risks"
        ]),
        "task_type": raw.get("task_type", "prd"),
    }


class BmadPrdDataLoader(SplitDataLoader):
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
