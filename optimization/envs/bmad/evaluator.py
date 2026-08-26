"""BMAD Benchmark Evaluator — scores rollout results against expected outcomes."""
from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip whitespace, collapse spaces."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def exact_match(prediction: str, ground_truth: str) -> bool:
    """Check if normalized prediction equals normalized ground truth."""
    return normalize_text(prediction) == normalize_text(ground_truth)


def contains_match(prediction: str, ground_truth: str) -> bool:
    """Check if ground truth is contained in prediction."""
    return normalize_text(ground_truth) in normalize_text(prediction)


def evaluate_task(item: dict, predicted_action: str) -> dict:
    """Evaluate a single benchmark task.

    Returns dict with 'hard' (0/1) and 'soft' (float 0-1) scores.
    """
    ground_truth = str(item.get("ground_truth") or "")
    hard_metric = str(item.get("hard_metric") or "exact_match")
    expected_action = str(item.get("expected_action") or "")

    # First check: did the model produce the expected action type?
    action_match = normalize_text(predicted_action) == normalize_text(expected_action)

    if hard_metric == "exact_match":
        hard = 1 if exact_match(predicted_action, ground_truth) else 0
    elif hard_metric == "contains":
        hard = 1 if contains_match(predicted_action, ground_truth) else 0
    elif hard_metric == "file_exists":
        # For file existence checks, the model should say "present" or "exists"
        hard = 1 if "present" in normalize_text(predicted_action) or "exists" in normalize_text(predicted_action) else 0
    elif hard_metric == "all_present":
        # For chain completeness, all links must be present
        hard = 1 if "complete" in normalize_text(predicted_action) or "present" in normalize_text(predicted_action) else 0
    else:
        hard = 1 if action_match else 0

    # Soft score: partial credit for correct action type even if wrong detail
    soft = 1.0 if action_match else 0.0

    return {"hard": hard, "soft": soft}
