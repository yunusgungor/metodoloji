from .._base_.rollout import run_batch as _run_batch, score_field_presence


def _score(output_text, item):
    return score_field_presence(output_text, item["expected_fields"])


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are producing a Quality Review (QR) methodology record. "
        f"Follow the template fields exactly, in Turkish field labels."
    )
    user = (
        f"## Story\n\n{item['story_summary']}\n\n"
        f"## Diff Summary\n\n{item['diff_summary']}\n\n"
        f"## Test Results\n\n{item['test_results']}\n\n"
        f"Produce the complete QR record (docs/quality/QR-XXX.md) with all fields."
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="custom-qr")
