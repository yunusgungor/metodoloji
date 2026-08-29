"""Environment adapter for bmad-prd benchmark."""

import pathlib
from skillopt.envs.base import EnvAdapter, BatchSpec
from .dataloader import BmadPrdDataLoader
from .rollout import run_batch


class BmadPrdAdapter(EnvAdapter):

    def __init__(self, *, split_dir, data_path=None, split_mode="split_dir",
                 split_ratio=None, split_seed=42, split_output_dir=None,
                 workers=1, analyst_workers=1, failure_only=False,
                 minibatch_size=8, edit_budget=4, seed=42, limit=0,
                 max_completion_tokens=4096, **_kw):
        self._split_dir = pathlib.Path(split_dir)
        self._workers = workers
        self._limit = limit
        self._max_completion_tokens = max_completion_tokens
        self.dataloader = BmadPrdDataLoader()

    def setup(self, cfg):
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **_kw):
        return batch.items

    def build_train_env(self, batch_size, seed, **_kw):
        items = self.dataloader.build_train_batch(batch_size, seed)
        return self.build_env_from_batch(BatchSpec(items=items))

    def build_eval_env(self, env_num, split, seed, **_kw):
        items = self.dataloader.build_eval_batch(env_num, split, seed)
        return self.build_env_from_batch(BatchSpec(items=items))

    def rollout(self, env_manager, skill_content, out_dir, **_kw):
        items = env_manager
        if self._limit > 0:
            items = items[:self._limit]
        return run_batch(items, skill_content, out_dir,
                         workers=self._workers,
                         max_completion_tokens=self._max_completion_tokens)

    def get_task_types(self):
        return ["prd"]
