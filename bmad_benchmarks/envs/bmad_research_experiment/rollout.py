"""Rollout + scoring for bmad-research-experiment benchmark.

Scoring:
  hard: 1 if output contains ALL expected experiment record fields AND
        hypothesis follows H-NNN format, else 0
  soft: float [0,1] = fraction of expected fields found in output
"""

import json
import pathlib
import re
from skillopt.model import chat_target

# Regex patterns for experiment record fields (Turkish labels from manifesto)
_FIELD_PATTERNS = {
    "Teori": re.compile(r"##\s*Teori|###\s*Teori|\*\*Teori:", re.IGNORECASE),
    "Hipotez": re.compile(r"Hipotez.*H-\d+|##\s*Hipotez|###\s*Hipotez|\*\*Hipotez:", re.IGNORECASE),
    "Ölçüm metrikleri": re.compile(r"Ölçüm metrikleri|##\s*Ölçüm|###\s*Ölçüm|\*\*Ölçüm", re.IGNORECASE),
    "Deney tasarımı": re.compile(r"Deney tasarımı|##\s*Deney|###\s*Deney tasarımı|\*\*Deney tasarımı", re.IGNORECASE),
    "Kod kapsamı": re.compile(r"Kod kapsamı|##\s*Kod|###\s*Kod kapsamı|\*\*Kod kapsamı", re.IGNORECASE),
}

# Hypothesis format: H-NNN anywhere in text (format flexibility)
_HYPOTHESIS_RE = re.compile(r"H-\d+")


def _score(output_text: str, expected_fields: list[str],
           check_hypothesis_format: bool = True) -> tuple[int, float]:
    """Score experiment record output against expected fields."""
    found = 0
    for field in expected_fields:
        pattern = _FIELD_PATTERNS.get(field)
        if pattern and pattern.search(output_text):
            found += 1

    soft = found / len(expected_fields) if expected_fields else 0.0
    hard = 1 if soft >= 0.8 else 0

    # Additional hard check: hypothesis format correctness
    if check_hypothesis_format and hard == 1:
        if not _HYPOTHESIS_RE.search(output_text):
            hard = 0  # Hypozez formatı bozuksa hard=0

    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                 max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are a research methodology expert. Generate a complete "
        f"experiment record following the methodology manifesto. "
        f"The record MUST contain these fields in Turkish: "
        f"Teori, Hipotez (H-NNN format), Ölçüm metrikleri, "
        f"Deney tasarımı, Kod kapsamı."
    )
    user_prompt = f"## Senaryo\n\n{item['task_desc']}\n\nBu senaryo için tam bir deney kaydı üret."

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

    hard, soft = _score(output_text, item["expected_fields"],
                        item.get("expected_hypothesis_format", True))

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "research-experiment"),
        "predicted_output_length": len(output_text),
        "n_expected_fields": len(item["expected_fields"]),
        "n_fields_found": sum(
            1 for f in item["expected_fields"]
            if _FIELD_PATTERNS.get(f, re.compile("NEVER_MATCH")).search(output_text)
        ),
        "hypothesis_format_valid": bool(_HYPOTHESIS_RE.search(output_text)),
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
                "task_type": item.get("task_type", "research-experiment"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
