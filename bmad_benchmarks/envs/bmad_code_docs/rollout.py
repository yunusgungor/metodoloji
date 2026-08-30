"""Rollout + scoring for bmad-code-docs benchmark.

Scoring:
  hard: 1 if output contains correct doc type AND all expected sections AND
        valid frontmatter with required fields, else 0
  soft: float [0,1] = fraction of expected elements found in output
"""

import json
import pathlib
import re
import sys

from skillopt.model import chat_target

# Required frontmatter fields
_REQUIRED_FRONTMATTER = {"id", "type", "title", "date", "tags"}

# Section patterns by doc type
_SECTION_PATTERNS = {
    "P": {  # pattern
        "Kalıp": re.compile(r"##\s*Kalıp", re.IGNORECASE),
        "Kullanım Senaryosu": re.compile(r"##\s*Kullanım\s+Senaryosu", re.IGNORECASE),
        "Örnek": re.compile(r"##\s*Örnek", re.IGNORECASE),
        "Avantajlar": re.compile(r"##\s*Avantajlar", re.IGNORECASE),
        "Dezavantajlar": re.compile(r"##\s*Dezavantajlar", re.IGNORECASE),
    },
    "T": {  # troubleshooting
        "Hata": re.compile(r"##\s*Hata", re.IGNORECASE),
        "Neden": re.compile(r"##\s*Neden", re.IGNORECASE),
        "Çözüm": re.compile(r"##\s*Çözüm", re.IGNORECASE),
        "Önleme": re.compile(r"##\s*Önleme", re.IGNORECASE),
    },
    "D": {  # decision
        "Karar": re.compile(r"##\s*Karar", re.IGNORECASE),
        "Gerekçe": re.compile(r"##\s*Gerekçe", re.IGNORECASE),
        "Sonuçlar": re.compile(r"##\s*Sonuçlar", re.IGNORECASE),
    },
    "L": {  # learning
        "Öğrenilen": re.compile(r"##\s*Öğrenilen", re.IGNORECASE),
        "Bağlam": re.compile(r"##\s*Bağlam", re.IGNORECASE),
        "Kanıt": re.compile(r"##\s*Kanıt", re.IGNORECASE),
        "Uygulama": re.compile(r"##\s*Uygulama", re.IGNORECASE),
    },
    "A": {  # api
        "API": re.compile(r"##\s*API", re.IGNORECASE),
        "İmza": re.compile(r"##\s*İmza", re.IGNORECASE),
        "Kullanım": re.compile(r"##\s*Kullanım", re.IGNORECASE),
        "Dikkat Edilecekler": re.compile(r"##\s*Dikkat\s+Edilecekler", re.IGNORECASE),
    },
    "X": {  # pending
        "Açıklama": re.compile(r"##\s*Açıklama", re.IGNORECASE),
        "Bağlam": re.compile(r"##\s*Bağlam", re.IGNORECASE),
        "Sonraki Adımlar": re.compile(r"##\s*Sonraki\s+Adımlar", re.IGNORECASE),
    },
}

_DOC_TYPE_NAMES = {
    "P": "pattern",
    "T": "troubleshooting",
    "D": "decision",
    "L": "learning",
    "A": "api",
    "X": "pending",
}


def _check_frontmatter(output_text: str) -> tuple[int, int]:
    """Check frontmatter for required fields. Returns (found, total)."""
    fm_match = re.match(r"^---\n(.+?)\n---", output_text, re.DOTALL)
    if not fm_match:
        return 0, len(_REQUIRED_FRONTMATTER)
    fm_text = fm_match.group(1)
    found = sum(1 for field in _REQUIRED_FRONTMATTER if field in fm_text)
    return found, len(_REQUIRED_FRONTMATTER)


def _check_sections(output_text: str, doc_type: str) -> tuple[int, int]:
    """Check for expected sections. Returns (found, total)."""
    patterns = _SECTION_PATTERNS.get(doc_type, {})
    if not patterns:
        return 0, 0
    found = sum(1 for pat in patterns.values() if pat.search(output_text))
    return found, len(patterns)


def _check_tags(output_text: str, expected_tags: list[str]) -> tuple[int, int]:
    """Check if expected tags are present. Returns (found, total)."""
    if not expected_tags:
        return 0, 0
    fm_match = re.match(r"^---\n(.+?)\n---", output_text, re.DOTALL)
    if not fm_match:
        return 0, len(expected_tags)
    fm_text = fm_match.group(1)
    found = sum(1 for tag in expected_tags if tag.lower() in fm_text.lower())
    return found, len(expected_tags)


def _check_context_loading(output_text: str, context: dict) -> bool:
    """Check if LLM correctly referenced existing docs or used context.

    Returns True if:
    - Output references related experiments (E-NNN)
    - Output mentions previous decisions/patterns
    - Output acknowledges existing work (not duplicating)
    """
    output_lower = output_text.lower()

    # Check for experiment references
    has_exp_ref = bool(re.search(r"E-\d+", output_text))

    # Check for context-aware phrases
    context_phrases = [
        "daha önce", "mevcut", "önceki", "var olan",
        "önceden", "bilinen", "daha önceki", "mevcut kalıp",
    ]
    has_context_ref = any(phrase in output_lower for phrase in context_phrases)

    # Check for cross-references to docs
    has_doc_ref = bool(re.search(r"(decision|pattern|learning|troubleshooting|pending)\s+(D|P|L|T|X)-\d+", output_lower))

    return has_exp_ref or has_context_ref or has_doc_ref


def _score(output_text: str, expected_type: str, expected_tags: list[str],
           expected_sections: list[str], context: dict | None = None) -> tuple[int, float]:
    """Score code-doc output against expectations."""
    # Hard check 1: correct doc type in frontmatter
    type_match = re.search(r"type:\s*(\w+)", output_text)
    type_correct = type_match and type_match.group(1) == _DOC_TYPE_NAMES.get(expected_type, "")

    # Hard check 2: valid frontmatter
    fm_found, fm_total = _check_frontmatter(output_text)
    fm_valid = fm_found == fm_total

    # Hard check 3: all expected sections present
    sec_found, sec_total = _check_sections(output_text, expected_type)
    sec_valid = sec_found == sec_total

    # Hard = all checks pass
    hard = 1 if (type_correct and fm_valid and sec_valid) else 0

    # Soft = fraction of all expected elements
    tag_found, tag_total = _check_tags(output_text, expected_tags)
    total_elements = fm_total + sec_total + tag_total
    found_elements = fm_found + sec_found + tag_found
    soft = found_elements / total_elements if total_elements > 0 else 0.0

    # Bonus: context loading check (0.1 bonus if correctly referenced existing docs)
    if context and _check_context_loading(output_text, context):
        soft = min(1.0, soft + 0.1)

    return hard, soft


def _rollout_one(item: dict, skill_content: str, out_dir: pathlib.Path,
                 max_completion_tokens: int = 4096) -> dict:
    doc_type_name = _DOC_TYPE_NAMES.get(item["expected_type"], "pattern")

    system_prompt = (
        f"{skill_content}\n\n"
        f"You are a code documentation expert. Generate a structured code-doc "
        f"following the methodology. The doc MUST be of type '{doc_type_name}' "
        f"with valid YAML frontmatter (id, type, title, date, tags) and "
        f"all required sections in Turkish."
    )
    user_prompt = (
        f"## Senaryo\n\n{item['scenario']}\n\n"
        f"Bu senaryo için uygun code-doc'u üret. "
        f"Beklenen tür: {doc_type_name} ({item['expected_type']})\n"
        f"Beklenen etiketler: {', '.join(item.get('expected_tags', []))}"
    )

    output_text, meta = chat_target(
        system=system_prompt,
        user=user_prompt,
        max_completion_tokens=max_completion_tokens,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": output_text},
    ]

    hard, soft = _score(output_text, item["expected_type"],
                        item.get("expected_tags", []),
                        item.get("expected_sections", []),
                        item.get("context"))

    pred_dir = out_dir / "predictions" / item["id"]
    pred_dir.mkdir(parents=True, exist_ok=True)
    (pred_dir / "conversation.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "task_type": item.get("task_type", "code-docs"),
        "predicted_output_length": len(output_text),
        "expected_type": item["expected_type"],
        "detected_type": (type_match.group(1) if (type_match := re.search(r"type:\s*(\w+)", output_text)) else ""),
        "n_expected_sections": len(item.get("expected_sections", [])),
        "n_sections_found": _check_sections(output_text, item["expected_type"])[0],
        "n_expected_tags": len(item.get("expected_tags", [])),
        "n_tags_found": _check_tags(output_text, item.get("expected_tags", []))[0],
        "frontmatter_valid": _check_frontmatter(output_text) == (len(_REQUIRED_FRONTMATTER), len(_REQUIRED_FRONTMATTER)),
        "target_system_prompt": system_prompt[:500],
        "target_user_prompt": user_prompt[:500],
        "n_turns": 1,
    }


def run_batch(items: list[dict], skill_content: str, out_dir,
              workers: int = 1, max_completion_tokens: int = 4096) -> list[dict]:
    """Run batch with optional parallel processing."""
    import concurrent.futures

    out_dir = pathlib.Path(out_dir)

    def _safe_rollout(item):
        try:
            return _rollout_one(item, skill_content, out_dir,
                              max_completion_tokens=max_completion_tokens)
        except Exception as exc:
            return {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "code-docs"),
                "error": str(exc), "n_turns": 0,
            }

    # Use parallel processing if workers > 1
    if workers > 1 and len(items) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_safe_rollout, items))
    else:
        results = [_safe_rollout(item) for item in items]

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def _selfcheck() -> None:
    """Assert the code-docs scorer for every doc type. A perfect doc passes;
    wrong type, missing frontmatter, or missing sections fail.
    Run: python3 rollout.py --selfcheck."""
    # A complete pattern doc must pass (frontmatter + all 5 sections + tags).
    perfect_p = (
        "---\nid: P-001\n type: pattern\n title: \"Repo\"\n date: 2026-08-30\n"
        " tags: [pattern, auth]\n---\n"
        "## Kalıp\n...\n## Kullanım Senaryosu\n...\n## Örnek\n...\n"
        "## Avantajlar\n...\n## Dezavantajlar\n...\n"
    )
    hard, soft = _score(perfect_p, "P", ["pattern", "auth"],
                        ["## Kalıp", "## Kullanım Senaryosu", "## Örnek"])
    assert hard == 1, f"perfect pattern doc should pass, got hard={hard}"

    # Wrong doc type must fail.
    wrong_type = perfect_p.replace("type: pattern", "type: api")
    assert _score(wrong_type, "P", ["pattern"], ["## Kalıp"])[0] == 0

    # Missing frontmatter must fail.
    no_fm = perfect_p.split("---\n", 1)[-1]
    assert _score(no_fm, "P", ["pattern"], ["## Kalıp"])[0] == 0

    # Missing a required section must fail.
    no_section = perfect_p.replace("## Kalıp\n", "")
    assert _score(no_section, "P", ["pattern"], ["## Kalıp", "## Kullanım Senaryosu"])[0] == 0

    # Each doc type's section set must be recognized (pattern table exists).
    for code in ("P", "T", "D", "L", "A", "X"):
        assert code in _SECTION_PATTERNS, f"missing section table for {code}"
    print("selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
