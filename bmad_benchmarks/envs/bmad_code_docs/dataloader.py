from .._base_.dataloader import BmadDataLoader

class BmadCodeDocsDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "scenario": raw.get("scenario", ""),
            "expected_type": raw.get("expected_type", "P"),
            "expected_tags": raw.get("expected_tags", []),
            "expected_sections": raw.get("expected_sections", []),
            "context": raw.get("context", {}),
            "task_type": raw.get("task_type", "code-docs"),
        }
