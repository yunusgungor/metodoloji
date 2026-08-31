#!/usr/bin/env python3
"""Create Quality Record (QR-XXX.md) from story file DoD validation.

This script implements bridge #3 from the bridge document.
It reads a story file and creates a QR record.

Usage:
    python3 scripts/create-qr-record.py --story <story-file> [--sira <number>]

The script:
1. Reads the native story file
2. Extracts DoD items and their verification status
3. Creates docs/quality/QR-<sira>.md
4. Updates story file Quality Record section
"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path


def extract_dod_items(content: str) -> list[dict]:
    """Extract DoD items and their status from story file."""
    items = []

    dod_section = re.search(
        r"##\s+Definition\s+of\s+Done\s*\n(.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not dod_section:
        return items

    lines = dod_section.group(1).splitlines()
    current_item = None

    for line in lines:
        stripped = line.strip()

        # Top-level DoD item
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            if current_item:
                items.append(current_item)

            is_checked = stripped.startswith("- [x]")
            dod_id_match = re.search(r"DoD-(\d+)", stripped)
            dod_id = f"DoD-{dod_id_match.group(1)}" if dod_id_match else f"DoD-{len(items)+1}"

            # Extract description (after the checkbox and optional DoD-XXX:)
            desc = stripped
            desc = re.sub(r"^- \[[ x]\]\s*", "", desc)
            desc = re.sub(r"DoD-\d+:\s*", "", desc)

            # Extract AC references
            ac_refs = re.findall(r"AC-(\d+)", stripped)
            ac_refs = [f"AC-{r}" for r in ac_refs]

            # Extract Verify method
            verify_match = re.search(r"Verify:\s*(.+)", stripped)
            verify = verify_match.group(1).strip() if verify_match else ""

            current_item = {
                "id": dod_id,
                "checked": is_checked,
                "description": desc,
                "ac_refs": ac_refs,
                "verify": verify,
                "evidence": "",
                "status": "passed" if is_checked else "pending",
            }

        # Sub-lines with Verify/Evidence
        elif current_item and stripped.startswith("- Verify:"):
            current_item["verify"] = stripped.replace("- Verify:", "").strip()
        elif current_item and stripped.startswith("- Evidence:"):
            current_item["evidence"] = stripped.replace("- Evidence:", "").strip()

    if current_item:
        items.append(current_item)

    return items


def extract_story_metadata(content: str) -> dict:
    """Extract basic story metadata."""
    meta = {"title": "", "story_key": ""}

    title_match = re.search(r"^#\s+Story\s+(\S+)\s*:\s*(.+)$", content, re.MULTILINE)
    if title_match:
        meta["story_key"] = title_match.group(1).strip()
        meta["title"] = title_match.group(2).strip()

    return meta


def create_qr_record(
    meta: dict,
    dod_items: list[dict],
    sira: int,
    project_root: Path,
) -> Path:
    """Create QR-<sira>.md record."""
    qr_dir = project_root / "docs" / "quality"
    qr_dir.mkdir(parents=True, exist_ok=True)
    qr_path = qr_dir / f"QR-{sira:03d}.md"

    today = date.today().isoformat()

    passed = sum(1 for d in dod_items if d["status"] == "passed")
    failed = sum(1 for d in dod_items if d["status"] == "failed")
    total = len(dod_items)

    if total == 0:
        qr_status = "pending"
    elif passed == total:
        qr_status = "pass"
    elif failed > 0:
        qr_status = "fail"
    else:
        qr_status = "partial"

    # Build DoD table
    dod_table = ""
    for d in dod_items:
        status_icon = "✅" if d["status"] == "passed" else ("❌" if d["status"] == "failed" else "⏳")
        dod_table += f"| {d['id']} | {status_icon} {d['status']} | {d.get('evidence', '—') or '—'} | {today} |\n"

    record = f"""# Quality Record: QR-{sira:03d}

| Field | Value |
|------|-------|
| Story | {meta.get('story_key', '—')} |
| Story Title | {meta.get('title', '—')} |
| Date | {today} |
| QR Status | {qr_status} |

## DoD Verification Results

| DoD Item | Status | Evidence | Date |
|----------|-------|-------|-------|
{dod_table}
## AC Verification Results

| AC | Status | Method | Evidence |
|----|-------|--------|----------|
| — | — | — | — |

## Test Summary

- Unit tests: —
- Integration tests: —
- Regression: —

## File List

- —

## Change Summary

- —

## Summary

- **Total DoD Items**: {total}
- **Passed**: {passed}
- **Failed**: {failed}
- **Pending**: {total - passed - failed}
"""

    qr_path.write_text(record, encoding="utf-8")
    return qr_path


def update_story_qr_section(story_path: Path, qr_path: Path, dod_items: list[dict], project_root: Path):
    """Update the Quality Record section in the story file."""
    if not story_path.exists():
        return

    content = story_path.read_text(encoding="utf-8")
    rel_qr = qr_path.relative_to(project_root)

    today = date.today().isoformat()
    passed = sum(1 for d in dod_items if d["status"] == "passed")
    total = len(dod_items)

    # Build QR table
    qr_table = ""
    for d in dod_items:
        status_icon = "✅" if d["status"] == "passed" else ("❌" if d["status"] == "failed" else "⏳")
        qr_table += f"| {d['id']} | {status_icon} {d['status']} | {d.get('evidence', '—') or '—'} | {today} |\n"

    new_qr_section = f"""## Quality Record (QR)

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
{qr_table}
### QR Summary
- **Total DoD Items**: {total}
- **Passed**: {passed}
- **Failed**: {total - passed}
- **QR Record Path**: {rel_qr}
"""

    # Replace existing QR section or append
    qr_pattern = r"##\s+Quality\s+Record\s*\(QR\).*?(?=\n##\s|\Z)"
    if re.search(qr_pattern, content, re.DOTALL | re.IGNORECASE):
        content = re.sub(qr_pattern, new_qr_section.strip(), content, flags=re.DOTALL | re.IGNORECASE)
    else:
        content += "\n" + new_qr_section

    story_path.write_text(content, encoding="utf-8")


def find_next_sira(quality_dir: Path) -> int:
    """Find the next available QR-XXX number."""
    existing = list(quality_dir.glob("QR-*.md"))
    if not existing:
        return 1

    max_sira = 0
    for f in existing:
        match = re.search(r"QR-(\d+)", f.name)
        if match:
            num = int(match.group(1))
            if num > max_sira:
                max_sira = num

    return max_sira + 1


def main():
    parser = argparse.ArgumentParser(description="Create QR record from story DoD")
    parser.add_argument("--story", required=True, help="Path to native story file")
    parser.add_argument("--sira", type=int, default=0, help="QR number (auto if 0)")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    _proj = os.environ.get("OPENHANDS_PROJECT_DIR") or args.project_root
    project_root = Path(_proj).resolve()
    story_path = Path(args.story).resolve()

    if not story_path.exists():
        print(f"❌ Story file not found: {story_path}", file=sys.stderr)
        sys.exit(1)

    # Read and parse story
    content = story_path.read_text(encoding="utf-8")
    meta = extract_story_metadata(content)
    dod_items = extract_dod_items(content)

    if not dod_items:
        print("⚠️  No DoD items found in story file", file=sys.stderr)
        sys.exit(1)

    # Determine sira number
    quality_dir = project_root / "docs" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)

    if args.sira > 0:
        sira = args.sira
    else:
        sira = find_next_sira(quality_dir)

    # Create QR record
    qr_path = create_qr_record(meta, dod_items, sira, project_root)

    # Update story file QR section
    update_story_qr_section(story_path, qr_path, dod_items, project_root)

    passed = sum(1 for d in dod_items if d["status"] == "passed")
    total = len(dod_items)

    print(f"✅ QR record created: {qr_path}")
    print(f"   Story: {meta.get('title', '—')}")
    print(f"   DoD items: {total}")
    print(f"   Passed: {passed}")
    print(f"   Failed: {total - passed}")


if __name__ == "__main__":
    main()
