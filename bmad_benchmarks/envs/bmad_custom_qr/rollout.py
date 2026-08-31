from .._base_.rollout import run_custom_batch

_FIELDS = [
    ("Story", "story_summary"),
    ("Diff Summary", "diff_summary"),
    ("Test Results", "test_results"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Quality Review (QR)", _FIELDS,
        "custom-qr", workers=workers, max_completion_tokens=max_completion_tokens,
        outro="Produce the complete QR record (docs/quality/QR-XXX.md) with all fields.",
    )
