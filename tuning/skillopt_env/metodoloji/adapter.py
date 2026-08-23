"""Metodoloji environment adapter'ı (SkillOpt/ReflACT).

Eğitilen artefakt tek bir markdown "Süreç Rehberi"dir (skills/initial.md ile
tohumlanır). Rollout, chat harness üzerinde senaryo simülasyonu yapar; skorlama
tamamen deterministiktir (evaluator.py) — validation gate tekrarlanabilir kalır.
"""
from __future__ import annotations

import os

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter
from skillopt.envs.metodoloji.dataloader import MetodolojiDataLoader
from skillopt.envs.metodoloji.rollout import run_batch

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


class MetodolojiAdapter(EnvAdapter):
    """Metodoloji süreç-kalitesi environment adapter'ı."""

    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "split_dir",
        split_ratio: str = "2:1:1",
        split_seed: int = 42,
        split_output_dir: str = "",
        exec_timeout: int = 300,
        workers: int = 8,
        analyst_workers: int = 8,
        failure_only: bool = False,
        minibatch_size: int = 4,
        edit_budget: int = 4,
        seed: int = 42,
        limit: int = 0,
        max_completion_tokens: int = 8192,
    ) -> None:
        self.exec_timeout = exec_timeout
        self.workers = workers
        self.max_completion_tokens = int(max_completion_tokens)
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.dataloader = MetodolojiDataLoader(
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
        items: list[dict] = env_manager
        return run_batch(
            items=items,
            out_root=out_dir,
            skill_content=skill_content,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
            exec_timeout=self.exec_timeout,
        )

    def get_task_types(self) -> list[str]:
        return [
            "research_mod_a",
            "research_mod_bcd",
            "dev_chain",
            "routing",
            "honesty_guard",
            "communication",
        ]

    # ── Env'e özel reflect prompt'ları ───────────────────────────────────
    # Modül skillopt.envs.metodoloji altında symlink ile yaşadığında varsayılan
    # _load_env_prompt zaten bulur; dışarıdan import edilirse diye açıkça yüklüyoruz.

    @staticmethod
    def _read_prompt(name: str) -> str | None:
        path = os.path.join(_PROMPTS_DIR, f"{name}.md")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()

    def get_error_minibatch_prompt(self) -> str | None:
        return self._read_prompt("analyst_error")

    def get_success_minibatch_prompt(self) -> str | None:
        return self._read_prompt("analyst_success")
