"""Tests for bmad_benchmarks/envs/_base_/rollout.py — scoring utilities."""

import importlib.util
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent / "envs" / "_base_"
sys.path.insert(0, str(_BASE))

from rollout import normalize_field_label, score_field_presence  # noqa: E402


def test_normalize_field_label_lowercases_and_strips():
    assert normalize_field_label("  Date  ") == "date"
    assert normalize_field_label("(E-XXX)") == "e-xxx"
    assert normalize_field_label("Status:") == "status"


def test_score_field_presence_full_match():
    output = "## Date: 2026-01-01\n## Status: done\n## Decision: approved"
    expected = ["Date", "Status", "Decision"]
    hard, soft = score_field_presence(output, expected)
    assert hard == 1
    assert soft == 1.0


def test_score_field_presence_partial_match():
    output = "## Date: 2026-01-01"
    expected = ["Date", "Status", "Decision"]
    hard, soft = score_field_presence(output, expected)
    assert hard == 0
    assert soft == 1 / 3


def test_score_field_presence_threshold():
    output = "## Date: x\n## Status: y\n## Decision: z"
    expected = ["Date", "Status", "Decision"]
    # 3/3 found -> pass even at high threshold
    assert score_field_presence(output, expected, threshold=0.9) == (1, 1.0)
    output2 = "## Date: x\n## Status: y"
    assert score_field_presence(output2, expected, threshold=0.9) == (0, 2 / 3)


def test_score_field_presence_empty_expected():
    assert score_field_presence("anything", []) == (1, 1.0)
