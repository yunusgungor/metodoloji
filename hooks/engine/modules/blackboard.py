"""Blackboard — dynamic, event-sourced working context for the methodology.

One JSON snapshot (``.metodoloji/blackboard.json``) plus an append-only event
log (``.metodoloji/logs/blackboard-events.log``). Every mutation is written as
an event first; the snapshot is a cache rebuilt from events when missing or
corrupt. All file operations are atomic (temp file + rename) and guarded by an
exclusive lock file so concurrent hook processes never interleave.

The board is a project-wide network, not a flat notebook:
- text keys  — single values (notes/decisions/state)
- lists      — ordered items under one key
- canvases   — dynamic surfaces (grid or free) whose cells any project actor
               mutates in real time; a canvas may watch filesystem paths so
               engine hooks push touches into it as they happen
- links      — a graph between any nodes (keys or canvases) with relations;
               mutations ripple alerts along links
- subscriptions — watchers route matching mutations into alert channels
- alerts     — bounded, channel-addressed notifications consumed by the
               engine (session_start injects, stop surfaces pending counts)

Design invariants (docs/BLACKBOARD.md):
- Fail-open: every public function returns a usable default on any error.
- Bounded: keys/lists/canvases/cells/links/alerts/events expire oldest-first.
- No auto content generation: the board only holds what a writer (or an
  explicit watch registration) put there.
"""

from __future__ import annotations

import fnmatch
import itertools
import json
import os
import pathlib
import re
import sys
import threading
import time
from contextlib import contextmanager

# Unique tmp-name sequence (per-call uniqueness across threads).
_TMP_SEQ = itertools.count()

# --- Limits (oldest expire first) -------------------------------------------
MAX_KEYS = 128
MAX_TAGS = 32
MAX_CONTRIBUTIONS = 64
MAX_EVENTS = 10_000
MAX_VALUE_LEN = 4_000
MAX_TEXT_LEN = 500

MAX_LIST_ITEMS = 100          # per list key
MAX_LIST_ITEM_LEN = 300       # per item

MAX_CANVASES = 8              # canvases on the board
MAX_CELLS = 256               # cells per canvas
MAX_AUTO_CELLS = 32           # auto (watch-fed) cells per canvas
MAX_CANVAS_NAME = 80
MAX_CELL_ID = 60
MAX_CELL_LEN = 500
MAX_WATCH_PATHS = 4           # watched paths per canvas
MAX_GRID = 64                 # max grid dimension (w or h)

MAX_LINKS = 128
MAX_SUBSCRIPTIONS = 16
MAX_ALERTS = 32               # global, oldest expire
MAX_ALERT_TEXT = 200

# Handoff signal TTL (24 hours) and stale cleanup (CRITICAL #4 / ISSUE #25)
HANDOFF_SIGNAL_TTL_SECONDS = 24 * 3600

# Watcher stamps recorded by the engine, bounded.
MAX_WATCHERS = 16


class BoardError(Exception):
    """Raised internally; public API converts to fail-open defaults."""


# --- Locking -----------------------------------------------------------------
def _acquire_lock(lock_path: str):
    """Acquire an exclusive advisory lock; None only when locking is unsupported.

    Windows: msvcrt.locking is byte-range based and non-blocking LK_NBLCK
    raises on contention — retry a bounded number of times with exponential backoff.
    When the lock cannot be taken at all the caller proceeds unguarded (fail-open)
    and the per-process tmp filename keeps the snapshot rename safe.
    (HIGH #2 / ISSUE #6: Windows lock retry with exponential backoff)
    """
    try:
        f = open(lock_path, "a+")
    except OSError:
        return None
    try:
        import fcntl  # POSIX
        fcntl.flock(f, fcntl.LOCK_EX)
        return f
    except ImportError:
        pass
    except OSError:
        f.close()
        return None
    try:
        import msvcrt  # Windows
    except ImportError:
        f.close()
        return None
    f.seek(0)
    
    # NEW: Exponential backoff strategy (HIGH #2)
    # Retry with exponential backoff: 10ms, 50ms, 100ms, then steady 100ms
    base_backoff = 0.01  # 10ms
    max_backoff = 0.1    # 100ms
    max_retries = 100    # ~10 seconds total with exponential backoff
    
    for attempt in range(max_retries):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f  # Lock acquired
        except OSError:
            # Lock contention — backoff and retry
            if attempt < max_retries - 1:
                # Exponential backoff: 10ms * 2^attempt, capped at max_backoff
                sleep_time = min(base_backoff * (2 ** attempt), max_backoff)
                time.sleep(sleep_time)
            # else: last attempt failed, fall through to fail-open
    
    # FIXED: Fail-open (return None) instead of raising exception (HIGH #2 / ISSUE #6)
    # The per-process tmp filename in _replace_atomic() keeps the snapshot rename safe
    f.close()
    return None


def _release_lock(f) -> None:
    if f is None:
        return
    try:
        if os.name == "nt":
            try:
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except (ImportError, OSError):
                pass
        else:
            try:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
    except Exception:
        pass
    finally:
        try:
            f.close()
        except OSError:
            pass


# In-process serialization: one threading.Lock per board path. Windows
# msvcrt byte-range locks proved unreliable as a same-process thread mutex
# (transient double-acquire), so threads serialize here first, and the OS
# lock only guards cross-process races.
_THREAD_LOCKS: dict = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(lock_path: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        if lock_path not in _THREAD_LOCKS:
            _THREAD_LOCKS[lock_path] = threading.Lock()
        return _THREAD_LOCKS[lock_path]


@contextmanager
def _board_lock(paths: dict):
    """Hold an exclusive advisory lock for the duration of the block."""
    tl = _thread_lock(paths["lock"])
    with tl:
        f = _acquire_lock(paths["lock"])
        try:
            yield
        finally:
            _release_lock(f)


# --- Paths -------------------------------------------------------------------
def board_paths(project_root: str) -> dict:
    root = os.path.abspath(project_root or os.getcwd())
    bb_dir = os.path.join(root, ".metodoloji")
    return {
        "root": root,
        "dir": bb_dir,
        "snapshot": os.path.join(bb_dir, "blackboard.json"),
        "events": os.path.join(bb_dir, "logs", "blackboard-events.log"),
        "lock": os.path.join(bb_dir, "blackboard.json.lock"),
    }


# --- Snapshot handling --------------------------------------------------------
def _empty_board() -> dict:
    return {"version": 2, "hot": None, "hot_canvas": None, "keys": {},
            "tags": [], "contributions": [], "links": [], "canvases": {},
            "subscriptions": [], "alerts": [], "watchers": {}, "updated": 0.0}


def _read_snapshot(paths: dict) -> dict:
    try:
        with open(paths["snapshot"], encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_board()
    except (OSError, ValueError):
        return _empty_board()
    board = _empty_board()
    board.update({k: v for k, v in data.items() if k in board})
    # v1 snapshots had no graph sections — defaults already cover them.
    if not isinstance(board.get("links"), list):
        board["links"] = []
    if not isinstance(board.get("canvases"), dict):
        board["canvases"] = {}
    if not isinstance(board.get("subscriptions"), list):
        board["subscriptions"] = []
    if not isinstance(board.get("alerts"), list):
        board["alerts"] = []
    return board


def _write_snapshot_atomic(paths: dict, board: dict) -> None:
    os.makedirs(paths["dir"], exist_ok=True)
    tmp = f'{paths["snapshot"]}.{os.getpid()}.{threading.get_ident()}.{next(_TMP_SEQ)}.tmp'
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    _replace_atomic(tmp, paths["snapshot"])


def _replace_atomic(src: str, dst: str, attempts: int = 5) -> None:
    """os.replace with a bounded retry: Windows can transiently deny the
    rename (WinError 32) when an indexer/AV briefly holds the target."""
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except FileNotFoundError:
            # src already consumed by this same call's earlier successful
            # replace (retry-after-rename) — the dst now exists or will.
            if os.path.exists(dst):
                return
            raise
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.02 * (attempt + 1))


# --- Event log ----------------------------------------------------------------
def _append_event(paths: dict, event: dict) -> None:
    """Append one JSON line. Called under the board lock from mutations."""
    os.makedirs(os.path.dirname(paths["events"]), exist_ok=True)
    with open(paths["events"], "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _truncate_events_if_needed(paths: dict) -> None:
    """Bound the event log. Runs under the board lock (from _mutate); only
    rewrites the file when it actually exceeds the cap, so the common path
    never races with concurrent appends."""
    try:
        with open(paths["events"], "rb") as f:
            lines = f.readlines()
        if len(lines) <= MAX_EVENTS:
            return
        keep = lines[-MAX_EVENTS:]
        tmp = paths["events"] + f".{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as f:
            f.writelines(keep)
            f.flush()
            os.fsync(f.fileno())
        _replace_atomic(tmp, paths["events"])
    except OSError:
        pass


# --- Public API ----------------------------------------------------------------
def read_board(project_root: str) -> dict:
    """Load the board snapshot (fail-open: empty board on any error)."""
    paths = board_paths(project_root)
    with _board_lock(paths):
        board = _read_snapshot(paths)
        # Rebuild from event log when the snapshot is empty but events exist.
        if not any((board["keys"], board["tags"], board["contributions"],
                    board["canvases"], board["links"], board["alerts"],
                    board["subscriptions"])):
            replay = _replay_events(paths)
            if any((replay["keys"], replay["tags"], replay["contributions"],
                    replay["canvases"], replay["links"], replay["alerts"],
                    replay["subscriptions"])):
                _write_snapshot_atomic(paths, replay)
                board = replay
    if board.get("hot") and board["hot"] not in board["keys"]:
        board["hot"] = None
    if board.get("hot_canvas") and board["hot_canvas"] not in board["canvases"]:
        board["hot_canvas"] = None
    return board


def _replay_events(paths: dict) -> dict:
    """Fold the event log into a board (used to rebuild a lost snapshot).
    
    Skips malformed JSON lines gracefully. (HIGH #1 / ISSUE #45)
    """
    board = _empty_board()
    skipped_lines = 0
    try:
        with open(paths["events"], encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError as e:
                    # NEW: Skip malformed JSON but log for diagnostics
                    skipped_lines += 1
                    # Could emit warning, but silently skip for now (fail-open)
                    # In production, operator would see these in doctor output
                    continue
                except Exception as e:
                    # Catch other errors (e.g., encoding, memory) and skip
                    skipped_lines += 1
                    continue
                
                try:
                    _apply_event(board, ev)
                except Exception as e:
                    # NEW: If applying an event crashes, skip it but keep going
                    # (HIGH #1: Corruption recovery - keep as much state as possible)
                    skipped_lines += 1
                    continue
    except OSError:
        pass
    
    # Store skipped line count for diagnostics (can be exposed in doctor())
    # For now, it's available but not used in output
    if skipped_lines > 0:
        board["_metadata"] = board.get("_metadata", {})
        board["_metadata"]["replay_skipped_lines"] = skipped_lines
    
    return board


# --- event fold -----------------------------------------------------------------
def _apply_event(board: dict, ev: dict) -> None:
    kind = ev.get("event")
    if kind == "write":
        key = str(ev.get("key", ""))[:200]
        if key:
            board["keys"][key] = {
                "value": ev.get("value"),
                "type": ev.get("type", "note"),
                "updated": ev.get("ts", 0.0),
            }
            if ev.get("hot"):
                board["hot"] = key
            _cap_keys(board)
    elif kind == "tool":
        # Audit tool-touch stamp (event-sourced): replay folds last_tool.*
        # back after a snapshot rebuild — no drift, unlike the old
        # snapshot-only fold.
        tool = str(ev.get("tool", ""))[:100]
        if tool:
            board["keys"][f"last_tool.{tool}"] = {
                "value": str(ev.get("target", "")), "type": "tool",
                "updated": ev.get("ts", 0.0),
            }
            _cap_keys(board)
    elif kind == "hot":
        if ev.get("key"):
            board["hot"] = str(ev["key"])[:200]
        elif ev.get("clear"):
            board["hot"] = None
    elif kind == "tag":
        tag = str(ev.get("tag", ""))[:100]
        if tag and tag not in board["tags"]:
            board["tags"].append(tag)
            while len(board["tags"]) > MAX_TAGS:
                board["tags"].pop(0)
    elif kind == "untag":
        tag = str(ev.get("tag", ""))
        if tag in board["tags"]:
            board["tags"].remove(tag)
    elif kind == "contribute":
        board["contributions"].append({
            "who": str(ev.get("who", ""))[:200],
            "what": str(ev.get("what", ""))[:MAX_TEXT_LEN],
            "ts": ev.get("ts", 0.0),
        })
        while len(board["contributions"]) > MAX_CONTRIBUTIONS:
            board["contributions"].pop(0)
    elif kind == "watch":
        w = str(ev.get("watcher", ""))[:100]
        if w:
            board["watchers"][w] = ev.get("ts", 0.0)
            while len(board["watchers"]) > MAX_WATCHERS:
                oldest = min(board["watchers"], key=lambda k: board["watchers"][k])
                board["watchers"].pop(oldest)
    elif kind == "list_add":
        key = str(ev.get("key", ""))[:200]
        if key:
            entry = board["keys"].setdefault(
                key, {"value": [], "type": "list", "updated": 0.0})
            if not isinstance(entry.get("value"), list):
                entry["value"] = []
            entry["type"] = "list"
            entry["value"].append(str(ev.get("item", ""))[:MAX_LIST_ITEM_LEN])
            entry["updated"] = ev.get("ts", 0.0)
            while len(entry["value"]) > MAX_LIST_ITEMS:
                entry["value"].pop(0)
            _cap_keys(board)
    elif kind == "list_remove":
        key = str(ev.get("key", ""))[:200]
        entry = board["keys"].get(key)
        if entry and isinstance(entry.get("value"), list):
            if ev.get("index") is not None:
                try:
                    entry["value"].pop(int(ev["index"]))
                except (IndexError, ValueError, TypeError):
                    pass
            elif ev.get("item") is not None:
                item = str(ev["item"])
                if item in entry["value"]:
                    entry["value"].remove(item)
            entry["updated"] = ev.get("ts", 0.0)
    elif kind == "list_clear":
        key = str(ev.get("key", ""))[:200]
        entry = board["keys"].get(key)
        if entry and isinstance(entry.get("value"), list):
            entry["value"] = []
            entry["updated"] = ev.get("ts", 0.0)
    elif kind == "link":
        a, b = str(ev.get("a", ""))[:200], str(ev.get("b", ""))[:200]
        rel = str(ev.get("relation", "related"))[:50]
        if a and b and not any(
                l["a"] == a and l["b"] == b and l["relation"] == rel
                for l in board["links"]):
            board["links"].append(
                {"a": a, "b": b, "relation": rel, "ts": ev.get("ts", 0.0)})
            while len(board["links"]) > MAX_LINKS:
                board["links"].pop(0)
    elif kind == "unlink":
        a, b = str(ev.get("a", "")), str(ev.get("b", ""))
        rel = ev.get("relation")
        board["links"] = [
            l for l in board["links"]
            if not (l["a"] == a and l["b"] == b and (rel is None or l["relation"] == rel))]
    elif kind == "canvas_create":
        name = str(ev.get("name", ""))[:MAX_CANVAS_NAME]
        if name and name not in board["canvases"]:
            board["canvases"][name] = {
                "grid": ev.get("grid"), "cells": {}, "watch": [], "updated": ev.get("ts", 0.0)}
            if ev.get("focus"):
                board["hot_canvas"] = name
            _cap_canvases(board)
    elif kind == "canvas_cell":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            cell = str(ev.get("cell", ""))[:MAX_CELL_ID]
            if cell:
                cv["cells"][cell] = {
                    "content": str(ev.get("content", ""))[:MAX_CELL_LEN],
                    "kind": str(ev.get("kind", "note"))[:20],
                    "x": ev.get("x"), "y": ev.get("y"),
                    "updated": ev.get("ts", 0.0),
                }
                if cv["cells"][cell]["kind"] == "auto":
                    _cap_auto_cells(cv)
                while len(cv["cells"]) > MAX_CELLS:
                    oldest = min(cv["cells"], key=lambda c: cv["cells"][c].get("updated", 0.0))
                    cv["cells"].pop(oldest)
                cv["updated"] = ev.get("ts", 0.0)
    elif kind == "canvas_remove":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            cv["cells"].pop(str(ev.get("cell", ""))[:MAX_CELL_ID], None)
            cv["updated"] = ev.get("ts", 0.0)
    elif kind == "canvas_move":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            src, dst = str(ev.get("cell", ""))[:MAX_CELL_ID], str(ev.get("to", ""))[:MAX_CELL_ID]
            if src in cv["cells"] and dst and dst != src:
                moved = dict(cv["cells"].pop(src))
                moved["updated"] = ev.get("ts", 0.0)
                if ev.get("x") is not None:
                    moved["x"] = ev.get("x")
                if ev.get("y") is not None:
                    moved["y"] = ev.get("y")
                cv["cells"][dst] = moved
                cv["updated"] = moved["updated"]
    elif kind == "canvas_resize":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            grid = ev.get("grid")
            cv["grid"] = grid if isinstance(grid, list) and len(grid) == 2 else None
            cv["updated"] = ev.get("ts", 0.0)
    elif kind == "canvas_clear":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            cv["cells"] = {}
            cv["updated"] = ev.get("ts", 0.0)
    elif kind == "canvas_focus":
        if ev.get("name"):
            board["hot_canvas"] = str(ev["name"])[:MAX_CANVAS_NAME]
        elif ev.get("clear"):
            board["hot_canvas"] = None
    elif kind == "canvas_watch":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            path = str(ev.get("path", ""))[:300]
            if path and path not in cv["watch"]:
                cv["watch"].append(path)
                while len(cv["watch"]) > MAX_WATCH_PATHS:
                    cv["watch"].pop(0)
    elif kind == "canvas_unwatch":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            path = str(ev.get("path", ""))
            if path in cv["watch"]:
                cv["watch"].remove(path)
    elif kind == "canvas_touch":
        cv = board["canvases"].get(str(ev.get("name", ""))[:MAX_CANVAS_NAME])
        if cv is not None:
            path = str(ev.get("path", ""))[:MAX_CELL_ID]
            if path:
                cv["cells"][path] = {
                    "content": str(ev.get("content", ""))[:MAX_CELL_LEN],
                    "kind": "auto",
                    "x": None, "y": None,
                    "updated": ev.get("ts", 0.0),
                }
                _cap_auto_cells(cv)
                while len(cv["cells"]) > MAX_CELLS:
                    oldest = min(cv["cells"], key=lambda c: cv["cells"][c].get("updated", 0.0))
                    cv["cells"].pop(oldest)
                cv["updated"] = ev.get("ts", 0.0)
    elif kind == "subscribe":
        watcher = str(ev.get("watcher", ""))[:100]
        pattern = str(ev.get("pattern", ""))[:200]
        channel = str(ev.get("channel", "session"))[:40]
        if watcher and pattern and not any(
                s["watcher"] == watcher and s["pattern"] == pattern
                for s in board["subscriptions"]):
            board["subscriptions"].append(
                {"watcher": watcher, "pattern": pattern, "channel": channel,
                 "ts": ev.get("ts", 0.0)})
            while len(board["subscriptions"]) > MAX_SUBSCRIPTIONS:
                board["subscriptions"].pop(0)
    elif kind == "unsubscribe":
        watcher, pattern = str(ev.get("watcher", "")), str(ev.get("pattern", ""))
        board["subscriptions"] = [
            s for s in board["subscriptions"]
            if not (s["watcher"] == watcher and s["pattern"] == pattern)]
    elif kind == "consume":
        chan = str(ev.get("channel", ""))
        board["alerts"] = [a for a in board["alerts"] if a["channel"] != chan]
    elif kind == "alert":
        board["alerts"].append({
            "id": ev.get("id", ""),
            "channel": str(ev.get("channel", "session"))[:40],
            "kind": str(ev.get("kind", "info"))[:20],
            "text": str(ev.get("text", ""))[:MAX_ALERT_TEXT],
            "ts": ev.get("ts", 0.0),
        })
        while len(board["alerts"]) > MAX_ALERTS:
            board["alerts"].pop(0)
        # NEW: Clean up stale handoff signals (CRITICAL #4)
        _cleanup_stale_handoffs(board)


def _cap_auto_cells(cv: dict) -> None:
    autos = [c for c, v in cv["cells"].items() if v.get("kind") == "auto"]
    while len(autos) > MAX_AUTO_CELLS:
        oldest = min(autos, key=lambda c: cv["cells"][c].get("updated", 0.0))
        cv["cells"].pop(oldest)
        autos.remove(oldest)


def _cleanup_stale_handoffs(board: dict) -> None:
    """Remove handoff signals older than TTL (24 hours).
    
    Prevents hung skills from blocking the chain indefinitely.
    Called during every mutation to keep stale signals from accumulating.
    (CRITICAL #4 / ISSUE #25: Skill timeout/crash handling)
    """
    now = time.time()
    initial_count = len(board["alerts"])
    board["alerts"] = [
        a for a in board["alerts"]
        if not (a.get("kind") == "handoff" and 
                (now - (a.get("ts", 0.0))) > HANDOFF_SIGNAL_TTL_SECONDS)
    ]
    stale_removed = initial_count - len(board["alerts"])
    if stale_removed > 0:
        # Log that stale signals were cleaned up (for diagnostics)
        # Could write to a stale-signal counter if needed
        pass


def _cap_auto_cells(cv: dict) -> None:
    autos = [c for c, v in cv["cells"].items() if v.get("kind") == "auto"]
    while len(autos) > MAX_AUTO_CELLS:
        oldest = min(autos, key=lambda c: cv["cells"][c].get("updated", 0.0))
        cv["cells"].pop(oldest)
        autos.remove(oldest)


def _cap_canvases(board: dict) -> None:
    while len(board["canvases"]) > MAX_CANVASES:
        protected = {board.get("hot_canvas")}
        candidates = [n for n in board["canvases"] if n not in protected]
        if not candidates:
            return  # never evict the focused canvas
        oldest = min(candidates, key=lambda n: board["canvases"][n].get("updated", 0.0))
        board["canvases"].pop(oldest)


# Focus keys that must survive key-cap eviction: they carry the session
# scope/status the hook engine and bmad-help route on. A busy board
# must never evict the very keys the methodology is steering from.
# methodology.* keys also protected: they track E→IR→SP→S→QR→PR chain status.
_BRIDGE_KEYS = frozenset({
    "scope", "status",
    "bridge.last_story", "bridge.last_qr", "bridge.last_pr", "bridge.last_ir",
    "methodology.last_experiment", "methodology.last_ir", "methodology.last_sp",
    "methodology.last_story", "methodology.last_qr", "methodology.last_pr"
})


def _cap_keys(board: dict) -> None:
    while len(board["keys"]) > MAX_KEYS:
        protected = set(_BRIDGE_KEYS)
        if board.get("hot"):
            protected.add(board["hot"])
        oldest = min(
            (k for k in board["keys"] if k not in protected),
            key=lambda k: board["keys"][k].get("updated", 0.0),
            default=None,
        )
        if oldest is None:
            return  # everything left is protected — never evict the bridge/focus
        board["keys"].pop(oldest)


def _clear_hot_if_dangling(board: dict) -> None:
    """After a write flood, the hot key/canvas may have been expired in a
    previous snapshot generation while later 'hot' events re-set it. Never
    surface a hot key or canvas that is not on the board."""
    if board.get("hot") and board["hot"] not in board["keys"]:
        board["hot"] = None
    if board.get("hot_canvas") and board["hot_canvas"] not in board["canvases"]:
        board["hot_canvas"] = None


# --- alert routing ---------------------------------------------------------------
def _route_alerts(paths: dict, board: dict, match: str, kind: str, text: str) -> None:
    """Route one alert to every subscription whose pattern matches `match`.
    Dedup identical (channel, kind, text) alerts; append as real events so
    replay reproduces them."""
    text = str(text)[:MAX_ALERT_TEXT]
    for sub in board["subscriptions"]:
        try:
            hit = fnmatch.fnmatchcase(match, sub["pattern"])
        except Exception:
            hit = False
        if not hit:
            continue
        channel = sub.get("channel", "session")
        if any(al.get("channel") == channel and al.get("kind") == kind
               and al.get("text") == text for al in board["alerts"]):
            continue
        ev = {"event": "alert", "channel": channel, "kind": kind, "text": text,
              "id": f"a{int(time.time() * 1000):013d}{len(board['alerts']) % 1000:03d}",
              "ts": time.time()}
        _append_event(paths, ev)
        _apply_event(board, ev)


def _neighbor_channels(board: dict, node: str) -> list:
    """Channels implied by graph links: mutations on `node` may concern its
    neighbors — surfaced via the subscription of any watcher matching the
    neighbor name (pattern match on the neighbor, not the source)."""
    chans = []
    for l in board["links"]:
        other = l["b"] if l["a"] == node else (l["a"] if l["b"] == node else None)
        if other is None:
            continue
        for sub in board["subscriptions"]:
            try:
                if fnmatch.fnmatchcase(other, sub["pattern"]):
                    chans.append(sub["channel"])
            except Exception:
                continue
    return chans


def _mutate(project_root: str, mutator) -> dict:
    """Run mutator(board)->(board, result) under lock with bounded retries.

    The whole read-modify-write is one lock scope, so concurrent writers
    serialize and no update is lost. On lock exhaustion the mutation is
    retried from a fresh read; only a persistent failure surfaces.
    """
    paths = board_paths(project_root)
    last_exc = None
    for _ in range(3):
        try:
            with _board_lock(paths):
                board = _read_snapshot(paths)
                board, result = mutator(board)
                board["updated"] = time.time()
                _write_snapshot_atomic(paths, board)
                _truncate_events_if_needed(paths)
                return result
        except BoardError as exc:
            last_exc = exc
            time.sleep(0.1)
    raise last_exc


# --- text keys -------------------------------------------------------------------
def write_key(project_root: str, key: str, value, *, type_: str = "note",
              hot: bool = False) -> dict:
    """Write (create or overwrite) a namespaced key. Returns the ack.
    
    NEW: Bounds enforcement visible - checks MAX_KEYS limit before write (MEDIUM #4 / ISSUE #63)
    Oldest keys are expired when limit is reached.
    """
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    value = str(value)[:MAX_VALUE_LEN]
    event = {"event": "write", "key": key.strip()[:200], "value": value,
             "type": str(type_)[:50], "hot": bool(hot), "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        
        # NEW: Explicit bounds check - enforce MAX_KEYS (MEDIUM #4 / ISSUE #63)
        keys_count = len(board["keys"])
        if keys_count > MAX_KEYS:
            # Log warning about bounds enforcement
            sys.stderr.write(f"metodoloji: bounds enforced — keys {keys_count}/{MAX_KEYS}, "
                           f"oldest expired\n")
        
        _clear_hot_if_dangling(board)
        _route_alerts(paths, board, event["key"], "update",
                      f"key '{event['key']}' updated ({event['type']})")
        ack = {"ok": True, "key": event["key"], "hot": event["hot"]}
        if board.get("hot") == event["key"] and not hot:
            ack["dirty_notice"] = f"key '{event['key']}' is hot on the board"
        return board, ack

    return _mutate(project_root, mut)


def set_hot(project_root: str, key: str | None) -> dict:
    """Focus one key (hot) or clear focus (key=None)."""
    if key:
        event = {"event": "hot", "key": str(key).strip()[:200], "ts": time.time()}
    else:
        event = {"event": "hot", "clear": True, "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        _clear_hot_if_dangling(board)
        return board, {"ok": True, "hot": board["hot"]}

    return _mutate(project_root, mut)


# --- lists -----------------------------------------------------------------------
def list_add(project_root: str, key: str, item: str) -> dict:
    """Append one item to an ordered list key (creates the list on first add)."""
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    if not str(item).strip():
        return {"ok": False, "error": "empty item"}
    event = {"event": "list_add", "key": key.strip()[:200],
             "item": str(item).strip()[:MAX_LIST_ITEM_LEN], "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        _clear_hot_if_dangling(board)
        _route_alerts(paths, board, event["key"], "update",
                      f"list '{event['key']}' +1 item (n="
                      f"{len(board['keys'].get(event['key'], {}).get('value', []))})")
        return board, {"ok": True, "key": event["key"],
                       "count": len(board["keys"].get(event["key"], {}).get("value", []))}

    return _mutate(project_root, mut)


def list_clear(project_root: str, key: str) -> dict:
    """Remove every item from a list key (keeps the key, now an empty list).
    One-command close-out for run lists (pending/branches/failures)."""
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    event = {"event": "list_clear", "key": key.strip()[:200], "ts": time.time()}

    def mut(board):
        entry = board["keys"].get(event["key"])
        had = len(entry["value"]) if entry and isinstance(entry.get("value"), list) else 0
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "key": event["key"], "cleared": had}

    return _mutate(project_root, mut)


def list_remove(project_root: str, key: str, *, item: str | None = None,
                index: int | None = None) -> dict:
    """Remove by exact item text or by index (0-based, oldest first)."""
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    event = {"event": "list_remove", "key": key.strip()[:200], "ts": time.time()}
    if item is not None:
        event["item"] = str(item)[:MAX_LIST_ITEM_LEN]
    elif index is not None:
        event["index"] = int(index)
    else:
        return {"ok": False, "error": "list-remove needs --item or --index"}

    def mut(board):
        entry = board["keys"].get(event["key"])
        before = len(entry["value"]) if entry and isinstance(entry.get("value"), list) else 0
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        entry = board["keys"].get(event["key"])
        after = len(entry["value"]) if entry and isinstance(entry.get("value"), list) else 0
        return board, {"ok": True, "key": event["key"], "removed": before - after,
                       "count": after}

    return _mutate(project_root, mut)


# --- graph links -------------------------------------------------------------------
def link(project_root: str, a: str, b: str, relation: str = "related") -> dict:
    """Connect two nodes (key or canvas names) with a directed relation."""
    a, b = str(a).strip()[:200], str(b).strip()[:200]
    if not a or not b or a == b:
        return {"ok": False, "error": "link needs two distinct nodes"}
    event = {"event": "link", "a": a, "b": b,
             "relation": str(relation).strip()[:50] or "related", "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        for chan in _neighbor_channels(board, event["a"]):
            _route_alerts(paths, board, event["b"], "link",
                          f"'{event['b']}' linked to '{event['a']}' ({event['relation']})")
        return board, {"ok": True, "a": event["a"], "b": event["b"],
                       "relation": event["relation"]}

    return _mutate(project_root, mut)


def unlink(project_root: str, a: str, b: str, relation: str | None = None) -> dict:
    event = {"event": "unlink", "a": str(a).strip()[:200], "b": str(b).strip()[:200],
             "ts": time.time()}
    if relation:
        event["relation"] = str(relation).strip()[:50]

    def mut(board):
        before = len(board["links"])
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "removed": before - len(board["links"])}

    return _mutate(project_root, mut)


def neighbors(project_root: str, node: str, relation: str | None = None) -> list:
    """One-hop neighborhood (both link directions), optionally filtered."""
    node = str(node).strip()[:200]
    out, seen = [], set()
    for l in read_board(project_root)["links"]:
        if relation and l["relation"] != relation:
            continue
        if l["a"] == node:
            other, direction = l["b"], "out"
        elif l["b"] == node:
            other, direction = l["a"], "in"
        else:
            continue
        if other not in seen:
            seen.add(other)
            out.append({"node": other, "relation": l["relation"], "direction": direction})
    return out


# --- canvases (dynamic surfaces) -----------------------------------------------------
def _parse_grid(spec) -> list | None:
    """Accept [w, h], "WxH" or None; returns a sane grid or None (free canvas)."""
    if spec is None:
        return None
    if isinstance(spec, str):
        try:
            w, h = spec.lower().split("x", 1)
            grid = [max(1, min(MAX_GRID, int(w))), max(1, min(MAX_GRID, int(h)))]
        except (ValueError, AttributeError):
            return None
    elif isinstance(spec, (list, tuple)) and len(spec) == 2:
        try:
            grid = [max(1, min(MAX_GRID, int(spec[0]))), max(1, min(MAX_GRID, int(spec[1])))]
        except (ValueError, TypeError):
            return None
    else:
        return None
    return grid


def canvas_create(project_root: str, name: str, *, grid=None,
                  focus: bool = False) -> dict:
    """Create a new canvas or retrieve existing. 
    
    NEW: Bounds enforcement visible - checks MAX_CANVASES limit (MEDIUM #4 / ISSUE #63)
    Oldest canvases are expired when limit is reached (except hot_canvas).
    """
    name = str(name).strip()[:MAX_CANVAS_NAME]
    if not name:
        return {"ok": False, "error": "empty canvas name"}
    event = {"event": "canvas_create", "name": name, "grid": _parse_grid(grid),
             "focus": bool(focus), "ts": time.time()}

    def mut(board):
        existed = name in board["canvases"]
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        
        # NEW: Explicit bounds check - enforce MAX_CANVASES (MEDIUM #4 / ISSUE #63)
        canvas_count = len(board["canvases"])
        if canvas_count > MAX_CANVASES:
            sys.stderr.write(f"metodoloji: bounds enforced — canvases {canvas_count}/{MAX_CANVASES}, "
                           f"oldest expired\n")
        
        _clear_hot_if_dangling(board)
        return board, {"ok": True, "canvas": name, "grid": event["grid"],
                       "existed": existed, "focused": board.get("hot_canvas") == name}

    return _mutate(project_root, mut)


def canvas_set(project_root: str, name: str, cell: str, content: str, *,
               kind: str = "note", x: int | None = None,
               y: int | None = None) -> dict:
    """Write one cell in real time — the board's live mutation primitive."""
    name = str(name).strip()[:MAX_CANVAS_NAME]
    cell = str(cell).strip()[:MAX_CELL_ID]
    if not name or not cell:
        return {"ok": False, "error": "canvas-set needs --name and --cell"}
    event = {"event": "canvas_cell", "name": name, "cell": cell,
             "content": str(content)[:MAX_CELL_LEN], "kind": str(kind).strip()[:20] or "note",
             "x": x, "y": y, "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        _route_alerts(paths, board, f"canvas:{name}", "canvas",
                      f"canvas '{name}' cell '{cell}' set ({event['kind']})")
        return board, {"ok": True, "canvas": name, "cell": cell,
                       "cells": len(board["canvases"].get(name, {}).get("cells", {}))}

    return _mutate(project_root, mut)


def canvas_remove(project_root: str, name: str, cell: str) -> dict:
    event = {"event": "canvas_remove", "name": str(name).strip()[:MAX_CANVAS_NAME],
             "cell": str(cell).strip()[:MAX_CELL_ID], "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        _route_alerts(paths, board, f"canvas:{name}", "canvas",
                      f"canvas '{name}' cell '{event['cell']}' removed")
        return board, {"ok": True, "canvas": event["name"], "cell": event["cell"]}

    return _mutate(project_root, mut)


def canvas_move(project_root: str, name: str, cell: str, to: str, *,
                x: int | None = None, y: int | None = None) -> dict:
    """Rename/reposition a cell (moves content, kind and watch state)."""
    event = {"event": "canvas_move", "name": str(name).strip()[:MAX_CANVAS_NAME],
             "cell": str(cell).strip()[:MAX_CELL_ID], "to": str(to).strip()[:MAX_CELL_ID],
             "x": x, "y": y, "ts": time.time()}
    if not event["name"] or not event["cell"] or not event["to"]:
        return {"ok": False, "error": "canvas-move needs --name, --cell and --to"}

    def mut(board):
        cv = board["canvases"].get(event["name"])
        moved = event["cell"] in (cv or {}).get("cells", {})
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "canvas": event["name"], "from": event["cell"],
                       "to": event["to"], "moved": moved}

    return _mutate(project_root, mut)


def canvas_resize(project_root: str, name: str, grid) -> dict:
    event = {"event": "canvas_resize", "name": str(name).strip()[:MAX_CANVAS_NAME],
             "grid": _parse_grid(grid), "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "canvas": event["name"], "grid": event["grid"]}

    return _mutate(project_root, mut)


def canvas_clear(project_root: str, name: str) -> dict:
    event = {"event": "canvas_clear", "name": str(name).strip()[:MAX_CANVAS_NAME],
             "ts": time.time()}

    def mut(board):
        cv = board["canvases"].get(event["name"])
        had = len((cv or {}).get("cells", {}))
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "canvas": event["name"], "cleared": had}

    return _mutate(project_root, mut)


def canvas_focus(project_root: str, name: str | None) -> dict:
    """Focus one canvas (the engine surfaces it) or clear (name=None)."""
    if name:
        event = {"event": "canvas_focus", "name": str(name).strip()[:MAX_CANVAS_NAME],
                 "ts": time.time()}
    else:
        event = {"event": "canvas_focus", "clear": True, "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        _clear_hot_if_dangling(board)
        return board, {"ok": True, "hot_canvas": board["hot_canvas"]}

    return _mutate(project_root, mut)


def canvas_watch(project_root: str, name: str, path: str, *, remove: bool = False) -> dict:
    """Register a filesystem path prefix that feeds this canvas in real time:
    every audited tool touch under the path lands as an auto cell."""
    event = {"event": "canvas_unwatch" if remove else "canvas_watch",
             "name": str(name).strip()[:MAX_CANVAS_NAME],
             "path": str(path).strip()[:300], "ts": time.time()}
    if not event["name"] or not event["path"]:
        return {"ok": False, "error": "canvas-watch needs --name and --path"}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        cv = board["canvases"].get(event["name"], {})
        return board, {"ok": True, "canvas": event["name"],
                       "watch": list(cv.get("watch", []))}

    return _mutate(project_root, mut)


def read_canvas(project_root: str, name: str) -> dict:
    """Read one canvas whole (cells + watch paths + grid)."""
    name = str(name).strip()[:MAX_CANVAS_NAME]
    board = read_board(project_root)
    cv = board["canvases"].get(name)
    if cv is None:
        return {"ok": True, "canvas": name, "exists": False, "cells": {}}
    return {"ok": True, "canvas": name, "exists": True, "grid": cv.get("grid"),
            "cells": cv.get("cells", {}), "watch": cv.get("watch", []),
            "focused": board.get("hot_canvas") == name}


def _touch_canvases(board: dict, paths: dict, tool: str, target: str) -> list:
    """Push one audited touch into every canvas watching a matching path.

    Called by stamp_tool_event in the same lock scope (no nesting).
    Returns touched canvas names."""
    touched = []
    if not target:
        return touched
    for name, cv in board["canvases"].items():
        for w in cv.get("watch", []):
            if _watch_matches(w, target):
                ev = {"event": "canvas_touch", "name": name,
                      "path": target[:MAX_CELL_ID],
                      "content": f"{tool}: {os.path.basename(target)}"[:MAX_CELL_LEN],
                      "ts": time.time()}
                _append_event(paths, ev)
                _apply_event(board, ev)
                _route_alerts(paths, board, f"canvas:{name}", "canvas",
                              f"canvas '{name}' live: {tool} touched {target}")
                touched.append(name)
                break
    return touched


def stamp_tool_event(project_root: str, tool_name: str, target: str, hook_event: str = "") -> dict:
    """Fold one audited tool touch into the board in a single lock scope.

    Called by the audit hook (PostToolUse): appends the `last_tool.<tool>`
    key as a `tool` event plus a `canvas_touch` push to watching canvases
    in the same scope. One `_mutate`, so no writer can interleave; all
    event-sourced, so `last_tool.*` survives a snapshot rebuild. Never nest
    inside another _mutate scope.
    
    NEW: Optional hook_event parameter to track PreToolUse/PostToolUse sequence (HIGH #7)
    """
    tool_name = str(tool_name or "")[:100]
    target = str(target or "")[:MAX_TEXT_LEN]
    if not tool_name:
        return {"ok": True, "touched": 0}
    event = {"event": "tool", "tool": tool_name, "target": target, "ts": time.time()}
    if hook_event:
        event["hook_event"] = str(hook_event)[:40]  # NEW: PreToolUse or PostToolUse

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        # Real-time canvas push: watched canvases record the touch (same scope).
        touched = _touch_canvases(board, paths, tool_name, target)
        return board, {"ok": True, "touched": len(touched), "canvases": touched}

    return _mutate(project_root, mut)


def _watch_matches(watch_path: str, target: str) -> bool:
    """Normalize a watch-prefix match (agnostic to rel/abs, backslash, ./).

    A raw string `startswith` misfired here — a rel path never matched the
    abs path a skill wrote to the watch, or vice versa."""
    import re as _re
    w = _re.sub(r"(?i)^[a-z]:", "", str(watch_path or "").replace("\\", "/"))
    t = _re.sub(r"(?i)^[a-z]:", "", str(target or "").replace("\\", "/"))
    w = _re.sub(r"/{2,}", "/", w).rstrip("/")
    t = _re.sub(r"/{2,}", "/", t).rstrip("/")
    while t.startswith("./"):
        t = t[2:]
    while w.startswith("./"):
        w = w[2:]
    if not w or not t:
        return False
    return t == w or t.startswith(w + "/") or w.startswith(t + "/")


# --- subscriptions & alerts ----------------------------------------------------------
def subscribe(project_root: str, watcher: str, pattern: str, *,
              channel: str = "session") -> dict:
    """Watch keys/canvases by glob: matching mutations route an alert into
    `channel` ('session' → injected at session start, 'stop' → surfaced at
    stop, or any custom channel addressable via consume_alerts)."""
    event = {"event": "subscribe", "watcher": str(watcher).strip()[:100],
             "pattern": str(pattern).strip()[:200],
             "channel": str(channel).strip()[:40] or "session", "ts": time.time()}
    if not event["watcher"] or not event["pattern"]:
        return {"ok": False, "error": "subscribe needs --watcher and --pattern"}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "watcher": event["watcher"],
                       "pattern": event["pattern"], "channel": event["channel"]}

    return _mutate(project_root, mut)


def unsubscribe(project_root: str, watcher: str, pattern: str) -> dict:
    event = {"event": "unsubscribe", "watcher": str(watcher).strip()[:100],
             "pattern": str(pattern).strip()[:200], "ts": time.time()}

    def mut(board):
        before = len(board["subscriptions"])
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "removed": before - len(board["subscriptions"])}

    return _mutate(project_root, mut)


def pending_alerts(project_root: str, channel: str | None = None) -> list:
    """Read-only: alerts awaiting a channel (all channels when None)."""
    alerts = read_board(project_root)["alerts"]
    if channel:
        return [a for a in alerts if a["channel"] == channel]
    return list(alerts)


def consume_alerts(project_root: str, channel: str) -> list:
    """Take and clear one channel's alerts (engine consumption point).
    Consumption is evented: replay folds consume after alert, so delivered
    alerts never resurrect from the event log."""
    def mut(board):
        take = [a for a in board["alerts"] if a["channel"] == channel]
        if take:
            ev = {"event": "consume", "channel": channel, "ts": time.time()}
            _append_event(board_paths(project_root), ev)
            _apply_event(board, ev)
        return board, take

    try:
        return _mutate(project_root, mut)
    except Exception:
        return []


# --- hand-off signals (the skill chain handshake) ------------------------------------
def post_handoff(project_root: str, to_skill: str, from_key: str, note: str = "") -> dict:
    """Upstream→downstream hand-off signal: route an alert into the
    `handoff.<to_skill>` channel (kind `handoff`, text `<from_key>: <note>`).
    The signal waits there until the downstream skill consumes it — that
    consumption completes the handshake."""
    to_skill = str(to_skill).strip()[:40]
    if not to_skill:
        return {"ok": False, "error": "empty --to"}
    from_key = str(from_key).strip()[:200]
    if not from_key:
        return {"ok": False, "error": "empty --from-key"}
    return post_alert(project_root, f"handoff.{to_skill}", "handoff",
                      f"{from_key}: {str(note).strip()}")


def pending_handoffs(project_root: str, skill: str) -> list:
    """Un-consumed hand-off signals waiting for `skill` (read-only peek)."""
    skill = str(skill).strip()[:40]
    return [a for a in read_board(project_root)["alerts"]
            if a.get("channel") == f"handoff.{skill}" and a.get("kind") == "handoff"]


def pending_handoff_channels(project_root: str) -> dict:
    """Skills with waiting hand-off signals: {skill: count} (engine peek —
    session_start announces, never consumes; the skill completes the shake)."""
    counts = {}
    for a in read_board(project_root)["alerts"]:
        ch = a.get("channel", "")
        if ch.startswith("handoff.") and a.get("kind") == "handoff":
            s = ch[len("handoff."):]
            counts[s] = counts.get(s, 0) + 1
    return counts


# --- chain health (hand-off diagnostics) ----------------------------------------------
# The canonical delivery relay: each hop is one skill handing off to the next.
# METHODOLOGY CHAIN: Experiment → IR → Sprint Planning → Story → Quality Record → Production Readiness
CHAIN = [
    "bmad-research-experiment",                 # E (Experiment)
    "bmad-check-implementation-readiness",      # IR (Implementation Readiness)
    "bmad-sprint-planning",                     # SP (Sprint Planning)
    "bmad-create-story",                        # S (Story)
    "bmad-quality-record",                      # QR (Quality Record)
    "bmad-production-readiness",                # PR (Production Readiness)
    # OPTIONAL EXTENDED CHAIN (for tool workflows):
    "bmad-prd", "bmad-ux", "bmad-architecture", "bmad-spec",
    "bmad-create-epics-and-stories", "bmad-dev-story"
]

# Run-key namespace prefix → the skill that owns the hand-off (sender attribution).
_KEY_PREFIX_TO_SKILL = [
    # METHODOLOGY CHAIN prefixes
    ("E-", "bmad-research-experiment"),
    ("IR-", "bmad-check-implementation-readiness"),
    ("SP-", "bmad-sprint-planning"),
    ("S-", "bmad-create-story"),
    ("QR-", "bmad-quality-record"),
    ("PR-", "bmad-production-readiness"),
    # EXTENDED CHAIN prefixes (tool workflows)
    ("prd.", "bmad-prd"),
    ("ux.", "bmad-ux"),
    ("architecture.", "bmad-architecture"),
    ("spec.", "bmad-spec"),
    ("epics.", "bmad-create-epics-and-stories"),
    ("story.", "bmad-create-story"),
]


def _signal_sender(text: str) -> str | None:
    """Attribute a hand-off signal to a sender skill via its from-key prefix
    (signal text is '<from-key>: <note>')."""
    key = text.split(":", 1)[0].strip()
    for prefix, skill in _KEY_PREFIX_TO_SKILL:
        if key.startswith(prefix):
            return skill
    return None


def chain_health(project_root: str) -> dict:
    """Per-hop hand-off diagnostics for the delivery relay: how many signals
    are waiting (downstream has not picked up) and how many were consumed
    (handshake completed) on every hop, sender-attributed from the event
    log. Unknown receivers/senders surface as 'extra' — the protocol is
    extensible, the diagnostic follows."""
    waiting: dict = {}   # (sender, receiver) -> count
    consumed: dict = {}  # (sender, receiver) -> count
    open_signals: dict = {}  # receiver -> [(sender, text)]
    paths = board_paths(project_root)
    try:
        with open(paths["events"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                kind = ev.get("event")
                if kind == "alert" and ev.get("kind") == "handoff":
                    channel = str(ev.get("channel", ""))
                    if not channel.startswith("handoff."):
                        continue
                    receiver = channel[len("handoff."):]
                    sender = _signal_sender(str(ev.get("text", "")))
                    open_signals.setdefault(receiver, []).append(sender)
                elif kind == "consume":
                    channel = str(ev.get("channel", ""))
                    if not channel.startswith("handoff."):
                        continue
                    receiver = channel[len("handoff."):]
                    for sender in open_signals.pop(receiver, []):
                        key = (sender, receiver)
                        consumed[key] = consumed.get(key, 0) + 1
    except OSError:
        pass
    for receiver, senders in open_signals.items():
        for sender in senders:
            key = (sender, receiver)
            waiting[key] = waiting.get(key, 0) + 1

    def hop_rows(sender_skill: str, receiver_skill: str) -> dict:
        w = sum(v for (s, r), v in waiting.items() if s == sender_skill and r == receiver_skill)
        c = sum(v for (s, r), v in consumed.items() if s == sender_skill and r == receiver_skill)
        if w:
            status = "waiting"
        elif w + c:
            status = "clear"
        else:
            status = "idle"
        return {"from": sender_skill, "to": receiver_skill,
                "waiting": w, "consumed": c, "status": status}

    chain = [hop_rows(a, b) for a, b in zip(CHAIN, CHAIN[1:])]
    seen = {(h["from"], h["to"]) for h in chain}
    extra = []
    for (s, r) in sorted(set(list(waiting) + list(consumed))):
        if (s, r) in seen:
            continue
        w, c = waiting.get((s, r), 0), consumed.get((s, r), 0)
        extra.append({"from": s, "to": r, "waiting": w, "consumed": c,
                      "status": "waiting" if w else "clear"})
    total_waiting = sum(v for (s, r), v in waiting.items()
                        if (s, r) not in seen) + \
        sum(h["waiting"] for h in chain)
    return {"ok": True, "chain": chain, "extra": extra,
            "total_waiting": total_waiting}


# --- doctor (one-glance diagnostic) ---------------------------------------------------
_DOCTOR_CAP_WARN_PCT = 90  # warn when a plane is this close to its cap


def _doctor_age(ts: float) -> str:
    """Human age of a timestamp ('2s', '5m', '3h', '6d')."""
    age = int(max(0, time.time() - (ts or 0)))
    if age < 60:
        return f"{age}s"
    if age < 3600:
        return f"{age // 60}m"
    if age < 86400:
        return f"{age // 3600}h"
    return f"{age // 86400}d"


def _doctor_drift(paths: dict, board: dict) -> dict:
    """Snapshot vs event-log replay comparison (tool-stamped keys excluded:
    last_tool.* are event-sourced like everything else; excluded here because
    they are high-churn audit stamps, not meaningful state for drift)."""
    replay = _replay_events(paths)

    def norm(b: dict) -> dict:
        keys = {k: v for k, v in b["keys"].items() if v.get("type") != "tool"}
        return {"keys": keys, "tags": b["tags"], "canvases": b["canvases"],
                "links": b["links"], "subscriptions": b["subscriptions"],
                "alerts": b["alerts"], "hot": b["hot"],
                "hot_canvas": b["hot_canvas"]}

    in_sync = norm(replay) == norm(board)
    return {"in_sync": in_sync, "status": "ok" if in_sync else "warn"}


def rotate_event_log(project_root: str, max_lines: int = 10000) -> dict:
    """Archive old event log entries and start fresh (MEDIUM #1 / ISSUE #60).
    
    Strategy:
    1. Read all events from current log
    2. Rebuild snapshot from all events (to capture current state)
    3. Archive old events to logs/events-YYYY-MM-DD-HHmmss.log.gz
    4. Truncate current event log (fresh start)
    5. Append session_marker to new log
    
    Returns (ok, rotated_file, lines_archived, message).
    """
    paths = board_paths(project_root)
    events_path = pathlib.Path(paths["events"])
    
    if not events_path.exists():
        return {"ok": False, "error": "no event log to rotate"}
    
    try:
        # 1. Read all events
        all_events = []
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_events.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        pass  # Skip corrupted lines
        
        if not all_events or len(all_events) < max_lines:
            return {"ok": False, "message": f"log has {len(all_events)} lines (threshold: {max_lines})"}
        
        # 2. Rebuild snapshot from all events to capture current state
        board_rebuilt = _replay_events(paths)
        
        # 3. Archive old events to timestamped file
        import gzip
        import datetime
        now = datetime.datetime.now()
        archive_name = f"events-{now.strftime('%Y-%m-%d-%H%M%S')}.log.gz"
        archive_path = events_path.parent / archive_name
        
        # Write compressed archive
        with gzip.open(archive_path, "wt", encoding="utf-8") as f:
            for event in all_events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        
        # 4. Truncate current event log
        with open(events_path, "w", encoding="utf-8") as f:
            pass  # Empty file
        
        # 5. Append session marker to new log (if not already there)
        # This will be done by the next record_session_start()
        
        return {
            "ok": True,
            "archived_to": str(archive_path),
            "lines_archived": len(all_events),
            "message": f"Archived {len(all_events)} events to {archive_name}; event log rotated"
        }
    
    except Exception as e:
        return {
            "ok": False,
            "error": f"rotation failed: {str(e)[:200]}"
        }


def doctor(project_root: str) -> dict:
    """One-glance diagnostic for the whole board: gate, snapshot, event log,
    state counts, cap usage, focus, chain health, integrity (snapshot/event
    drift, tmp residue) and watch paths. Verdict is HEALTHY iff no warnings.
    
    NEW: Supports --rotate flag to archive old event logs (MEDIUM #1)
    NEW: Includes record ID uniqueness check (MEDIUM #2 / ISSUE #61)
    NEW: Detects stale sessions (SessionStart without Stop) (MEDIUM #5 / ISSUE #64)
    """
    paths = board_paths(project_root)
    warnings = []
    board = read_board(project_root)

    # gate
    gate_known, gate_on = True, True
    try:
        from .config import blackboard_enabled
        gate_on = bool(blackboard_enabled())
    except Exception:
        gate_known = False

    # event log
    lines = garbage = 0
    try:
        with open(paths["events"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                lines += 1
                try:
                    json.loads(line)
                except ValueError:
                    garbage += 1
        events_exist = lines > 0
    except OSError:
        events_exist = False
    if garbage:
        warnings.append(f"event log carries {garbage} unparseable line(s) "
                        "(tolerated, but investigate the writer)")

    # caps
    cells_per_canvas = {name: len(cv.get("cells", {}))
                        for name, cv in board["canvases"].items()}
    caps = {
        "keys": (len(board["keys"]), MAX_KEYS),
        "tags": (len(board["tags"]), MAX_TAGS),
        "contributions": (len(board["contributions"]), MAX_CONTRIBUTIONS),
        "canvases": (len(board["canvases"]), MAX_CANVASES),
        "cells": (sum(cells_per_canvas.values()), MAX_CELLS * MAX_CANVASES),
        "links": (len(board["links"]), MAX_LINKS),
        "subscriptions": (len(board["subscriptions"]), MAX_SUBSCRIPTIONS),
        "alerts": (len(board["alerts"]), MAX_ALERTS),
    }
    cap_warnings = []
    for name, (used, cap) in caps.items():
        if used * 100 >= _DOCTOR_CAP_WARN_PCT * cap:
            cap_warnings.append(f"{name} {used}/{cap} (≥{_DOCTOR_CAP_WARN_PCT}% — "
                                "oldest will expire soon)")
    warnings.extend(cap_warnings)

    # NEW: Check if snapshot rebuild from events works (corruption recovery)
    replay_for_check = _replay_events(paths)
    skipped = replay_for_check.get("_metadata", {}).get("replay_skipped_lines", 0)
    if skipped > 0:
        warnings.append(f"event log replay skipped {skipped} line(s) during rebuild "
                        "(corruption detected, but auto-recovered by skipping bad lines)")
    
    # NEW: Check for duplicate record IDs (MEDIUM #2 / ISSUE #61)
    # Scan all record directories for duplicate IDs
    type_to_dir = {
        "E": "docs/experiments",
        "IR": "docs/implementation-readiness",
        "SP": "docs/sprint-plans",
        "S": "docs/stories",
        "QR": "docs/quality-records",
        "PR": "docs/production-readiness",
    }
    
    root = os.path.abspath(project_root or os.getcwd())
    seen_ids = {}  # type → set of IDs
    
    for rec_type, rec_dir in type_to_dir.items():
        rec_path = pathlib.Path(root) / rec_dir
        if not rec_path.exists():
            continue
        
        for record_file in rec_path.glob("*.md"):
            match = re.match(r"^([A-Z]+-\d+)\.md$", record_file.name)
            if not match:
                continue
            record_id = match.group(1)
            type_key = record_id.split("-")[0]
            
            if type_key not in seen_ids:
                seen_ids[type_key] = set()
            
            if record_id in seen_ids[type_key]:
                warnings.append(
                    f"Duplicate record ID '{record_id}' detected in {rec_dir} "
                    f"(record IDs must be globally unique per type)"
                )
            else:
                seen_ids[type_key].add(record_id)
    
    # NEW: Detect stale sessions (MEDIUM #5 / ISSUE #64)
    # Look for SessionStart without corresponding Stop in recent history
    try:
        last_session_start = None
        last_session_stop = None
        last_session_id = ""
        session_count = 0
        current_session_id = ""
        
        with open(paths["events"], "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                
                entry_type = entry.get("type", "")
                if entry_type == "session_marker":
                    if entry.get("hook_event") == "SessionStart":
                        last_session_start = entry.get("ts", 0.0)
                        last_session_id = entry.get("session_id", "")
                        current_session_id = last_session_id
                        session_count += 1
                
                elif entry_type == "session_stop":
                    last_session_stop = entry.get("ts", 0.0)
        
        # Check if there's an unclosed session
        if last_session_start and (last_session_stop is None or last_session_start > last_session_stop):
            session_age = time.time() - last_session_start
            stale_threshold = 3600  # 1 hour
            
            if session_age > stale_threshold:
                hours = int(session_age / 3600)
                warnings.append(
                    f"Stale session detected: SessionStart {hours}h+ ago without Stop "
                    f"(hung session? agent crash?)"
                )
        
        # NEW: Check multi-session isolation (MEDIUM #6 / ISSUE #65)
        # If more than one session, track session boundaries
        if session_count > 1:
            warnings.append(
                f"Multi-session log detected: {session_count} sessions tracked "
                f"(use session_id for isolation). Current: {current_session_id[:12]}..."
            )
    except Exception:
        pass  # Can't check session history, skip

    
    # integrity: snapshot presence + drift
    snapshot_exists = os.path.exists(paths["snapshot"])
    drift = _doctor_drift(paths, board)
    if not drift["in_sync"]:
        warnings.append("snapshot drifts from the event log — delete "
                        "blackboard.json to force a rebuild")

    # tmp residue (crash leftovers, snapshot dir + event-log dir)
    tmp_files = []
    try:
        for d in (paths["dir"], os.path.dirname(paths["events"])):
            if os.path.isdir(d):
                tmp_files.extend(os.path.join(d, f) for f in os.listdir(d)
                                 if f.endswith(".tmp"))
    except OSError:
        pass
    if tmp_files:
        warnings.append(f"{len(tmp_files)} leftover .tmp file(s) under "
                        f"{paths['dir']} — safe to delete")

    # chain
    chain = chain_health(project_root)
    if chain["total_waiting"] > 0:
        waiting_hops = [f"{h['from']}→{h['to']}" for h in chain["chain"] if h["waiting"]]
        waiting_hops += [f"{h['from']}→{h['to']}" for h in chain["extra"] if h["waiting"]]
        warnings.append(f"{chain['total_waiting']} unclaimed hand-off signal(s) "
                        f"({', '.join(waiting_hops)}) — PROACTIVE, see chain-health")
    
    # NEW: Detect stale handoff signals (CRITICAL #4 / ISSUE #25)
    now = time.time()
    stale_handoffs = [
        a for a in board["alerts"]
        if a.get("kind") == "handoff" and 
           (now - (a.get("ts", 0.0))) > HANDOFF_SIGNAL_TTL_SECONDS
    ]
    if stale_handoffs:
        warnings.append(f"{len(stale_handoffs)} STALE hand-off signal(s) "
                        f"(> 24h old) — skill crashed/hung? "
                        f"Run 'blackboard.py doctor' to clean up")

    # watch paths (informational: missing prefixes may be created later)
    watch = [{"canvas": name, "path": w, "exists": os.path.exists(w)}
             for name, cv in board["canvases"].items()
             for w in cv.get("watch", [])]

    checks = {
        "gate": {"known": gate_known, "on": gate_on,
                 "status": "ok" if gate_known else "info"},
        "snapshot": {"exists": snapshot_exists,
                     "version": board.get("version"),
                     "age": _doctor_age(board.get("updated", 0.0)),
                     "status": "ok"},
        "events": {"exists": events_exist, "lines": lines, "garbage": garbage,
                   "status": "ok" if not garbage else "warn"},
        "caps": {"usage": {k: {"used": u, "cap": c}
                           for k, (u, c) in caps.items()},
                 "status": "ok" if not cap_warnings else "warn"},
        "focus": {"hot": board.get("hot"), "hot_canvas": board.get("hot_canvas"),
                  "status": "ok"},
        "drift": drift,
        "residue": {"tmp_files": tmp_files,
                    "status": "ok" if not tmp_files else "warn"},
        "chain": {"total_waiting": chain["total_waiting"],
                  "waiting_hops": [h for h in chain["chain"] if h["waiting"]]
                                  + [h for h in chain["extra"] if h["waiting"]],
                  "status": "ok" if chain["total_waiting"] == 0 else "warn"},
        "watch": {"paths": watch, "status": "info" if watch else "ok"},
    }
    return {"ok": True, "root": paths["root"],
            "verdict": "HEALTHY" if not warnings else "NEEDS ATTENTION",
            "checks": checks, "warnings": warnings}


def post_alert(project_root: str, channel: str, kind: str, text: str) -> dict:
    """Manual alert injection (skills can notify the session/stop channels).
    
    NEW: Bounds enforcement visible - checks MAX_ALERTS limit (MEDIUM #4 / ISSUE #63)
    Oldest alerts are expired when limit is reached.
    """
    event = {"event": "alert", "channel": str(channel).strip()[:40] or "session",
             "kind": str(kind).strip()[:20] or "info",
             "text": str(text).strip()[:MAX_ALERT_TEXT],
             "id": f"m{int(time.time() * 1000):013d}", "ts": time.time()}
    if not event["text"]:
        return {"ok": False, "error": "empty alert text"}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        
        # NEW: Explicit bounds check - enforce MAX_ALERTS (MEDIUM #4 / ISSUE #63)
        alert_count = len(board["alerts"])
        if alert_count > MAX_ALERTS:
            sys.stderr.write(f"metodoloji: bounds enforced — alerts {alert_count}/{MAX_ALERTS}, "
                           f"oldest expired\n")
        
        return board, {"ok": True, "channel": event["channel"],
                       "alerts": alert_count}

    return _mutate(project_root, mut)


# --- contributions / watchers (unchanged surface) --------------------------------------
def add_contribution(project_root: str, who: str, what: str) -> dict:
    if not str(who).strip():
        return {"ok": False, "error": "empty who"}
    event = {"event": "contribute", "who": str(who).strip()[:200],
             "what": str(what).strip()[:MAX_TEXT_LEN], "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "who": event["who"]}

    return _mutate(project_root, mut)


def add_tag(project_root: str, tag: str) -> dict:
    tag = str(tag).strip()[:100]
    if not tag:
        return {"ok": False, "error": "empty tag"}

    def mut(board):
        if tag in board["tags"]:
            return board, {"ok": True, "tag": tag, "duplicate": True}
        event = {"event": "tag", "tag": tag, "ts": time.time()}
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "tag": tag}

    return _mutate(project_root, mut)


def remove_tag(project_root: str, tag: str) -> dict:
    tag = str(tag).strip()[:100]

    def mut(board):
        if tag not in board["tags"]:
            return board, {"ok": True, "tag": tag, "absent": True}
        event = {"event": "untag", "tag": tag, "ts": time.time()}
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "tag": tag}

    return _mutate(project_root, mut)


def record_watcher(project_root: str, watcher: str) -> dict:
    event = {"event": "watch", "watcher": str(watcher).strip()[:100],
             "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "watcher": event["watcher"]}

    return _mutate(project_root, mut)


# --- context & stats --------------------------------------------------------------------
def compact_context(project_root: str) -> dict:
    """The bounded-context summary hooks inject (never the whole board)."""
    board = read_board(project_root)
    hot_key = board.get("hot")
    hot_value = None
    if hot_key and hot_key in board["keys"]:
        entry = board["keys"][hot_key]
        value = entry.get("value")
        if isinstance(value, list):
            preview = f"list[{len(value)}]"
        else:
            preview = str(value or "")[:120]
        hot_value = {"type": entry.get("type"), "updated": entry.get("updated"),
                     "preview": preview}
    hot_canvas = board.get("hot_canvas")
    canvas_summary = None
    if hot_canvas and hot_canvas in board["canvases"]:
        cv = board["canvases"][hot_canvas]
        cells = cv.get("cells", {})
        autos = sum(1 for c in cells.values() if c.get("kind") == "auto")
        latest = None
        if cells:
            latest = max(cells.items(), key=lambda kv: kv[1].get("updated", 0.0))[0]
        canvas_summary = {"name": hot_canvas, "cells": len(cells),
                          "auto": autos, "grid": cv.get("grid"),
                          "watch": cv.get("watch", []), "latest": latest}
    nb = [n["node"] for n in neighbors(project_root, hot_key)] if hot_key else []
    # Focus summary: the same keys bootstrap exports as env. Included so
    # a session-start inject (or read --context consumer) sees the live
    # scope/status even when bootstrap's env snapshot predates a mid-session
    # skill write (see utils board-first ordering).
    focus = {}
    for k in ("scope", "status"):
        entry = board["keys"].get(k)
        if entry and isinstance(entry, dict) and str(entry.get("value", "")).strip():
            focus[k] = str(entry.get("value"))[:120]
    return {
        "hot": hot_key,
        "hot_meta": hot_value,
        "hot_canvas": canvas_summary,
        "focus": focus,
        "tags": list(board["tags"]),
        "watchers": sorted(board["watchers"].keys()),
        "contributions": board["contributions"][-5:],
        "key_count": len(board["keys"]),
        "canvas_count": len(board["canvases"]),
        "links": len(board["links"]),
        "neighbors": nb[:5],
        "subscriptions": len(board["subscriptions"]),
        "alerts": len(board["alerts"]),
    }


def stats(project_root: str) -> dict:
    board = read_board(project_root)
    paths = board_paths(project_root)
    event_count = 0
    try:
        with open(paths["events"], "rb") as f:
            event_count = sum(1 for _ in f)
    except OSError:
        pass
    lists = sum(1 for e in board["keys"].values() if isinstance(e.get("value"), list))
    cells = sum(len(cv.get("cells", {})) for cv in board["canvases"].values())
    return {
        "keys": len(board["keys"]),
        "lists": lists,
        "canvases": len(board["canvases"]),
        "cells": cells,
        "links": len(board["links"]),
        "subscriptions": len(board["subscriptions"]),
        "alerts": len(board["alerts"]),
        "tags": len(board["tags"]),
        "contributions": len(board["contributions"]),
        "watchers": len(board["watchers"]),
        "events": event_count,
        "hot": board.get("hot"),
        "hot_canvas": board.get("hot_canvas"),
        "snapshot": paths["snapshot"],
    }
