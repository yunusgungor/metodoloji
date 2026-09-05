"""Utility functions for BMAD hooks engine."""

import os
import pathlib
import re
import sys

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


def normalize_hook_input(json_in: dict) -> dict:
    """Normalize hook input from either Claude Code or OpenHands to a common schema.

    Claude Code sends: tool_name=Write|Edit|MultiEdit|Bash,
      tool_input={file_path,content,command,...}
    OpenHands sends: tool_name=file_editor|terminal,
      tool_input={path,content,command,...}

    Returns a normalized dict with keys: tool_name, tool_input (with
    file_path/content/command), raw_tool_name, raw_tool_input.
    """
    runtime = os.environ.get("METODOLOJI_RUNTIME", "")
    tool_name = json_in.get("tool_name", "")
    tool_input = dict(json_in.get("tool_input", {}))

    raw_name = tool_name
    raw_input = dict(tool_input)

    if runtime == "claude" or tool_name in ("Write", "Edit", "MultiEdit", "Bash"):
        # Claude Code → normalize to OpenHands convention
        if tool_name in ("Write", "Edit", "MultiEdit"):
            if "file_path" in tool_input and "path" not in tool_input:
                tool_input["path"] = tool_input["file_path"]
            tool_name = "file_editor"
        elif tool_name == "Bash":
            if "command" not in tool_input and "cmd" in tool_input:
                tool_input["command"] = tool_input["cmd"]
            tool_name = "terminal"
    elif runtime == "openhands" or tool_name in ("file_editor", "terminal"):
        pass  # already normalized
    else:
        # Unknown tool — pass through as-is
        pass

    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "raw_tool_name": raw_name,
        "raw_tool_input": raw_input,
        **{k: v for k, v in json_in.items() if k not in ("tool_name", "tool_input")},
    }


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


# --- Intent bridge -----------------------------------------------------------

_MEMLOG_IMPORTED = None


def _memlog_split(text: str) -> dict:
    """Parse .memlog.md frontmatter via bmad/scripts/memlog.split().

    Loaded lazily so hooks that never need intent don't pay the import cost,
    and so a broken memlog module can't break unrelated hook paths.
    """
    global _MEMLOG_IMPORTED
    if _MEMLOG_IMPORTED is None:
        try:
            from .config import _METHODOLOGY_ROOT
            _scripts = pathlib.Path(_METHODOLOGY_ROOT) / "bmad" / "scripts"
            if str(_scripts) not in sys.path:
                sys.path.insert(0, str(_scripts))
            import memlog as _m
            _MEMLOG_IMPORTED = _m
        except Exception:
            _MEMLOG_IMPORTED = False
    if not _MEMLOG_IMPORTED:
        return {}
    try:
        meta, _ = _MEMLOG_IMPORTED.split(text)
        return meta
    except Exception:
        return {}


def _active_memlog_meta(root: str) -> dict:
    """Return the frontmatter of the most recent .memlog.md under root ({} if none)."""
    root = os.path.abspath(root)
    cands: list[pathlib.Path] = []
    for base in ("bmad-output", ".metodoloji", "docs", ""):
        p = pathlib.Path(root) / base / ".memlog.md"
        if p.is_file():
            cands.append(p)
    # Also scan recursively for any .memlog.md under the root (bounded).
    if not cands:
        for p in pathlib.Path(root).rglob(".memlog.md"):
            try:
                if p.is_file():
                    cands.append(p)
            except OSError:
                continue
    if not cands:
        return {}
    newest = max(cands, key=lambda p: p.stat().st_mtime)
    return _memlog_split(newest.read_text(encoding="utf-8", errors="replace"))


def _active_intent(root: str, env_override: bool = True) -> str:
    """Return the active intent (purpose) for this session.

    Priority:
      1. METODOLOJI_INTENT env (set by bootstrap.sh at SessionStart) — the
         same intent for every hook process in the session.
      2. The most recently modified .memlog.md under the project root, read
         from purpose, then topic, goal, or idea (the per-skill vocabulary
         variants) so every skill's intent reaches the bridge.
    Returns '' when no intent is recorded.
    """
    if env_override:
        env_intent = os.environ.get("METODOLOJI_INTENT", "").strip()
        if env_intent:
            return env_intent
    meta = _active_memlog_meta(root)
    for key in ("purpose", "topic", "goal", "idea"):
        val = str(meta.get(key, "")).strip()
        if val:
            return val
    return ""


def _active_progress(root: str) -> str:
    """Return the session progress status from the active memlog.

    Skills write it with `memlog.py set --key status --value complete` (or
    active / in-progress). Returns '' when unset.
    """
    return str(_active_memlog_meta(root).get("status", "")).strip()


def _active_scope(root: str, env_override: bool = True) -> str:
    """Return the active scope (a path scope from the memlog or env).

    Scope is separate from purpose: a memlog can carry `purpose: auth flow`
    and `scope: src/auth`. This returns the path scope so enforcement (e.g.
    guard) can check writes against it.

    Priority:
      1. METODOLOJI_SCOPE env (set by bootstrap.sh at SessionStart).
      2. A scope: tag inside METODOLOJI_INTENT (for older bootstrap versions).
      3. The scope field of the most recent .memlog.md.
    """
    if env_override:
        env_scope = os.environ.get("METODOLOJI_SCOPE", "").strip()
        if env_scope:
            return env_scope
        env_intent = os.environ.get("METODOLOJI_INTENT", "").strip()
        if env_intent:
            m = re.search(r"(?:scope|kapsam)\s*[:=]\s*([\w\-./]+(?:/[\w\-./]+)*)", env_intent)
            if m:
                return m.group(1).strip()
    return str(_active_memlog_meta(root).get("scope", "")).strip()


_STORY_KEY_IN_INTENT = re.compile(
    r"(?i)\b(S-\d+|(?:\d+-\d+-[a-z][a-z0-9-]*))\.md\b|"
    r"\b(S-\d+|(?:\d+-\d+-[a-z][a-z0-9-]*))\b")


def _story_key_from_intent(intent: str) -> str:
    """Extract a story key (S-003 or 1-2-login) from an intent string.

    Returns '' when the intent doesn't name a story. E.g.
    "S-003'ü bitir" → "S-003", "finish 1-2-login" → "1-2-login".
    """
    if not intent:
        return ""
    m = _STORY_KEY_IN_INTENT.search(intent)
    if not m:
        return ""
    key = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").rstrip(".md")
    return key.strip()
