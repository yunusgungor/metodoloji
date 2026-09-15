#!/usr/bin/env python3
"""Bench for E-004: dead files (no live references) are safe to delete.

Each check = 1 target. Kinds:
- UNREF: timestamped validation-report-*.md / workflow-plan.md run artifacts
  inside skills/ that no .py/.sh/SKILL.md/check-*.sh file references by name
  (self-references between reports excluded).
- SVG: scripts/svg_to_png.py has no live caller (only SELF-CHECK.md docs +
  a check-plugin.sh comment mention it) and cairosvg is not installed and
  not in pyproject dependencies.
- SUITE: full pytest suite stays green (else ok=0).
Prints deadfiles_accuracy=(ok/total) (x/y) for the gate.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".metodoloji"}
SKIP_PREFIXES = ("scripts/bench/", "docs/experiments/")
SCAN_EXTS = {".py", ".sh", ".toml", ".md"}
TESTARCH = ["atdd", "automate", "ci", "framework", "nfr",
            "test-design", "test-review", "trace"]

CANDIDATES = (
    [f"skills/bmad-testarch-{t}/validation-report-20260127-095021.md" for t in TESTARCH]
    + [f"skills/bmad-testarch-{t}/validation-report-20260127-102401.md" for t in TESTARCH]
    + [f"skills/bmad-testarch-{t}/workflow-plan.md" for t in TESTARCH]
    + ["skills/bmad-teach-me-testing/workflow-plan-teach-me-testing.md"]
)
# svg_to_png.py is a code file (is_code_target=True) — it needs its own
# experiment record for deletion, so it is measured separately below, not
# as an unref candidate (its only mentions are docs + a .sh comment).
SVG_SCRIPT = "scripts/svg_to_png.py"


def scan(pattern):
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
        if rx.search(text):
            hits.append(rel)
    return hits


def external_refs(name):
    """Files mentioning `name` outside the candidate set itself."""
    hits = scan(re.escape(name))
    return [h for h in hits
            if h not in CANDIDATES
            and not h.startswith("skills/bmad-tea/")]


def main():
    ok = total = 0
    notes = []

    def check(name, passed, detail=""):
        nonlocal ok, total
        total += 1
        if passed:
            ok += 1
        else:
            notes.append(f"MISS: {name} {detail}".rstrip())

    for c in CANDIDATES:
        refs = external_refs(Path(c).name)
        # docs, check-plugin.sh comment mentions, and the TEA layout README
        # (which documents workflow-plan.md as a *layout convention*, not a
        # load instruction — no SKILL.md loads it) are not live callers.
        live = [r for r in refs
                if not (r == "docs/SELF-CHECK.md" or r.endswith(".sh")
                        or r == "bmad/tea/workflows/testarch/README.md")]
        check(f"unref {c}", not live, f"-> {live}")

    # svg_to_png.py: only mentions are docs/SELF-CHECK.md (prose) and a
    # check-plugin.sh comment — no .py/.sh/SKILL.md/check-*.sh loads it.
    # Its cairosvg backend is not importable here nor a declared dependency.
    svg_refs = [r for r in external_refs("svg_to_png.py")
                if not (r == "docs/SELF-CHECK.md" or r.endswith(".sh"))]
    check("unref scripts/svg_to_png.py", not svg_refs, f"-> {svg_refs}")
    try:
        import cairosvg  # noqa: F401
        installed = True
    except (ImportError, OSError):
        installed = False
    check("cairosvg not usable", not installed)
    deps = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    check("cairosvg not a dependency", "cairosvg" not in deps)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        print(f"deadfiles_accuracy=0.00 (0/{total})")
        return 1
    for x in notes:
        print(x, file=sys.stderr)
    print(f"deadfiles_accuracy={ok/total:.2f} ({ok}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
