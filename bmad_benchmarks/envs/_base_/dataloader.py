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
