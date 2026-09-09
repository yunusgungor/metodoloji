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

# Watcher stamps recorded by the engine, bounded.
MAX_WATCHERS = 16


class BoardError(Exception):
    """Raised internally; public API converts to fail-open defaults."""


# --- Locking -----------------------------------------------------------------
def _acquire_lock(lock_path: str):
    """Acquire an exclusive advisory lock; None only when locking is unsupported.

    Windows: msvcrt.locking is byte-range based and non-blocking LK_NBLCK
    raises on contention — retry a bounded number of times. When the lock
    cannot be taken at all the caller proceeds unguarded (fail-open) and the
    per-process tmp filename keeps the snapshot rename safe.
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
    for attempt in range(600):  # ~12s worst case
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            if attempt in (25, 50, 100, 200):  # progressive backoff marks
                time.sleep(0.05 + 0.01 * attempt)
            else:
                time.sleep(0.02)
    raise BoardError("lock busy")  # caller retries the mutation atomically


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
    """Fold the event log into a board (used to rebuild a lost snapshot)."""
    board = _empty_board()
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
                _apply_event(board, ev)
    except OSError:
        pass
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


def _cap_keys(board: dict) -> None:
    while len(board["keys"]) > MAX_KEYS:
        oldest = min(board["keys"], key=lambda k: board["keys"][k].get("updated", 0.0))
        board["keys"].pop(oldest)
        if board["hot"] == oldest:
            board["hot"] = None


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
    """Write (create or overwrite) a namespaced key. Returns the ack."""
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    value = str(value)[:MAX_VALUE_LEN]
    event = {"event": "write", "key": key.strip()[:200], "value": value,
             "type": str(type_)[:50], "hot": bool(hot), "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
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
    name = str(name).strip()[:MAX_CANVAS_NAME]
    if not name:
        return {"ok": False, "error": "empty canvas name"}
    event = {"event": "canvas_create", "name": name, "grid": _parse_grid(grid),
             "focus": bool(focus), "ts": time.time()}

    def mut(board):
        existed = name in board["canvases"]
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
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


def watch_touch(project_root: str, tool: str, target: str) -> dict:
    """Real-time push: an audited tool touched `target` — land it into every
    canvas that watches a matching path prefix and alert the session channel.
    Single lock scope: all matched canvases update atomically together."""
    target = str(target or "")
    if not target or target == tool:
        return {"ok": True, "touched": 0}

    def mut(board):
        paths = board_paths(project_root)
        touched = []
        for name, cv in board["canvases"].items():
            for w in cv.get("watch", []):
                if target.startswith(w):
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
        return board, {"ok": True, "touched": len(touched), "canvases": touched}

    return _mutate(project_root, mut)


def canvas_touch(project_root: str, name: str, path: str, *,
                 content: str = "") -> dict:
    """Land one auto cell into a canvas (real-time feed primitive — used by
    watch_touch's single-scope path and callable directly for programmatic
    feeds). Never nest inside another _mutate scope."""
    name = str(name).strip()[:MAX_CANVAS_NAME]
    path = str(path).strip()[:MAX_CELL_ID]
    if not name or not path:
        return {"ok": False, "error": "canvas-touch needs --name and --path"}
    event = {"event": "canvas_touch", "name": name, "path": path,
             "content": str(content)[:MAX_CELL_LEN], "ts": time.time()}

    def mut(board):
        paths = board_paths(project_root)
        _append_event(paths, event)
        _apply_event(board, event)
        _route_alerts(paths, board, f"canvas:{name}", "canvas",
                      f"canvas '{name}' live: {path} updated")
        return board, {"ok": True, "canvas": name, "cell": path,
                       "cells": len(board["canvases"].get(name, {}).get("cells", {}))}

    return _mutate(project_root, mut)


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


def post_alert(project_root: str, channel: str, kind: str, text: str) -> dict:
    """Manual alert injection (skills can notify the session/stop channels)."""
    event = {"event": "alert", "channel": str(channel).strip()[:40] or "session",
             "kind": str(kind).strip()[:20] or "info",
             "text": str(text).strip()[:MAX_ALERT_TEXT],
             "id": f"m{int(time.time() * 1000):013d}", "ts": time.time()}
    if not event["text"]:
        return {"ok": False, "error": "empty alert text"}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "channel": event["channel"],
                       "alerts": len(board["alerts"])}

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
    return {
        "hot": hot_key,
        "hot_meta": hot_value,
        "hot_canvas": canvas_summary,
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
