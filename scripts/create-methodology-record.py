#!/usr/bin/env python3
"""Create methodology story record (S-XXX.md) from native story file.

This script implements KÖPRÜ #1 from the bridge document.
It reads a native story file and creates a methodology record.

Usage:
    python3 scripts/create-methodology-record.py --story <story-file> [--sira <number>]

The script:
1. Reads the native story file
2. Extracts metadata (title, epic, AC, experiment refs)
3. Creates docs/development/stories/S-<sira>.md from template
4. Updates story file with methodology reference comment
"""

import argparse
import os
import re
import sys
from pathlib import Path


def extract_story_metadata(content: str) -> dict:
    """Extract metadata from a native story file."""
    meta = {
        "title": "",
        "epic": "",
        "status": "",
        "acceptance_criteria": [],
        "experiment_refs": [],
        "tasks": [],
        "dod": [],
    }

    # Title
    title_match = re.search(r"^#\s+Story\s+\S+\s*:\s*(.+)$", content, re.MULTILINE)
    if title_match:
        meta["title"] = title_match.group(1).strip()

    # Status
    status_match = re.search(r"^Status:\s*(.+)$", content, re.MULTILINE)
    if status_match:
        meta["status"] = status_match.group(1).strip()

    # Epic
    epic_match = re.search(r"Epic:\s*(.+)$", content, re.MULTILINE)
    if epic_match:
        meta["epic"] = epic_match.group(1).strip()

    # Acceptance Criteria
    ac_match = re.search(
        r"##\s+Acceptance\s+Criteria\s*\n(.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if ac_match:
        ac_section = ac_match.group(1)
        for line in ac_section.splitlines():
            ac_id_match = re.search(r"\[AC-(\d+)\]", line)
            if ac_id_match and line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                ac_id = f"AC-{ac_id_match.group(1)}"
                experiment_match = re.search(r"Experiment:\s*(.+)", line)
                experiment = ""
                # Check next lines for metadata
                ac_lines = ac_section.split(ac_id_match.group(0))
                if len(ac_lines) > 1:
                    next_lines = ac_lines[1].split("\n")[:5]
                    for nl in next_lines:
                        exp_m = re.search(r"Experiment:\s*(.+)", nl)
                        if exp_m:
                            experiment = exp_m.group(1).strip()
                meta["acceptance_criteria"].append({
                    "id": ac_id,
                    "experiment": experiment,
                    "status": "pending",
                })

    # Experiment refs from frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        in_refs = False
        current_ref = {}
        for line in frontmatter.splitlines():
            stripped = line.strip()
            if stripped.startswith("experiment_refs"):
                in_refs = True
                continue
            if in_refs:
                if stripped.startswith("- "):
                    if current_ref:
                        meta["experiment_refs"].append(current_ref)
                    current_ref = {}
                    inner = stripped[2:].strip()
                    kv = inner.split(":", 1)
                    if len(kv) == 2:
                        current_ref[kv[0].strip()] = kv[1].strip()
                elif ":" in stripped and current_ref:
                    kv = stripped.split(":", 1)
                    current_ref[kv[0].strip()] = kv[1].strip()
                elif stripped and not stripped.startswith("-"):
                    break
        if current_ref:
            meta["experiment_refs"].append(current_ref)

    # Tasks
    task_section = re.search(
        r"##\s+Technical\s+Tasks\s*\n(.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if task_section:
        for line in task_section.group(1).splitlines():
            if line.strip().startswith("- [ ]") or line.strip().startswith("- [x]"):
                meta["tasks"].append(line.strip())

    # DoD
    dod_section = re.search(
        r"##\s+Definition\s+of\s+Done\s*\n(.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if dod_section:
        for line in dod_section.group(1).splitlines():
            if line.strip().startswith("- [ ]") or line.strip().startswith("- [x]"):
                meta["dod"].append(line.strip())

    return meta


def create_methodology_record(meta: dict, sira: int, project_root: Path) -> Path:
    """Create S-<sira>.md methodology record from template."""
    template_path = project_root / "docs" / "development" / "_template_S.md"
    output_path = project_root / "docs" / "development" / "stories" / f"S-{sira:03d}.md"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        # Minimal template if file doesn't exist
        template = "# Metodoloji Kaydı: S-{{sira}}\n\n| Alan | Değer |\n|------|-------|\n| Tarih | {{tarih}} |\n| Durum | {{durum}} |\n"

    # Build AC table
    ac_table = ""
    for ac in meta["acceptance_criteria"]:
        ac_table += f"| {ac['id']} | ⏳ pending | {ac.get('experiment', '—')} | — | — | — |\n"

    # Build experiment refs string
    exp_refs_str = ", ".join(
        f"{r.get('id', '?')} ({r.get('status', '?')})"
        for r in meta["experiment_refs"]
    ) or "—"

    # Build task list
    task_list = "\n".join(f"- {t}" for t in meta["tasks"]) or "- —"

    # Build DoD table
    dod_table = ""
    for dod in meta["dod"]:
        dod_id_match = re.search(r"DoD-(\d+)", dod)
        dod_id = f"DoD-{dod_id_match.group(1)}" if dod_id_match else "DoD-?"
        dod_table += f"| {dod_id} | ⏳ pending | — | — |\n"

    # Substitute in template
    from datetime import date
    today = date.today().isoformat()

    record = f"""# Metodoloji Kaydı: S-{sira:03d}

| Alan | Değer |
|------|-------|
| Tarih | {today} |
| Durum | backlog |
| Story Başlığı | {meta.get('title', '—')} |
| Epic | {meta.get('epic', '—')} |
| Experiment Refs | {exp_refs_str} |
| Dosya Listesi | — (implementasyon sonrası doldurulur) |
| Sprint Ref | sprint-status.yaml |
| Native Story | {meta.get('native_story_path', '—')} |

## Acceptance Criteria Detayları

| AC | Durum | Experiment | Type | Measured | Verify |
|----|-------|------------|------|----------|--------|
{ac_table}
## Technical Tasks

{task_list}

## Definition of Done

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
{dod_table}
## Dev Agent Record

### Debug Log
- —

### Completion Notes
- —

### File List
- —

### Change Log
- —

## Quality Record (QR)

| DoD Item | Durum | Kanit | Tarih |
|----------|-------|-------|-------|
{dod_table}
### QR Summary
- **Total DoD Items**: {len(meta['dod'])}
- **Passed**: 0
- **Failed**: 0
- **QR Record Path**: docs/quality/QR-{sira:03d}.md
"""

    output_path.write_text(record, encoding="utf-8")
    return output_path


def update_story_with_reference(story_path: Path, methodology_path: Path, project_root: Path):
    """Add methodology reference comment to story file."""
    if not story_path.exists():
        return

    content = story_path.read_text(encoding="utf-8")
    rel_methodology = methodology_path.relative_to(project_root)

    # Check if reference already exists
    if str(rel_methodology) in content:
        return

    # Add reference after frontmatter or at top
    ref_comment = f"\n<!-- Metodoloji kaydı: {rel_methodology} -->\n"

    # Find insertion point (after frontmatter --- block)
    fm_end = re.search(r"^---\s*\n.*?\n---", content, re.DOTALL | re.MULTILINE)
    if fm_end:
        insert_pos = fm_end.end()
        content = content[:insert_pos] + ref_comment + content[insert_pos:]
    else:
        content = ref_comment + content

    story_path.write_text(content, encoding="utf-8")


def find_next_sira(stories_dir: Path) -> int:
    """Find the next available S-XXX number."""
    existing = list(stories_dir.glob("S-*.md"))
    if not existing:
        return 1

    max_sira = 0
    for f in existing:
        match = re.search(r"S-(\d+)", f.name)
        if match:
            num = int(match.group(1))
            if num > max_sira:
                max_sira = num

    return max_sira + 1


def main():
    parser = argparse.ArgumentParser(description="Create methodology story record")
    parser.add_argument("--story", required=True, help="Path to native story file")
    parser.add_argument("--sira", type=int, default=0, help="Record number (auto if 0)")
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
    meta["native_story_path"] = str(story_path.relative_to(project_root))

    # Determine sira number
    stories_dir = project_root / "docs" / "development" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    if args.sira > 0:
        sira = args.sira
    else:
        sira = find_next_sira(stories_dir)

    # Create methodology record
    output_path = create_methodology_record(meta, sira, project_root)

    # Update story file with reference
    update_story_with_reference(story_path, output_path, project_root)

    print(f"✅ Methodology record created: {output_path}")
    print(f"   Story: {meta.get('title', '—')}")
    print(f"   AC count: {len(meta['acceptance_criteria'])}")
    print(f"   Experiment refs: {len(meta['experiment_refs'])}")
    print(f"   Tasks: {len(meta['tasks'])}")
    print(f"   DoD items: {len(meta['dod'])}")


if __name__ == "__main__":
    main()
