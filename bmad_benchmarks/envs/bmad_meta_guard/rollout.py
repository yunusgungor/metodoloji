"""Rollout + scoring for bmad-meta-guard benchmark.

Task: given a scenario, decide DENY or ALLOW per guard rules.
Scoring: hard = decision correct; soft = 1.0 if correct else 0.
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, expected_decision: str) -> tuple[int, float]:
    lower = output_text.lower()
    expected = expected_decision.upper()
    # Detect decision
    denied = ("deny" in lower or "engelle" in lower or "reddet" in lower or "block" in lower)
    allowed = ("allow" in lower or "izin" in lower or "serbest" in lower or "geçerli" in lower)
    decided = "DENY" if denied else ("ALLOW" if allowed else None)
    correct = decided == expected
    hard = 1 if correct else 0
    soft = 1.0 if correct else 0.0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You decide whether the guard hook should DENY or ALLOW a tool call. "
        f"State the decision explicitly as 'DENY' or 'ALLOW' and justify it."
    )
    user_prompt = (
        f"## Scenario\n\n{item['scenario']}\n\n"
        f"Should the guard hook DENY or ALLOW? State your decision first."
    )

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

    hard, soft = _score(output_text, item["expected_decision"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "meta-guard"),
        "expected_decision": item["expected_decision"],
        "predicted_output_length": len(output_text),
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
                "task_type": item.get("task_type", "meta-guard"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
