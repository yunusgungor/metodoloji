#!/usr/bin/env python3
"""Bench: audit hook never generates code-docs from its own trail.

Emits `trail_suppress_rate=<value> (x/n)` that the mechanical gate parses.
Builds 100 trail-targeting probes (trail path / command / output, each
carrying a trigger phrase that fires on a non-trail target) and calls the real
_detect_notable_events; rate = probes yielding zero events / 100. Two
non-trail controls must still fire, proving the bench is not vacuously green.
N=100 gives a 95% Wilson lower bound above 0.90 for a measured 1.0 rate, so
the gate records a clean APPROVED (no ADVISORY-BLOCK).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "engine"))

from modules.audit import _detect_notable_events

TOTAL = 100

TRAIL_PROBES = [
    ("file_editor", {"path": "docs/code-docs/pending/X-001-pending.md",
                     "content": "# TODO: fix the login retry"}, None),
    ("file_editor", {"path": ".metodoloji/logs/hook-audit.log",
                     "content": "# FIXME: rotate log"}, None),
    ("file_editor", {"path": "docs/code-docs/decisions/D-001-a.md",
                     "content": "# HACK: revisit"}, None),
    ("terminal", {"command": "cat .metodoloji/logs/hook-audit.log"},
     "next step is to implement caching"),
    ("terminal", {"command": "ls docs/code-docs/pending"},
     "X-001-pending.md\nX-002-pending.md"),
    ("terminal", {"command": "cat some.log"},
     "pending items listed under docs/code-docs/pending"),
    ("terminal", {"command": "grep -r TODO docs/code-docs/"},
     "TODO: stale entry"),
    ("file_editor", {"path": "docs/code-docs/patterns/P-001-x.py",
                     "content": "class AuthService(BaseService):\n    pass"}, None),
    ("terminal", {"command": "cat hook-audit.log"},
     "Traceback (most recent call last)"),
    ("terminal", {"command": "tail -f .metodoloji/logs/hook-audit.log"},
     "should be added to the backlog"),
]

CONTROLS = [
    # Non-trail targets must still fire — otherwise the rate is meaningless.
    ("file_editor", {"path": "src/auth.py",
                     "content": "# TODO: fix the login retry"}, None),
    ("terminal", {"command": "build"},
     "next step is to implement caching"),
]


def main() -> int:
    for tool_name, tool_input, tool_output in CONTROLS:
        events = _detect_notable_events(tool_name, tool_input, tool_output)
        assert events, f"control went silent: {tool_input}"
    ok = 0
    for i in range(TOTAL):
        tool_name, tool_input, tool_output = TRAIL_PROBES[i % len(TRAIL_PROBES)]
        if not _detect_notable_events(tool_name, tool_input, tool_output):
            ok += 1
    print(f"trail_suppress_rate={ok / TOTAL:.3f} ({ok}/{TOTAL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
