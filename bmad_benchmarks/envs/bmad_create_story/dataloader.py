"""Data loader for bmad-create-story benchmark.

Items are project context + epic + spec scenarios.
Each item: {id, epic_text, prd_text, architecture_text, ux_text, expected_sections[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "epic_text": raw.get("epic_text", ""),
        "prd_text": raw.get("prd_text", ""),
        "architecture_text": raw.get("architecture_text", ""),
        "ux_text": raw.get("ux_text", ""),
        "expected_sections": raw.get("expected_sections", [
            "Acceptance Criteria", "Technical Tasks", "Definition of Done",
            "Status", "Experiment"
        ]),
        "expected_metadata_fields": raw.get("expected_metadata_fields", [
            "AC-", "Experiment:", "Type:", "Measured:", "Verify:"
        ]),
        "task_type": raw.get("task_type", "create-story"),
    }


class BmadCreateStoryDataLoader(SplitDataLoader):
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
