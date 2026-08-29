"""Rollout + scoring for bmad-meta-root benchmark.

Task: given an operation, classify correct root ({project-root} vs
{metodoloji-root}) and direction (output vs read).
Scoring: hard = both root and direction correct; soft = per-component.
"""

import json
import pathlib
from skillopt.model import chat_target


def _score(output_text: str, item: dict) -> tuple[int, float]:
    lower = output_text.lower()
    checks = []

    # 1. Root classification
    exp_root = item["expected_root"].lower()  # "project-root" | "metodoloji-root"
    if exp_root == "project-root":
        root_ok = ("project" in lower) or ("hedef" in lower and "proje" in lower)
    else:
        root_ok = ("metodoloji" in lower) or ("plugin" in lower)
    checks.append(root_ok)

    # 2. Direction classification
    exp_dir = item["expected_direction"].lower()  # "output" | "read"
    if exp_dir == "output":
        dir_ok = ("output" in lower or "yaz" in lower or "oluştur" in lower or "üret" in lower)
    else:
        dir_ok = ("read" in lower or "oku" in lower or "yükle" in lower)
    checks.append(dir_ok)

    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 1.0 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You classify methodology path operations. State the root "
        f"({'{project-root}'} or {'{metodoloji-root}'}) and the direction "
        f"(output or read)."
    )
    user_prompt = (
        f"## Operation\n\n{item['operation']}\n\n"
        f"Which root does this belong to, and is it an output or a read?"
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
        "task_type": item.get("task_type", "meta-root"),
        "expected_root": item["expected_root"],
        "expected_direction": item["expected_direction"],
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
                "task_type": item.get("task_type", "meta-root"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
