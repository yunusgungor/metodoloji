from .._base_.adapter import BmadAdapter
from .dataloader import BmadPrdDataLoader
from . import rollout as _rollout


class BmadPrdAdapter(BmadAdapter):
    TASK_TYPES = ["prd"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadPrdDataLoader, **kw)
