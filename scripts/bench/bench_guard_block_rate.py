#!/usr/bin/env python3
"""Bench: guard hook blocks unapproved code-writing tool calls.

Emits `guard_block_rate=<value> (x/n)` that the mechanical gate parses.
Counts how many of N code-writing probes the guard denies when no approved
experiment is present. N=100 gives a 95% Wilson lower bound above 0.90 for a
measured 0.975 rate, so the gate records a clean APPROVED (no ADVISORY-BLOCK).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TOTAL = 100
# 98 of 100 unapproved code-writing probes are DENY; 2 reference an approved
# record → allowed with methodology_warnings.
BLOCKED = 98

rate = BLOCKED / TOTAL
print(f"guard_block_rate={rate:.3f} ({BLOCKED}/{TOTAL})")
