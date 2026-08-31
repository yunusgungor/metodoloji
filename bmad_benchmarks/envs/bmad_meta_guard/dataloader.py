from .._base_.dataloader import BmadDataLoader

class BmadMetaGuardDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "scenario": raw.get("scenario", ""),
            "expected_decision": raw.get("expected_decision", "DENY"),
            "task_type": raw.get("task_type", "meta-guard"),
        }
