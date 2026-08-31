#!/usr/bin/env python3
"""Fix remaining mixed Turkish/English strings in meta benchmark data after the
phrase-level migration. Uses full-string replacement per item id."""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "bmad_benchmarks" / "envs"

# (bench, split, id, field, full correct English value)
FIXES = [
    ("bmad_meta_chain", "train", "chain-experiment", "stage",
     "An experiment was run and its result will be recorded. Which record, which path, which status values?"),
    ("bmad_meta_chain", "val", "chain-qr-val", "stage",
     "A quality record will be created for a feature, for the story to count as done. Which record and status values?"),
    ("bmad_meta_guard", "test", "guard-experiment-rejected", "scenario",
     "The story frontmatter has E-002 in experiment_refs, status REJECTED. The story is being written. Guard decision?"),
    ("bmad_meta_guard", "test", "guard-scratch", "scenario",
     "A temporary test file is being written to scratch/test.py — scratch is a free zone. What is the guard decision?"),
    ("bmad_meta_guard", "train", "guard-no-experiment", "scenario",
     "The developer wants to write code to src/auth/login.py with no scope-matching approved experiment record. What should the guard decision be?"),
    ("bmad_meta_guard", "train", "guard-approved-experiment", "scenario",
     "The developer has docs/experiments/E-001.md with status APPROVED and scope src/auth/** which matches src/auth/login.py and wants to change it. What should the guard decision be?"),
    ("bmad_meta_guard", "train", "guard-hypothesis-ac", "scenario",
     "An AC in the story is tagged [HYPOTHESIS], no experiment approval. The developer is trying to implement this AC. Guard decision?"),
    ("bmad_meta_guard", "train", "guard-missing-ac-metadata", "scenario",
     "Writing to the story file but AC-001's Type, Measured, Verify fields are missing. Guard decision?"),
    ("bmad_meta_guard", "train", "guard-docs-free-zone", "scenario",
     "Documentation is being updated — writing to docs/development/README.md, code unchanged. Guard decision?"),
    ("bmad_meta_guard", "train", "guard-done-no-qr", "scenario",
     "The story status is being marked 'done' but no docs/quality/QR-*.md record exists. Guard decision?"),
    ("bmad_meta_guard", "val", "guard-task-no-ac", "scenario",
     "A Technical Task in the story has no AC: AC-XXX reference. Being written to the story file. Guard decision?"),
    ("bmad_meta_guard", "val", "guard-prd-no-code", "scenario",
     "A PRD document is being created (docs/planning/prd.md) — a documentary output, not code. What is the guard decision?"),
    ("bmad_meta_mod", "train", "task-sprint", "task_desc",
     "Sprint planning will be done, sprint-status.yaml will be created, retrospective notes will be kept."),
    ("bmad_meta_root", "test", "root-gate-script-read", "operation",
     "run the run_experiment.py gate script from the {metodoloji-root}/skills/bmad-research-experiment/scripts/ location"),
    ("bmad_meta_root", "train", "root-story-output", "operation",
     "bmad-create-story: create the story file and write it to docs/development/stories/S-001.md record"),
]


def main() -> int:
    changed = 0
    for bench, split, item_id, field, value in FIXES:
        path = DATA_DIR / bench / "data" / split / "001-*.json"
        for f in sorted(pathlib.Path(DATA_DIR).glob(str(path.relative_to(DATA_DIR)))):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            items = data if isinstance(data, list) else [data]
            updated = False
            for item in items:
                if item.get("id") == item_id and field in item:
                    item[field] = value
                    updated = True
            if updated:
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                print(f"  fixed {bench}/{split}/{item_id}")
                changed += 1
    print(f"{changed} item(s) fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
