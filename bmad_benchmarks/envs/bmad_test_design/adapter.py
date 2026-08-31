from .._base_.adapter import BmadAdapter
from .dataloader import BmadTestDesignDataLoader
from . import rollout as _rollout


class BmadTestDesignAdapter(BmadAdapter):
    TASK_TYPES = ["test-design"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadTestDesignDataLoader, **kw)
