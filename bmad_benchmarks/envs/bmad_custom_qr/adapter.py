from .._base_.adapter import BmadAdapter
from .dataloader import BmadCustomQRDataLoader
from . import rollout as _rollout


class BmadCustomQRAdapter(BmadAdapter):
    TASK_TYPES = ["custom-qr"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadCustomQRDataLoader, **kw)
