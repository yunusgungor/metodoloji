from .._base_.adapter import BmadAdapter
from .dataloader import BmadMetaChainDataLoader
from . import rollout as _rollout


class BmadMetaChainAdapter(BmadAdapter):
    TASK_TYPES = ["meta-chain"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadMetaChainDataLoader, **kw)
