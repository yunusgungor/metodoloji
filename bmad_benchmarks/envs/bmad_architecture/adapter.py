from .._base_.adapter import BmadAdapter
from .dataloader import BmadArchitectureDataLoader
from . import rollout as _rollout


class BmadArchitectureAdapter(BmadAdapter):
    TASK_TYPES = ["architecture"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadArchitectureDataLoader, **kw)
