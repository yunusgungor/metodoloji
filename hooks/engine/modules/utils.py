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


def repo_root(json_in: dict) -> str:
    """Get repository root from environment or JSON input."""
    root = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("OPENHANDS_PROJECT_DIR")
        or json_in.get("cwd")
        or json_in.get("working_dir")
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
