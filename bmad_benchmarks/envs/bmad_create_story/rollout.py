from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    output_lower = output_text.lower()
    sections = item["expected_sections"]
    metadata = item["expected_metadata_fields"]
    section_score = sum(1 for s in sections if s.lower() in output_lower) / len(sections) if sections else 1.0
    meta_score = sum(1 for m in metadata if m.lower() in output_lower) / len(metadata) if metadata else 1.0
    soft = (section_score + meta_score) / 2
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a story context engine. Create a comprehensive story file."
    )
    user = f"## Epic\n\n{item['epic_text']}"
    for key, label in [("prd_text", "PRD"), ("architecture_text", "Architecture"), ("ux_text", "UX")]:
        if item.get(key):
            user += f"\n\n## {label}\n\n{item[key]}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="create-story")


def _selfcheck():
    item = {
        "expected_sections": ["Acceptance Criteria", "Technical Notes"],
        "expected_metadata_fields": ["status", "priority"],
    }
    # All sections + metadata → pass.
    assert _score(
        "## Acceptance Criteria\n...\n## Technical Notes\n...\nstatus: draft\npriority: high",
        item,
    ) == (1, 1.0)
    # All sections, no metadata → (1.0 + 0.0)/2 = 0.5 < 0.9 → fail.
    assert _score(
        "## Acceptance Criteria\n...\n## Technical Notes\n...",
        item,
    ) == (0, 0.5)
    # Missing one section, all metadata → (0.5 + 1.0)/2 = 0.75 → fail.
    assert _score(
        "## Acceptance Criteria\n...\nstatus: draft\npriority: high",
        item,
    ) == (0, 0.75)
    # None → fail.
    assert _score("A story.", item) == (0, 0.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
