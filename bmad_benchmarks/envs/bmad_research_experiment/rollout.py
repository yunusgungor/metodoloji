import re
from .._base_.rollout import run_batch as _run_batch, rollout_one
import concurrent.futures
import json
import pathlib

_FIELD_PATTERNS = {
    "Theory": re.compile(r"##\s*Theory|###\s*Theory|\*\*Theory:", re.IGNORECASE),
    "Hypothesis": re.compile(r"Hypothesis.*H-\d+|##\s*Hypothesis|###\s*Hypothesis|\*\*Hypothesis:", re.IGNORECASE),
    "Measurement Metrics": re.compile(r"Measurement Metrics|##\s*Measurement|###\s*Measurement|\*\*Measurement", re.IGNORECASE),
    "Experiment Design": re.compile(r"Experiment Design|##\s*Experiment|###\s*Experiment Design|\*\*Experiment Design", re.IGNORECASE),
    "Code Scope": re.compile(r"Code Scope|##\s*Code|###\s*Code Scope|\*\*Code Scope", re.IGNORECASE),
}

_HYPOTHESIS_RE = re.compile(r"H-\d+")


def _score(output_text, item):
    expected = item["expected_fields"]
    found = sum(1 for f in expected if _FIELD_PATTERNS.get(f, re.compile("NEVER_MATCH")).search(output_text))
    soft = found / len(expected) if expected else 0.0
    hard = 1 if soft >= 0.8 else 0
    if item.get("expected_hypothesis_format", True) and hard == 1:
        if not _HYPOTHESIS_RE.search(output_text):
            hard = 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a research methodology expert. Generate a complete "
        f"experiment record following the methodology manifesto. "
        f"The record MUST contain these fields: "
        f"Theory, Hypothesis (H-NNN format), Measurement Metrics, "
        f"Experiment Design, Code Scope."
    )
    user = f"## Scenario\n\n{item['task_desc']}\n\nGenerate a complete experiment record for this scenario."
    return system, user


def _extra_result(output_text, item):
    return {
        "n_expected_fields": len(item["expected_fields"]),
        "n_fields_found": sum(
            1 for f in item["expected_fields"]
            if _FIELD_PATTERNS.get(f, re.compile("NEVER_MATCH")).search(output_text)
        ),
        "hypothesis_format_valid": bool(_HYPOTHESIS_RE.search(output_text)),
    }


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    out_dir = pathlib.Path(out_dir)

    def _safe(item):
        try:
            sys_p, usr_p = _prompt(item, skill_content)
            return rollout_one(item, skill_content, out_dir, sys_p, usr_p,
                               _score, max_completion_tokens,
                               extra_result=_extra_result)
        except Exception as exc:
            return {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "research-experiment"),
                "error": str(exc), "n_turns": 0,
            }

    if workers > 1 and len(items) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_safe, items))
    else:
        results = [_safe(item) for item in items]

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
