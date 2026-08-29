"""Rollout + scoring for bmad-create-story benchmark.

Scoring:
  hard: 1 if ALL expected sections + metadata fields present, else 0
  soft: float [0,1] = fraction of (sections + metadata) found
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, expected_sections: list[str],
           expected_metadata: list[str]) -> tuple[int, float]:
    output_lower = output_text.lower()

    # Check sections (## heading)
    sections_found = sum(1 for s in expected_sections if s.lower() in output_lower)
    section_score = sections_found / len(expected_sections) if expected_sections else 1.0

    # Check metadata fields
    metadata_found = sum(1 for m in expected_metadata if m.lower() in output_lower)
    meta_score = metadata_found / len(expected_metadata) if expected_metadata else 1.0

    soft = (section_score + meta_score) / 2
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are a story context engine. Create a comprehensive story file."
    )
    user_prompt = f"## Epic\n\n{item['epic_text']}"
    if item.get("prd_text"):
        user_prompt += f"\n\n## PRD\n\n{item['prd_text']}"
    if item.get("architecture_text"):
        user_prompt += f"\n\n## Architecture\n\n{item['architecture_text']}"
    if item.get("ux_text"):
        user_prompt += f"\n\n## UX\n\n{item['ux_text']}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = chat_target(messages)
    output_text = response if isinstance(response, str) else response.get("content", "")

    hard, soft = _score(output_text, item["expected_sections"],
                        item["expected_metadata_fields"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    conversation = messages + [{"role": "assistant", "content": output_text}]
    (pred_dir / "conversation.json").write_text(
        json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "create-story"),
        "predicted_output_length": len(output_text),
        "n_expected_sections": len(item["expected_sections"]),
        "n_expected_metadata": len(item["expected_metadata_fields"]),
        "target_system_prompt": system_prompt[:500],
        "target_user_prompt": user_prompt[:500],
        "n_turns": 1,
    }


def run_batch(items: list[dict], skill_content: str, out_dir: pathlib.Path,
              workers: int = 1, max_completion_tokens: int = 4096) -> list[dict]:
    results = []
    for item in items:
        try:
            result = _rollout_one(item, skill_content, out_dir)
        except Exception as exc:
            result = {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "create-story"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
