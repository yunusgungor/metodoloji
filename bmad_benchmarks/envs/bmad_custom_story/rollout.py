from .._base_.rollout import run_custom_batch, _base_selfcheck

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


def _selfcheck():
    # Shares the field-presence scorer in _base_; exercise it with this
    # benchmark's labels.
    _base_selfcheck()
    from .._base_.rollout import score_field_presence
    labels = ["Epic", "Experiments", "Architecture"]
    assert score_field_presence(
        "## epic\n## experiments\n## architecture", labels,
    ) == (1, 1.0)
    assert score_field_presence(
        "## epic\n## experiments", labels,
    ) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
