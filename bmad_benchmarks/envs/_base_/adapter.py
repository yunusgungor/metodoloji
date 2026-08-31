"""Base adapter for all BMAD benchmarks.

Subclass and set TASK_TYPES + dataloader_cls. Override setup() only when
extra logic is needed (e.g. meta_root's verify_coverage).
"""

import pathlib
from skillopt.envs.base import EnvAdapter


class BmadAdapter(EnvAdapter):

    TASK_TYPES: list[str] = []
    _run_batch_fn = None  # Set in subclass to benchmark's run_batch

    def __init__(self, *, split_dir, split_mode="split_dir",
                 workers=1, analyst_workers=1, failure_only=False,
                 minibatch_size=8, edit_budget=4, seed=42, limit=0,
                 max_completion_tokens=4096, dataloader_cls=None, **_kw):
        self.split_dir_path = pathlib.Path(split_dir)
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.limit = limit
        self.max_completion_tokens = max_completion_tokens
        self.dataloader_cls = dataloader_cls
        self.dataloader = None

    def setup(self, cfg):
        super().setup(cfg)
        self.dataloader = self.dataloader_cls(
            split_dir=str(self.split_dir_path),
            split_mode=cfg.get("split_mode", "split_dir"),
        )
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_train_env(self, batch_size, seed, **_kw):
        return self.dataloader.build_train_batch(batch_size, seed).payload

    def build_eval_env(self, env_num, split, seed, **_kw):
        return self.dataloader.build_eval_batch(env_num, split, seed).payload

    def rollout(self, env_manager, skill_content, out_dir, **_kw):
        items = env_manager
        if self.limit > 0:
            items = items[:self.limit]
        return self._run_batch_fn(
            items, skill_content, out_dir,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
        )

    def get_task_types(self):
        return self.TASK_TYPES
