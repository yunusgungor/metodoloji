import re
from .._base_.rollout import run_batch as _run_batch

_UNCERTAINTY_RE = re.compile(
    r"(?:i don't know|i dont know|not sure|unsure|unknown|"
    r"not certain|not certain|cannot say|cant say|probably|maybe|i guess|"
    r"i think|hesitant|undecided)"
)

# Root extraction: the model names the anchor explicitly. Look for the
# literal anchor token first; fall back to "plugin" for metodoloji-root.
_ROOT_RE = {
    "project-root": re.compile(r"\{?\s*project[\s-]*root\s*\}?", re.IGNORECASE),
    "metodoloji-root": re.compile(r"\{?\s*(?:metodoloji[\s-]*root|plugin)\s*\}?", re.IGNORECASE),
}
# Direction extraction: writes/produces/creates → output; reads/consumes → read.
# The model answers with a noun ("Direction: writes") or a verb in context.
_OUTPUT_RE = re.compile(
    r"\b(?:write|writes|writting|writing|produce|produces|create|creates|"
    r"generat|output|save|saves|emit)\w*", re.IGNORECASE)
_READ_RE = re.compile(
    r"\b(?:read|reads|reading|load|loads|loading|consume|consumes|consuming|"
    r"import)\w*", re.IGNORECASE)


def _extract(text: str) -> tuple[str | None, str | None]:
    """Extract (root, direction) the answer actually claims. Returns None for
    a component the answer doesn't commit to, so scoring can demand it."""
    lower = text.lower()
    root = None
    if _ROOT_RE["project-root"].search(lower):
        root = "project-root"
    elif _ROOT_RE["metodoloji-root"].search(lower):
        root = "metodoloji-root"
    out_hit = _OUTPUT_RE.search(lower)
    read_hit = _READ_RE.search(lower)
    direction = None
    if out_hit and read_hit:
        # Both verbs present — pick the one the answer frames as the action.
        # "write ... read" in the same sentence is usually a rejection of the
        # other direction; default to output (writing is the riskier claim).
        direction = "output" if out_hit.start() <= read_hit.start() else "read"
    elif out_hit:
        direction = "output"
    elif read_hit:
        direction = "read"
    return root, direction


def _score(output_text, item):
    lower = output_text.lower()
    if _UNCERTAINTY_RE.search(lower):
        return 0, 0.0
    exp_root = item["expected_root"].lower()
    exp_dir = item["expected_direction"].lower()
    root, direction = _extract(output_text)
    if root is None or direction is None:
        return 0, 0.0  # answer doesn't commit to both axes — fail
    checks = [
        root == exp_root,
        direction == exp_dir,
    ]
    found = sum(checks)
    soft = found / len(checks)
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
    P = {"expected_root": "project-root", "expected_direction": "output"}
    M = {"expected_root": "metodoloji-root", "expected_direction": "read"}
    # Correct answers — each names the root and direction explicitly.
    assert _score("Root anchor: {project-root}. Direction: writes — creates the record.",
                  P) == (1, 1.0)
    assert _score("Root anchor: {project-root}. Direction: reads — consumes the manifesto.",
                  {"expected_root": "project-root", "expected_direction": "read"}) == (1, 1.0)
    assert _score("Root anchor: {metodoloji-root}. Direction: reads the plugin config.",
                  M) == (1, 1.0)
    # Plugin write rejected, correct answer is project-root output.
    assert _score("Writing to the plugin is wrong; the record is created under project-root.",
                  P) == (1, 1.0)
    # Wrong root must fail even if keywords overlap (old scorer passed these).
    # Direction matches (output) but root is wrong → hard 0, soft 0.5.
    assert _score("This writes to the plugin, NOT the project.", P) == (0, 0.5)
    # Both axes wrong → hard 0, soft 0.0.
    assert _score("I will not create anything in project root; I read the plugin config.",
                  {"expected_root": "metodoloji-root", "expected_direction": "read"}) == (0, 0.0)
    # Wrong direction must fail.
    assert _score("Do NOT write the config; just read it from the project.",
                  {"expected_root": "project-root", "expected_direction": "read"}) == (0, 0.0)
    # Refusal / no commitment.
    assert _score("Sorry, I don't know.", P) == (0, 0.0)
    assert _score("The anchor is resolve and the operation writes.", P) == (0, 0.0)
    # Minimal explicit answers still pass.
    assert _score("project-root output", P) == (1, 1.0)
    assert _score("metodoloji-root read", M) == (1, 1.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
