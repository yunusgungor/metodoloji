"""Data loader for bmad-custom-ideation benchmark.

Items are user idea-sharing scenarios.
Each item: {id, user_idea, expected_behaviors[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "user_idea": raw.get("user_idea", ""),
        "expected_behaviors": raw.get("expected_behaviors", [
            "proactive_inference",
            "explicit_decision",
            "multiple_perspective",
            "focused_one_question",
            "hypothesis_offer",
        ]),
        "task_type": raw.get("task_type", "custom-ideation"),
    }


class BmadCustomIdeationDataLoader(SplitDataLoader):
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
