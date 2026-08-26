"""BMAD Benchmark Data Loader — loads guard/quality/deploy/stop/audit/bridge/chain tasks."""
from __future__ import annotations

import json
from pathlib import Path

from skillopt.datasets.base import SplitDataLoader


def _normalize_item(raw: dict) -> dict:
    """Normalize one raw benchmark entry into SkillOpt's expected shape."""
    return {
        "id": str(raw.get("id") or ""),
        "question": str(raw.get("question") or ""),
        "ground_truth": str(raw.get("ground_truth") or ""),
        "task_type": str(raw.get("task_type") or "bmad"),
        "reference_text": str(raw.get("reference_text") or ""),
        "expected_action": str(raw.get("expected_action") or ""),
        "skill_target": str(raw.get("skill_target") or ""),
        "hard_metric": str(raw.get("hard_metric") or "exact_match"),
    }


class BmadLoader(SplitDataLoader):
    """Data loader for BMAD methodology benchmark tasks.

    Loads JSONL files from the benchmarks/data/ directory.
    Each file represents a task category (guard, quality, deploy, etc.).
    """

    def load_split_items(self, split_path: str) -> list[dict]:
        """Load all items for one split directory."""
        path = Path(split_path)
        items: list[dict] = []

        # Load all JSONL files in the split directory
        for jsonl_file in sorted(path.glob("*.jsonl")):
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    items.append(_normalize_item(json.loads(line)))

        # Also check for a single combined JSON file
        if not items:
            for json_file in sorted(path.glob("*.json")):
                with json_file.open(encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, list):
                    items.extend(_normalize_item(row) for row in payload)

        if not items:
            raise FileNotFoundError(
                f"No .json or .jsonl file found in {split_path}"
            )

        return items
