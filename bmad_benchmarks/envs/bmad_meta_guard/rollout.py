import re

from .._base_.rollout import run_batch as _run_batch

# The prompt tells the model to "State your decision first" as DENY/ALLOW, so
# trust an explicit decision token before falling back to keyword scanning.
# A negated keyword ("do NOT deny", "should not allow") must not flip a word
# into its opposite — lesson from bmad-meta-root (explicit declaration wins;
# see docs/TRAINING-LESSONS.md #6).
_DECISION_RE = re.compile(
    r"\*{0,2}\s*(?:decision|verdict|answer|result|conclusion)\s*[:\-]?\s*"
    r"\*{0,2}\s*`?\s*\{?\s*(DENY|ALLOW|BLOCK|PERMIT|GRANT)\b",
    re.IGNORECASE,
)


def _extract_decision(lower: str) -> str | None:
    """Return the decision the answer actually claims: 'DENY' or 'ALLOW'."""
    # Explicit declaration wins (matches bmad-meta-root scorer design).
    m = _DECISION_RE.search(lower)
    if m:
        return m.group(1).upper()
    # Explicit first-token "DENY:" / "ALLOW:" / bare "DENY" leading the reply.
    m = re.match(r"\s*\*?\s*`?\s*(DENY|ALLOW)\b", lower, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: keyword scan with negation handled. A negated verb means the
    # opposite: "not deny" → ALLOW, "not allow" → DENY. A verb bound inside a
    # negation marker is not a positive claim.
    neg_deny = re.search(
        r"\b(?:not|never|don't|dont|do\s+not|should\s+not|shouldn't|won't|"
        r"can't|cannot)\s+(?:\w+\s+){0,3}"
        r"(?:deny|denies|denying|denied|block|blocks|blocked|blocking)\b",
        lower,
    )
    neg_allow = re.search(
        r"\b(?:not|never|don't|dont|do\s+not|should\s+not|shouldn't|won't|"
        r"can't|cannot)\s+(?:\w+\s+){0,3}"
        r"(?:allow|allows|allowing|allowed|permit|permits|permitted|grant|grants|granted)\b",
        lower,
    )
    if neg_deny and not neg_allow:
        return "ALLOW"
    if neg_allow and not neg_deny:
        return "DENY"
    if neg_deny and neg_allow:
        return None
    # "nothing is blocked" / "no blockers" / "not blocked" is NOT a deny
    # signal — it means the call is fine. A deny verb is positive only when
    # not preceded by a negation in its clause.
    _DENY_VERB_RE = re.compile(
        r"\b(?:deny|denies|denying|denied|block|blocks|blocked|blocking)\b",
        re.IGNORECASE,
    )
    denied = False
    for m in _DENY_VERB_RE.finditer(lower):
        pre = lower[max(0, m.start() - 25):m.start()]
        if re.search(r"(nothing|no\b|not|never)\b\s*[^.;!?]*$", pre):
            continue  # "nothing is blocked" — negated deny, skip
        denied = True
        break
    allowed = any(w in lower for w in
                  ("allow", "allows", "allowing", "allowed", "permit", "permits",
                   "permitted", "grant", "grants", "granted"))
    if denied and allowed:
        return None
    if denied:
        return "DENY"
    if allowed:
        return "ALLOW"
    return None


def _score(output_text, item):
    expected = item["expected_decision"].upper()
    decided = _extract_decision(output_text.lower())
    correct = decided == expected
    return (1 if correct else 0), (1.0 if correct else 0.0)


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You decide whether the guard hook should DENY or ALLOW a tool call. "
        f"State the decision explicitly as 'DENY' or 'ALLOW' and justify it."
    )
    user = (
        f"## Scenario\n\n{item['scenario']}\n\n"
        f"Should the guard hook DENY or ALLOW? State your decision first."
    )
    return system, user


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    return _run_batch(items, skill_content, out_dir, _score, _prompt,
                      max_completion_tokens=max_completion_tokens,
                      workers=workers, default_task_type="meta-guard")


def _selfcheck():
    deny = {"expected_decision": "DENY"}
    allow = {"expected_decision": "ALLOW"}
    # Explicit declaration wins.
    assert _score("Decision: DENY — the story is in REJECTED state.", deny) == (1, 1.0)
    assert _score("**Decision:** ALLOW — no blockers.", allow) == (1, 1.0)
    assert _score("ALLOW", allow) == (1, 1.0)
    # Keyword fallback.
    assert _score("This must be denied; the experiment is rejected.", deny) == (1, 1.0)
    assert _score("Grant the call; nothing is blocked.", allow) == (1, 1.0)
    # Negation must not flip: "not deny" means allow.
    assert _score("I would NOT deny this call.", allow) == (1, 1.0)
    assert _score("Do not allow it.", deny) == (1, 1.0)
    # No commitment → fail.
    assert _score("The guard hook checks the status.", deny) == (0, 0.0)
    assert _score("Sorry, I don't know.", deny) == (0, 0.0)
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
