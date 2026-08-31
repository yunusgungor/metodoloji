import re
from .._base_.rollout import run_batch as _run_batch

_REQUIRED_FRONTMATTER = {"id", "type", "title", "date", "tags"}

_SECTION_PATTERNS = {
    "P": {
        "Kalıp": re.compile(r"##\s*Kalıp", re.IGNORECASE),
        "Kullanım Senaryosu": re.compile(r"##\s*Kullanım\s+Senaryosu", re.IGNORECASE),
        "Örnek": re.compile(r"##\s*Örnek", re.IGNORECASE),
        "Avantajlar": re.compile(r"##\s*Avantajlar", re.IGNORECASE),
        "Dezavantajlar": re.compile(r"##\s*Dezavantajlar", re.IGNORECASE),
    },
    "T": {
        "Hata": re.compile(r"##\s*Hata", re.IGNORECASE),
        "Neden": re.compile(r"##\s*Neden", re.IGNORECASE),
        "Çözüm": re.compile(r"##\s*Çözüm", re.IGNORECASE),
        "Önleme": re.compile(r"##\s*Önleme", re.IGNORECASE),
    },
    "D": {
        "Karar": re.compile(r"##\s*Karar", re.IGNORECASE),
        "Gerekçe": re.compile(r"##\s*Gerekçe", re.IGNORECASE),
        "Sonuçlar": re.compile(r"##\s*Sonuçlar", re.IGNORECASE),
    },
    "L": {
        "Öğrenilen": re.compile(r"##\s*Öğrenilen", re.IGNORECASE),
        "Bağlam": re.compile(r"##\s*Bağlam", re.IGNORECASE),
        "Kanıt": re.compile(r"##\s*Kanıt", re.IGNORECASE),
        "Uygulama": re.compile(r"##\s*Uygulama", re.IGNORECASE),
    },
    "A": {
        "API": re.compile(r"##\s*API", re.IGNORECASE),
        "İmza": re.compile(r"##\s*İmza", re.IGNORECASE),
        "Kullanım": re.compile(r"##\s*Kullanım", re.IGNORECASE),
        "Dikkat Edilecekler": re.compile(r"##\s*Dikkat\s+Edilecekler", re.IGNORECASE),
    },
    "X": {
        "Açıklama": re.compile(r"##\s*Açıklama", re.IGNORECASE),
        "Bağlam": re.compile(r"##\s*Bağlam", re.IGNORECASE),
        "Sonraki Adımlar": re.compile(r"##\s*Sonraki\s+Adımlar", re.IGNORECASE),
    },
}

_DOC_TYPE_NAMES = {"P": "pattern", "T": "troubleshooting", "D": "decision",
                   "L": "learning", "A": "api", "X": "pending"}


def _check_frontmatter(text):
    fm = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not fm:
        return 0, len(_REQUIRED_FRONTMATTER)
    found = sum(1 for f in _REQUIRED_FRONTMATTER if f in fm.group(1))
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
    fm = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not fm:
        return 0, len(expected_tags)
    fm_text = fm.group(1).lower()
    found = sum(1 for t in expected_tags if t.lower() in fm_text)
    return found, len(expected_tags)


def _check_context_loading(text, context):
    text_lower = text.lower()
    has_exp_ref = bool(re.search(r"E-\d+", text))
    context_phrases = ["daha önce", "mevcut", "önceki", "var olan",
                       "önceden", "bilinen", "daha önceki", "mevcut kalıp"]
    has_ctx = any(p in text_lower for p in context_phrases)
    has_doc_ref = bool(re.search(
        r"(decision|pattern|learning|troubleshooting|pending)\s+(D|P|L|T|X)-\d+", text_lower))
    return has_exp_ref or has_ctx or has_doc_ref


def _score(output_text, item):
    type_match = re.search(r"^\s*type:\s*(\w+)", output_text, re.MULTILINE)
    type_correct = type_match and type_match.group(1) == _DOC_TYPE_NAMES.get(item["expected_type"], "")
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
    doc_type_name = _DOC_TYPE_NAMES.get(item["expected_type"], "pattern")
    system = (
        f"{skill_content}\n\n"
        f"You are a code documentation expert. Generate a structured code-doc "
        f"following the methodology. The doc MUST be of type '{doc_type_name}' "
        f"with valid YAML frontmatter (id, type, title, date, tags) and "
        f"all required sections in Turkish."
    )
    user = (
        f"## Senaryo\n\n{item['scenario']}\n\n"
        f"Bu senaryo için uygun code-doc'u üret. "
        f"Beklenen tür: {doc_type_name} ({item['expected_type']})\n"
        f"Beklenen etiketler: {', '.join(item.get('expected_tags', []))}"
    )
    return system, user


def _extra_result(output_text, item):
    type_match = re.search(r"^\s*type:\s*(\w+)", output_text, re.MULTILINE)
    sec_found, _ = _check_sections(output_text, item["expected_type"])
    tag_found, _ = _check_tags(output_text, item.get("expected_tags", []))
    fm_valid = _check_frontmatter(output_text) == (len(_REQUIRED_FRONTMATTER), len(_REQUIRED_FRONTMATTER))
    return {
        "expected_type": item["expected_type"],
        "detected_type": type_match.group(1) if type_match else "",
        "n_expected_sections": len(item.get("expected_sections", [])),
        "n_sections_found": sec_found,
        "n_expected_tags": len(item.get("expected_tags", [])),
        "n_tags_found": tag_found,
        "frontmatter_valid": fm_valid,
    }


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    def _score_fn(text, item):
        return _score(text, item)

    def _prompt_fn(item, sc):
        return _prompt(item, sc)

    from .._base_.rollout import rollout_one
    import concurrent.futures
    import json
    import pathlib

    out_dir = pathlib.Path(out_dir)

    def _safe(item):
        try:
            sys_p, usr_p = _prompt_fn(item, skill_content)
            return rollout_one(item, skill_content, out_dir, sys_p, usr_p,
                               _score_fn, max_completion_tokens,
                               extra_result=_extra_result)
        except Exception as exc:
            return {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "code-docs"),
                "error": str(exc), "n_turns": 0,
            }

    if workers > 1 and len(items) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_safe, items))
    else:
        results = [_safe(item) for item in items]

    (out_dir / "rollouts.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "rollouts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def _selfcheck():
    perfect_p = (
        "---\nid: P-001\n type: pattern\n title: \"Repo\"\n date: 2026-08-30\n"
        " tags: [pattern, auth]\n---\n"
        "## Kalıp\n...\n## Kullanım Senaryosu\n...\n## Örnek\n...\n"
        "## Avantajlar\n...\n## Dezavantajlar\n...\n"
    )
    item_p = {"expected_type": "P", "expected_tags": ["pattern", "auth"],
              "expected_sections": ["## Kalıp", "## Kullanım Senaryosu", "## Örnek"]}
    hard, soft = _score(perfect_p, item_p)
    assert hard == 1, f"perfect pattern doc should pass, got hard={hard}"
    wrong_type = perfect_p.replace("type: pattern", "type: api")
    assert _score(wrong_type, item_p)[0] == 0
    no_fm = perfect_p.split("---\n", 1)[-1]
    item_min = {"expected_type": "P", "expected_tags": ["pattern"],
                "expected_sections": ["## Kalıp"]}
    assert _score(no_fm, item_min)[0] == 0
    no_section = perfect_p.replace("## Kalıp\n", "")
    item_no_sec = {"expected_type": "P", "expected_tags": ["pattern"],
                   "expected_sections": ["## Kalıp", "## Kullanım Senaryosu"]}
    assert _score(no_section, item_no_sec)[0] == 0
    for code in ("P", "T", "D", "L", "A", "X"):
        assert code in _SECTION_PATTERNS, f"missing section table for {code}"
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
