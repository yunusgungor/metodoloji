from .._base_.adapter import BmadAdapter
from .dataloader import BmadMetaGuardDataLoader
from . import rollout as _rollout


class BmadMetaGuardAdapter(BmadAdapter):
    TASK_TYPES = ["meta-guard"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadMetaGuardDataLoader, **kw)
