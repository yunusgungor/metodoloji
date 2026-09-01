import re
from .._base_.rollout import run_batch as _run_batch


def _extract_modes(lower: str) -> set[str]:
    """Collect the mode letters the answer explicitly claims.

    Handles the formats the model actually emits: 'Mod D', 'Mod-D', 'Mode D',
    'MOD D'. A bare letter counts only when framed as the mode ("it is D",
    "mode: D", a leading/trailing "D"), never as prose ("touches a and b").
    """
    modes = set()
    for m in re.finditer(
        r"\bmod(?:e)?\s*[-:]\s*\*{0,2}\s*`?\s*\{?\s*([abcd])\b", lower, re.IGNORECASE,
    ):
        modes.add(m.group(1).upper())
    for m in re.finditer(r"\bmod(?:e)?[\s-]?([abcd])\b(?!\w)", lower, re.IGNORECASE):
        modes.add(m.group(1).upper())
    # A bare letter that stands alone as the answer: "D", "it is D", "D.",
    # "the mode is D". Not inside prose like "a and b".
    for m in re.finditer(
        r"(?:^|it\s+is|mode\s*[:\-]|the\s+mode\s+is|answer\s*[:\-])\s*"
        r"`?\*?\(?([abcd])\b", lower,
    ):
        modes.add(m.group(1).upper())
    return modes


def _score(output_text, item):
    expected = item["expected_mode"].upper()
    modes_found = _extract_modes(output_text.lower())
    correct = expected in modes_found
    return (1 if correct else 0), (1.0 if correct else 0.0)


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You classify development tasks into methodology modes. "
        f"State the mode explicitly as 'Mod X'."
    )
    user = (
        f"## Task\n\n{item['task_desc']}\n\n"
        f"Which methodology mode (Mod A, B, C, or D) does this task belong to, "
        f"and what gate/protection does it carry?"
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-mod")


def _selfcheck():
    def m(mode):
        return {"expected_mode": mode}
    # Explicit mode formats the model emits.
    assert _score("Mod D — documentation task.", m("D")) == (1, 1.0)
    assert _score("**Mode:** B", m("B")) == (1, 1.0)
    assert _score("mode: A", m("A")) == (1, 1.0)
    assert _score("it is D", m("D")) == (1, 1.0)
    assert _score("C", m("C")) == (1, 1.0)
    # Wrong mode fails.
    assert _score("Mod A — the task is documentation.", m("D")) == (0, 0.0)
    # A bare letter in prose, not framed as a mode, must NOT count.
    assert _score("The task touches a and b but is primarily delivery.", m("A")) == (0, 0.0)
    assert _score("The task touches a and b but is primarily delivery.", m("B")) == (0, 0.0)
    # No commitment.
    assert _score("I am unsure which mode this is.", m("D")) == (0, 0.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
