from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomPrDataLoader
from . import rollout as _rollout


class BmadCustomPrAdapter(BmadAdapter):
    TASK_TYPES = ["custom-pr"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCustomPrDataLoader, **kw)
