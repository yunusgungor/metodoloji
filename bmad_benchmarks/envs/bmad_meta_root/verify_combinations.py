#!/usr/bin/env python3
"""Verify bmad-meta-root training data covers every root×direction combination.

The classification has 2 axes → 4 combinations. Three are valid; the fourth
({metodoloji-root} + output — writing into the plugin) is INVALID and must be
represented as a TRAP case labeled with the CORRECT answer ({project-root} +
output), because the correct behavior is "the write goes to the target project,
never the plugin."

Checks per split:
  1. Every VALID combination appears at least once as expected_root×direction.
  2. Every split has at least one TRAP (plugin-write) case.
  3. Every trap case is labeled expected_root=project-root (the correct answer).
  4. JSON is well-formed and every item has the required fields.

Exit code 0 = coverage complete; 1 = a gap.
"""

import json
import pathlib
import sys

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"
REQUIRED_FIELDS = ("id", "operation", "expected_root", "expected_direction", "task_type")

# The three valid combinations a correct answer can claim.
VALID_COMBOS = {
    ("project-root", "output"),
    ("project-root", "read"),
    ("metodoloji-root", "read"),
}
# The invalid combination must surface as a trap labeled with the correct root.
# A plugin-write trap (writing INTO {metodoloji-root}) must be labeled with the
# CORRECT answer {project-root}+output. A tilde trap (~/{metodoloji-root}) is a
# malformed PATH but still a plugin read — its expected label is the true
# classification (metodoloji-root+read); it tests malformed-path recognition,
# not the write-root rule.
PLUGIN_WRITE_TRAP_IDS = ("plugin-write", "malformed-output", "malformed-plugin")
TILDE_TRAP_IDS = ("tilde",)


def load_split(split: str, data_dir: pathlib.Path | None = None) -> list[dict]:
    root = data_dir or DATA_DIR
    path = root / split / "001-ops.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verify_coverage(split_dir: pathlib.Path | str | None = None) -> int:
    """Check every split covers all valid root×direction combinations plus a
    plugin-write trap. Returns 0 when coverage is complete, raises SystemExit(1)
    otherwise. Called by the adapter's setup() so train/eval fail fast on a
    partial matrix."""
    data_dir = pathlib.Path(split_dir) if split_dir is not None else DATA_DIR
    problems = []
    for split in ("train", "val", "test"):
        items = load_split(split, data_dir)
        if not items:
            problems.append(f"[{split}] no data")
            continue
        combos = {(i["expected_root"], i["expected_direction"]) for i in items}
        write_traps = [i for i in items
                       if any(t in i["id"] for t in PLUGIN_WRITE_TRAP_IDS)]
        tilde_traps = [i for i in items if any(t in i["id"] for t in TILDE_TRAP_IDS)]

        # 1. Valid combinations present.
        missing = VALID_COMBOS - combos
        if missing:
            problems.append(f"[{split}] missing valid combos: {sorted(missing)}")

        # 2. Plugin-write trap cases present (the invalid 4th combination).
        if not write_traps:
            problems.append(f"[{split}] no plugin-write trap case")

        # 3. Plugin-write traps labeled with the CORRECT answer.
        bad_writes = [i["id"] for i in write_traps
                      if i["expected_root"] != "project-root"
                      or i["expected_direction"] != "output"]
        if bad_writes:
            problems.append(f"[{split}] plugin-write traps mislabeled: {bad_writes}")

        # 3b. Tilde traps: malformed path, but the true classification is
        #     metodoloji-root + read (the read still comes from the plugin).
        bad_tildes = [i["id"] for i in tilde_traps
                      if i["expected_root"] != "metodoloji-root"
                      or i["expected_direction"] != "read"]
        if bad_tildes:
            problems.append(f"[{split}] tilde traps mislabeled: {bad_tildes}")

        # 4. Field completeness.
        for i in items:
            for f in REQUIRED_FIELDS:
                if f not in i or not i[f]:
                    problems.append(f"[{split}] {i.get('id', '?')} missing field '{f}'")

        print(f"[{split}] {len(items)} items, "
              f"{len(write_traps)} plugin-write trap(s), "
              f"{len(tilde_traps)} tilde trap(s), combos={sorted(combos)}")

    if problems:
        for p in problems:
            print(f"  ✗ {p}", file=sys.stderr)
        print("COVERAGE INCOMPLETE", file=sys.stderr)
        raise SystemExit(1)
    print("COVERAGE COMPLETE: all valid combos + plugin-write traps present.")
    return 0


def main() -> int:
    try:
        return verify_coverage()
    except SystemExit as exc:
        return exc.code or 1


if __name__ == "__main__":
    sys.exit(main())
