from .._base_.dataloader import BmadDataLoader

class BmadMetaChainDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "stage": raw.get("stage", ""),
            "expected_record": raw.get("expected_record", ""),
            "expected_path": raw.get("expected_path", ""),
            "expected_status": raw.get("expected_status", ""),
            "task_type": raw.get("task_type", "meta-chain"),
        }
