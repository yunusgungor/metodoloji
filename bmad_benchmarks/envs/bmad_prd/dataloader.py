from .._base_.dataloader import BmadDataLoader

class BmadPrdDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "idea_text": raw.get("idea_text", ""),
            "target_audience": raw.get("target_audience", ""),
            "expected_sections": raw.get("expected_sections", ["Overview", "Goals", "User Stories", "Requirements", "Success Metrics", "Risks"]),
            "task_type": raw.get("task_type", "prd"),
        }
