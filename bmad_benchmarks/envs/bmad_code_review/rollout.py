"""Rollout + scoring for bmad-code-review benchmark.

Scoring layers:
  hard: 1 if output contains ALL expected finding categories, else 0
  soft: float [0,1] = fraction of expected findings actually present
"""

import json
import os
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, expected: list[dict]) -> tuple[int, float]:
    """Score review output against expected findings."""
    if not expected:
        return 1, 1.0

    output_lower = output_text.lower()
    found = 0
    for exp in expected:
        # Check by category keyword + severity keyword
        cat = exp.get("category", "").lower()
        sev = exp.get("severity", "").lower()
        title_kw = exp.get("title_keyword", "").lower()

        matched = False
        if title_kw and title_kw in output_lower:
            matched = True
        elif cat and cat in output_lower:
            matched = True

        if matched:
            found += 1

    hard = 1 if found == len(expected) else 0
    soft = found / len(expected) if expected else 1.0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are an elite code reviewer. Review the following diff "
        f"and produce structured findings."
    )
    user_prompt = f"## Diff\n\n{item['diff_text']}"
    if item.get("spec_text"):
        user_prompt += f"\n\n## Spec\n\n{item['spec_text']}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = chat_target(messages)
    output_text = response if isinstance(response, str) else response.get("content", "")

    hard, soft = _score(output_text, item["expected_findings"])

    # Persist conversation for reflection
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
        "task_type": item.get("task_type", "code-review"),
        "predicted_output_length": len(output_text),
        "n_expected_findings": len(item["expected_findings"]),
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
            result = _rollout_one(item, skill_content, out_dir)
        except Exception as exc:
            result = {
                "id": item["id"],
                "hard": 0,
                "soft": 0.0,
                "task_type": item.get("task_type", "code-review"),
                "error": str(exc),
                "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
