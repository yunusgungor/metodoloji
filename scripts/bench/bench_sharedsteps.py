#!/usr/bin/env python3
"""Bench for E-006: shared steps-e dedup across 8 testarch skills
(plus E-002's redundancy inventory re-confirmed on the deduped tree).

Each check = 1 target:
- SHARED: skills/bmad-tea/steps-e/{step-01,step-02} exist with recorded md5.
- GONE: per-skill steps-e dirs/files are gone (8 skills x 2 files + dir).
- LOAD: each SKILL.md points at the shared path (exactly 1 hit, no
  {skill-root}/steps-e remnant).
- STALE: no per-skill steps-e path references in .md/.py/.toml outside
  benches/records/caches.
- REDUND: E-002's hash-group + pair + dead-symbol inventory, adapted to the
  deduped tree (steps-e groups now resolve to the shared dir; research/
  discover/canon groups unchanged).
- SUITE: related pytest suites stay green (else ok=0).
Prints sharedsteps_accuracy=(ok/total) (x/y) for the gate.
"""
import hashlib
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
# step-01's nextStepFile line now points at the shared dir (the intended
# change); step-02 is untouched. LF-normalized (checkout may be CRLF).
MD5 = {"step-01-assess.md": None, "step-02-apply-edit.md": "06955f3f0b7cb2333b64783301bd66ff"}
NEXTSTEP = "nextStepFile: '{metodoloji-root}/skills/bmad-tea/steps-e/step-02-apply-edit.md'"
SHARED = "skills/bmad-tea/steps-e"
LOAD_LINE = ("Load `{metodoloji-root}/skills/bmad-tea/steps-e/"
             "step-01-assess.md`")


def md5(p):
    return hashlib.md5((ROOT / p).read_bytes()).hexdigest()


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

    for f, h in MD5.items():
        p = f"{SHARED}/{f}"
        try:
            raw = (ROOT / p).read_bytes().replace(b"\r\n", b"\n")
            same = hashlib.md5(raw).hexdigest() == (h or "")
            if f == "step-01-assess.md":
                # intended edit: only the nextStepFile line changed
                same = (NEXTSTEP in raw.decode("utf-8", "replace")
                        and raw.decode("utf-8", "replace").count(
                            "nextStepFile:") == 1)
            check(f"shared {f}", (ROOT / p).is_file() and same)
        except OSError:
            check(f"shared {f}", False)

    for t in TESTARCH:
        d = ROOT / f"skills/bmad-testarch-{t}/steps-e"
        check(f"gone {t}/steps-e", not d.exists())
        sk = ROOT / f"skills/bmad-testarch-{t}/SKILL.md"
        try:
            txt = sk.read_text(encoding="utf-8")
            check(f"load {t}", txt.count(LOAD_LINE) == 1
                  and "{skill-root}/steps-e" not in txt)
        except OSError:
            check(f"load {t}", False)

    stale = [h for h in scan(r"bmad-testarch-[a-z-]+/steps-e/")
             if not h.startswith("skills/bmad-tea/")]
    check("no stale per-skill refs", not stale, f"-> {stale[:5]}")

    # E-002 inventory on the deduped tree (steps-e groups -> shared dir).
    def sha(p):
        return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()

    e2_groups = [
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
    ]
    for g in e2_groups:
        try:
            base = sha(g[0])
            for dup in g[1:]:
                check(f"redund dup {dup}", sha(dup) == base)
        except OSError as e:
            check(f"redund group {g[0]}", False, str(e)[:60])
    e2_pairs = (
        [(f"skills/bmad-ux/{p}", f"skills/gds-ux/{p}") for p in
         ("assets/color-themes.md", "assets/design-example-editorial.md",
          "assets/design-example-mobile.md", "assets/excalidraw-wireframe.md",
          "assets/experience-example-mobile.md",
          "assets/validation-report-template.html",
          "references/design-md-spec.md")]
        + [(f"skills/bmad-document-project/{p}", f"skills/gds-document-project/{p}")
           for p in ("checklist.md", "documentation-requirements.csv",
                     "templates/deep-dive-template.md", "templates/index-template.md",
                     "templates/project-overview-template.md",
                     "templates/source-tree-template.md")]
        + [(f"skills/bmad-quick-dev/{p}", f"skills/gds-quick-dev/{p}") for p in
           ("compile-epic-context.md", "step-05-present.md", "sync-sprint-status.md")]
    )
    for a, b in e2_pairs:
        try:
            check(f"redund pair {b}", sha(a) == sha(b))
        except OSError as e:
            check(f"redund pair {b}", False, str(e)[:60])

    def prod_refs(pat):
        return [h for h in scan(pat)
                if "/tests/" not in h and h not in (
                    "hooks/engine/modules/guard.py", "hooks/engine/modules/config.py",
                    "hooks/engine/modules/utils.py", "hooks/engine/modules/blackboard.py")]

    check("redund dead fn", not prod_refs(r"_check_methodology_chain_readiness"))
    check("redund dead dict", not prod_refs(r"ERROR_CODE_REGISTRY"))
    check("redund dead consts", not prod_refs(
        r"MAX_AC_PER_STORY|MAX_VALIDATION_LOOP_ITERATIONS"))
    check("redund dead timeouts", not prod_refs(
        r"BLACKBOARD_READ_TIMEOUT_SECONDS|BLACKBOARD_WRITE_TIMEOUT_SECONDS|"
        r"LOCK_ACQUIRE_TIMEOUT_SECONDS|FILE_OPERATION_TIMEOUT_SECONDS"))
    check("redund dead key", not prod_refs(r"raw_tool_input"))
    check("redund _TMP_SEQ", not prod_refs(r"_TMP_SEQ"))
    check("redund unused consts", not prod_refs(
        r"MAX_CHAIN_DEPTH|MAX_EXPERIMENTS_TO_CHECK"))

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "bmad/tests",
         "skills/bmad-customize/scripts/tests",
         "skills/bmad-workflow-builder/scripts/tests",
         "hooks/engine/tests", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        print(f"sharedsteps_accuracy=0.00 (0/{total})")
        return 1
    for x in notes:
        print(x, file=sys.stderr)
    print(f"sharedsteps_accuracy={ok/total:.2f} ({ok}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
