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
import re
import time

from skillopt.model import chat_target, chat_optimizer

# Some gateways (e.g. a CMC proxy) return a 503 *as the response body* with a
# 200 status — the SDK sees a normal reply, so the backend's own retry loop
# never fires. Detect that inline error and retry at the rollout layer.
# Also covers the OPTIMIZER path: ReflACT's analyst (reflect) calls hit the
# same proxy, so a body-level 503 silently kills patch generation (the reflect
# stage sees a "normal" reply, parses no patch, and the step is skipped). We
# wrap chat_optimizer the same way chat_target already is.
_GATEWAY_ERROR_RE = re.compile(
    r"\[?CommandCode error.*?(?:503|service temporarily unavailable"
    r"|rate limit|429|timeout|internal server error)",
    re.IGNORECASE,
)

# laguna's :free gateway drops ~20-50% of calls with a body-level 503 under
# load. Retry enough to absorb transient 503s without making every step
# extremely slow. workers=2 (config) keeps the parallel 503 spike manageable;
# the drop filter was removed so the gate always scores the full split.
# ponytail: fixed count; if 503s persist, use a more stable non-free model.
_ROLLOUT_RETRIES = 4
_ROLLOUT_RETRY_DELAY_S = 3.0


def _extract_text(output):
    """chat_target/chat_optimizer return (text, usage) tuples; take the text."""
    return output[0] if isinstance(output, tuple) else output


def _retry_body_gateway_errors(call_fn, *args, **kwargs):
    """Call an LLM fn; if the *body* contains a gateway error (503/429 returned
    inside a 200 reply), retry with backoff instead of trusting it as output.
    Falls back to the last result after _ROLLOUT_RETRIES.
    Handles both string-returning fns and (text, usage) tuples."""
    output = None
    for attempt in range(_ROLLOUT_RETRIES):
        output = call_fn(*args, **kwargs)
        text = _extract_text(output)
        if text and not _GATEWAY_ERROR_RE.search(text):
            return output
        if attempt < _ROLLOUT_RETRIES - 1:
            time.sleep(_ROLLOUT_RETRY_DELAY_S * (2 ** attempt))
    return output


def _call_with_retry(system_prompt, user_prompt, max_completion_tokens):
    result = _retry_body_gateway_errors(
        chat_target,
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
    )
    # chat_target returns (text, usage); rollout_one expects the text string.
    return _extract_text(result)


def call_optimizer_with_retry(system_prompt, user_prompt, max_completion_tokens,
                              stage="optimizer"):
    """Like _call_with_retry but for the OPTIMIZER model (ReflACT analyst/reflect).
    Same body-level 503/429 guard, so reflect never reads an infrastructure
    error as a model failure (which previously caused silent skip_no_patches)."""
    result = _retry_body_gateway_errors(
        chat_optimizer,
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
        stage=stage,
    )
    return _extract_text(result)


def _patch_optimizer_gateway_retry():
    """Monkeypatch SkillOpt's chat_optimizer so ReflACT's analyst/reflect AND
    merge/aggregate calls get the same body-level 503/429 retry guard as target
    rollouts.

    Every SkillOpt module does `from skillopt.model import chat_optimizer` at
    import time (reflect, aggregate/merge_patches, trainer, optimizer/*...). So
    patch the source attribute AND every already-imported submodule's bound
    name. The wrapper captures the ORIGINAL function so there is no recursion.
    """
    import skillopt.model as _sm
    _orig = _sm.chat_optimizer

    def _wrapped(system, user, max_completion_tokens=16384, retries=5,
                 stage="optimizer", reasoning_effort=None, timeout=None):
        text = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for attempt in range(retries):
            try:
                out_text, usage = _orig(
                    system=system, user=user,
                    max_completion_tokens=max_completion_tokens,
                    stage=stage, reasoning_effort=reasoning_effort,
                    timeout=timeout,
                )
            except Exception:
                raise
            text = out_text or ""
            if text and not _GATEWAY_ERROR_RE.search(text):
                return text, usage
            time.sleep(min(2 ** attempt, 30))
        return text, usage

    _sm.chat_optimizer = _wrapped

    # Patch every skillopt submodule that already bound the name.
    import pkgutil
    import importlib
    for mod in pkgutil.walk_packages(_sm.__path__, _sm.__name__ + "."):
        try:
            m = importlib.import_module(mod.name)
        except Exception:
            continue
        if getattr(m, "chat_optimizer", None) is _orig:
            m.chat_optimizer = _wrapped


_patch_optimizer_gateway_retry()


def rollout_one(item, skill_content, out_dir, system_prompt, user_prompt,
                score_fn, max_completion_tokens=4096, extra_result=None):
    """Common rollout: call LLM, score, save conversation."""
    output_text = _call_with_retry(
        system_prompt, user_prompt, max_completion_tokens,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": output_text},
    ]
    hard, soft = score_fn(output_text, item)
    pred_dir = pathlib.Path(out_dir) / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    conv_path = pred_dir / "conversation.json"
    conv_path.write_text(
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
        "_conv_path": str(conv_path),
        "_raw_output": output_text,
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
            err_text = str(exc)
            return {
                "id": item["id"],
                "hard": 0,
                "soft": 0.0,
                "task_type": item.get("task_type", default_task_type),
                "error": err_text,
                "n_turns": 0,
                "_raw_output": err_text,
            }

    if workers > 1 and len(items) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_safe, items))
    else:
        results = [_safe(item) for item in items]

    # NOTE: persistent gateway failures (503/429 returned *as the body*) are
    # NOT dropped here. _call_with_retry already retries them; if one survives
    # it stays in the list as hard:0 so the gate ALWAYS scores the full split.
    # Dropping them made the gate score a truncated set (5/9 items vanished)
    # and reject good patches. Serial rollout (workers=1) keeps the rate low.

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    serializable = [
        {k: v for k, v in r.items() if k not in ("_conv_path", "_raw_output")}
        for r in results
    ]
    (out_dir / "rollouts.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8",
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
    pairs rendered as '## <title>' headers. The expected output section labels
    (item["expected_fields"]) are listed so the model produces the exact
    headings the scorer looks for.
    """
    expected = item.get("expected_fields") or []
    expected_list = ", ".join(f"'{f}'" for f in expected)
    system = (
        f"{skill_content}\n\n"
        f"You are producing a {record_name} methodology record. "
        f"Follow the template fields exactly, in English field labels."
    )
    sections = "".join(f"## {title}\n\n{item[key]}\n\n" for title, key in fields)
    user = (
        f"{sections}"
        f"Produce the record with these exact section headings: {expected_list}.\n"
        f"{outro}"
    )
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


def _base_selfcheck():
    """Self-check for the shared field-presence scorer used by custom_*."""
    # normalize: parens/colons stripped, lowercased, whitespace trimmed.
    assert normalize_field_label("  Durum: (E-XXX)  ") == "durum e-xxx"
    assert normalize_field_label("STATUS") == "status"
    # Full presence.
    assert score_field_presence(
        "## Incident\n...\n## Root Cause\n...\n## Action Items\n...",
        ["Incident", "Root Cause", "Action Items"],
    ) == (1, 1.0)
    # Partial: 2/3 fields → soft 0.667 < 0.9 → hard 0.
    assert score_field_presence(
        "## Incident\n...\n## Root Cause\n...",
        ["Incident", "Root Cause", "Action Items"],
    ) == (0, 0.6666666666666666)
    # Threshold at 0.9: 3/3 = 1.0 passes; 2/3 fails.
    assert score_field_presence(
        "incident, root cause, action items",
        ["Incident", "Root Cause", "Action Items"],
    ) == (1, 1.0)
    # Missing field entirely → fails.
    assert score_field_presence(
        "nothing here",
        ["Incident", "Root Cause"],
    ) == (0, 0.0)
    print("selfcheck OK")
