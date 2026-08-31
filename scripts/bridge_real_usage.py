#!/usr/bin/env python3
"""Bridge real methodology usage into SkillOpt training data.

The methodology already records real use: audit-log events (intent-stamped),
approved experiment records (docs/experiments/E-*.md), and auto-generated
code-docs learnings (docs/code-docs/learnings/L-*.md). None of that reaches the
SkillOpt benchmarks — whose training JSONs are hand-written synthetic scenarios.

This script converts the real artifacts into bmad_research_experiment training
items so the self-optimization loop learns from actual sessions, not just
synthetic ones. It is additive and idempotent: items are keyed by their source
artifact (E-id / L-id / audit timestamp), and a re-run overwrites the same ids
instead of duplicating them.

Usage:
  python3 scripts/bridge_real_usage.py [--audit-log PATH] [--learnings-dir PATH]
    [--out PATH]
Defaults: .metodoloji/logs/hook-audit.log, docs/code-docs/learnings,
bmad_benchmarks/envs/bmad_research_experiment/data/train/real-usage.json
"""

import argparse
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

EXPECTED_FIELDS = ["Theory", "Hypothesis", "Measurement Metrics",
                   "Experiment Design", "Code Scope"]


def _read_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    items = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def _write_train(items: list[dict], out: pathlib.Path) -> int:
    """Merge into out, keyed by id. Returns count written."""
    existing: dict[str, dict] = {}
    if out.is_file():
        try:
            for it in json.loads(out.read_text(encoding="utf-8")):
                existing[it["id"]] = it
        except (json.JSONDecodeError, OSError, KeyError):
            existing = {}
    for it in items:
        existing[it["id"]] = it
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = sorted(existing.values(), key=lambda x: x["id"])
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return len(merged)


def from_experiment_records(exp_dir: pathlib.Path) -> list[dict]:
    """E-*.md records with a real (non-placeholder) decision → train items."""
    if not exp_dir.is_dir():
        return []
    items = []
    for rec in sorted(exp_dir.glob("E-*.md")):
        if rec.name.startswith("_"):
            continue
        try:
            text = rec.read_text(encoding="utf-8")
        except OSError:
            continue
        # A decided record has a real Decision — not a placeholder. Placeholders
        # come in two forms: "<gate writes: ...>" and "— (gate writes)" (the
        # em-dash draft marker used by the templates).
        m = re.search(r"-\s*\*\*Decision:\*\*\s*([^\n]+)", text)
        if not m:
            continue
        decision = m.group(1).strip()
        if re.fullmatch(r"<.*>", decision) or decision.startswith("—"):
            continue
        eid = rec.stem
        hypothesis = ""
        hm = re.search(r"-\s*\*\*Hypothesis:\*\*\s*([^\n]+)", text)
        if hm:
            hypothesis = hm.group(1).strip()
        metric = "accuracy"
        mm = re.search(r"-\s*\*\*Measurement Metrics:\*\*\s*([^\n]+)", text)
        if mm:
            metric = mm.group(1).strip()
        scope = ""
        sm = re.search(r"-\s*\*\*Code Scope:\*\*\s*([^\n]+)", text)
        if sm:
            scope = sm.group(1).strip()
        theory = ""
        tm = re.search(r"-\s*\*\*Theory:\*\*\s*([^\n]+)", text)
        if tm:
            theory = tm.group(1).strip()
        items.append({
            "id": f"real-{eid}",
            "task_desc": (
                f"Reproduce experiment {eid}: {theory} "
                f"(hypothesis: {hypothesis or 'n/a'}, metric: {metric}). "
                f"Write a complete methodology record with all required fields; "
                f"the code scope is {scope or 'n/a'}."
            ),
            "expected_fields": EXPECTED_FIELDS,
            "expected_hypothesis_format": True,
            "expected_metric_type": "accuracy",
            "task_type": "research-experiment",
            "source": f"experiment:{eid}",
        })
    return items


def from_learnings(learnings_dir: pathlib.Path) -> list[dict]:
    """L-*.md learnings (auto-generated from approved experiments) → items."""
    if not learnings_dir.is_dir():
        return []
    items = []
    for doc in sorted(learnings_dir.glob("L-*.md")):
        try:
            text = doc.read_text(encoding="utf-8")
        except OSError:
            continue
        # Learning docs carry related_experiments: [E-XXX].
        m = re.search(r"related_experiments:\s*\[([^\]]*)\]", text)
        exp_refs = [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []
        eid = exp_refs[0] if exp_refs else doc.stem
        title = ""
        tm = re.search(r"title:\s*\"([^\"]+)\"", text)
        if tm:
            title = tm.group(1)
        items.append({
            "id": f"real-{doc.stem}",
            "task_desc": (
                f"Apply the learning from {eid} ('{title}'): produce a "
                f"methodology record capturing the approved experiment, its "
                f"hypothesis, measurement, and decision."
            ),
            "expected_fields": EXPECTED_FIELDS,
            "expected_hypothesis_format": True,
            "expected_metric_type": "accuracy",
            "task_type": "research-experiment",
            "source": f"learning:{doc.stem}",
        })
    return items


def from_audit_log(audit_log: pathlib.Path) -> list[dict]:
    """Audit-log events mentioning an approved experiment → items."""
    events = _read_jsonl(audit_log)
    items = []
    for ev in events:
        tool = ev.get("tool", "")
        if tool != "terminal":
            continue
        cmd = str(ev.get("input", {}).get("command", ""))
        output = str(ev.get("output_summary", "") or "")
        if "run_experiment.py" not in cmd:
            continue
        if "--verify" in cmd:
            continue  # verifying is not an approval event (audit hook parity)
        if "APPROVED" not in output and "VERIFIED" not in output:
            continue
        m = re.search(r"E-\d+", cmd)
        eid = m.group(0) if m else "E-?"
        ts = str(ev.get("timestamp", ""))
        intent = ev.get("intent", "")
        items.append({
            "id": f"real-audit-{abs(hash(ts)) % 10**8:08d}",
            "task_desc": (
                f"Experiment {eid} was approved in a real session"
                f"{' (intent: ' + intent + ')' if intent else ''}. "
                f"Reproduce the methodology record with all required fields."
            ),
            "expected_fields": EXPECTED_FIELDS,
            "expected_hypothesis_format": True,
            "expected_metric_type": "accuracy",
            "task_type": "research-experiment",
            "source": f"audit:{ts}",
        })
    return items


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit-log", type=pathlib.Path,
                   default=REPO_ROOT / ".metodoloji/logs/hook-audit.log")
    p.add_argument("--experiments-dir", type=pathlib.Path,
                   default=REPO_ROOT / "docs/experiments")
    p.add_argument("--learnings-dir", type=pathlib.Path,
                   default=REPO_ROOT / "docs/code-docs/learnings")
    p.add_argument("--out", type=pathlib.Path,
                   default=REPO_ROOT / "bmad_benchmarks/envs/bmad_research_experiment/data/train/real-usage.json")
    args = p.parse_args()

    items = []
    items += from_experiment_records(args.experiments_dir)
    items += from_learnings(args.learnings_dir)
    items += from_audit_log(args.audit_log)
    total = _write_train(items, args.out)
    print(f"bridge_real_usage: {len(items)} real-usage items → {args.out} "
          f"(train now has {total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
