from .._base_.adapter import BmadAdapter
from .dataloader import BmadMetaRootDataLoader
from . import rollout as _rollout


class BmadMetaRootAdapter(BmadAdapter):
    TASK_TYPES = ["meta-root"]
    _run_batch_fn = _rollout.run_batch

    def __init__(self, **kw):
        super().__init__(dataloader_cls=BmadMetaRootDataLoader, **kw)

    def setup(self, cfg):
        super().setup(cfg)
        from .verify_combinations import verify_coverage
        verify_coverage(split_dir=self.split_dir_path)
