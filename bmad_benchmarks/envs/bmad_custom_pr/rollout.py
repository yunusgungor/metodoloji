from .._base_.rollout import run_custom_batch

_FIELDS = [
    ("Release Scope", "release_scope"),
    ("Staging Status", "staging_status"),
    ("Rollback Plan", "rollback_plan"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Production Readiness (PR)", _FIELDS,
        "custom-pr", workers=workers, max_completion_tokens=max_completion_tokens,
    )
