#!/usr/bin/env python3
"""Bench for E-001: confirm ponytail-flagged engine targets are dead code.

Checks each target for production references (grep) and runs the engine
pytest suite. Prints cleanup_accuracy=(confirmed/total) (x/y) for the gate.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (file, pattern, allowed-ref-dirs): confirmed dead when every remaining match
# is either the definition site itself or inside an allowed dir.
TARGETS = [
    # dead fn: zero callers (only a comment mention + these bench lines)
    ("hooks/engine/modules/guard.py", r"_check_methodology_chain_readiness", ["tests", "bench"]),
    # dead dict: only test imports asserting its keys, zero production reads
    ("hooks/engine/modules/config.py", r"ERROR_CODE_REGISTRY", ["tests", "bench"]),
    # dead timeout consts: defined, never imported anywhere
    ("hooks/engine/modules/config.py", r"BLACKBOARD_READ_TIMEOUT_SECONDS|BLACKBOARD_WRITE_TIMEOUT_SECONDS|LOCK_ACQUIRE_TIMEOUT_SECONDS|FILE_OPERATION_TIMEOUT_SECONDS", ["tests", "bench"]),
    # notebook_editor: live (stop.py touched-set + utils normalize handle it);
    # only guard's _notebook_content_to_text helper is a dup of str(content)
    ("hooks/engine/modules/guard.py", r"_notebook_content_to_text", ["tests", "bench"]),
    # dead passthrough key: written by normalize, never read by any caller
    ("hooks/engine/modules/utils.py", r"raw_tool_input", ["tests", "bench"]),
    # hand-rolled tmp seq: itertools.count where tempfile.mkstemp belongs
    ("hooks/engine/modules/blackboard.py", r"_TMP_SEQ", ["tests", "bench"]),
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
SKIP_FILES = {"scripts/bench/bench_ponytail.py"}  # ponytail: bench must not count its own grep patterns as references


def files_with(pattern, skip_file):
    rx = re.compile(pattern)
    hits = []
    for p in ROOT.rglob("*.py"):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in SKIP_FILES or p == skip_file:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if rx.search(text):
            hits.append(p.relative_to(ROOT).as_posix())
    return hits


def main():
    confirmed = 0
    total = 0
    for rel, pattern, allowed in TARGETS:
        total += 1
        skip = ROOT / rel
        hits = files_with(pattern, skip)
        # self-file references + test dirs are allowed; anything else blocks
        prod = [h for h in hits if not any(a in h for a in allowed)]
        # definition lives in skip file itself — remaining question is prod use
        if not prod:
            confirmed += 1
        else:
            print(f"ALIVE: {rel} :: {pattern} -> {prod}", file=sys.stderr)
    # falsifier: full engine suite must stay green on the untouched tree
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "hooks/engine/tests", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    suite_green = proc.returncode == 0
    if not suite_green:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
    ok = confirmed if suite_green else 0
    print(f"cleanup_accuracy={ok/total:.2f} ({ok}/{total})")
    return 0 if suite_green else 1


if __name__ == "__main__":
    sys.exit(main())
