"""Rollout + scoring for bmad_custom_sp benchmark.

Task: given the sprint scope and capacity, produce an SP record.
Scoring: hard = all expected fields present; soft = fraction present.
"""

import json
import pathlib
from skillopt.model import chat_target


def _normalize_field(field: str) -> str:
    """Normalize a Turkish field label for matching: strip punctuation, handle
    singular/plural, accents. 'Test Sonuçları' matches 'test sonucu'."""
    f = field.lower()
    for plural, singular in [("sonuçları", "sonucu"), ("kriterleri", "kriter"), ("bağımlılıkları", "bağımlılık")]:
        f = f.replace(plural, singular)
    if f.endswith("lar"):
        f = f[:-3]
    elif f.endswith("ler"):
        f = f[:-3]
    return f.strip()


def _score(output_text: str, expected_fields: list[str]) -> tuple[int, float]:
    output_lower = output_text.lower()
    norm_output = _normalize_field(output_lower)
    found = 0
    for f in expected_fields:
        norm_f = _normalize_field(f)
        if norm_f in output_lower or norm_f in norm_output:
            found += 1
    soft = found / len(expected_fields) if expected_fields else 1.0
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are producing a Sprint (SP) methodology record. "
        f"Follow the template fields exactly, in Turkish field labels."
    )
    user_prompt = (
        f"## Sprint Scope\n\n{item['sprint_scope']}\n\n"
        f"## Capacity\n\n{item['capacity']}\n\n"
        f"## Tech Debt\n\n{item['tech_debt']}\n\n"
        f"Produce the complete record with all fields."
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

    hard, soft = _score(output_text, item["expected_fields"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "custom-sp"),
        "predicted_output_length": len(output_text),
        "n_expected_fields": len(item["expected_fields"]),
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
                "task_type": item.get("task_type", "custom-sp"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
