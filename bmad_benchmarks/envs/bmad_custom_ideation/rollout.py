"""Rollout + scoring for bmad-custom-ideation benchmark.

Task: user shares a half-formed idea → model must run a proactive brainstorm
with meaningful inferences and explicit decisions.

Scoring: hard/soft over behavioral quality signals present in the output.
"""

import json
import pathlib
from skillopt.model import chat_target


# Behavioral signals the model output must contain. Each maps to a keyword
# family the output is checked against (case-insensitive, Turkish+English).
_BEHAVIOR_KEYWORDS = {
    # Model makes a concrete inference/offer, not just an open question
    "proactive-inference": [
        "düşünüyorum", "şöyle olabilir", "öneriyorum", "hipotez", "belki şöyle",
        "i think", "maybe", "suggestion", "hypothesis", "what if", "one angle",
    ],
    # Model surfaces an explicit decision that needs the user's call
    "explicit-decision": [
        "karar", "netleştirelim", "seçim", "karar vermen", "belirlemeliyiz",
        "decision", "clarify", "we need to decide", "pick one", "resolve",
    ],
    # Model brings multiple perspectives / alternative viewpoints
    "multiple-perspective": [
        "perspektif", "açıdan", "biri şöyle derdi", "alternatif", "farklı açı",
        "perspective", "angle", "on the other hand", "another view", "stakeholder",
    ],
    # Model stays focused: asks one question at a time, does not shotgun
    "focused-one-question": [
        "ilk sorum", "tek soru", "şu soru", "odaklan",
        "one question", "let's focus", "the first question",
    ],
    # Model offers a concrete hypothesis/current-best-answer to react to
    "hypothesis-offer": [
        "benim tahminim", "en güçlü varsayım", "şu varsayımla",
        "my guess", "strongest assumption", "let's test",
    ],
}


def _score(output_text: str, expected_behaviors: list[str]) -> tuple[int, float]:
    lower = output_text.lower()
    found = 0
    details = []
    for behavior in expected_behaviors:
        keywords = _BEHAVIOR_KEYWORDS.get(behavior, [])
        if not keywords:
            found += 1  # unknown behavior treated as present (don't penalize)
            continue
        matched = any(kw in lower for kw in keywords)
        if matched:
            found += 1
            details.append(f"{behavior}=Y")
        else:
            details.append(f"{behavior}=N")
    soft = found / len(expected_behaviors) if expected_behaviors else 1.0
    hard = 1 if soft >= 0.8 else 0
    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                  max_completion_tokens: int = 4096) -> dict:
    system_prompt = (
        f"{skill_content}\n\n"
        f"You are running a proactive idea brainstorm. The user just shared a "
        f"half-formed idea. Respond with meaningful inferences, an open brainstorm, "
        f"and surface explicit decisions that need the user's call."
    )
    user_prompt = (
        f"## User's message\n\n{item['user_idea']}\n\n"
        f"Respond as the brainstorm lead."
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

    hard, soft = _score(output_text, item["expected_behaviors"])

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "custom-ideation"),
        "predicted_output_length": len(output_text),
        "n_expected_behaviors": len(item["expected_behaviors"]),
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
                "task_type": item.get("task_type", "custom-ideation"),
                "error": str(exc), "n_turns": 0,
            }
        results.append(result)

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
