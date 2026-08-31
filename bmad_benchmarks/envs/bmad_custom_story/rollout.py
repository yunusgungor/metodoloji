from .._base_.rollout import run_batch as _run_batch, score_field_presence


def _score(output_text, item):
    return score_field_presence(output_text, item["expected_fields"])


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are producing a Story (S) methodology record. "
        f"Follow the template fields exactly, in English field labels."
    )
    user = (
        f"## Epic\n\n{item['epic']}\n\n"
        f"## Experiments\n\n{item['experiments']}\n\n"
        f"## Architecture\n\n{item['architecture']}\n\n"
        f"Produce the complete record with all fields."
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="custom-story")
