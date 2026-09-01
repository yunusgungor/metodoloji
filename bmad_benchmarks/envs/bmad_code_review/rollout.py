from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    expected = item.get("expected_findings", [])
    if not expected:
        return 1, 1.0
    output_lower = output_text.lower()
    found = 0
    for exp in expected:
        title_kw = exp.get("title_keyword", "").lower()
        cat = exp.get("category", "").lower()
        if title_kw and title_kw in output_lower:
            found += 1
        elif cat and cat in output_lower:
            found += 1
    hard = 1 if found == len(expected) else 0
    soft = found / len(expected) if expected else 1.0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are an elite code reviewer. Review the following diff "
        f"and produce structured findings."
    )
    user = f"## Diff\n\n{item['diff_text']}"
    if item.get("spec_text"):
        user += f"\n\n## Spec\n\n{item['spec_text']}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="code-review")


def _selfcheck():
    item = {"expected_findings": [
        {"title_keyword": "SQL injection", "category": "security"},
        {"title_keyword": "race condition", "category": "concurrency"},
    ]}
    # Both findings (via title keyword) → pass.
    assert _score(
        "Finding 1: SQL injection in the query builder. Finding 2: race condition on the counter.",
        item,
    ) == (1, 1.0)
    # One found → 1/2 → hard 0.
    assert _score("The diff has a SQL injection.", item) == (0, 0.5)
    # Category fallback counts too.
    assert _score(
        "A security issue and a concurrency issue were found.",
        item,
    ) == (1, 1.0)
    # None → fail.
    assert _score("Looks fine.", item) == (0, 0.0)
    # No expected findings → trivially pass.
    assert _score("anything", {"expected_findings": []}) == (1, 1.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
