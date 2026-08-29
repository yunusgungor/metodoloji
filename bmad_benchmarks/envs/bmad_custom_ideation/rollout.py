"""Rollout + scoring for bmad-custom-ideation benchmark.

Task: user shares a half-formed idea → model must run a proactive brainstorm
with meaningful inferences and explicit decisions.

Scoring: LLM-judge evaluates the output on 5 behavioral dimensions (not
keyword matching — that would let the model game the score by using trigger
words without actually brainstorming well).
"""

import json
import pathlib
from skillopt.model import chat_target

# Judge prompt: scores output on behavioral quality, returns JSON verdict
_JUDGE_SYSTEM = (
    "You are a strict judge of brainstorm quality. A user shared a half-formed "
    "idea, and an assistant led a brainstorm. Evaluate the assistant's response "
    "on 5 dimensions. For each, respond 1 if clearly demonstrated, 0 if absent "
    "or weak. Be strict — surface language without substance does not count.\n\n"
    "Dimensions:\n"
    "1. proactive_inference: Does the assistant offer its own reading of the idea "
    "   (what's promising, what's shaky, what it implies) rather than only asking "
    "   open questions? A concrete hypothesis or proposal to react to counts.\n"
    "2. explicit_decision: Does the assistant name a specific decision the user "
    "   must make and ask for the call (e.g. 'we need to decide X or Y')? Merely "
    "   asking a question is not enough; it must surface a real fork.\n"
    "3. multiple_perspective: Does the assistant pressure the idea from more than "
    "   one angle (competitor, buyer, domain expert, critic, opposing view)?\n"
    "4. focused_one_question: Does the assistant work one question at a time "
    "   rather than shotgun many questions at once?\n"
    "5. hypothesis_offer: Does the assistant offer a concrete current-best-answer "
    "   or hypothesis the user can accept, reject, or revise?\n\n"
    "Respond with ONLY a JSON object: {\"proactive_inference\": 0 or 1, "
    "\"explicit_decision\": 0 or 1, \"multiple_perspective\": 0 or 1, "
    "\"focused_one_question\": 0 or 1, \"hypothesis_offer\": 0 or 1}"
)

_BEHAVIOR_KEYS = [
    "proactive_inference",
    "explicit_decision",
    "multiple_perspective",
    "focused_one_question",
    "hypothesis_offer",
]


def _judge(output_text: str) -> dict[str, int]:
    """Ask the judge model to score the output. Returns {behavior: 0|1}."""
    import re
    verdict_text, _ = chat_target(
        system=_JUDGE_SYSTEM,
        user=f"## Assistant's response\n\n{output_text}",
        max_completion_tokens=300,
    )
    # Extract JSON from the verdict
    m = re.search(r"\{.*\}", verdict_text, re.DOTALL)
    if not m:
        return {k: 0 for k in _BEHAVIOR_KEYS}
    try:
        verdict = json.loads(m.group(0))
        return {k: int(verdict.get(k, 0)) for k in _BEHAVIOR_KEYS}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {k: 0 for k in _BEHAVIOR_KEYS}


def _score(output_text: str, expected_behaviors: list[str]) -> tuple[int, float]:
    """Score via LLM judge: soft = fraction of behaviors judged present."""
    verdict = _judge(output_text)
    found = sum(verdict.get(k, 0) for k in expected_behaviors)
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
