from .._base_.dataloader import BmadDataLoader

class BmadMetaPathDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "stage": raw.get("stage", raw.get("operation", "")),
            "expected_root": raw.get("expected_root", "project-root"),
            "expected_path": raw.get("expected_path", ""),
            "expected_status": raw.get("expected_status", ""),
            "task_type": raw.get("task_type", "meta-path"),
        }
