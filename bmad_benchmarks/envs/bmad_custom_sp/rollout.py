from .._base_.rollout import run_custom_batch, _base_selfcheck

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


def _selfcheck():
    # Shares the field-presence scorer in _base_; exercise it with this
    # benchmark's labels.
    _base_selfcheck()
    from .._base_.rollout import score_field_presence
    labels = ["Sprint Goal", "Capacity", "Technical Debt"]
    assert score_field_presence(
        "## sprint goal\n## capacity\n## technical debt", labels,
    ) == (1, 1.0)
    assert score_field_presence(
        "## sprint goal\n## capacity", labels,
    ) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
