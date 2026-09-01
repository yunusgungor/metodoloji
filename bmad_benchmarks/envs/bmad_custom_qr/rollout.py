from .._base_.rollout import run_custom_batch, _base_selfcheck

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


def _selfcheck():
    # Shares the field-presence scorer in _base_; exercise it with this
    # benchmark's labels.
    _base_selfcheck()
    from .._base_.rollout import score_field_presence
    labels = ["Story", "Diff Summary", "Test Results"]
    assert score_field_presence(
        "## story\n## diff summary\n## test results", labels,
    ) == (1, 1.0)
    assert score_field_presence(
        "## story\n## diff summary", labels,
    ) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
