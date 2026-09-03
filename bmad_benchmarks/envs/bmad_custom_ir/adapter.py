from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomIrDataLoader
from . import rollout as _rollout


class BmadCustomIrAdapter(BmadAdapter):
    TASK_TYPES = ["custom-ir"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, *, split_dir=None, split_mode="split_dir", workers=1, analyst_workers=1, failure_only=False, minibatch_size=8, edit_budget=4, seed=42, limit=0, max_completion_tokens=4096, **kw):
        super().__init__(dataloader_cls=BmadCustomIrDataLoader, split_dir=split_dir, split_mode=split_mode, workers=workers, analyst_workers=analyst_workers, failure_only=failure_only, minibatch_size=minibatch_size, edit_budget=edit_budget, seed=seed, limit=limit, max_completion_tokens=max_completion_tokens, **kw)
