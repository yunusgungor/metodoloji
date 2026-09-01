import re

from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    lower = output_text.lower()
    # The record token (IR/PR/QR/SP...) is 2-3 letters and also appears inside
    # file paths ("docs/development/IR-003.md"). Match it as a word, not a
    # substring, so naming the wrong record fails even when the path mentions
    # the expected record's prefix (bmad-meta-root lesson: score what the
    # answer *claims*, not what the path text contains).
    record = re.escape(item["expected_record"].lower())
    checks = [
        # Word token NOT followed by a word char or "-", so "IR" inside a file
        # prefix "IR-003.md" is not counted as naming the record IR.
        re.search(rf"\b{record}(?![\w-])", lower) is not None,
        item["expected_path"].lower() in lower,
        any(v in lower for v in
            [s.strip().lower() for s in item["expected_status"].split("|") if s.strip()]),
    ]
    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 0.9 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You identify the methodology record for a stage, its exact file path, "
        f"and its allowed status values."
    )
    user = (
        f"## Stage\n\n{item['stage']}\n\n"
        f"Which methodology record is required at this stage, at what path, "
        f"and what are its allowed status values?"
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-chain")


def _selfcheck():
    item = {
        "expected_record": "IR",
        "expected_path": "docs/development/IR-",
        "expected_status": "READY | INCOMPLETE",
    }
    # All three fields present → pass.
    assert _score("The record is IR at docs/development/IR-007.md, status READY.", item) == (1, 1.0)
    assert _score("IR — docs/development/IR-002.md — INCOMPLETE.", item) == (1, 1.0)
    # Status variants (any of the alternatives counts).
    assert _score("IR at docs/development/IR-001.md, status INCOMPLETE.", item) == (1, 1.0)
    # Missing path → hard 0, soft 0.667 (2/3).
    assert _score("The record is IR, status READY.", item) == (0, 0.6666666666666666)
    # Wrong record → fail.
    assert _score("The record is PR at docs/development/IR-003.md, status READY.", item) == (0, 0.6666666666666666)
    # Hard threshold is 0.9: 2/3 = 0.667 → 0.
    assert _score("IR with status READY.", item) == (0, 0.6666666666666666)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
