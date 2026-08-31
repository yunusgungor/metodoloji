from .._base_.adapter import BmadAdapter
from .dataloader import BmadCreateStoryDataLoader
from . import rollout as _rollout


class BmadCreateStoryAdapter(BmadAdapter):
    TASK_TYPES = ["create-story"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCreateStoryDataLoader, **kw)
