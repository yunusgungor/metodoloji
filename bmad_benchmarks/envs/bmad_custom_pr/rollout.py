from .._base_.rollout import run_custom_batch, _base_selfcheck

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


def _selfcheck():
    # Shares the field-presence scorer in _base_; exercise it with this
    # benchmark's labels.
    _base_selfcheck()
    from .._base_.rollout import score_field_presence
    labels = ["Release Scope", "Staging Status", "Rollback Plan"]
    assert score_field_presence(
        "## release scope\n## staging status\n## rollback plan", labels,
    ) == (1, 1.0)
    assert score_field_presence(
        "## release scope\n## staging status", labels,
    ) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
