#!/usr/bin/env python3
"""Bench: measure skill-less baseline scores for all BMAD benchmarks.

Runs each benchmark's scorer against LLM outputs with an empty skill,
and emits: baseline_accept_rate=<value> (in_range/total)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

import httpx
from bmad_benchmarks.registry import _ADAPTERS, load_benchmark_config

# custom_* benchmarks use build_custom_prompt from _base_
_CUSTOM_RECORDS = {
    "bmad-custom-ir": ("Implementation Readiness (IR)",
                       [("Research Inputs", "research_inputs"),
                        ("Design Documents", "design_docs"),
                        ("Technical Dependencies", "dependencies")]),
    "bmad-custom-sp": ("Sprint Planning (SP)",
                       [("Sprint Goal", "sprint_scope"),
                        ("Capacity", "capacity"),
                        ("Technical Debt", "tech_debt")]),
    "bmad-custom-story": ("User Story",
                          [("Epic", "epic"),
                           ("Experiments", "experiments"),
                           ("Architecture", "architecture")]),
    "bmad-custom-qr": ("Quality Record (QR)",
                       [("Story", "story_summary"),
                        ("Diff Summary", "diff_summary"),
                        ("Test Results", "test_results")]),
    "bmad-custom-pr": ("Production Readiness (PR)",
                       [("Release Scope", "release_scope"),
                        ("Staging Status", "staging_status"),
                        ("Rollback Plan", "rollback_plan")]),
}
import importlib

MODEL = os.environ.get("BASELINE_MODEL", "oc/mimo-v2.5-free")


def _call_llm(system: str, user: str, retries: int = 2) -> str:
    base = os.environ["OPENAI_COMPATIBLE_BASE_URL"]
    key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    for attempt in range(retries + 1):
        try:
            r = httpx.post(
                f"{base}/chat/completions",
                json={"model": MODEL, "max_tokens": 2048, "temperature": 0,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}]},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=180.0,
            )
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(r.text)
            msg = obj["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning_content") or ""
        except (httpx.TimeoutException, httpx.ReadTimeout) as e:
            if attempt < retries:
                print(f"    [retry {attempt+1}] timeout, waiting 5s...", file=sys.stderr)
                import time; time.sleep(5)
            else:
                raise


def _load_items(data_dir: Path, split: str) -> list[dict]:
    split_dir = data_dir / split
    if not split_dir.is_dir():
        return []
    items = []
    for f in sorted(split_dir.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        items.extend(data if isinstance(data, list) else [data])
    return items


def measure_baseline(bench_name: str, max_items: int = 3) -> dict:
    module_path = _ADAPTERS[bench_name][0].replace(".adapter", ".rollout")
    mod = importlib.import_module(module_path)
    score_fn = getattr(mod, "_score", None)
    prompt_fn = getattr(mod, "_prompt", None)

    # custom_* benchmarks use run_custom_batch with score_field_presence
    if score_fn is None:
        from bmad_benchmarks.envs._base_.rollout import score_field_presence
        score_fn = lambda output_text, item: score_field_presence(
            output_text, item.get("expected_fields", []))
    if prompt_fn is None and bench_name in _CUSTOM_RECORDS:
        from bmad_benchmarks.envs._base_.rollout import build_custom_prompt
        record_name, fields = _CUSTOM_RECORDS[bench_name]
        prompt_fn = lambda item, skill, _rn=record_name, _f=fields: (
            build_custom_prompt(item, skill, _rn, _f))
    elif prompt_fn is None:
        prompt_fn = lambda item, skill: (
            f"{skill}\n\nYou are a helpful assistant.",
            f"Complete this task: {json.dumps(item, default=str)[:500]}")

    env_name = module_path.split(".")[-2]
    data_dir = Path(__file__).resolve().parents[2] / "bmad_benchmarks" / "envs" / env_name / "data"

    items = _load_items(data_dir, "val")
    if not items:
        items = _load_items(data_dir, "test")
    if not items:
        return {"score": 0.0, "hard_rate": 0.0, "n": 0}

    items = items[:max_items]
    hards, softs = [], []
    for item in items:
        try:
            system, user = prompt_fn(item, "")
            output = _call_llm(system, user)
            if not output:
                raise ValueError("empty LLM response")
            hard, soft = score_fn(output, item)
            hards.append(hard)
            softs.append(soft)
        except Exception as e:
            print(f"  [err] {bench_name}/{item.get('id','?')}: {e}", file=sys.stderr)
            hards.append(0)
            softs.append(0.0)

    return {
        "score": sum(softs) / len(softs) if softs else 0.0,
        "hard_rate": sum(hards) / len(hards) if hards else 0.0,
        "n": len(items),
    }


def main():
    results = {}
    for bench in _ADAPTERS:
        print(f"  {bench}...", file=sys.stderr, end=" ", flush=True)
        r = measure_baseline(bench, max_items=3)
        results[bench] = r
        s = r["score"]
        tag = "OK" if 0.6 <= s <= 0.8 else ("EASY" if s >= 0.9 else "HARD" if s <= 0.3 else "OUT")
        print(f"baseline={s:.3f} n={r['n']} [{tag}]", file=sys.stderr)

    scored = [(n, r) for n, r in results.items() if r["n"] > 0]
    in_range = sum(1 for _, r in scored if 0.6 <= r["score"] <= 0.8)
    total = len(scored)
    rate = in_range / total if total else 0.0
    print(f"baseline_accept_rate={rate:.3f} ({in_range}/{total})")


if __name__ == "__main__":
    main()
