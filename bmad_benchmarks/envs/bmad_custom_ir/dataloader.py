"""Data loader for bmad_custom_ir benchmark.

Items are scenarios that must produce a Implementation Readiness (IR) methodology record.
Each item: {id, research_inputs, design_docs, dependencies, expected_fields[], task_type}
"""

import json
import pathlib
from skillopt.datasets.base import SplitDataLoader


def _normalize(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "research_inputs": raw.get("research_inputs", ""),
        "design_docs": raw.get("design_docs", ""),
        "dependencies": raw.get("dependencies", ""),
        "expected_fields": raw.get("expected_fields", ['Tarih', 'Durum', 'Araştırma girdileri', 'Tasarım belgeleri', 'Başarı kriterleri', 'Teknik bağımlılıklar', 'Risk değerlendirmesi', 'Eksikler', 'Karar', 'Sonraki adım']),
        "task_type": raw.get("task_type", "custom-ir"),
    }


class BmadCustomIrDataLoader(SplitDataLoader):
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
