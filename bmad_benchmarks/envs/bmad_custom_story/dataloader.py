from .._base_.dataloader import BmadDataLoader

class BmadCustomStoryDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "epic": raw.get("epic", ""),
            "experiments": raw.get("experiments", ""),
            "architecture": raw.get("architecture", ""),
            "expected_fields": raw.get("expected_fields", ["Date", "Status", "Sprint", "User Story", "Acceptance Criteria", "Technical Tasks", "Definition of Done", "Dependencies", "Research Inputs"]),
            "task_type": raw.get("task_type", "custom-story"),
        }
