from .._base_.dataloader import BmadDataLoader

class BmadArchitectureDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "input_text": raw.get("input_text", ""),
            "input_type": raw.get("input_type", "raw-idea"),
            "expected_invariants": raw.get("expected_invariants", ["paradigm", "boundary", "dependency", "state", "ownership"]),
            "task_type": raw.get("task_type", "architecture"),
        }
