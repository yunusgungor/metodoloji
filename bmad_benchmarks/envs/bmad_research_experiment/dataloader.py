from .._base_.dataloader import BmadDataLoader

class BmadResearchExperimentDataLoader(BmadDataLoader):
    def _normalize(self, raw):
        return {
            "id": raw["id"],
            "task_desc": raw.get("task_desc", ""),
            "expected_fields": raw.get("expected_fields", ["Theory", "Hypothesis", "Measurement Metrics", "Experiment Design", "Code Scope"]),
            "expected_hypothesis_format": raw.get("expected_hypothesis_format", True),
            "expected_metric_type": raw.get("expected_metric_type", "accuracy"),
            "task_type": raw.get("task_type", "research-experiment"),
        }
