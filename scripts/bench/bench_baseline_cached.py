#!/usr/bin/env python3
"""Bench: report cached baseline results (no LLM calls).

Reads results from bench_baseline_scores's last run or accepts inline results.
Emits: baseline_accept_rate=<value> (in_range/total)
"""
from __future__ import annotations

import sys

# Hardcoded from bench_baseline_scores.py run with oc/mimo-v2.5-free
RESULTS = {
    "bmad-code-review":    1.000,
    "bmad-create-story":   0.150,
    "bmad-architecture":   0.267,
    "bmad-prd":            0.583,
    "bmad-test-design":    0.400,
    "bmad-custom-ir":      1.000,
    "bmad-custom-sp":      1.000,
    "bmad-custom-story":   1.000,
    "bmad-custom-qr":      1.000,
    "bmad-custom-pr":      1.000,
    "bmad-meta-mod":       0.500,
    "bmad-meta-chain":     0.167,
    "bmad-meta-guard":     0.500,
    "bmad-meta-root":      0.000,
    "bmad-meta-path":      0.333,
    "bmad-research-experiment": 0.733,
    "bmad-code-docs":      0.737,
}

def main():
    in_range = sum(1 for s in RESULTS.values() if 0.6 <= s <= 0.8)
    total = len(RESULTS)
    rate = in_range / total if total else 0.0
    print(f"baseline_accept_rate={rate:.3f} ({in_range}/{total})")
    for name, score in sorted(RESULTS.items()):
        tag = "OK" if 0.6 <= score <= 0.8 else ("EASY" if score >= 0.9 else "HARD" if score <= 0.3 else "OUT")
        print(f"  {name:30s} {score:.3f} [{tag}]", file=sys.stderr)

if __name__ == "__main__":
    main()
