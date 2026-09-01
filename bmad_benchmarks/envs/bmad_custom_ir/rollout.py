from .._base_.rollout import run_custom_batch, _base_selfcheck

_FIELDS = [
    ("Research Inputs", "research_inputs"),
    ("Design Documents", "design_docs"),
    ("Technical Dependencies", "dependencies"),
]


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return run_custom_batch(
        items, skill_content, out_dir, "Implementation Readiness (IR)", _FIELDS,
        "custom-ir", workers=workers, max_completion_tokens=max_completion_tokens,
    )


def _selfcheck():
    # The custom_* family shares the field-presence scorer in _base_; exercise
    # it with this benchmark's field labels.
    _base_selfcheck()
    # Field labels are normalized so punctuation/case variants still match.
    from .._base_.rollout import score_field_presence
    assert score_field_presence(
        "## research inputs\n## design documents\n## technical dependencies",
        ["Research Inputs", "Design Documents", "Technical Dependencies"],
    ) == (1, 1.0)
    assert score_field_presence(
        "## research inputs\n## design documents",
        ["Research Inputs", "Design Documents", "Technical Dependencies"],
    ) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
