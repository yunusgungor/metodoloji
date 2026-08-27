"""Manifesto benchmark evaluator — scores LLM responses against ground truth rules."""
from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def evaluate_task(item: dict, response: str) -> dict:
    """Evaluate a manifesto rule task. Returns hard (0/1) and soft (0-1)."""
    ground_truth = str(item.get("ground_truth", "")).lower()
    hard_metric = str(item.get("hard_metric", "contains"))

    upper = response.lower()

    if hard_metric == "contains":
        hard = 1 if ground_truth in upper else 0
    else:
        hard = 1 if ground_truth in upper else 0

    # Soft: partial credit if the model mentions related concepts
    soft = hard  # Simple: same as hard for this use case

    return {"hard": hard, "soft": soft}
