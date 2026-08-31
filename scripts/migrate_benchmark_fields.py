#!/usr/bin/env python3
"""Migrate benchmark training/val/test data JSON field labels Turkish -> English.

Run once after the template/hook translation. Idempotent (mapping applied only
when the old label is present).
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIRS = ROOT / "bmad_benchmarks" / "envs"

FIELD_MAP = {
    # Shared
    "Tarih": "Date",
    "Durum": "Status",
    "Karar": "Decision",
    "Sonraki adım": "Next Step",
    "Bağımlılıklar": "Dependencies",
    # IR
    "Araştırma girdileri": "Research Inputs",
    "Başarı kriterleri": "Success Criteria",
    "Eksikler": "Gaps",
    "Risk değerlendirmesi": "Risk Assessment",
    "Tasarım belgeleri": "Design Documents",
    "Teknik bağımlılıklar": "Technical Dependencies",
    # SP
    "Blokerler": "Blockers",
    "Kapasite": "Capacity",
    "Sprint hedefi": "Sprint Goal",
    "Story'ler": "Stories",
    "Teknik borç": "Technical Debt",
    # Story
    "Araştırma Girdileri": "Research Inputs",
    # QR
    "Test Sonuçları": "Test Results",
    # PR
    "Release kapsamı": "Release Scope",
    "Release tipi": "Release Type",
    "Rollback Planı": "Rollback Plan",
    "Versiyon": "Version",
    # Research experiment
    "Teori": "Theory",
    "Hipotez": "Hypothesis",
    "Ölçüm metrikleri": "Measurement Metrics",
    "Deney tasarımı": "Experiment Design",
    "Kod kapsamı": "Code Scope",
    # Code docs sections
    "## Kalıp": "## Pattern",
    "## Kullanım Senaryosu": "## Usage Scenario",
    "## Örnek": "## Example",
    "## Avantajlar": "## Advantages",
    "## Dezavantajlar": "## Disadvantages",
    "## Hata": "## Error",
    "## Neden": "## Cause",
    "## Çözüm": "## Solution",
    "## Önleme": "## Prevention",
    "## Gerekçe": "## Rationale",
    "## Sonuçlar": "## Results",
    "## Öğrenilen": "## Learned",
    "## Bağlam": "## Context",
    "## Kanıt": "## Evidence",
    "## Uygulama": "## Application",
    "## İmza": "## Signature",
    "## Kullanım": "## Usage",
    "## Dikkat Edilecekler": "## Notes",
    "## Açıklama": "## Description",
    "## Sonraki Adımlar": "## Next Steps",
    "## API": "## API",
}


def map_field(label: str) -> str:
    return FIELD_MAP.get(label, label)


def migrate_item(item: dict) -> dict:
    item = dict(item)
    for key in ("expected_fields", "expected_sections"):
        if key in item:
            item[key] = [map_field(f) for f in item[key]]
    return item


def main() -> int:
    changed = 0
    for bench in ["bmad_custom_ir", "bmad_custom_sp", "bmad_custom_story",
                  "bmad_custom_qr", "bmad_custom_pr",
                  "bmad_research_experiment", "bmad_code_docs"]:
        bench_dir = DATA_DIRS / bench / "data"
        for f in sorted(bench_dir.rglob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                new_data = [migrate_item(i) for i in data]
            else:
                new_data = migrate_item(data)
            if new_data != data:
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(new_data, fh, ensure_ascii=False, indent=2)
                print(f"  migrated {f}")
                changed += 1
    print(f"{changed} file(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
