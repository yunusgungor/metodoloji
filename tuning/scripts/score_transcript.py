#!/usr/bin/env python3
"""Bagimsiz transcript skorlayici — SkillOpt kurmadan evaluator'u dener.

Kullanim:
    python3 tuning/scripts/score_transcript.py <transcript.md> <item.json>
    python3 tuning/scripts/score_transcript.py <transcript.md> --item-id TRA-A01

Ikinci form item'i tuning/data/metodoloji_split/*/items.json icinden bulur.
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skillopt_env"))

from metodoloji.evaluator import evaluate  # noqa: E402

TUNING_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def find_item(item_id: str) -> dict:
    for path in glob.glob(os.path.join(TUNING_ROOT, "data", "metodoloji_split", "*", "items.json")):
        for item in json.load(open(path, encoding="utf-8")):
            if str(item.get("id")) == item_id:
                return item
    raise SystemExit(f"item bulunamadi: {item_id}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    transcript = open(sys.argv[1], encoding="utf-8").read()
    if sys.argv[2] == "--item-id":
        item = find_item(sys.argv[3])
    else:
        item = json.load(open(sys.argv[2], encoding="utf-8"))

    scores = evaluate(transcript, item)
    print(json.dumps(scores, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
