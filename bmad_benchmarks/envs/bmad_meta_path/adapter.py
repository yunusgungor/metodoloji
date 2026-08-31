from .._base_.adapter import BmadAdapter
from .dataloader import BmadMetaPathDataLoader
from . import rollout as _rollout


class BmadMetaPathAdapter(BmadAdapter):
    TASK_TYPES = ["meta-path"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadMetaPathDataLoader, **kw)
