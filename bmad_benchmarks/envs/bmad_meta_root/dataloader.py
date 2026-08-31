from .._base_.dataloader import BmadDataLoader

class BmadMetaRootDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "operation": raw.get("operation", ""),
            "expected_root": raw.get("expected_root", "project-root"),
            "expected_direction": raw.get("expected_direction", "output"),
            "task_type": raw.get("task_type", "meta-root"),
        }
