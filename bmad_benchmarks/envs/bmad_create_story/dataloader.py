from .._base_.dataloader import BmadDataLoader

class BmadCreateStoryDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "epic_text": raw.get("epic_text", ""),
            "prd_text": raw.get("prd_text", ""),
            "architecture_text": raw.get("architecture_text", ""),
            "ux_text": raw.get("ux_text", ""),
            "expected_sections": raw.get("expected_sections", ["Acceptance Criteria", "Technical Tasks", "Definition of Done", "Status", "Dev Notes"]),
            "expected_metadata_fields": raw.get("expected_metadata_fields", ["AC-", "Experiment:", "Type:", "Measured:", "Verify:"]),
            "task_type": raw.get("task_type", "create-story"),
        }
