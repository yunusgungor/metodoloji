from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    lower = output_text.lower()
    checks = [
        item["expected_record"].lower() in lower,
        item["expected_path"].lower() in lower,
        any(v in lower for v in
            [s.strip().lower() for s in item["expected_status"].split("|") if s.strip()]),
    ]
    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You identify the methodology record for a stage, its exact file path, "
        f"and its allowed status values."
    )
    user = (
        f"## Stage\n\n{item['stage']}\n\n"
        f"Which methodology record is required at this stage, at what path, "
        f"and what are its allowed status values?"
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-chain")
