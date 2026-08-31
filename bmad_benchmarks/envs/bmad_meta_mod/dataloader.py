from .._base_.dataloader import BmadDataLoader

class BmadMetaModDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "task_desc": raw.get("task_desc", ""),
            "expected_mode": raw.get("expected_mode", "A"),
            "task_type": raw.get("task_type", "meta-mod"),
        }
