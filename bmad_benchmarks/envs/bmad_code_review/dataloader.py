from .._base_.dataloader import BmadDataLoader

class BmadCodeReviewDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "diff_text": raw.get("diff_text", ""),
            "spec_text": raw.get("spec_text", ""),
            "expected_findings": raw.get("expected_findings", []),
            "task_type": raw.get("task_type", "code-review"),
        }
