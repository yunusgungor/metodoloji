"""Base dataloader for all BMAD benchmarks.

Subclass and override _normalize() to define the per-benchmark schema.
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


class BmadDataLoader(SplitDataLoader):

    def _normalize(self, raw: dict) -> dict:
        return raw

    def load_split_items(self, split_path) -> list[dict]:
        items = []
        for f in sorted(pathlib.Path(split_path).glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                items.extend(self._normalize(r) for r in data)
            else:
                items.append(self._normalize(data))
        return items

    def verify_split_data(self) -> None:
        """Verify every split under split_dir loads and yields items.

        Raises SystemExit(1) on a split with no usable items — a split that
        yields zero training/eval items makes ReflACT silently skip every step
        (bmad-meta-root lesson: an empty split reads as 'nothing to learn').
        A JSON file that is a valid but *empty* list is treated as a placeholder
        (e.g. research_experiment real-usage.json is populated by
        bridge_real_usage.py) and skipped rather than counted.
        """
        problems = []
        for split in ("train", "val", "test"):
            split_path = pathlib.Path(self.split_dir) / split
            if not split_path.is_dir():
                problems.append(f"[{split}] missing directory {split_path}")
                continue
            items = self.load_split_items(split_path)
            if not items:
                problems.append(f"[{split}] no usable items under {split_path}")
        if problems:
            for p in problems:
                print(f"  ✗ {p}", file=__import__("sys").stderr)
            print("SPLIT DATA INCOMPLETE", file=__import__("sys").stderr)
            raise SystemExit(1)
        print(f"  [{type(self).__name__}] split data OK "
              f"(train/val/test all non-empty)")
