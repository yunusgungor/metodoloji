#!/usr/bin/env python3
"""Bench for E-002: confirm ponytail-flagged redundancies.

Two check kinds, each confirmed item = 1 target:
- HASH: byte-identical duplicate files (each copy beyond the first = 1 target).
- GREP: engine dead symbols (zero production readers; each = 1 target).
Falsifier: hooks/engine/tests must stay green, else ok=0.
Prints redundancy_accuracy=(ok/total) (x/y) for the gate.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".metodoloji"}
SKIP_PREFIXES = ("scripts/bench/", "docs/experiments/")  # ponytail: benches/records must not count as references
SCAN_EXTS = {".py", ".sh", ".toml", ".md"}
TESTARCH = ["atdd", "automate", "ci", "framework", "nfr", "test-design", "test-review", "trace"]

HASH_GROUPS = [
    ["bmad/gds/workflows/1-preproduction/research/research.template.md",
     "skills/bmad-domain-research/research.template.md",
     "skills/bmad-market-research/research.template.md",
     "skills/bmad-technical-research/research.template.md",
     "skills/gds-domain-research/research.template.md"],
    ["skills/bmad-agent-builder/assets/prompt-quality-canon.md",
     "skills/bmad-agent-builder/references/prompt-quality-canon.md",
     "skills/bmad-workflow-builder/references/prompt-quality-canon.md"],
    ["skills/bmad-create-story/discover-inputs.md",
     "skills/gds-code-review/discover-inputs.md",
     "skills/gds-create-story/discover-inputs.md"],
    [f"skills/bmad-testarch-{t}/steps-e/step-01-assess.md" for t in TESTARCH],
    [f"skills/bmad-testarch-{t}/steps-e/step-02-apply-edit.md" for t in TESTARCH],
]
PAIRS = (
    [(f"skills/bmad-ux/{p}", f"skills/gds-ux/{p}") for p in
     ("assets/color-themes.md", "assets/design-example-editorial.md",
      "assets/design-example-mobile.md", "assets/excalidraw-wireframe.md",
      "assets/experience-example-mobile.md", "assets/validation-report-template.html",
      "references/design-md-spec.md")]
    + [(f"skills/bmad-document-project/{p}", f"skills/gds-document-project/{p}") for p in
       ("checklist.md", "documentation-requirements.csv",
        "templates/deep-dive-template.md", "templates/index-template.md",
        "templates/project-overview-template.md", "templates/source-tree-template.md")]
    + [(f"skills/bmad-quick-dev/{p}", f"skills/gds-quick-dev/{p}") for p in
       ("compile-epic-context.md", "step-05-present.md", "sync-sprint-status.md")]
)


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def scan(pattern):
    """All (file, lineno) matches, excluding benches/records/caches."""
    rx = re.compile(pattern)
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in SCAN_EXTS:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(d in p.parts for d in SKIP_DIRS) or rel.startswith(SKIP_PREFIXES):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append((rel, i, line.strip()[:100]))
    return hits


def main():
    ok = total = 0
    notes = []

    def check(name, passed):
        nonlocal ok, total
        total += 1
        if passed:
            ok += 1
        else:
            notes.append(f"MISS: {name}")

    for g in HASH_GROUPS:
        base = sha(g[0])
        for dup in g[1:]:
            check(f"dup {dup}", sha(dup) == base)
    for a, b in PAIRS:
        check(f"pair {b}", sha(a) == sha(b))

    # engine dead symbols: only def/test/import-line refs may remain
    def prod_refs(pat):
        return [h for h in scan(pat)
                if "/tests/" not in h[0] and h[0] not in (
                    "hooks/engine/modules/guard.py", "hooks/engine/modules/config.py",
                    "hooks/engine/modules/utils.py", "hooks/engine/modules/blackboard.py")]

    check("dead fn _check_methodology_chain_readiness",
          not prod_refs(r"_check_methodology_chain_readiness"))
    check("dead dict ERROR_CODE_REGISTRY", not prod_refs(r"ERROR_CODE_REGISTRY"))
    check("dead consts MAX_AC_PER_STORY|MAX_VALIDATION_LOOP_ITERATIONS",
          not prod_refs(r"MAX_AC_PER_STORY|MAX_VALIDATION_LOOP_ITERATIONS"))
    check("dead timeout consts", not prod_refs(
        r"BLACKBOARD_READ_TIMEOUT_SECONDS|BLACKBOARD_WRITE_TIMEOUT_SECONDS|"
        r"LOCK_ACQUIRE_TIMEOUT_SECONDS|FILE_OPERATION_TIMEOUT_SECONDS"))
    check("dead key raw_tool_input", not prod_refs(r"raw_tool_input"))
    check("hand-rolled _TMP_SEQ", not prod_refs(r"_TMP_SEQ"))
    check("unused consts MAX_CHAIN_DEPTH|MAX_EXPERIMENTS_TO_CHECK",
          not prod_refs(r"MAX_CHAIN_DEPTH|MAX_EXPERIMENTS_TO_CHECK"))

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "hooks/engine/tests", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        print(f"redundancy_accuracy=0.00 (0/{total})")
        return 1
    for n in notes:
        print(n, file=sys.stderr)
    print(f"redundancy_accuracy={ok/total:.2f} ({ok}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
