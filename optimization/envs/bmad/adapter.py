"""BMAD Methodology Benchmark — SkillOpt EnvAdapter for openhands-metodoloji.

Integrates the BMAD hook-chain skills with SkillOpt's ReflACT training loop.
Each benchmark task tests a specific methodology rule (guard, quality, deploy, etc.).
"""
from __future__ import annotations

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter

from .dataloader import BmadLoader
from .rollout import run_batch


class BmadAdapter(EnvAdapter):
    """Environment adapter for BMAD methodology benchmark.

    Tests the hook-chain skills (guard, quality, deploy, stop, audit, bridge, chain)
    against the methodology rules. Each task has an expected action and the adapter
    scores whether the skill-instructed model produces the correct output.
    """

    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "split_dir",
        split_ratio: str = "2:1:7",
        split_seed: int = 42,
        split_output_dir: str = "",
        workers: int = 4,
        analyst_workers: int = 4,
        failure_only: bool = False,
        minibatch_size: int = 8,
        edit_budget: int = 4,
        seed: int = 42,
        limit: int = 0,
        max_completion_tokens: int = 4096,
    ) -> None:
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.max_completion_tokens = int(max_completion_tokens)
        self.dataloader = BmadLoader(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
            seed=seed,
            limit=limit,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        batch = self.dataloader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        batch = self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        """Run a batch of BMAD benchmark tasks under the current skill.

        Each task tests a methodology rule. The skill document is used as the
        system prompt to instruct the model how to analyze the scenario.
        """
        items: list[dict] = env_manager
        return run_batch(
            items=items,
            out_root=out_dir,
            skill_content=skill_content,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
        )

    def get_task_types(self) -> list[str]:
        """Distinct task types for stratified sampling."""
        seen: list[str] = []
        all_items = (
            self.dataloader.train_items
            + self.dataloader.val_items
            + self.dataloader.test_items
        )
        for item in all_items:
            tt = str(item.get("task_type") or "bmad")
            if tt not in seen:
                seen.append(tt)
        return seen or ["bmad"]
