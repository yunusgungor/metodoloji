"""Data loader for bmad-code-review benchmark.

Items are diff + spec pairs with expected findings.
Each item: {id, diff_text, spec_text, expected_findings[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "diff_text": raw.get("diff_text", ""),
        "spec_text": raw.get("spec_text", ""),
        "expected_findings": raw.get("expected_findings", []),
        "task_type": raw.get("task_type", "code-review"),
    }


class BmadCodeReviewDataLoader(SplitDataLoader):
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
