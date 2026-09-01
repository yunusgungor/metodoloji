from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    output_lower = output_text.lower()
    expected = item["expected_invariants"]
    found = sum(1 for inv in expected if inv.lower() in output_lower)
    soft = found / len(expected) if expected else 1.0
    hard = 1 if soft >= 0.8 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a system architect. Produce an architecture spine "
        f"with clear invariants."
    )
    user = f"## Input\n\n{item['input_text']}"
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="architecture")


def _selfcheck():
    item = {"expected_invariants": ["separation of concerns", "immutable config", "event-driven"]}
    # All invariants present → pass.
    assert _score(
        "The spine enforces separation of concerns, immutable config, and event-driven flow.",
        item,
    ) == (1, 1.0)
    # 2/3 → soft 0.667 < 0.8 → hard 0.
    assert _score(
        "The spine enforces separation of concerns and event-driven flow.",
        item,
    ) == (0, 0.6666666666666666)
    # None → fail.
    assert _score("The spine focuses on caching and retries.", item) == (0, 0.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
