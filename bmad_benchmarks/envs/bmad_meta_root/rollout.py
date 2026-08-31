import re
from .._base_.rollout import run_batch as _run_batch

_UNCERTAINTY_RE = re.compile(
    r"(?:i don't know|i dont know|not sure|unsure|unknown|"
    r"not certain|not certain|cannot say|cant say|probably|maybe|i guess|"
    r"i think|hesitant|undecided)"
)


def _score(output_text, item):
    lower = output_text.lower()
    if _UNCERTAINTY_RE.search(lower):
        return 0, 0.0
    exp_root = item["expected_root"].lower()
    exp_dir = item["expected_direction"].lower()
    checks = []
    if exp_root == "project-root":
        checks.append("project" in lower)
    else:
        checks.append("metodoloji" in lower or "plugin" in lower)
    if exp_dir == "output":
        checks.append("output" in lower or "write" in lower or "create" in lower or "generate" in lower)
    else:
        checks.append("read" in lower or "load" in lower or "consume" in lower)
    found = sum(checks)
    soft = found / len(checks) if checks else 1.0
    hard = 1 if soft >= 1.0 else 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You classify a methodology path operation. Use the rules above to "
        f"decide which anchor the operation resolves against, and whether the "
        f"operation writes or reads. Explain your reasoning in your own words "
        f"in at least one full sentence — do not merely restate the categories."
    )
    user = (
        f"## Operation\n\n{item['operation']}\n\n"
        f"State the root anchor and the direction (does the operation produce "
        f"or consume?). Justify your answer briefly."
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-root")


def _selfcheck():
    assert _score("This operation writes a story under project-root — produces output.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("I read the manifesto from the docs/bmad copy in project-root — a read operation.",
                  {"expected_root": "project-root", "expected_direction": "read"}) == (1, 1.0)
    assert _score("This reads the config in the plugin installation, from metodoloji-root.",
                  {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    assert _score("Writing to the plugin is wrong; the record is created under project-root — output.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("The record is written to project-root, not the plugin — an output operation.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("Copies the template from metodoloji-root; a reading operation, produces no output.",
                  {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    assert _score("The anchor is resolve and the operation writes.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (0, 0.5)
    assert _score("Sorry, I don't know.",
                  {"expected_root": "project-root", "expected_direction": "output"}) == (0, 0.0)
    hard, soft = _score("This operation produces output, but the record is in metodoloji-root.",
                        {"expected_root": "project-root", "expected_direction": "output"})
    assert hard == 0 and soft == 0.5
    assert _score("project-root output", {"expected_root": "project-root", "expected_direction": "output"}) == (1, 1.0)
    assert _score("metodoloji-root read", {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (1, 1.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
