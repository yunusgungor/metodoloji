"""Base rollout utilities shared by all BMAD benchmarks.

Provides:
  - rollout_one(): call LLM, score, save conversation
  - run_batch(): parallel batch rollout with error handling
  - normalize_turkish_field(): Turkish singular/plural normalization
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
              max_completion_tokens=4096, workers=1, default_task_type="unknown"):
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
    """
    out_dir = pathlib.Path(out_dir)

    def _safe(item):
        try:
            sys_prompt, usr_prompt = prompt_fn(item, skill_content)
            return rollout_one(
                item, skill_content, out_dir, sys_prompt, usr_prompt,
                score_fn, max_completion_tokens,
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
# Turkish field normalization — shared by custom_ir, custom_sp, custom_story,
# custom_qr, custom_pr rollouts
# ---------------------------------------------------------------------------

def normalize_turkish_field(field: str) -> str:
    """Normalize a Turkish field label for matching.

    Handles singular/plural (sonuçları→sonucu, kriterleri→kriter,
    bağımlılıkları→bağımlılık) and strips trailing -lar/-ler.
    """
    f = field.lower()
    for plural, singular in [
        ("sonuçları", "sonucu"),
        ("kriterleri", "kriter"),
        ("bağımlılıkları", "bağımlılık"),
    ]:
        f = f.replace(plural, singular)
    if f.endswith("lar") or f.endswith("ler"):
        f = f[:-3]
    return f.strip()


def score_field_presence(output_text, expected_fields, threshold=0.9):
    """Score output against expected Turkish field labels.

    Returns (hard, soft) where hard=1 iff soft >= threshold.
    """
    output_lower = output_text.lower()
    norm_output = normalize_turkish_field(output_lower)
    found = sum(
        1 for f in expected_fields
        if normalize_turkish_field(f) in output_lower
        or normalize_turkish_field(f) in norm_output
    )
    soft = found / len(expected_fields) if expected_fields else 1.0
    hard = 1 if soft >= threshold else 0
    return hard, soft
