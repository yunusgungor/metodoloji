"""Tests for skills/bmad-research-experiment/scripts/run_experiment.py.

Covers the pure helpers the module's --selfcheck does NOT exercise: record
parsing, hypothesis/claim extraction, uncertainty notes, metric naming, and
the advisory-block / legacy-token verify paths.
"""

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import run_experiment as gate  # noqa: E402


# --- record_fields ----------------------------------------------------------

def test_record_fields_parses_bold_lines():
    text = "- **Status:** planned\n- **Theory:** T\n- **Hypothesis:** H-001: \"x >= 0.9\"\n"
    fields = gate.record_fields(text)
    assert fields["Status"] == "planned"
    assert fields["Theory"] == "T"
    assert fields["Hypothesis"] == 'H-001: "x >= 0.9"'


def test_record_fields_ignores_non_bold():
    assert gate.record_fields("## Experiment: E-001\nplain line\n") == {}


def test_record_fields_multiline_value_only_first_line():
    fields = gate.record_fields("- **Theory:** first line\n  continuation\n")
    assert fields["Theory"] == "first line"


# --- deney_id / hypothesis_claim -------------------------------------------

def test_deney_id():
    assert gate.deney_id("## Experiment: E-042\n") == "E-042"
    assert gate.deney_id("no id") == "E-?"


def test_hypothesis_claim_quoted():
    hid, claim = gate.hypothesis_claim('H-001: "accuracy >= 0.90"')
    assert (hid, claim) == ("H-001", "accuracy >= 0.90")


def test_hypothesis_claim_unquoted_tail():
    hid, claim = gate.hypothesis_claim("H-007: accuracy >= 0.80")
    assert (hid, claim) == ("H-007", "accuracy >= 0.80")


def test_hypothesis_claim_no_colon_uses_tail():
    # A claim with whitespace but no H-id/colon falls back to the tail regex:
    # the text before the first separator is dropped, the rest is the claim.
    hid, claim = gate.hypothesis_claim("no id or claim")
    assert hid == "H-?"
    assert claim == "id or claim"


def test_hypothesis_claim_truly_empty_raises():
    with pytest.raises(ValueError):
        gate.hypothesis_claim("")


# --- parse_claim / evaluate ------------------------------------------------

def test_parse_claim_operators():
    assert gate.parse_claim("x >= 0.90") == (0.90, ">=")
    assert gate.parse_claim("x == 1") == (1.0, "==")
    assert gate.parse_claim("x < 5") == (5.0, "<")


def test_parse_claim_no_operator_raises():
    with pytest.raises(ValueError):
        gate.parse_claim("x is fine")


def test_parse_claim_bad_number_raises():
    with pytest.raises(ValueError):
        gate.parse_claim("x >= abc")


def test_evaluate_passes_and_fails():
    assert gate.evaluate("accuracy >= 0.90", 0.93)[0] is True
    assert gate.evaluate("accuracy >= 0.90", 0.87)[0] is False
    assert gate.evaluate("x == 1", 1)[0] is True


# --- uncertainty_note -------------------------------------------------------

def test_uncertainty_lower_bound_claim_no_note():
    # A lower-bound claim (<=, <) has no small-sample risk.
    note = gate.uncertainty_note(35, 40, 0.875, 0.8, "<=")
    assert "none" in note


def test_uncertainty_small_sample_flags():
    note = gate.uncertainty_note(3, 3, 1.0, 0.90, ">=")
    assert "small sample" in note


def test_uncertainty_adequate_sample_ok():
    # n=40 perfect (40/40) clears a 0.90 upper-threshold claim; 38/40 does not
    # (Wilson bound 0.83 < 0.90), so 38/40 is correctly flagged small-sample.
    assert "none" in gate.uncertainty_note(40, 40, 1.0, 0.90, ">=")
    assert "small sample" in gate.uncertainty_note(38, 40, 0.95, 0.90, ">=")


def test_uncertainty_unknown_n():
    assert "n unknown" in gate.uncertainty_note(None, None, 0.9, 0.8, ">=")


def test_uncertainty_inconsistent():
    note = gate.uncertainty_note(1, 10, 0.9, 0.5, ">=")
    assert "inconsistent" in note


# --- metric naming ----------------------------------------------------------

def test_metric_stem():
    assert gate.metric_stem("llm_overnight_accuracy") == "llm_overnight"
    assert gate.metric_stem("plain") == "plain"


def test_claim_metric_name():
    assert gate.claim_metric_name("llm_overnight_accuracy >= 0.90") == "llm_overnight"
    assert gate.claim_metric_name("no op here") == ""


# --- MEASURED_RE ------------------------------------------------------------

def test_measured_re_with_fraction():
    m = gate.MEASURED_RE.search("metric_accuracy=0.93 (14/15)")
    assert (m.group(2), m.group(3), m.group(4)) == ("0.93", "14", "15")


def test_measured_re_without_fraction():
    m = gate.MEASURED_RE.search("metric_score=0.80")
    assert (m.group(2), m.group(3), m.group(4)) == ("0.80", None, None)


def test_measured_re_negative():
    assert gate.MEASURED_RE.search("nothing here") is None


# --- gate_token -------------------------------------------------------------

def test_gate_token_deterministic():
    a = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k")
    b = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k")
    assert a == b


def test_gate_token_binds_cmd():
    a = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k")
    b = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k", "cmd")
    assert a != b


def test_gate_token_binds_scope():
    a = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k", "cmd", "src/**")
    b = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k", "cmd", "src/**,lib/**")
    assert a != b


def test_verify_scope_widening_forges(tmp_path, monkeypatch):
    # Approved for "none", then scope widened post-approval → FORGED.
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _write_approved(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Code Scope:**", "src/**")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 1


def test_gate_token_differs_by_secret():
    a = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k1")
    b = gate.gate_token("c >= 0.9", 1.0, "E-X", b"k2")
    assert a != b


# --- upsert ----------------------------------------------------------------

def test_upsert_replaces_existing():
    lines = ["- **Decision:** old", "- **Status:** planned"]
    new = gate.upsert(lines, "- **Decision:**", "APPROVED")
    assert new[0] == "- **Decision:** APPROVED"
    assert len(new) == 2


def test_upsert_appends_missing():
    lines = ["- **Status:** planned"]
    new = gate.upsert(lines, "- **Decision:**", "APPROVED")
    assert new[-1] == "- **Decision:** APPROVED"


# --- bench_in_free_zone -----------------------------------------------------

def test_bench_in_free_zone():
    assert gate.bench_in_free_zone("python3 scratch/bench.py") is True
    assert gate.bench_in_free_zone("python3 tmp/bench.py") is True
    assert gate.bench_in_free_zone("python3 src/bench.py data.csv") is False
    assert gate.bench_in_free_zone("sh scripts/bench.sh") is False
    assert gate.bench_in_free_zone("python3 -c 'print(1)'") is False


# --- verify paths beyond selfcheck -----------------------------------------

def _draft_record(tmp_path, eid="E-001"):
    rec = tmp_path / f"{eid}.md"
    rec.write_text(
        f"## Experiment: {eid}\n"
        "- **Status:** planned\n"
        "- **Theory:** T\n"
        '- **Hypothesis:** H-001: "fake_accuracy >= 0.90"\n'
        "- **Measurement Metrics:** fake_accuracy >= 0.90\n"
        "- **Experiment Design:** unit\n"
        "- **Code Scope:** none\n",
        encoding="utf-8",
    )
    return rec


def _write_approved(tmp_path, secret=b"test-secret", cmd="run x"):
    """Create a record the gate has approved under `secret` and `cmd`."""
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Raw Results:**", "measured=1.0; n=40")
    lines = gate.upsert(lines, "- **Uncertainty:**", "none (adequate)")
    lines = gate.upsert(lines, "- **Metric:**", "consistent")
    lines = gate.upsert(lines, "- **Measurement Command:**", cmd)
    tok = gate.gate_token("fake_accuracy >= 0.90", 1.0, "E-001", secret, cmd, "none")
    lines = gate.upsert(lines, "- **Decision:**", "APPROVED — H-001: measured=1.0 >= threshold=0.90")
    lines = gate.upsert(
        lines, "- **Gate Evidence:**",
        f'measured=1.0 claim="fake_accuracy >= 0.90" {tok}')
    lines = gate.upsert(lines, "- **Next Step:**", "Proceed to Code")
    lines = gate.upsert(lines, "- **Status:**", "completed")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rec


def test_verify_missing_secret_returns_3(tmp_path, monkeypatch):
    monkeypatch.delenv("BMAD_GATE_KEY", raising=False)
    # Point SECRET_FILE away so no key is found.
    monkeypatch.setattr(gate, "SECRET_FILE", str(tmp_path / "no-key"))
    rec = _write_approved(tmp_path)
    assert gate.verify(str(rec)) == 3


def test_verify_small_sample_advisory_block(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Raw Results:**", "measured=0.91; n=4")
    lines = gate.upsert(lines, "- **Uncertainty:**", "n=4 (small sample: 95% Wilson lower bound 0.55 < threshold 0.9)")
    lines = gate.upsert(lines, "- **Metric:**", "consistent")
    lines = gate.upsert(lines, "- **Measurement Command:**", "cmd")
    tok = gate.gate_token("fake_accuracy >= 0.90", 0.91, "E-001", b"test-secret", "cmd", "none")
    lines = gate.upsert(lines, "- **Decision:**", "APPROVED — H-001: measured=0.91 >= threshold=0.90")
    lines = gate.upsert(lines, "- **Gate Evidence:**", f'measured=0.91 claim="fake_accuracy >= 0.90" {tok}')
    lines = gate.upsert(lines, "- **Next Step:**", "Proceed to Code")
    lines = gate.upsert(lines, "- **Status:**", "completed")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 2  # ADVISORY-BLOCK


def test_verify_metric_mismatch_advisory_block(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Raw Results:**", "measured=1.0; n=40")
    lines = gate.upsert(lines, "- **Uncertainty:**", "none (n=40)")
    lines = gate.upsert(lines, "- **Metric:**", "MISMATCH — measured other_metric, claimed fake_accuracy")
    lines = gate.upsert(lines, "- **Measurement Command:**", "cmd")
    tok = gate.gate_token("fake_accuracy >= 0.90", 1.0, "E-001", b"test-secret", "cmd", "none")
    lines = gate.upsert(lines, "- **Decision:**", "APPROVED — H-001: measured=1.0 >= threshold=0.90")
    lines = gate.upsert(lines, "- **Gate Evidence:**", f'measured=1.0 claim="fake_accuracy >= 0.90" {tok}')
    lines = gate.upsert(lines, "- **Next Step:**", "Proceed to Code")
    lines = gate.upsert(lines, "- **Status:**", "completed")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 2


def test_verify_legacy_token_without_cmd(tmp_path, monkeypatch):
    # A record with no Measurement Command field must verify via the legacy
    # (non-command-bound) token.
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Raw Results:**", "measured=1.0; n=40")
    lines = gate.upsert(lines, "- **Uncertainty:**", "none (n=40)")
    lines = gate.upsert(lines, "- **Metric:**", "consistent")
    tok = gate.gate_token("fake_accuracy >= 0.90", 1.0, "E-001", b"test-secret")
    lines = gate.upsert(lines, "- **Decision:**", "APPROVED — H-001: measured=1.0 >= threshold=0.90")
    lines = gate.upsert(lines, "- **Gate Evidence:**", f'measured=1.0 claim="fake_accuracy >= 0.90" {tok}')
    lines = gate.upsert(lines, "- **Next Step:**", "Proceed to Code")
    lines = gate.upsert(lines, "- **Status:**", "completed")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 0


def test_verify_rejected_returns_1(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Decision:**", "REJECTED — H-001: gate FAIL")
    lines = gate.upsert(lines, "- **Status:**", "REJECTED")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 1


def test_verify_undecided_returns_1(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    assert gate.verify(str(rec)) == 1


def test_verify_template_placeholder_is_undecided(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Decision:**", "<gate writes: APPROVED | REJECTED — reason>")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 1  # undecided, not forged-APPROVED


def test_verify_approved_without_evidence_forged(tmp_path, monkeypatch):
    monkeypatch.setenv("BMAD_GATE_KEY", "test-secret")
    rec = _draft_record(tmp_path)
    text = rec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    lines = gate.upsert(lines, "- **Decision:**", "APPROVED — H-001: measured=1.0 >= threshold=0.90")
    lines = gate.upsert(lines, "- **Status:**", "completed")
    rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert gate.verify(str(rec)) == 1  # APPROVED without token -> forged


def test_scope_matches():
    assert gate.scope_matches("src/**", "src/foo.py")
    assert gate.scope_matches("src/**", "src/engine/foo.py")
    assert not gate.scope_matches("src/**", "tests/foo.py")
    assert gate.scope_matches("src/*.py", "src/foo.py")
    assert not gate.scope_matches("src/*.py", "src/foo/bar.py")
    assert gate.scope_matches("src/**", "src\\engine\\foo.py")


def test_record_scope(tmp_path):
    rec = tmp_path / "E.md"
    rec.write_text("- **Code Scope:** src/**,tests/*\n", encoding="utf-8")
    assert gate.record_scope(str(rec)) == "src/**,tests/*"
    assert gate.record_scope(str(tmp_path / "missing.md")) == ""
