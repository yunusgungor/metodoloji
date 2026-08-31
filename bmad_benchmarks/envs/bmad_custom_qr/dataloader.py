from .._base_.dataloader import BmadDataLoader

class BmadCustomQRDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "story_summary": raw.get("story_summary", ""),
            "diff_summary": raw.get("diff_summary", ""),
            "test_results": raw.get("test_results", ""),
            "expected_fields": raw.get("expected_fields", ["Date", "Status", "Story", "PR/MR", "Test Coverage", "Test Results", "Linter", "Security Scan", "Performance", "Code Review", "Decision", "Next Step"]),
            "task_type": raw.get("task_type", "custom-qr"),
        }
