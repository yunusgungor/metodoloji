from .._base_.adapter import BmadAdapter
from .dataloader import BmadMetaModDataLoader
from . import rollout as _rollout


class BmadMetaModAdapter(BmadAdapter):
    TASK_TYPES = ["meta-mod"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadMetaModDataLoader, **kw)
