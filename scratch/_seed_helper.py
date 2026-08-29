"""Seed helper for sandbox scenarios — creates minimal record files for hook testing."""
from __future__ import annotations
import os
from pathlib import Path


def seed_experiment(sandbox: str, eid: str = "E-001", status: str = "ONAYLANDI") -> None:
    exp_dir = os.path.join(sandbox, "docs", "experiments")
    os.makedirs(exp_dir, exist_ok=True)
    path = os.path.join(exp_dir, f"{eid}.md")
    if not os.path.exists(path):
        Path(path).write_text(
            f"# Deney: {eid}\n\n- **Tarih:** 2026-01-01\n"
            f"- **Durum:** {status}\n- **Teori:** Test teorisi\n"
            f"- **Hipotez:** H-001: 'test >= 0.90'\n", encoding="utf-8"
        )


def seed_qr(sandbox: str, qid: str = "QR-001", story_ref: str = "S-001") -> None:
    qr_dir = os.path.join(sandbox, "docs", "quality")
    os.makedirs(qr_dir, exist_ok=True)
    path = os.path.join(qr_dir, f"{qid}.md")
    if not os.path.exists(path):
        Path(path).write_text(
            f"# Quality Record: {qid}\n\n- **Tarih:** 2026-01-01\n"
            f"- **Durum:** ONAYLANDI\n- **Story:** {story_ref}\n", encoding="utf-8"
        )


def seed_methodology(sandbox: str, story_key: str = "S-001") -> None:
    stories_dir = os.path.join(sandbox, "docs", "development", "stories")
    os.makedirs(stories_dir, exist_ok=True)
    path = os.path.join(stories_dir, f"{story_key}.md")
    if not os.path.exists(path):
        Path(path).write_text(
            f"# Story: {story_key}\n\n- **Durum:** done\n", encoding="utf-8"
        )


def seed_story(
    sandbox: str,
    story_key: str = "S-001",
    status: str | None = None,
    ac: str | None = None,
    dod: str | None = None,
    story_body_sp_refs: str | None = None,
    experiment_refs: str | None = None,
) -> None:
    stories_dir = os.path.join(sandbox, "docs", "development", "stories")
    os.makedirs(stories_dir, exist_ok=True)
    path = os.path.join(stories_dir, f"{story_key}.md")
    parts = [f"# Story: {story_key}\n"]
    if experiment_refs:
        parts.append(f"---\nexperiment_refs:\n  - id: {experiment_refs}\n    status: ONAYLANDI\n---\n")
    if status:
        parts.append(f"**Status:** {status}\n")
    if ac:
        parts.append(f"## Acceptance Criteria\n\n{ac}\n")
    if dod:
        parts.append(f"## Definition of Done\n\n{dod}\n")
    if story_body_sp_refs:
        parts.append(f"\n{story_body_sp_refs}\n")
    Path(path).write_text("\n".join(parts), encoding="utf-8")
