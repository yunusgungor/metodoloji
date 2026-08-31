from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    expected = item.get("expected_findings", [])
    if not expected:
        return 1, 1.0
    output_lower = output_text.lower()
    found = 0
    for exp in expected:
        title_kw = exp.get("title_keyword", "").lower()
        cat = exp.get("category", "").lower()
        if title_kw and title_kw in output_lower:
            found += 1
        elif cat and cat in output_lower:
            found += 1
    hard = 1 if found == len(expected) else 0
    soft = found / len(expected) if expected else 1.0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are an elite code reviewer. Review the following diff "
        f"and produce structured findings."
    )
    user = f"## Diff\n\n{item['diff_text']}"
    if item.get("spec_text"):
        user += f"\n\n## Spec\n\n{item['spec_text']}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="code-review")
