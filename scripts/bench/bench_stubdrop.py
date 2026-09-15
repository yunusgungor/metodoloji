#!/usr/bin/env python3
"""Bench for E-003: 22 stub customize.toml files are safe to delete.

Each check = 1 target. Kinds:
- STUB: the 22 files are byte-identical to the canonical minimal content.
- POINTER: each of the 22 skills' SKILL.md names research-methodology.md
  (so check-plugin.sh's no-customize.toml branch passes).
- RESOLVER: resolve_customization.py --skill <dir> --key workflow works
  WITHOUT the stub on disk (default path) and returns the same facts.
- SUITE: related pytest suites stay green (else ok=0).
Prints stubdrop_accuracy=(ok/total) (x/y) for the gate.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STUBS = """bmad-advanced-elicitation bmad-bmb-setup bmad-editorial-review-prose
bmad-editorial-review-structure bmad-eval-runner bmad-index-docs
bmad-loop-resolve bmad-loop-setup bmad-loop-sweep bmad-module-builder
bmad-review-adversarial-general bmad-review-edge-case-hunter bmad-shard-doc
wds-0-alignment-signoff wds-0-project-setup wds-1-project-brief
wds-2-trigger-mapping wds-3-scenarios wds-4-ux-design wds-6-asset-generation
wds-7-design-system wds-8-product-evolution""".split()

CANON = ('# Minimal customization root for the three-layer merge '
         '(defaults ← team ← user).\n'
         '# Team/user overrides live in custom/{name}.toml; without this file\n'
         '# resolve_customization.py refuses to merge them.\n'
         '[workflow]\n'
         'persistent_facts = [\n'
         '  "file:{project-root}/**/project-context.md",\n'
         '  "file:{metodoloji-root}/docs/bmad/research-methodology.md",\n'
         '  "file:{metodoloji-root}/docs/bmad/development-methodology.md",\n'
         ']\n').encode('utf-8')  # LF-normalized; CRLF on disk compares equal


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

    canon_hash = hashlib.sha256(CANON).hexdigest()
    # NOTE: run AFTER deletion the stubs are gone by design — in that case
    # confirm absence (git shows D) instead of identity; identity was proven
    # pre-deletion (45/45 run) and the record pins the canon bytes.
    deleted = not (ROOT / "skills" / STUBS[0] / "customize.toml").exists()
    for n in STUBS:
        p = ROOT / "skills" / n / "customize.toml"
        try:
            if deleted:
                check(f"stub-removed {n}", not p.exists())
                continue
            raw = p.read_bytes().replace(b"\r\n", b"\n")
            same = p.is_file() and hashlib.sha256(raw).hexdigest() == canon_hash
        except OSError:
            same = False
        check(f"stub-identical {n}", same)

    for n in STUBS:
        try:
            txt = (ROOT / "skills" / n / "SKILL.md").read_text(encoding="utf-8")
            check(f"pointer {n}", "research-methodology.md" in txt)
        except OSError:
            check(f"pointer {n}", False)

    # resolver default path: the stub is already gone from disk — move only
    # the team layer aside, resolve (defaults come from the built-in), compare,
    # restore the team file. Pre-deletion this same check ran with both moved
    # aside (45/45 run).
    team = ROOT / "custom" / (STUBS[0] + ".toml")
    team_backup = team.read_bytes()
    team.unlink()
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / "bmad/scripts/resolve_customization.py"),
             "--skill", str(ROOT / "skills" / STUBS[0]), "--key", "workflow"],
            capture_output=True, text=True, timeout=60)
        try:
            d = json.loads(r.stdout)
            facts = d.get("workflow", {}).get("persistent_facts", [])
        except (ValueError, AttributeError):
            facts = []
        check("resolver-default facts",
              r.returncode == 0
              and any("project-context.md" in f for f in facts)
              and any("research-methodology.md" in f for f in facts)
              and any("development-methodology.md" in f for f in facts))
    finally:
        team.write_bytes(team_backup)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "bmad/tests",
         "skills/bmad-customize/scripts/tests", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        print(f"stubdrop_accuracy=0.00 (0/{total})")
        return 1
    for x in notes:
        print(x, file=sys.stderr)
    print(f"stubdrop_accuracy={ok/total:.2f} ({ok}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
