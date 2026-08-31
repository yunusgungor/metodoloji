from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    output_lower = output_text.lower()
    expected = item["expected_test_categories"]
    found = sum(1 for c in expected if c.lower() in output_lower)
    soft = found / len(expected) if expected else 1.0
    hard = 1 if soft >= 0.8 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a test architect. Create a comprehensive test design plan."
    )
    user = f"## Story\n\n{item['story_text']}"
    if item.get("architecture_text"):
        user += f"\n\n## Architecture\n\n{item['architecture_text']}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="test-design")
