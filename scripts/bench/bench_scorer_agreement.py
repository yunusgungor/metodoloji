#!/usr/bin/env python3
"""Bench: scorer agreement with gold-standard labels.

Measures how well each benchmark's _score() function agrees with
human-labeled gold standard outputs. Emits:
    scorer_agreement=<value> (correct/total)

Covers all 6 scoring strategies:
  A: field-presence (custom_ir family)
  C: explicit-declaration (meta_root, meta_guard)
  D: multi-axis word (meta_chain)
  E: section/invariant (architecture)
  F: rich structural (research_experiment, code_docs)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ---------------------------------------------------------------------------
# Gold standard: (output_text, item_dict, expected_hard, expected_soft, label)
# label: "good" = should score hard=1, "bad" = should score hard=0,
#        "corrupted" = deliberately malformed, MUST score hard=0
# ---------------------------------------------------------------------------

# Strategy A: field-presence (custom_ir family)
_FIELDS_IR = ["Research Inputs", "Design Documents", "Technical Dependencies"]
_FIELDS_SP = ["Sprint Goal", "Backlog Items", "Capacity Plan", "Risks"]

def _fp(fields):
    return {"expected_fields": fields}

GOLD_A = [
    # good: all fields present as section headings
    ("## Research Inputs\nAPI docs reviewed\n## Design Documents\nFigma linked\n## Technical Dependencies\nRedis, Postgres",
     _fp(_FIELDS_IR), 1, 1.0, "good"),
    # bad: missing 1/4 fields
    ("## Sprint Goal\nShip v2\n## Backlog Items\n10 items\n## Capacity Plan\n5 devs",
     _fp(_FIELDS_SP), 0, 0.75, "bad"),
    # corrupted: gibberish with one field label as plain text
    ("Research Inputs is a word. Nothing else matters here. No structure.",
     _fp(_FIELDS_IR), 0, 0.333, "corrupted"),
    # good: all fields as inline text (normalize matches substrings)
    ("Fields: Research Inputs, Design Documents, Technical Dependencies are all present.",
     _fp(_FIELDS_IR), 1, 1.0, "good"),
    # bad: empty output
    ("", _fp(_FIELDS_SP), 0, 0.0, "bad"),
]

# Strategy C: meta_root (2-axis: root + direction)
def _mr(root, direction):
    return {"expected_root": root, "expected_direction": direction}

GOLD_C = [
    # good: explicit declaration
    ("Root anchor: {project-root}. Direction: writes — creates the record.",
     _mr("project-root", "output"), 1, 1.0, "good"),
    # good: minimal explicit
    ("metodoloji-root read", _mr("metodoloji-root", "read"), 1, 1.0, "good"),
    # bad: wrong root (direction matches but root doesn't)
    ("Root anchor: {metodoloji-root}. Direction: writes.",
     _mr("project-root", "output"), 0, 0.5, "bad"),
    # bad: wrong direction (root matches but direction doesn't)
    ("Root anchor: {project-root}. Direction: reads.",
     _mr("project-root", "output"), 0, 0.5, "bad"),
    # corrupted: uncertainty → hard=0, soft=0.0
    ("I think maybe it's project-root? Not sure though.",
     _mr("project-root", "output"), 0, 0.0, "corrupted"),
    # good: rejection marker handled correctly
    ("Writing to the plugin is wrong; the record is created under project-root.",
     _mr("project-root", "output"), 1, 1.0, "good"),
    # corrupted: no commitment to either axis
    ("The operation involves files and directories.",
     _mr("project-root", "output"), 0, 0.0, "corrupted"),
]

# Strategy C: meta_guard (1-axis: DENY/ALLOW)
def _mg(expected):
    return {"expected_decision": expected}

GOLD_GUARD = [
    ("Decision: DENY — the operation writes to the plugin root.",
     _mg("DENY"), 1, 1.0, "good"),
    ("ALLOW", _mg("ALLOW"), 1, 1.0, "good"),
    ("Decision: ALLOW — this is a read operation.",
     _mg("DENY"), 0, 0.0, "bad"),
    ("I'm not sure, maybe DENY?",
     _mg("DENY"), 0, 0.0, "corrupted"),
]

# Strategy D: meta_chain (3-axis: record, path, status)
def _mc(record, path, status):
    return {"expected_record": record, "expected_path": path, "expected_status": status}

GOLD_CHAIN = [
    ("Record: IR at docs/development/IR-007.md, status READY.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 1, 1.0, "good"),
    ("IR — docs/development/IR-002.md — INCOMPLETE.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 1, 1.0, "good"),
    # bad: missing path → 2/3 = 0.667 < 0.9
    ("The record is IR, status READY.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 0, 0.667, "bad"),
    # bad: wrong record token
    ("The record is PR at docs/development/IR-003.md, status READY.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 0, 0.667, "bad"),
    # corrupted: no structure
    ("Some random text about records.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 0, 0.0, "corrupted"),
]

# Strategy E: architecture (invariant substring match, threshold 0.8)
def _arch(invariants):
    return {"expected_invariants": invariants}

GOLD_E = [
    ("The spine enforces separation of concerns, immutable config, and event-driven flow.",
     _arch(["separation of concerns", "immutable config", "event-driven"]), 1, 1.0, "good"),
    # 2/3 → soft 0.667 < 0.8 → hard 0
    ("The spine enforces separation of concerns and event-driven flow.",
     _arch(["separation of concerns", "immutable config", "event-driven"]), 0, 0.667, "bad"),
    ("The spine focuses on caching and retries.",
     _arch(["separation of concerns", "immutable config"]), 0, 0.0, "corrupted"),
]

# Strategy F: research_experiment (regex per field + content depth ≥ 20 chars + H-\d+)
def _re(fields, hyp_fmt=True):
    return {"expected_fields": fields, "expected_hypothesis_format": hyp_fmt}

GOLD_RE = [
    # good: all fields filled with content + H-\d+ format
    ("## Theory\nScorer quality matters for reliable training feedback loops.\n\n"
     "## Hypothesis\nH-001: scorer_agreement >= 0.90 on gold standard dataset.\n\n"
     "## Measurement Metrics\nscorer_agreement = correct / total decisions.\n\n"
     "## Experiment Design\nRun scorer against gold standard outputs.\n\n"
     "## Code Scope\nbench_scorer_agreement.py covers all strategies.",
     _re(["Theory", "Hypothesis", "Measurement Metrics", "Experiment Design", "Code Scope"]),
     1, 1.0, "good"),
    # bad: all fields filled but NO H-\d+ format → hard demoted to 0
    ("## Theory\nScorer quality matters.\n\n"
     "## Hypothesis\nagreement is good enough.\n\n"
     "## Measurement Metrics\naccuracy score.\n\n"
     "## Experiment Design\nRun tests.\n\n"
     "## Code Scope\nfoo.py is the file.",
     _re(["Theory", "Hypothesis", "Measurement Metrics", "Experiment Design", "Code Scope"]),
     0, 1.0, "bad"),
    # corrupted: too short, sections not filled
    ("Hi",
     _re(["Theory", "Hypothesis"]), 0, 0.0, "corrupted"),
    # good: Turkish headings ( scorer also accepts these)
    ("## Teori\nGuard hook kapsam dışı yazmayı reddeder.\n\n"
     "## Hipotez\nH-017: kapsam_dışı_red_oranı == 1.0.\n\n"
     "## Ölçüm metrikleri\nred_oranı ve kabul_oranı ölçülür.\n\n"
     "## Deney tasarımı\n5 yazma denemesi çalıştırılır.\n\n"
     "## Kod kapsamı\nhooks/engine/**/*.py dosyaları.",
     _re(["Theory", "Hypothesis", "Measurement Metrics", "Experiment Design", "Code Scope"]),
     1, 1.0, "good"),
]

# Strategy F: code_docs (type=short code, frontmatter, section patterns)
def _cd(doc_type, sections, tags=None):
    return {"expected_type": doc_type, "expected_sections": sections,
            "expected_tags": tags or []}

# Good pattern doc: type=P, frontmatter with 5 fields, all P sections
_P_GOOD = (
    "---\nid: P-001\ntype: pattern\ntitle: \"Repo Auth\"\ndate: 2026-08-30\n"
    "tags: [pattern, auth]\n---\n"
    "## Pattern\nToken-based auth for repo access.\n"
    "## Usage Scenario\nWhen API access requires authentication.\n"
    "## Example\ncurl -H 'Authorization: Bearer ...' url\n"
    "## Advantages\nStateless, scalable.\n"
    "## Disadvantages\nToken rotation complexity."
)

GOLD_CD = [
    # good: correct type (P), complete frontmatter, all P sections
    (_P_GOOD, _cd("P", ["## Pattern", "## Usage Scenario", "## Example"],
                  ["pattern", "auth"]), 1, 1.0, "good"),
    # bad: wrong type (detected=P but expected=A)
    (_P_GOOD, _cd("A", ["## Pattern", "## Usage Scenario", "## Example"]),
     0, 0.0, "bad"),
    # corrupted: no frontmatter at all
    ("## Signature\nchat_target(system, user)\n## Usage\nCall to chat",
     _cd("A", ["## Signature", "## Usage"]), 0, 0.0, "corrupted"),
    # good: decision doc
    ("---\nid: D-001\ntype: decision\ntitle: \"x\"\ndate: 01.09.2026\n"
     "tags: [decision]\n---\n"
     "## Decision\nUse Redis for caching.\n"
     "## Rationale\nPerformance requirements.\n"
     "## Results\n50ms p99 latency.",
     _cd("D", ["## Decision", "## Rationale", "## Results"], ["decision"]),
     1, 1.0, "good"),
]

# ---------------------------------------------------------------------------
# Corrupted-output regression cases (label="corrupted-regression")
# These test edge cases where the scorer's logic MUST reject bad outputs.
# ---------------------------------------------------------------------------

GOLD_CORRUPTED = [
    # --- meta_root: "correct root" declaration overrides named-but-wrong root ---
    # The model says the correct root is metodoloji-root, but names project-root
    # as the invalid target. Scorer must trust "correct root" declaration.
    ("The config resolves to {project-root} but it's invalid; the correct "
     "destination writes to {metodoloji-root}.",
     _mr("metodoloji-root", "output"), 1, 1.0, "corrupted-regression"),
    # Verb negation: "do NOT write" kills the output direction claim
    ("Root anchor: {project-root}. Do NOT write the config; just read it.",
     _mr("project-root", "read"), 1, 1.0, "corrupted-regression"),
    # Rejection marker: "rather than {metodoloji-root}" excludes that anchor
    ("The operation writes to {project-root} rather than {metodoloji-root}.",
     _mr("project-root", "output"), 1, 1.0, "corrupted-regression"),
    # Double negative: "not deny" = ALLOW
    ("The operation does not deny the request; it should ALLOW.",
     _mg("ALLOW"), 1, 1.0, "corrupted-regression"),
    # --- meta_chain: record token as substring of path must NOT match ---
    # "IR" inside "IR-003.md" path must not count as naming the record "IR"
    # when the actual record named is "PR"
    ("The record is PR at docs/development/IR-003.md, status READY.",
     _mc("IR", "docs/development/IR-", "READY | INCOMPLETE"), 0, 0.667,
     "corrupted-regression"),
    # --- architecture: partial invariant match must fail (2/3 < 0.8) ---
    ("The spine enforces separation of concerns and immutable config.",
     _arch(["separation of concerns", "immutable config", "event-driven"]),
     0, 0.667, "corrupted-regression"),
    # --- research_experiment: heading spam without content MUST fail ---
    ("## Theory\n\n## Hypothesis\n\n## Measurement Metrics\n\n"
     "## Experiment Design\n\n## Code Scope\n\n",
     _re(["Theory", "Hypothesis", "Measurement Metrics", "Experiment Design", "Code Scope"]),
     0, 0.0, "corrupted-regression"),
    # --- code_docs: missing frontmatter MUST fail even if sections are perfect ---
    ("## API\nchat_target makes API calls.\n## Signature\nchat_target(sys, usr)\n"
     "## Usage\nCall it.\n## Notes\nBe careful.",
     _cd("A", ["## API", "## Signature", "## Usage", "## Notes"]), 0, 0.0,
     "corrupted-regression"),
]

# ---------------------------------------------------------------------------
# Scorer imports
# ---------------------------------------------------------------------------
from bmad_benchmarks.envs._base_.rollout import score_field_presence
from bmad_benchmarks.envs.bmad_meta_root.rollout import _score as score_meta_root


def _import_score(module_path, attr="_score"):
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, attr)


def _build_scorer_map():
    scorers = {}

    # A: field-presence
    def _score_fp(output_text, item):
        return score_field_presence(output_text, item["expected_fields"])
    scorers["custom_ir"] = (_score_fp, GOLD_A)

    # C: meta_root
    scorers["meta_root"] = (score_meta_root, GOLD_C)

    # C: meta_guard
    try:
        scorers["meta_guard"] = (
            _import_score("bmad_benchmarks.envs.bmad_meta_guard.rollout"), GOLD_GUARD)
    except Exception:
        pass

    # D: meta_chain
    try:
        scorers["meta_chain"] = (
            _import_score("bmad_benchmarks.envs.bmad_meta_chain.rollout"), GOLD_CHAIN)
    except Exception:
        pass

    # E: architecture
    try:
        scorers["architecture"] = (
            _import_score("bmad_benchmarks.envs.bmad_architecture.rollout"), GOLD_E)
    except Exception:
        pass

    # F: research_experiment
    try:
        scorers["research_experiment"] = (
            _import_score("bmad_benchmarks.envs.bmad_research_experiment.rollout"), GOLD_RE)
    except Exception:
        pass

    # F: code_docs
    try:
        scorers["code_docs"] = (
            _import_score("bmad_benchmarks.envs.bmad_code_docs.rollout"), GOLD_CD)
    except Exception:
        pass

    # Corrupted-output regression cases (merged into their respective scorers)
    _corrupted_by_scorer = {
        "meta_root": [], "meta_guard": [], "meta_chain": [],
        "architecture": [], "research_experiment": [], "code_docs": [],
    }
    for item in GOLD_CORRUPTED:
        output_text, item_dict, exp_hard, exp_soft, label = item
        # Route to the right scorer based on item shape
        if "expected_root" in item_dict:
            _corrupted_by_scorer["meta_root"].append(item)
        elif "expected_decision" in item_dict:
            _corrupted_by_scorer["meta_guard"].append(item)
        elif "expected_record" in item_dict:
            _corrupted_by_scorer["meta_chain"].append(item)
        elif "expected_invariants" in item_dict:
            _corrupted_by_scorer["architecture"].append(item)
        elif "expected_hypothesis_format" in item_dict:
            _corrupted_by_scorer["research_experiment"].append(item)
        elif "expected_type" in item_dict:
            _corrupted_by_scorer["code_docs"].append(item)

    for scorer_name, corrupted_items in _corrupted_by_scorer.items():
        if corrupted_items and scorer_name in scorers:
            score_fn, existing = scorers[scorer_name]
            scorers[scorer_name] = (score_fn, existing + corrupted_items)

    return scorers


def main():
    scorers = _build_scorer_map()
    if not scorers:
        print("scorer_agreement=0.000 (0/0)")
        sys.exit(1)

    correct = 0
    total = 0
    details = []

    for bench_name, (score_fn, gold_items) in sorted(scorers.items()):
        for output_text, item, exp_hard, exp_soft, label in gold_items:
            total += 1
            try:
                got_hard, got_soft = score_fn(output_text, item)
            except Exception as e:
                got_hard, got_soft = 0, 0.0
                details.append(f"  ERROR {bench_name}/{label}: {e}")
                continue

            agreed = (got_hard == exp_hard)
            if agreed:
                correct += 1

            status = "OK" if agreed else "FAIL"
            details.append(
                f"  {status} {bench_name:25s} {label:10s} "
                f"expected=({exp_hard},{exp_soft:.3f}) got=({got_hard},{got_soft:.3f})"
            )

    rate = correct / total if total else 0.0
    print(f"scorer_accuracy={rate:.3f} ({correct}/{total})")
    for d in details:
        print(d, file=sys.stderr)


if __name__ == "__main__":
    main()
