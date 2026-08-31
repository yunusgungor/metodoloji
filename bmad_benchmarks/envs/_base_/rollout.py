"""Base rollout utilities shared by all BMAD benchmarks.

Provides:
  - rollout_one(): call LLM, score, save conversation
  - run_batch(): parallel batch rollout with error handling
  - normalize_field_label(): singular/plural normalization
  - score_field_presence(): field-presence scoring for custom_* benchmarks
"""

import concurrent.futures
import json
import pathlib

from skillopt.model import chat_target


def rollout_one(item, skill_content, out_dir, system_prompt, user_prompt,
                score_fn, max_completion_tokens=4096, extra_result=None):
    """Common rollout: call LLM, score, save conversation."""
    output_text, _meta = chat_target(
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": output_text},
    ]
    hard, soft = score_fn(output_text, item)
    pred_dir = pathlib.Path(out_dir) / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    result = {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "unknown"),
        "predicted_output_length": len(output_text),
        "target_system_prompt": system_prompt[:500],
        "target_user_prompt": user_prompt[:500],
        "n_turns": 1,
    }
    if extra_result:
        result.update(extra_result(output_text, item))
    return result


def run_batch(items, skill_content, out_dir, score_fn, prompt_fn,
              max_completion_tokens=4096, workers=1, default_task_type="unknown",
              extra_result=None):
    """Parallel batch rollout with ThreadPoolExecutor.

    Args:
        items: list of data items
        skill_content: skill markdown text
        out_dir: output directory
        score_fn: (output_text, item) -> (hard, soft)
        prompt_fn: (item, skill_content) -> (system_prompt, user_prompt)
        max_completion_tokens: LLM max tokens
        workers: number of parallel workers (1 = serial)
        default_task_type: fallback task_type for error results
        extra_result: (output_text, item) -> dict, merged into each result
    """
    out_dir = pathlib.Path(out_dir)

    def _safe(item):
        try:
            sys_prompt, usr_prompt = prompt_fn(item, skill_content)
            return rollout_one(
                item, skill_content, out_dir, sys_prompt, usr_prompt,
                score_fn, max_completion_tokens, extra_result=extra_result,
            )
        except Exception as exc:
            return {
                "id": item["id"],
                "hard": 0,
                "soft": 0.0,
                "task_type": item.get("task_type", default_task_type),
                "error": str(exc),
                "n_turns": 0,
            }

    if workers > 1 and len(items) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_safe, items))
    else:
        results = [_safe(item) for item in items]

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return results


# ---------------------------------------------------------------------------
# Field label normalization — shared by custom_ir, custom_sp, custom_story,
# custom_qr, custom_pr rollouts
# ---------------------------------------------------------------------------

def normalize_field_label(field: str) -> str:
    """Normalize a field label for matching.

    Handles common singular/plural and punctuation variants, then lowercases.
    """
    f = field.lower()
    # Normalize parentheses and colons: "(E-XXX)" -> "E-XXX", "Durum:" -> "durum"
    f = f.replace("(", "").replace(")", "").replace(":", "")
    return f.strip()


def score_field_presence(output_text, expected_fields, threshold=0.9):
    """Score output against expected field labels.

    Returns (hard, soft) where hard=1 iff soft >= threshold.
    """
    output_lower = output_text.lower()
    norm_output = normalize_field_label(output_lower)
    found = sum(
        1 for f in expected_fields
        if normalize_field_label(f) in output_lower
        or normalize_field_label(f) in norm_output
    )
    soft = found / len(expected_fields) if expected_fields else 1.0
    hard = 1 if soft >= threshold else 0
    return hard, soft


def build_custom_prompt(item, skill_content, record_name, fields,
                        outro="Produce the complete record with all fields."):
    """Shared prompt builder for the custom_* methodology benchmarks.

    record_name is the human title of the record type (e.g. "Implementation
    Readiness (IR)"); fields is an ordered list of (section_title, item_key)
    pairs rendered as '## <title>' headers.
    """
    system = (
        f"{skill_content}\n\n"
        f"You are producing a {record_name} methodology record. "
        f"Follow the template fields exactly, in English field labels."
    )
    sections = "".join(f"## {title}\n\n{item[key]}\n\n" for title, key in fields)
    user = f"{sections}{outro}"
    return system, user


def run_custom_batch(items, skill_content, out_dir, record_name, fields,
                     default_task_type, workers=1, max_completion_tokens=4096,
                     outro="Produce the complete record with all fields."):
    """Shared batch runner for the custom_* methodology benchmarks.

    Scores by field-label presence and builds the prompt from record_name + fields.
    """
    def _score(output_text, item):
        return score_field_presence(output_text, item["expected_fields"])

    def _prompt(item, skill_content):
        return build_custom_prompt(item, skill_content, record_name, fields, outro)

    return run_batch(items, skill_content, out_dir, _score, _prompt,
                     max_completion_tokens=max_completion_tokens,
                     workers=workers, default_task_type=default_task_type)
