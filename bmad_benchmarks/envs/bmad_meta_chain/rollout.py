"""Rollout + scoring for bmad-meta-chain benchmark.

Task: given a stage, produce the correct record, its path, and allowed
status values. Scoring checks each against expected values.
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, item: dict) -> tuple[int, float]:
    lower = output_text.lower()
    checks = []
    # 1. Record type (e.g. "QR", "IR")
    rec = item["expected_record"].lower()
    checks.append(rec in lower)
    # 2. Path (e.g. "docs/quality/")
    path = item["expected_path"].lower()
    checks.append(path in lower)
    # 3. Status values (e.g. "pass", "fail")
    status_vals = [s.strip().lower() for s in item["expected_status"].split("|") if s.strip()]
    status_ok = any(v in lower for v in status_vals)
    checks.append(status_ok)
    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You identify the methodology record for a stage, its exact file path, "
        f"and its allowed status values."
    )
    user_prompt = (
        f"## Stage\n\n{item['stage']}\n\n"
        f"Which methodology record is required at this stage, at what path, "
        f"and what are its allowed status values?"
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

    hard, soft = _score(output_text, item)

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "meta-chain"),
        "expected_record": item["expected_record"],
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
                "task_type": item.get("task_type", "meta-chain"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
