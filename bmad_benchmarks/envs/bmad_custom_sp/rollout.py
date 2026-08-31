from .._base_.rollout import run_custom_batch

_FIELDS = [
    ("Sprint Goal", "sprint_scope"),
    ("Capacity", "capacity"),
    ("Technical Debt", "tech_debt"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Sprint (SP)", _FIELDS,
        "custom-sp", workers=workers, max_completion_tokens=max_completion_tokens,
    )
