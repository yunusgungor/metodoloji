"""Data loader for bmad_custom_pr benchmark.

Items are scenarios that must produce a Production Readiness (PR) methodology record.
Each item: {id, release_scope, staging_status, rollback_plan, expected_fields[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        release_scope: raw.get("release_scope", ""),
        staging_status: raw.get("staging_status", ""),
        rollback_plan: raw.get("rollback_plan", ""),
        "expected_fields": raw.get("expected_fields", ['Tarih', 'Durum', 'Release tipi', 'Versiyon', 'Release kapsamı', 'Staging Test', 'Rollback Planı', 'Monitoring', 'Runbook', 'Karar', 'Sonraki adım']),
        "task_type": raw.get("task_type", "custom-pr"),
    }


class BmadCustomPrDataLoader(SplitDataLoader):
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
