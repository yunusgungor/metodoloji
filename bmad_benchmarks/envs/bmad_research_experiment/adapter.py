"""Environment adapter for bmad-research-experiment benchmark.

Task: given a development scenario, generate a complete experiment record
with all required fields (Teori, Hipotez, Olcum metrikleri, Deney tasarimi,
Kod kapsami) following the methodology manifesto.
"""

import pathlib
from skillopt.envs.base import EnvAdapter
from .dataloader import BmadResearchExperimentDataLoader
from .rollout import run_batch


class BmadResearchExperimentAdapter(EnvAdapter):

    def __init__(self, **_kw):
        self.workers = _kw.get("workers", 1)
        self.analyst_workers = _kw.get("analyst_workers", 1)
        self.failure_only = _kw.get("failure_only", False)
        self.minibatch_size = _kw.get("minibatch_size", 8)
        self.edit_budget = _kw.get("edit_budget", 4)
        self.limit = _kw.get("limit", 0)
        self.max_completion_tokens = _kw.get("max_completion_tokens", 4096)
        self.dataloader = None

    def setup(self, cfg):
        super().setup(cfg)
        split_dir = cfg.get("split_dir", "")
        split_mode = cfg.get("split_mode", "split_dir")
        self.dataloader = BmadResearchExperimentDataLoader(
            split_dir=split_dir, split_mode=split_mode
        )
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_train_env(self, batch_size, seed, **_kw):
        batch = self.dataloader.build_train_batch(batch_size, seed)
        return batch.payload

    def build_eval_env(self, env_num, split, seed, **_kw):
        batch = self.dataloader.build_eval_batch(env_num, split, seed)
        return batch.payload

    def rollout(self, env_manager, skill_content, out_dir, **_kw):
        items = env_manager
        if self.limit > 0:
            items = items[:self.limit]
        return run_batch(items, skill_content, out_dir,
                         workers=self.workers,
                         max_completion_tokens=self.max_completion_tokens)

    def get_task_types(self):
        return ["research-experiment"]
