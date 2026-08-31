from .._base_.dataloader import BmadDataLoader

class BmadCustomQRDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "story_summary": raw.get("story_summary", ""),
            "diff_summary": raw.get("diff_summary", ""),
            "test_results": raw.get("test_results", ""),
            "expected_fields": raw.get("expected_fields", ["Tarih", "Durum", "Story", "PR/MR", "Test Coverage", "Test Sonuclari", "Linter", "Security Scan", "Performance", "Code Review", "Karar", "Sonraki adim"]),
            "task_type": raw.get("task_type", "custom-qr"),
        }
