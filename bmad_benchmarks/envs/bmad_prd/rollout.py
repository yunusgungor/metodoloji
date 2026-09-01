from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    output_lower = output_text.lower()
    expected = item["expected_sections"]
    found = sum(1 for s in expected if s.lower() in output_lower)
    soft = found / len(expected) if expected else 1.0
    hard = 1 if soft >= 0.8 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a product manager. Create a comprehensive PRD."
    )
    user = f"## Product Idea\n\n{item['idea_text']}"
    if item.get("target_audience"):
        user += f"\n\n## Target Audience\n\n{item['target_audience']}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="prd")


def _selfcheck():
    item = {"expected_sections": ["Problem Statement", "Goals", "Success Metrics"]}
    # All sections → pass.
    assert _score(
        "## Problem Statement\n...\n## Goals\n...\n## Success Metrics\n...",
        item,
    ) == (1, 1.0)
    # 2/3 → soft 0.667 < 0.8 → fail.
    assert _score("## Problem Statement\n...\n## Goals\n...", item) == (0, 0.6666666666666666)
    # None → fail.
    assert _score("A product idea.", item) == (0, 0.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
