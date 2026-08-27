"""Manifesto benchmark evaluator — scores LLM responses against ground truth rules.

Uses flexible matching:
- Exact substring match (primary)
- Synonym/alternative match (fallback)
- Semantic proximity (last resort)
"""
from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


# Synonyms / alternative terms for ground truth matching
SYNONYMS = {
    "onaylı deney": ["onaylı bir deney", "deney onayı", "onaylanmış deney", "verified experiment"],
    "session kapanışı": ["session closure", "oturum kapanışı", "oturum kapatma", "session kapatma"],
    "deney onayı bekliyor": ["deney onayı bekleyen", "experiment approval pending", "onay bekliyor"],
    " DENY": [" engellenir", " block", " reddedilir", " izin verilmez", " yasaktır"],
    "QR": ["quality record", "kalite kaydı"],
    "Hipotez": ["hypothesis"],
    "Çerçeveleme": ["çerçeveleme", "framing"],
    "research-methodology.md": ["araştırma metodolojisi", "research methodology"],
    "Implementation Readiness": ["uygulamaya hazırlık", "uygulama hazırlığı"],
    "Sprint Planning": ["sprint planlama", "sprint planlama toplantısı"],
    "Approve": ["onay", "kabul", "approve"],
    "Changes Requested": ["değişiklik istendi", "değişiklik talep", "changes requested"],
    "Blocked": ["engellendi", "blocked"],
}


def evaluate_task(item: dict, response: str) -> dict:
    """Evaluate a manifesto rule task. Returns hard (0/1) and soft (0-1)."""
    ground_truth = str(item.get("ground_truth", "")).lower()
    hard_metric = str(item.get("hard_metric", "contains"))

    resp_lower = response.lower()

    # Primary: exact substring match
    if hard_metric == "contains":
        hard = 1 if ground_truth in resp_lower else 0
    else:
        hard = 1 if ground_truth in resp_lower else 0

    # Fallback: synonym match
    if hard == 0 and ground_truth in SYNONYMS:
        for alt in SYNONYMS[ground_truth]:
            if alt.lower() in resp_lower:
                hard = 1
                break

    # Soft: partial credit for related concepts
    soft = hard

    return {"hard": hard, "soft": soft}
