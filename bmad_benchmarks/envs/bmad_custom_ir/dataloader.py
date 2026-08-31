from .._base_.dataloader import BmadDataLoader

class BmadCustomIrDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "research_inputs": raw.get("research_inputs", ""),
            "design_docs": raw.get("design_docs", ""),
            "dependencies": raw.get("dependencies", ""),
            "expected_fields": raw.get("expected_fields", ["Tarih", "Durum", "Araştirma girdileri", "Tasarim belgeleri", "Basari kriterleri", "Teknik bagimliliklar", "Risk degerlendirmesi", "Eksikler", "Karar", "Sonraki adim"]),
            "task_type": raw.get("task_type", "custom-ir"),
        }
