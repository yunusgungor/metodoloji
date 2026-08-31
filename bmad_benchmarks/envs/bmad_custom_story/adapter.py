from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomStoryDataLoader
from . import rollout as _rollout


class BmadCustomStoryAdapter(BmadAdapter):
    TASK_TYPES = ["custom-story"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCustomStoryDataLoader, **kw)
