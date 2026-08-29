"""Rollout + scoring for bmad-meta-mod benchmark.

Task: given a task, classify the methodology mode (A/B/C/D).
Scoring: hard = mode correct; soft = 1.0 if correct else 0.
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, expected_mode: str) -> tuple[int, float]:
    # Look for mode mention: "Mod A", "A)", "mode A", "Mod-A"
    import re
    lower = output_text.lower()
    # Find all mode mentions
    modes_found = set()
    for m in re.findall(r"mod\s*([abcd])", lower):
        modes_found.add(m.upper())
    for m in re.findall(r"\b([abcd])\s*modu", lower):
        modes_found.add(m.upper())
    # Also plain single letter at start of a mode line
    if "mod a" in lower or "mod-a" in lower or "moda" in lower:
        modes_found.add("A")
    if "mod b" in lower or "mod-b" in lower or "modb" in lower:
        modes_found.add("B")
    if "mod c" in lower or "mod-c" in lower or "modc" in lower:
        modes_found.add("C")
    if "mod d" in lower or "mod-d" in lower or "modd" in lower:
        modes_found.add("D")

    expected = expected_mode.upper()
    correct = expected in modes_found
    hard = 1 if correct else 0
    soft = 1.0 if correct else 0.0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You classify development tasks into methodology modes. "
        f"State the mode explicitly as 'Mod X'."
    )
    user_prompt = (
        f"## Task\n\n{item['task_desc']}\n\n"
        f"Which methodology mode (Mod A, B, C, or D) does this task belong to, "
        f"and what gate/protection does it carry?"
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

    hard, soft = _score(output_text, item["expected_mode"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "meta-mod"),
        "expected_mode": item["expected_mode"],
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
                "task_type": item.get("task_type", "meta-mod"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
