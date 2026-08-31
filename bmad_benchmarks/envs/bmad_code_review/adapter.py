from .._base_.adapter import BmadAdapter
from .dataloader import BmadCodeReviewDataLoader
from . import rollout as _rollout


class BmadCodeReviewAdapter(BmadAdapter):
    TASK_TYPES = ["code-review"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCodeReviewDataLoader, **kw)
