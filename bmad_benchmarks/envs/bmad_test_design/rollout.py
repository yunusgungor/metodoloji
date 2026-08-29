"""Rollout + scoring for bmad-test-design benchmark.

Scoring:
  hard: 1 if ALL expected test categories covered, else 0
  soft: float [0,1] = fraction of test categories found
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, expected_categories: list[str]) -> tuple[int, float]:
    output_lower = output_text.lower()
    found = sum(1 for c in expected_categories if c.lower() in output_lower)
    soft = found / len(expected_categories) if expected_categories else 1.0
    hard = 1 if soft >= 0.8 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are a test architect. Create a comprehensive test design plan."
    )
    user_prompt = f"## Story\n\n{item['story_text']}"
    if item.get("architecture_text"):
        user_prompt += f"\n\n## Architecture\n\n{item['architecture_text']}"

    output_text, meta = chat_target(
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": output_text},
    ]

    hard, soft = _score(output_text, item["expected_test_categories"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    conversation = messages
    (pred_dir / "conversation.json").write_text(
        json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "test-design"),
        "predicted_output_length": len(output_text),
        "n_expected_categories": len(item["expected_test_categories"]),
        "target_system_prompt": system_prompt[:500],
        "target_user_prompt": user_prompt[:500],
        "n_turns": 1,
    }


def run_batch(items: list[dict], skill_content: str, out_dir,
              workers: int = 1, max_completion_tokens: int = 4096) -> list[dict]:
    out_dir = pathlib.Path(out_dir)
    results = []
    for item in items:
        try:
            result = _rollout_one(item, skill_content, out_dir,
                                  max_completion_tokens=max_completion_tokens)
        except Exception as exc:
            result = {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "test-design"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
