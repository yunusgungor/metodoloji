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
    NON_CODE_CONFIG_RES,
    NON_CODE_EXTS,
    PLUGIN_FREE_PREFIXES,
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

    if runtime == "claude" or tool_name in ("Write", "Edit", "MultiEdit",
                                                  "NotebookEdit", "Bash"):
        # Claude Code → normalize to OpenHands convention
        if tool_name in ("Write", "Edit", "MultiEdit"):
            if "file_path" in tool_input and "path" not in tool_input:
                tool_input["path"] = tool_input["file_path"]
            tool_name = "file_editor"
        elif tool_name == "NotebookEdit":
            if "file_path" in tool_input and "path" not in tool_input:
                tool_input["path"] = tool_input["file_path"]
            tool_name = "notebook_editor"
        elif tool_name == "Bash":
            if "command" not in tool_input and "cmd" in tool_input:
                tool_input["command"] = tool_input["cmd"]
            tool_name = "terminal"
    elif runtime == "openhands" or tool_name in ("file_editor", "terminal",
                                                        "notebook_editor"):
        pass  # already normalized
    elif tool_name in ("", None):
        pass  # no tool info (e.g. Stop/SessionStart payloads) — nothing to map
    else:
        # Unknown tool — never silently pass through the gate. Mark it so
        # guard() treats it as unrecognized (warn-only) instead of allowing
        # a code write it doesn't understand.
        tool_name = "unknown"

    return {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "raw_tool_name": raw_name,
        "raw_tool_input": raw_input,
        **{k: v for k, v in json_in.items() if k not in ("tool_name", "tool_input")},
    }


def norm_path(p: str) -> str:
    """Normalize path to project-relative, forward-slash, no leading './'."""
    p = (p or "").strip().replace("\\", "/")
    p = re.sub(r"^[a-zA-Z]:", "", p)  # Remove drive letter
    p = re.sub(r"/{2,}", "/", p)  # collapse duplicate slashes
    while p.startswith("./"):
        p = p[2:]
    # Resolve .. and . lexically without touching the filesystem.
    parts: list[str] = []
    absolute = p.startswith("/")
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            elif not absolute:
                parts.append(seg)
            continue
        parts.append(seg)
    out = "/".join(parts)
    return ("/" + out) if absolute else out


def _project_is_methodology_root() -> bool:
    """True when the project being guarded IS this plugin's own repository.

    The plugin root resolved from env always equals the engine's methodology
    root (the engine lives inside the install dir), so the meaningful signal is
    the project root: CLAUDE_PROJECT_DIR / OPENHANDS_PROJECT_DIR / cwd. When it
    resolves to the methodology root, the plugin source trees (hooks/,
    scripts/, skills/, custom/) are released as a
    self-modification free zone — the methodology working on itself. In any
    ordinary project those trees stay behind the experiment gate.
    """
    try:
        from .config import _METHODOLOGY_ROOT
        project_root = repo_root({})
        return pathlib.Path(project_root).resolve() == pathlib.Path(_METHODOLOGY_ROOT).resolve()
    except Exception:
        return False


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
    if any(p.startswith(prefix) for prefix in FREE_PREFIXES):
        return True
    # Plugin source trees: free ONLY when the project is this repo itself
    # (self-modification). Otherwise they are protected by the experiment gate.
    if any(p.startswith(prefix) for prefix in PLUGIN_FREE_PREFIXES):
        return _project_is_methodology_root()
    return False


def is_code_target(path: str) -> bool:
    """True if the path is a code target (whitelist: everything except data/markup/asset).

    Order is deliberate: non-code signals (extension/basename, toolchain
    config) win over the CODE_DIRS directory shortcut, so `src/*.md` is
    never code just for living under src/.
    """
    p = norm_path(path).lstrip("/")
    base = pathlib.PurePosixPath(p).name
    first = p.split("/", 1)[0].lower()
    ext = pathlib.PurePosixPath(base).suffix.lower()
    if p == "dev/null" or p.startswith("dev/null/"):
        return False
    # Executable CI/config (workflows, compose, package.json) is always code,
    # even with a data extension like .yml — the pipeline runs it.
    if EXEC_CONFIG_NAME.search(p):
        return True
    if ext in NON_CODE_EXTS or base.lower() in NON_CODE_BASENAMES:
        return False
    # Toolchain config (prisma.config.ts, tsconfig.json, lockfiles): not
    # application code — never a code target, even under CODE_DIRS.
    if any(rx.search(p) for rx in NON_CODE_CONFIG_RES):
        return False
    if base.lower() in CODE_BASENAMES or first in CODE_DIRS:
        return True
    # Intentionally fail-closed: an unlisted extension is treated as code, so
    # a new data format never silently bypasses the experiment gate. Projects
    # with exotic data trees should add them to NON_CODE_* instead.
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
    """Resolve a possibly-relative path against cwd (or root) and relativize to root.

    Only a slash-boundary prefix match strips the root: /repo-evil/x under
    root /repo stays absolute (never rebased as repo-internal).
    """
    if not p:
        return ""
    p = p.strip().strip("\"'")
    base = cwd or root
    full = (
        p
        if os.path.isabs(p) or re.match(r"^[a-zA-Z]:[/\\]", p)
        else os.path.join(base, p)
    )
    r = norm_path(root).rstrip("/")
    f = norm_path(full)
    if r and (f == r or f.startswith(r + "/")):
        return f[len(r):].lstrip("/")
    return f


# --- Session focus (blackboard-backed) ----------------------------------------
# Two live signals steer the hooks; both are read per-call (board first, env
# snapshot fallback) so mid-session skill writes take effect immediately:
#   - status: `complete`/`done` skips the stop story check (session finished).
#   - scope: a path boundary; the guard flags out-of-scope writes warn-only.
# (The old purpose/topic/goal/idea intent mirror was removed: the audit trail
# already stamps per-record intent, and no hook consumed the mirror.)
# Fail-open throughout: blackboard disabled/unreadable → env → ''.

def _read_focus_key(root: str, field: str) -> str:
    """Fetch one focus key (status/scope) from the board ('' if none)."""
    try:
        from .config import blackboard_enabled
        if not blackboard_enabled():
            return ""
        from . import blackboard as bb
        entry = bb.read_board(root).get("keys", {}).get(field)
        if entry and isinstance(entry, dict):
            return str(entry.get("value", "")).strip()
    except Exception:
        pass
    return ""


def _active_progress(root: str) -> str:
    """Return the session progress status from the blackboard.

    Skills write it via `blackboard.py write --key status --value complete`
    (or active / in-progress). Returns '' when unrecorded.
    """
    return _read_focus_key(root, "status")


def _active_scope(root: str, env_override: bool = True) -> str:
    """Return the active scope (a path boundary).

    The guard uses it to flag out-of-scope writes as warn-only. Priority:
      1. scope key on the blackboard (the live value a skill wrote).
      2. METODOLOJI_SCOPE env (bootstrap.sh snapshot — fallback when empty).
    """
    scope = _read_focus_key(root, "scope")
    if scope:
        return scope
    if env_override:
        return os.environ.get("METODOLOJI_SCOPE", "").strip()
    return ""


_STORY_KEY_IN_FOCUS = re.compile(
    r"(?i)\b(S-\d+|(?:\d+-\d+-[a-z][a-z0-9-]*))\.md\b|"
    r"\b(S-\d+|(?:\d+-\d+-[a-z][a-z0-9-]*))\b")


def _story_key_from_focus(focus: str) -> str:
    """Extract a story key (S-003 or 1-2-login) from a focus string.

    The session scope usually names a path, but it may name a story instead
    (e.g. scope "S-003"): then only that story blocks stop. Returns '' when
    the focus doesn't name a story.
    """
    if not focus:
        return ""
    m = _STORY_KEY_IN_FOCUS.search(focus)
    if not m:
        return ""
    key = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
    if key.endswith(".md"):
        key = key[: -len(".md")]  # rstrip strips chars, not the suffix
    return key.strip()


# --- Definition-of-Done validation (shared: guard story + audit QR checks) ---
# Single source of truth for "what is a valid DoD item", so the guard's story
# DoD validation and the audit's QR DoD warning can never disagree about the
# rules: every DoD item needs a DoD-NNN identifier AND a recorded verification
# (a Verify: field for story definitions; a Verify:/Evidence/result marker for
# QR records, which report the verification outcome).

_DOD_ID_RE = re.compile(r"[\[\(]?DoD-(\d+)[\]\)]?")
_VERIFY_FIELD_RE = re.compile(r"Verify:\s*(.+)")
# QR result markers: status symbols, an arrowed verdict, or an Evidence field.
_QR_RESULT_RE = re.compile(
    r"[✓✅❌⚠️]|->\s*(?:PASS|FAIL|pass|fail|passed|failed|pending|blocked)|Evidence:\s*\S")
# Presence signals for "does this text carry DoD content at all".
_DOD_SIGNAL_RE = re.compile(
    r"DoD\s*Item|DoD-\s*\d+|Definition\s+of\s+Done|##\s+[^\n]*\bDoD\b",
    re.IGNORECASE)
_DOD_EMPTY_CELL = {"", "—", "-"}


def scan_dod_items(text: str, *, qr: bool = False) -> list[dict]:
    """Scan text for DoD items and their structural facts.

    Bullet items (checkbox "- [ ] DoD-001 …" or token "- [DoD-001] …" — the
    record-template style) are recognised together with their indented
    continuation lines, where a ``Verify:`` field (and, in QR mode, an
    ``Evidence:`` line or result marker) may live. In QR mode, markdown-table
    rows ("| DoD-001 | … |") are recognised as items too.

    Returns a list of dicts with keys: kind ("bullet" | "row"), first (the
    item's first line), has_identifier, has_verification.
    """
    lines = text.splitlines()
    items: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()

        # QR DoD verification tables: | DoD-001 | ✅ passed | evidence | date |
        if qr and line.startswith("|") and _DOD_ID_RE.search(line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            items.append({
                "kind": "row",
                "first": line,
                "has_identifier": bool(cells and _DOD_ID_RE.search(cells[0])),
                # A recorded result = any non-empty status/evidence cell.
                "has_verification": any(
                    c and c not in _DOD_EMPTY_CELL for c in cells[1:]),
            })
            i += 1
            continue

        is_checkbox = line.startswith(("- [ ]", "- [x]", "- [X]"))
        is_token = line.startswith("- ") and bool(_DOD_ID_RE.search(line))
        if not (is_checkbox or is_token):
            i += 1
            continue

        # Item block: the bullet plus its indented sub-lines (where Verify: /
        # Evidence: fields are written, template style).
        block = [line]
        j = i + 1
        while j < n and lines[j][:1].isspace():
            block.append(lines[j].strip())
            j += 1
        block_text = "\n".join(block)
        has_verify = bool(_VERIFY_FIELD_RE.search(block_text)) or "Verify:" in block_text
        has_result = _QR_RESULT_RE.search(block_text) if qr else None
        items.append({
            "kind": "bullet",
            "first": line,
            "has_identifier": bool(_DOD_ID_RE.search(line)),
            "has_verification": bool(has_verify or has_result),
        })
        i = j
    return items


def dod_issues(text: str, *, qr: bool = False) -> list[str]:
    """Structural DoD issues in *text* — identical rules for guard and audit.

    Story mode (qr=False): bullet items only; each item needs a DoD-NNN
    identifier and a Verify: field (inline or on an indented sub-line).
    QR mode (qr=True): bullet items and DoD table rows; each item needs an
    identifier and a recorded verification (Verify:, Evidence:, or a result
    marker such as "✓ PASS").

    Returns guard-style messages so both layers report the same defects.
    """
    issues: list[str] = []
    for item in scan_dod_items(text, qr=qr):
        first = item["first"]
        if not item["has_identifier"]:
            issues.append(f"DoD item without identifier: {first[:60]}...")
        if not item["has_verification"]:
            issues.append(f"DoD item missing Verify field: {first[:60]}...")
    return issues


def has_dod_content(text: str) -> bool:
    """True when *text* carries any DoD signal (section, table, or item)."""
    return bool(_DOD_SIGNAL_RE.search(text))
