from .._base_.adapter import BmadAdapter
from .dataloader import BmadCodeDocsDataLoader
from . import rollout as _rollout


class BmadCodeDocsAdapter(BmadAdapter):
    TASK_TYPES = ["code-docs"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCodeDocsDataLoader, **kw)
