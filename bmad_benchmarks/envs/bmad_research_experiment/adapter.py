from .._base_.adapter import BmadAdapter
from .dataloader import BmadResearchExperimentDataLoader
from . import rollout as _rollout


class BmadResearchExperimentAdapter(BmadAdapter):
    TASK_TYPES = ["research-experiment"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadResearchExperimentDataLoader, **kw)
