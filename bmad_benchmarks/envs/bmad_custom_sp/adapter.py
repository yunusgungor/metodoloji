from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomSpDataLoader
from . import rollout as _rollout


class BmadCustomSpAdapter(BmadAdapter):
    TASK_TYPES = ["custom-sp"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCustomSpDataLoader, **kw)
