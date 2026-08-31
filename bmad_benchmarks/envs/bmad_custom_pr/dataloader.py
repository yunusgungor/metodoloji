from .._base_.dataloader import BmadDataLoader

class BmadCustomPrDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "release_scope": raw.get("release_scope", ""),
            "staging_status": raw.get("staging_status", ""),
            "rollback_plan": raw.get("rollback_plan", ""),
            "expected_fields": raw.get("expected_fields", ["Tarih", "Durum", "Release tipi", "Versiyon", "Release kapsam", "Staging Test", "Rollback Plani", "Monitoring", "Runbook", "Karar", "Sonraki adim"]),
            "task_type": raw.get("task_type", "custom-pr"),
        }
