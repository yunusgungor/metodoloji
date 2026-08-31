import re
from .._base_.rollout import run_batch as _run_batch, rollout_one
import concurrent.futures
import json
import pathlib

# The model generates records in Turkish (the skill's language), so each
# field matches both the English and the Turkish heading used in the records.
_FIELD_PATTERNS = {
    "Theory": re.compile(r"##\s*(?:Theory|Teori)|###\s*(?:Theory|Teori)|\*\*(?:Theory|Teori):", re.IGNORECASE),
    "Hypothesis": re.compile(r"(?:Hypothesis|Hipotez).*H-\d+|##\s*(?:Hypothesis|Hipotez)|###\s*(?:Hypothesis|Hipotez)|\*\*(?:Hypothesis|Hipotez):", re.IGNORECASE),
    "Measurement Metrics": re.compile(r"(?:Measurement Metrics|Ölçüm metrikleri|Ölçüm)|##\s*(?:Measurement|Ölçüm)|###\s*(?:Measurement|Ölçüm metrikleri)|\*\*(?:Measurement|Ölçüm metrikleri)", re.IGNORECASE),
    "Experiment Design": re.compile(r"(?:Experiment Design|Deney tasarımı)|##\s*(?:Experiment|Deney)|###\s*(?:Experiment Design|Deney tasarımı)|\*\*(?:Experiment Design|Deney tasarımı)", re.IGNORECASE),
    "Code Scope": re.compile(r"(?:Code Scope|Kod kapsamı)|##\s*(?:Code|Kod)|###\s*(?:Code Scope|Kod kapsamı)|\*\*(?:Code Scope|Kod kapsamı)", re.IGNORECASE),
}

_HYPOTHESIS_RE = re.compile(r"H-\d+")

# A field counts as filled only when its heading is followed by real content
# (not just a heading with an empty body). 20 non-whitespace chars is the
# minimum a real record section (a sentence or two) reaches.
_MIN_SECTION_CHARS = 20
_NEXT_HEADING_RE = re.compile(r"(?m)^#+\s")


def _section_content(text: str, field: str) -> str:
    """Return the body after the field's heading, cut at the next heading."""
    m = _FIELD_PATTERNS.get(field)
    if not m:
        return ""
    m = m.search(text)
    if not m:
        return ""
    start = m.end()
    nxt = _NEXT_HEADING_RE.search(text, start)
    end = nxt.start() if nxt else len(text)
    return text[start:end].strip()


def _field_filled(text: str, field: str) -> bool:
    body = _section_content(text, field)
    return len(body) >= _MIN_SECTION_CHARS


def _score(output_text, item):
    expected = item["expected_fields"]
    found = sum(1 for f in expected if _field_filled(output_text, f))
    soft = found / len(expected) if expected else 0.0
    hard = 1 if soft >= 0.8 else 0
    if item.get("expected_hypothesis_format", True) and hard == 1:
        if not _HYPOTHESIS_RE.search(output_text):
            hard = 0
    return hard, soft


def _prompt(item, skill_content):
    system = (
        f"{skill_content}\n\n"
        f"You are a research methodology expert. Generate a complete "
        f"experiment record following the methodology manifesto. "
        f"The record MUST contain these fields: "
        f"Theory, Hypothesis (H-NNN format), Measurement Metrics, "
        f"Experiment Design, Code Scope."
    )
    user = f"## Scenario\n\n{item['task_desc']}\n\nGenerate a complete experiment record for this scenario."
    return system, user


def _extra_result(output_text, item):
    return {
        "n_expected_fields": len(item["expected_fields"]),
        "n_fields_found": sum(1 for f in item["expected_fields"] if _field_filled(output_text, f)),
        "hypothesis_format_valid": bool(_HYPOTHESIS_RE.search(output_text)),
    }


def run_batch(items, skill_content, out_dir, workers=1, max_completion_tokens=4096):
    out_dir = pathlib.Path(out_dir)

    def _safe(item):
        try:
            sys_p, usr_p = _prompt(item, skill_content)
            return rollout_one(item, skill_content, out_dir, sys_p, usr_p,
                               _score, max_completion_tokens,
                               extra_result=_extra_result)
        except Exception as exc:
            return {
                "id": item["id"], "hard": 0, "soft": 0.0,
                "task_type": item.get("task_type", "research-experiment"),
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
    item = {"expected_fields": ["Theory", "Hypothesis", "Measurement Metrics",
                                "Experiment Design", "Code Scope"],
            "expected_hypothesis_format": True}
    # A real, fully-filled record (as the model produces) → hard 1.0.
    good = (
        "## Theory\n\nA falsifiable claim about the guard hook.\n\n"
        "## Hypothesis\n\nH-001: the hook blocks writes outside scope.\n\n"
        "## Measurement Metrics\n\naccuracy, precision.\n\n"
        "## Experiment Design\n\nRun 5 writes in and out of scope.\n\n"
        "## Code Scope\n\nhooks/engine/**/*.py\n"
    )
    assert _score(good, item) == (1, 1.0), "fully-filled record must be 1.0"
    # The model actually writes Turkish headings — must also score 1.0.
    tr = (
        "## Teori\n\nGuard hook, kapsam dışı yazmayı reddeder.\n\n"
        "## Hipotez\n\nH-017: kapsam_dışı_red_oranı == 1.0.\n\n"
        "## Ölçüm metrikleri\n\nred_oranı, kabul_oranı.\n\n"
        "## Deney tasarımı\n\n5 yazma denemesi çalıştır.\n\n"
        "## Kod kapsamı\n\nhooks/engine/**/*.py\n"
    )
    assert _score(tr, item) == (1, 1.0), "Turkish-filled record must be 1.0"
    # Heading spam — the old scorer would pass this; the new one must not.
    bad = "## Theory\n\n## Hypothesis\n\n## Measurement Metrics\n\n## Experiment Design\n\n## Code Scope\n\n"
    assert _score(bad, item) == (0, 0.0), "empty-headed sections must fail"
    bad_tr = "## Teori\n\n## Hipotez\n\n## Ölçüm metrikleri\n\n## Deney tasarımı\n\n## Kod kapsamı\n\n"
    assert _score(bad_tr, item) == (0, 0.0), "empty Turkish sections must fail"
    # One empty field → soft 0.8 but hard 1 (>=0.8) — matches previous behavior.
    partial = good.replace("## Code Scope\n\nhooks/engine/**/*.py\n", "## Code Scope\n\n")
    hard, soft = _score(partial, item)
    assert soft == 0.8 and hard == 1, f"one empty field → soft 0.8, got {soft} hard {hard}"
    print("selfcheck OK")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit("rollout.py is a module — import run_batch via the adapter (or run --selfcheck)")
