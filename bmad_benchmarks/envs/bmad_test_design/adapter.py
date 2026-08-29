"""Environment adapter for bmad-test-design benchmark."""

import pathlib
from skillopt.envs.base import EnvAdapter, BatchSpec
from .dataloader import BmadTestDesignDataLoader
from .rollout import run_batch


class BmadTestDesignAdapter(EnvAdapter):

    def __init__(self, *, split_dir, data_path=None, split_mode="split_dir",
                 split_ratio=None, split_seed=42, split_output_dir=None,
                 workers=1, analyst_workers=1, failure_only=False,
                 minibatch_size=8, edit_budget=4, seed=42, limit=0,
                 max_completion_tokens=4096, **_kw):
        self.split_dir_path = pathlib.Path(split_dir)
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.limit = limit
        self.max_completion_tokens = max_completion_tokens
        self.dataloader = BmadTestDesignDataLoader(split_dir=str(self.split_dir_path), split_mode=split_mode)

    def setup(self, cfg):
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **_kw):
        return batch.payload

    def build_train_env(self, batch_size, seed, **_kw):
        items = self.dataloader.build_train_batch(batch_size, seed)
        return self.build_env_from_batch(BatchSpec(items=items))

    def build_eval_env(self, env_num, split, seed, **_kw):
        items = self.dataloader.build_eval_batch(env_num, split, seed)
        return self.build_env_from_batch(BatchSpec(items=items))

    def rollout(self, env_manager, skill_content, out_dir, **_kw):
        items = env_manager
        if self.limit > 0:
            items = items[:self.limit]
        return run_batch(items, skill_content, out_dir,
                         workers=self.workers,
                         max_completion_tokens=self.max_completion_tokens)

    def get_task_types(self):
        return ["test-design"]
