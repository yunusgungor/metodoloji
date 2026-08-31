from .._base_.rollout import run_custom_batch

_FIELDS = [
    ("Epic", "epic"),
    ("Experiments", "experiments"),
    ("Architecture", "architecture"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Story (S)", _FIELDS,
        "custom-story", workers=workers, max_completion_tokens=max_completion_tokens,
    )
