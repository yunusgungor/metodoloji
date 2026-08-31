"""Tests for scripts/bridge_real_usage.py — real-usage → benchmark data bridge.

Covers the three source converters and the idempotent merge, loaded via
importlib so no subprocess is involved.
"""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bridge_real_usage.py"


def _load():
    spec = importlib.util.spec_from_file_location("bridge_real_usage", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()

EXPECTED = ["Theory", "Hypothesis", "Measurement Metrics",
            "Experiment Design", "Code Scope"]


# --- from_experiment_records -------------------------------------------------

def test_experiment_decided_record(tmp_path):
    d = tmp_path / "experiments"
    d.mkdir()
    (d / "E-001.md").write_text(
        "- **Theory:** T\n- **Hypothesis:** H-001: \"x >= 0.9\"\n"
        "- **Measurement Metrics:** accuracy\n- **Code Scope:** src/**\n"
        "- **Decision:** APPROVED — H-001: measured=0.95 >= threshold=0.9\n",
        encoding="utf-8")
    items = mod.from_experiment_records(d)
    assert len(items) == 1
    it = items[0]
    assert it["id"] == "real-E-001"
    assert it["expected_fields"] == EXPECTED
    assert it["source"] == "experiment:E-001"


def test_experiment_placeholder_skipped(tmp_path):
    d = tmp_path / "experiments"
    d.mkdir()
    (d / "E-001.md").write_text(
        "- **Decision:** <gate writes: APPROVED | REJECTED>\n", encoding="utf-8")
    assert mod.from_experiment_records(d) == []


def test_experiment_em_dash_placeholder_skipped(tmp_path):
    # The templates use "— (gate writes)" as the undecided marker; a record
    # with it must NOT be treated as decided.
    d = tmp_path / "experiments"
    d.mkdir()
    (d / "E-001.md").write_text(
        "- **Decision:** — (gate writes)\n- **Status:** planned\n", encoding="utf-8")
    assert mod.from_experiment_records(d) == []


def test_experiment_missing_decision_skipped(tmp_path):
    d = tmp_path / "experiments"
    d.mkdir()
    (d / "E-001.md").write_text("- **Status:** planned\n", encoding="utf-8")
    assert mod.from_experiment_records(d) == []


def test_experiment_dir_missing():
    assert mod.from_experiment_records(Path("/nonexistent")) == []


# --- from_learnings ----------------------------------------------------------

def test_learning_with_experiment_ref(tmp_path):
    d = tmp_path / "learnings"
    d.mkdir()
    (d / "L-E-001-x.md").write_text(
        '---\ntitle: "Auth learning"\nrelated_experiments: [E-001]\n---\nbody\n',
        encoding="utf-8")
    items = mod.from_learnings(d)
    assert len(items) == 1
    assert items[0]["id"] == "real-L-E-001-x"
    assert "E-001" in items[0]["task_desc"]


def test_learning_no_experiment_uses_stem(tmp_path):
    d = tmp_path / "learnings"
    d.mkdir()
    (d / "L-001.md").write_text('---\ntitle: "X"\n---\n', encoding="utf-8")
    items = mod.from_learnings(d)
    assert len(items) == 1
    assert "L-001" in items[0]["task_desc"]


# --- from_audit_log ----------------------------------------------------------

def test_audit_approved_experiment(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text(json.dumps({
        "tool": "terminal",
        "input": {"command": "run_experiment.py --record docs/experiments/E-005.md --run x"},
        "output_summary": "E-005 APPROVED",
        "intent": "auth flow",
        "timestamp": 1700000000.0,
    }) + "\n", encoding="utf-8")
    items = mod.from_audit_log(log)
    assert len(items) == 1
    assert "E-005" in items[0]["task_desc"]
    assert "auth flow" in items[0]["task_desc"]  # intent embedded
    assert items[0]["source"].startswith("audit:")


def test_audit_verify_not_approved(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text(json.dumps({
        "tool": "terminal",
        "input": {"command": "run_experiment.py --record E.md --verify"},
        "output_summary": "VERIFIED",
    }) + "\n", encoding="utf-8")
    # --verify is not an APPROVED event → no item (the audit hook's own rule).
    assert mod.from_audit_log(log) == []


def test_audit_non_terminal_skipped(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text(json.dumps({
        "tool": "file_editor",
        "input": {"path": "x.md", "content": "run_experiment.py E APPROVED"},
        "output_summary": "",
    }) + "\n", encoding="utf-8")
    assert mod.from_audit_log(log) == []


def test_audit_missing_log():
    assert mod.from_audit_log(Path("/nonexistent.jsonl")) == []


def test_audit_garbage_lines(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("not json\n\n{broken\n", encoding="utf-8")
    assert mod.from_audit_log(log) == []


# --- _write_train (idempotent merge) -----------------------------------------

def test_write_train_merges_by_id(tmp_path):
    out = tmp_path / "train.json"
    mod._write_train([{"id": "a", "x": 1}], out)
    mod._write_train([{"id": "b", "x": 2}, {"id": "a", "x": 99}], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in data}
    assert by_id["a"]["x"] == 99  # overwritten, not duplicated
    assert by_id["b"]["x"] == 2
    assert len(data) == 2


def test_write_train_creates_parent(tmp_path):
    out = tmp_path / "nested" / "deep" / "train.json"
    mod._write_train([{"id": "a"}], out)
    assert out.exists()


def test_write_train_sorts_by_id(tmp_path):
    out = tmp_path / "train.json"
    mod._write_train([{"id": "b"}, {"id": "a"}], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [d["id"] for d in data] == ["a", "b"]
