#!/usr/bin/env python3
"""check-handoff.py — static handoff wiring lint (skill <-> chain contract).

Every CHAIN / METHODOLOGY_CHAIN member's SKILL.md must:
  - peek its own channel:  "handoffs --skill <self>"
    (origin skill bmad-research-experiment is exempt — it starts the relay)
  - post the next hop:     "handoff --to <next>"
    (terminal skills bmad-code-review / bmad-production-readiness are exempt)
The bridge skill bmad-create-story fans out (dev-story + quality-record),
so it must post BOTH.

Usage:  python scripts/check-handoff.py [--negtest]
Output: [OK] / [WARNING] / [ERROR] lines; exit 0 clean, 1 problems.
"""

import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN / "skills"

# skill -> expected --to targets; [] = terminal (no post required)
EXPECTED_POSTS = {
    "bmad-prd": ["bmad-ux"],
    "bmad-ux": ["bmad-architecture"],
    "bmad-architecture": ["bmad-spec"],
    "bmad-spec": ["bmad-create-epics-and-stories"],
    "bmad-create-epics-and-stories": ["bmad-create-story"],
    "bmad-create-story": ["bmad-dev-story", "bmad-quality-record"],  # bridge fan-out
    "bmad-dev-story": ["bmad-code-review"],
    "bmad-code-review": [],  # terminal
    "bmad-research-experiment": ["bmad-check-implementation-readiness"],  # origin
    "bmad-check-implementation-readiness": ["bmad-sprint-planning"],
    "bmad-sprint-planning": ["bmad-create-story"],
    "bmad-quality-record": ["bmad-production-readiness"],
    "bmad-production-readiness": [],  # terminal
}
PEEK_EXEMPT = {"bmad-research-experiment"}  # origin: nothing upstream to peek


def check() -> int:
    problems = 0
    for skill, wants in EXPECTED_POSTS.items():
        md = SKILLS / skill / "SKILL.md"
        if not md.is_file():
            print(f"[ERROR] {skill}: SKILL.md missing")
            problems += 1
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        # step files carry the close-out handoff for some skills (readiness,
        # epics) — read the whole skill dir for --to, SKILL.md only for peek.
        blob = text
        steps = SKILLS / skill / "steps"
        if steps.is_dir():
            for f in steps.glob("*.md"):
                try:
                    blob += "\n" + f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
        if skill not in PEEK_EXEMPT:
            if f"handoffs --skill {skill}" not in text:
                print(f"[ERROR] {skill}: missing peek 'handoffs --skill {skill}'")
                problems += 1
            else:
                print(f"[OK]   {skill}: peeks handoffs --skill {skill}")
        else:
            print(f"[OK]   {skill}: origin (no peek required)")
        posted = set(re.findall(r"handoff --to ([\w-]+)", blob))
        for want in wants:
            if want not in posted:
                print(f"[ERROR] {skill}: missing post 'handoff --to {want}' "
                      f"(found: {sorted(posted) or 'none'})")
                problems += 1
            else:
                print(f"[OK]   {skill}: posts handoff --to {want}")
        if not wants and posted:
            print(f"[WARNING] {skill}: terminal skill posts {sorted(posted)} "
                  f"(harmless, informational)")

    if problems:
        print(f"[ERROR] handoff wiring: {problems} problem(s)")
        return 1
    print("[OK] handoff wiring: all 13 skills match the chain contract")
    return 0


def negtest() -> int:
    skill = SKILLS / "bmad-ux" / "SKILL.md"
    orig = skill.read_text(encoding="utf-8")
    broken = orig.replace("handoff --to bmad-architecture",
                          "handoff --to bmad-NOWHERE")
    try:
        skill.write_text(broken, encoding="utf-8")
        r = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=str(PLUGIN))
        if r.returncode == 1 and "bmad-ux" in r.stdout:
            print("  [OK] wiring break caught, exit=1")
        else:
            print(f"  [ERROR] wiring break expected, rc={r.returncode} "
                  f"out=...{r.stdout[-400:]!r}")
            return 1
    finally:
        skill.write_text(orig, encoding="utf-8")
    print("[OK] check-handoff negtest passed")
    return 0


if __name__ == "__main__":
    sys.exit(negtest() if "--negtest" in sys.argv[1:] else check())
