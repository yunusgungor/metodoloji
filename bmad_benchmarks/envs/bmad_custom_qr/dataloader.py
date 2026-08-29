"""Data loader for bmad-custom-qr benchmark.

Items are review scenarios that must produce a QR (Quality Review) methodology record.
Each item: {id, story_summary, diff_summary, test_results, expected_fields[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "story_summary": raw.get("story_summary", ""),
        "diff_summary": raw.get("diff_summary", ""),
        "test_results": raw.get("test_results", ""),
        "expected_fields": raw.get("expected_fields", [
            "Tarih", "Durum", "Story", "PR/MR", "Test Coverage",
            "Test Sonuçları", "Karar", "Sonraki adım"
        ]),
        "task_type": raw.get("task_type", "custom-qr"),
    }


class BmadCustomQRDataLoader(SplitDataLoader):
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
