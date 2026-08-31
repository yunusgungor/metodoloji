from .._base_.dataloader import BmadDataLoader

class BmadTestDesignDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "story_text": raw.get("story_text", ""),
            "architecture_text": raw.get("architecture_text", ""),
            "expected_test_categories": raw.get("expected_test_categories", ["unit", "integration", "e2e", "edge-case", "negative"]),
            "task_type": raw.get("task_type", "test-design"),
        }
