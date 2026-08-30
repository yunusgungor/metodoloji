"""Utility functions for BMAD hooks engine."""

import os
import pathlib
import re

from .config import (
    CODE_BASENAMES,
    CODE_DIRS,
    EXEC_CONFIG_NAME,
    FREE_DOC_MD,
    FREE_DOC_RAW,
    FREE_PREFIXES,
    INFRA_FILES,
    NON_CODE_BASENAMES,
    NON_CODE_EXTS,
)


def norm_path(p: str) -> str:
    """Normalize path to project-relative, forward-slash, no leading './'."""
    p = (p or "").replace("\\", "/")
    p = re.sub(r"^[a-zA-Z]:", "", p)  # Remove drive letter
    while p.startswith("./"):
        p = p[2:]
    return p


def is_free(path: str) -> bool:
    """True if the project-relative path is inside a free zone (no approval needed)."""
    p = norm_path(path).lstrip("/")
    if not p:
        return True
    if FREE_DOC_MD.match(p) or FREE_DOC_RAW.match(p):
        return True
    if p in INFRA_FILES:
        return True
    if p.startswith("explore_"):
        return True
    return any(p.startswith(prefix) for prefix in FREE_PREFIXES)


def is_code_target(path: str) -> bool:
    """True if the path is a code target (whitelist: everything except data/markup/asset)."""
    p = norm_path(path).lstrip("/")
    base = pathlib.PurePosixPath(p).name
    first = p.split("/", 1)[0]
    ext = pathlib.PurePosixPath(base).suffix.lower()
    if p == "dev/null" or p.startswith("dev/null/"):
        return False
    if base.lower() in CODE_BASENAMES or first in CODE_DIRS:
        return True
    if EXEC_CONFIG_NAME.search(p):
        return True
    if ext in NON_CODE_EXTS or base.lower() in NON_CODE_BASENAMES:
        return False
    return True


def extract_story_key_from_content(content: str) -> str:
    """Extract story key from file content — matches 'S-XXX' in title or 'N-N-slug' pattern."""
    # Try '# Story: S-XXX' header first (handles space variations around colon)
    m = re.search(r"#\s+Story\s*:\s*(\S+)", content, re.IGNORECASE)
    if m:
        return m.group(1)
    # Try '# Story S-XXX' (no colon)
    m = re.search(r"#\s+Story\s+(\S+)", content, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def repo_root(json_in: dict) -> str:
    """Get repository root from environment variables.

    Priority:
    1. CLAUDE_PROJECT_DIR (Claude Code standard)
    2. OPENHANDS_PROJECT_DIR (OpenHands standard)
    3. json_in["cwd"] (hook input fallback)
    4. os.getcwd() (last resort)
    """
    root = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("OPENHANDS_PROJECT_DIR")
        or json_in.get("cwd")
        or os.getcwd()
    )
    return os.path.abspath(root)


def rel_to_root(root: str, p: str, cwd: str | None = None) -> str:
    """Resolve a possibly-relative path against cwd (or root) and relativize to root."""
    if not p:
        return ""
    p = p.strip().strip("\"'")
    base = cwd or root
    full = (
        p
        if os.path.isabs(p) or re.match(r"^[a-zA-Z]:[/\\]", p)
        else os.path.join(base, p)
    )
    r = norm_path(root)
    f = norm_path(full)
    if r and (f.startswith(r.rstrip("/") + "/") or f.startswith(r)):
        f = f[len(r.rstrip("/")):].lstrip("/")
    return f
