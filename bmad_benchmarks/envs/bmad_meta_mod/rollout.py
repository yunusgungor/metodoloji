import re
from .._base_.rollout import run_batch as _run_batch


def _score(output_text, item):
    lower = output_text.lower()
    modes_found = set()
    for m in re.findall(r"mod\s*([abcd])", lower):
        modes_found.add(m.upper())
    for m in re.findall(r"\b([abcd])\s*modu", lower):
        modes_found.add(m.upper())
    for letter, patterns in [("A", ("mod a", "mod-a", "moda")),
                              ("B", ("mod b", "mod-b", "modb")),
                              ("C", ("mod c", "mod-c", "modc")),
                              ("D", ("mod d", "mod-d", "modd"))]:
        if any(p in lower for p in patterns):
            modes_found.add(letter)
    expected = item["expected_mode"].upper()
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
