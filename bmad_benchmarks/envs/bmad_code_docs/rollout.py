import re
from .._base_.rollout import run_batch as _run_batch

_REQUIRED_FRONTMATTER = {"id", "type", "title", "date", "tags"}

# Section headings come from the REAL templates at docs/code-docs/<cat>/_template.md.
# NOTE: headings are English ("## Decision", NOT "## Karar") — matched loosely so
# an extra "## Related Records" / "## Change History" block does not break a doc.
_SECTION_PATTERNS = {
    "P": {
        "Pattern": re.compile(r"##\s*Pattern", re.IGNORECASE),
        "Usage Scenario": re.compile(r"##\s*Usage\s+Scenario", re.IGNORECASE),
        "Example": re.compile(r"##\s*Example", re.IGNORECASE),
        "Advantages": re.compile(r"##\s*Advantages", re.IGNORECASE),
        "Disadvantages": re.compile(r"##\s*Disadvantages", re.IGNORECASE),
    },
    "T": {
        "Error": re.compile(r"##\s*Error", re.IGNORECASE),
        "Cause": re.compile(r"##\s*Cause", re.IGNORECASE),
        "Solution": re.compile(r"##\s*Solution", re.IGNORECASE),
        "Prevention": re.compile(r"##\s*Prevention", re.IGNORECASE),
    },
    "D": {
        "Decision": re.compile(r"##\s*Decision", re.IGNORECASE),
        "Rationale": re.compile(r"##\s*Rationale", re.IGNORECASE),
        "Results": re.compile(r"##\s*Results", re.IGNORECASE),
    },
    "L": {
        "Learned": re.compile(r"##\s*Learned", re.IGNORECASE),
        "Context": re.compile(r"##\s*Context", re.IGNORECASE),
        "Evidence": re.compile(r"##\s*Evidence", re.IGNORECASE),
        "Application": re.compile(r"##\s*Application", re.IGNORECASE),
    },
    "A": {
        "API": re.compile(r"##\s*API", re.IGNORECASE),
        "Signature": re.compile(r"##\s*Signature", re.IGNORECASE),
        "Usage": re.compile(r"##\s*Usage", re.IGNORECASE),
        "Notes": re.compile(r"##\s*Notes", re.IGNORECASE),
    },
    "X": {
        "Description": re.compile(r"##\s*Description", re.IGNORECASE),
        "Context": re.compile(r"##\s*Context", re.IGNORECASE),
        "Next Steps": re.compile(r"##\s*Next\s+Steps", re.IGNORECASE),
    },
}

# Maps the short code -> full type name (as in the real frontmatter `type:` value).
_DOC_TYPE_NAMES = {"P": "pattern", "T": "troubleshooting", "D": "decision",
                   "L": "learning", "A": "api", "X": "pending"}
# Reverse map: accept whatever the model emits for `type:` — short code, full
# name, or the short code in parens. Keys are lowercased (the matcher lowercases
# the extracted value before lookup).
_DOC_TYPE_ACCEPT = {
    **{code.lower(): code for code in _DOC_TYPE_NAMES},
    **{name.lower(): code for code, name in _DOC_TYPE_NAMES.items()},
    **{f"({code.lower()})": code for code in _DOC_TYPE_NAMES},
}


def _extract_frontmatter_block(text):
    """Return the YAML frontmatter block body, wherever it sits in the text
    (model often wraps the doc in ```markdown ... ``` fences, so the opener
    may not be at line start)."""
    m = re.search(r"^\s*---\s*\n(.*?)\n---", text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    return m.group(1)


def _check_frontmatter(text):
    fm = _extract_frontmatter_block(text)
    if not fm:
        return 0, len(_REQUIRED_FRONTMATTER)
    found = sum(1 for f in _REQUIRED_FRONTMATTER if f in fm)
    return found, len(_REQUIRED_FRONTMATTER)


def _check_sections(text, doc_type):
    patterns = _SECTION_PATTERNS.get(doc_type, {})
    if not patterns:
        return 0, 0
    found = sum(1 for p in patterns.values() if p.search(text))
    return found, len(patterns)


def _check_tags(text, expected_tags):
    if not expected_tags:
        return 0, 0
    fm = _extract_frontmatter_block(text)
    if not fm:
        return 0, len(expected_tags)
    fm_text = fm.lower()
    found = sum(1 for t in expected_tags if t.lower() in fm_text)
    return found, len(expected_tags)


def _check_context_loading(text, context):
    text_lower = text.lower()
    has_exp_ref = bool(re.search(r"E-\d+", text))
    context_phrases = ["previously", "existing", "prior", "current",
                       "already known", "established", "before", "existing pattern"]
    has_ctx = any(p in text_lower for p in context_phrases)
    has_doc_ref = bool(re.search(
        r"(decision|pattern|learning|troubleshooting|pending)\s+(D|P|L|T|X)-\d+", text_lower))
    return has_exp_ref or has_ctx or has_doc_ref


def _detect_type_code(text):
    """Return the expected-type short code the model chose, or None.

    Accepts `type: P`, `type: pattern`, `type: (P)` anywhere in the text
    (frontmatter or inline) — matched on the frontmatter block first, then the
    whole text. Lowercased and stripped of quotes/brackets before lookup.
    """
    fm = _extract_frontmatter_block(text)
    body = fm if fm else text
    m = re.search(r"type\s*:\s*([^\s,}]+)", body, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).strip().strip('"\'[](){}').lower()
    if raw.endswith(")"):
        raw = raw[:-1]
    return _DOC_TYPE_ACCEPT.get(raw)


def _score(output_text, item):
    type_code = _detect_type_code(output_text)
    type_correct = type_code == item["expected_type"]
    fm_found, fm_total = _check_frontmatter(output_text)
    fm_valid = fm_found == fm_total
    sec_found, sec_total = _check_sections(output_text, item["expected_type"])
    sec_valid = sec_found == sec_total
    hard = 1 if (type_correct and fm_valid and sec_valid) else 0
    tag_found, tag_total = _check_tags(output_text, item.get("expected_tags", []))
    total_elements = fm_total + sec_total + tag_total
    found_elements = fm_found + sec_found + tag_found
    soft = found_elements / total_elements if total_elements > 0 else 0.0
    if item.get("context") and _check_context_loading(output_text, item["context"]):
        soft = min(1.0, soft + 0.1)
    return hard, soft


def _prompt(item, skill_content):
    # NOTE: the expected type/tags are NOT leaked to the model — it must infer
    # them from the scenario (otherwise the skill has nothing to learn). Only
    # the valid doc categories are given as a constraint.
    system = (
        f"{skill_content}\n\n"
        f"You are a code documentation expert. Given a scenario, decide which "
        f"type of code-doc to create (pattern, troubleshooting, decision, "
        f"learning, api, or pending) and produce the doc following the "
        f"methodology. Emit a YAML frontmatter block delimited by --- (with "
        f"id, type, title, date, tags) followed by the required ## sections. "
        f"Do not wrap the doc in a markdown code fence."
    )
    user = (
        f"## Scenario\n\n{item['scenario']}\n\n"
        f"Generate the appropriate code-doc for this scenario. Choose the "
        f"correct doc type yourself from the scenario, and include relevant "
        f"tags that describe the topic."
    )
    return system, user


def _extra_result(output_text, item):
    type_code = _detect_type_code(output_text)
    sec_found, _ = _check_sections(output_text, item["expected_type"])
    tag_found, _ = _check_tags(output_text, item.get("expected_tags", []))
    fm_valid = _check_frontmatter(output_text) == (len(_REQUIRED_FRONTMATTER), len(_REQUIRED_FRONTMATTER))
    return {
        "expected_type": item["expected_type"],
        "detected_type": type_code if type_code else "",
        "n_expected_sections": len(item.get("expected_sections", [])),
        "n_sections_found": sec_found,
        "n_expected_tags": len(item.get("expected_tags", [])),
        "n_tags_found": tag_found,
        "frontmatter_valid": fm_valid,
    }


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(
        items, skill_content, out_dir, _score, _prompt,
        max_completion_tokens=max_completion_tokens, workers=workers,
        default_task_type="code-docs", extra_result=_extra_result,
    )


def _selfcheck():
    perfect_p = (
        "---\nid: P-001\n type: pattern\n title: \"Repo\"\n date: 2026-08-30\n"
        " tags: [pattern, auth]\n---\n"
        "## Pattern\n...\n## Usage Scenario\n...\n## Example\n...\n"
        "## Advantages\n...\n## Disadvantages\n...\n"
    )
    item_p = {"expected_type": "P", "expected_tags": ["pattern", "auth"],
              "expected_sections": ["## Pattern", "## Usage Scenario", "## Example"]}
    hard, soft = _score(perfect_p, item_p)
    assert hard == 1, f"perfect pattern doc should pass, got hard={hard}"
    # Model often wraps the doc in a ```markdown fence and uses the short code.
    fenced_p = "```markdown\n" + perfect_p + "\n```"
    hard2, _ = _score(fenced_p, item_p)
    assert hard2 == 1, f"fenced pattern doc should still pass, got hard={hard2}"
    short_type = perfect_p.replace("type: pattern", "type: P")
    hard3, _ = _score(short_type, item_p)
    assert hard3 == 1, f"short-code type (P) should pass, got hard={hard3}"
    wrong_type = perfect_p.replace("type: pattern", "type: api")
    assert _score(wrong_type, item_p)[0] == 0
    no_fm = perfect_p.split("---\n", 1)[-1]
    item_min = {"expected_type": "P", "expected_tags": ["pattern"],
                "expected_sections": ["## Pattern"]}
    assert _score(no_fm, item_min)[0] == 0
    no_section = perfect_p.replace("## Pattern\n", "")
    item_no_sec = {"expected_type": "P", "expected_tags": ["pattern"],
                   "expected_sections": ["## Pattern", "## Usage Scenario"]}
    assert _score(no_section, item_no_sec)[0] == 0
    # Real decision template uses "## Decision" (English), not "## Karar".
    real_d = (
        "---\nid: D-001\n type: decision\n title: \"x\"\n date: 01.09.2026\n"
        " tags: [decision]\n---\n"
        "## Decision\n...\n## Rationale\n...\n## Results\n..."
    )
    item_d = {"expected_type": "D", "expected_tags": ["decision"],
              "expected_sections": ["## Decision", "## Rationale", "## Results"]}
    hard_d, _ = _score(real_d, item_d)
    assert hard_d == 1, f"real English decision doc should pass, got hard={hard_d}"
    for code in ("P", "T", "D", "L", "A", "X"):
        assert code in _SECTION_PATTERNS, f"missing section table for {code}"
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
