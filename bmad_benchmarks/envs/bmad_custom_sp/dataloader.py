from .._base_.dataloader import BmadDataLoader

class BmadCustomSpDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "sprint_scope": raw.get("sprint_scope", ""),
            "capacity": raw.get("capacity", ""),
            "tech_debt": raw.get("tech_debt", ""),
            "expected_fields": raw.get("expected_fields", ["Date", "Status", "Sprint Goal", "Stories", "Capacity", "Technical Debt", "Blockers", "Dependencies"]),
            "task_type": raw.get("task_type", "custom-sp"),
        }
