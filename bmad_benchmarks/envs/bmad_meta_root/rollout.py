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
# "generat" is deliberately NOT an output verb — "generate" describes the
# methodology producing the prompt/task, not a write to a root.
_OUTPUT_RE = re.compile(
    r"\b(?:write|writes|writting|writing|produce|produces|create|creates|"
    r"creat(?:ing|ed)?|output|save|saves|saving|emit\w*)\w*", re.IGNORECASE)
_READ_RE = re.compile(
    r"\b(?:read|reads|reading|load|loads|loading|consume|consumes|consuming|"
    r"import|copy|copies|copied|copying)\w*", re.IGNORECASE)


# Root-hefted rejection markers: the model says "not THAT root" — "rather
# than {project-root}", "instead of the plugin", "not the project". The next
# anchor after one of these (within a small gap) is the excluded root.
_ROOT_REJECT_MARKER_RE = re.compile(
    r"\b(?:rather\s+than|instead\s+of|not\s+the|not\s+into|not\s+in\s+the|"
    r"not\s+to|not\s+at|never\b|wrong\s+(?:to|at|in|for|under)|isn't\s+the|"
    r"shouldn't\s+be)\b",
    re.IGNORECASE,
)
_ROOT_REJECT_GAP = 30

# Verb-hefted rejection markers: "do NOT write", "not create", "never read".
# These reject the verb (direction), NOT a following root.
_VERB_REJECT_MARKER_RE = re.compile(
    r"\b(?:don't|dont|do\s+not|will\s+not|won't|never|not|isn't|shouldn't|"
    r"mustn't)\s+(?:write|writes|writing|create|creates|creating|produce|"
    r"produces|produces?|read|reads|reading|use|uses|using|sav\w*)\w*",
    re.IGNORECASE,
)


def _extract(text: str) -> tuple[str | None, str | None]:
    """Extract (root, direction) the answer actually claims. Returns None for
    a component the answer doesn't commit to, so scoring can demand it."""
    lower = text.lower()

    # The prompt tells the model to "State the root anchor", so a well-formed
    # answer names it up front: "Root anchor: `{project-root}`", "**Anchor:**
    # `{...}`", "The operation resolves against `{metodoloji-root}`". Trust
    # that explicit declaration over anchor tokens buried in the reasoning
    # (which are often rejected/excluded).
    root = None

    # A trap answer may name the (invalid) target first, then the correct one:
    # "resolves to {metodoloji-root} ... but it's invalid; the correct
    # destination would be under {project-root}". The *correct* root wins.
    correct_m = re.search(
        r"\b(?:correct|right|valid)\s+(?:root|anchor|destination|answer|place|location)"
        r".{0,60}?(project[\s-]*root|metodoloji[\s-]*root)",
        lower,
    )
    if correct_m:
        root = "project-root" if correct_m.group(1).startswith("project") else "metodoloji-root"

    if root is None:
        anchor_m = re.search(
            r"\b(?:root\s*anchor|anchor|resolves?\s+against|resolves?\s+to)\s*"
            r"[:\-]?\s*\*{0,2}\s*`?\s*\{?\s*"
            r"(project[\s-]*root|metodoloji[\s-]*root)\}?`?",
            lower,
        )
        if anchor_m:
            root = "project-root" if anchor_m.group(1).startswith("project") else "metodoloji-root"

    if root is None:
        # Fallback: the answer may name the anchor without the "Root anchor:"
        # label (e.g. "metodoloji-root read", "project-root output"). Then
        # honor rejection markers.
        rejected = set()
        for m in _ROOT_REJECT_MARKER_RE.finditer(lower):
            window = lower[m.end():m.end() + _ROOT_REJECT_GAP]
            best = None
            for name, pat in _ROOT_RE.items():
                hit = pat.search(window)
                if hit and (best is None or hit.start() < best[0]):
                    best = (hit.start(), name)
            if best:
                abs_pos = m.end() + best[0]
                rejected.add(abs_pos)

        def _root_for(anchor_name: str) -> str | None:
            pat = _ROOT_RE[anchor_name]
            for m in pat.finditer(lower):
                if m.start() in rejected:
                    continue
                return anchor_name
            return None

        root = _root_for("project-root") or _root_for("metodoloji-root")

    # Same rejection rule for direction verbs: "do NOT write", "not create",
    # "never read" — a verb bound to a rejection marker is not the claim.
    # A verb AFTER the marker ("... then I read the config") is an independent
    # positive claim and stays.
    _verb_rejected = set()
    for m in _VERB_REJECT_MARKER_RE.finditer(lower):
        for vpat in (_OUTPUT_RE, _READ_RE):
            for vh in vpat.finditer(lower, m.start(), m.end()):
                _verb_rejected.add(vh.start())

    # The prompt tells the model to state the direction ("writes or reads"),
    # so a well-formed answer declares it up front: "Direction: reads",
    # "**Direction:** writes". Trust that label over verbs buried in the
    # reasoning.
    direction = None
    dir_m = re.search(
        r"\bdirection\s*[:\-]?\s*\*{0,2}\s*\b(writes?|reads?|output|input)\b",
        lower,
    )
    if dir_m:
        d = dir_m.group(1).lower()
        direction = "output" if d.startswith(("write", "output")) else "read"

    if direction is None:
        def _first_verb(pat) -> re.Match | None:
            for m in pat.finditer(lower):
                if m.start() in _verb_rejected:
                    continue
                return m
            return None

        out_hit = _first_verb(_OUTPUT_RE)
        read_hit = _first_verb(_READ_RE)
        if out_hit and read_hit:
            # Both verbs present — pick the one the answer frames as the
            # action. "write ... read" in the same sentence is usually a
            # rejection of the other direction; default to output (writing is
            # the riskier claim).
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
    # "Do NOT write the config; just read it from the project-root." — the
    # verb negation kills the write; the read stays → project-root/read.
    assert _score("Do NOT write the config; just read it from the project-root.",
                  {"expected_root": "project-root", "expected_direction": "read"}) == (1, 1.0)
    # Refusal / no commitment.
    assert _score("Sorry, I don't know.", P) == (0, 0.0)
    assert _score("The anchor is resolve and the operation writes.", P) == (0, 0.0)
    # A model that says "generate the record" but never claims a write to a
    # root must NOT be credited with output direction.
    assert _score("The methodology generates the record; the anchor is project-root.",
                  P) == (0, 0.0)
    # Ambiguous double-sided answer — no root anchor named, no committed
    # direction → fail.
    assert _score("I could read from the plugin or write to the project; both "
                  "seem reasonable.", P) == (0, 0.0)
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
