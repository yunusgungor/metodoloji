from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomIrDataLoader
from . import rollout as _rollout


class BmadCustomIrAdapter(BmadAdapter):
    TASK_TYPES = ["custom-ir"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCustomIrDataLoader, **kw)
