"""Blackboard — dynamic, event-sourced working context for the methodology.

One JSON snapshot (``.metodoloji/blackboard.json``) plus an append-only event
log (``.metodoloji/logs/blackboard-events.log``). Every mutation is written as
an event first; the snapshot is a cache rebuilt from events when missing or
corrupt. All file operations are atomic (temp file + rename) and guarded by an
exclusive lock file so concurrent hook processes never interleave.

Design invariants (docs/BLACKBOARD.md):
- Fail-open: every public function returns a usable default on any error.
- Bounded: keys/tags/contributions/events expire oldest-first.
- No auto content generation: the board only holds what a writer put there.
"""

from __future__ import annotations

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
    return {"version": 1, "hot": None, "keys": {}, "tags": [],
            "contributions": [], "watchers": {}, "updated": 0.0}


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
        if not board["keys"] and not board["tags"] and not board["contributions"]:
            replay = _replay_events(paths)
            if replay["keys"] or replay["tags"] or replay["contributions"]:
                _write_snapshot_atomic(paths, replay)
                board = replay
    if board.get("hot") and board["hot"] not in board["keys"]:
        board["hot"] = None
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


def _cap_keys(board: dict) -> None:
    while len(board["keys"]) > MAX_KEYS:
        oldest = min(board["keys"], key=lambda k: board["keys"][k].get("updated", 0.0))
        board["keys"].pop(oldest)
        if board["hot"] == oldest:
            board["hot"] = None


def _clear_hot_if_dangling(board: dict) -> None:
    """After a write flood, the hot key may have been expired in a previous
    snapshot generation while later 'hot' events re-set it. Never surface a
    hot key that is not on the board."""
    if board.get("hot") and board["hot"] not in board["keys"]:
        board["hot"] = None


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


def write_key(project_root: str, key: str, value, *, type_: str = "note",
              hot: bool = False) -> dict:
    """Write (create or overwrite) a namespaced key. Returns the ack."""
    if not key or not str(key).strip():
        return {"ok": False, "error": "empty key"}
    value = str(value)[:MAX_VALUE_LEN]
    event = {"event": "write", "key": key.strip()[:200], "value": value,
             "type": str(type_)[:50], "hot": bool(hot), "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        _clear_hot_if_dangling(board)
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


def record_watcher(project_root: str, watcher: str) -> dict:
    event = {"event": "watch", "watcher": str(watcher).strip()[:100],
             "ts": time.time()}

    def mut(board):
        _append_event(board_paths(project_root), event)
        _apply_event(board, event)
        return board, {"ok": True, "watcher": event["watcher"]}

    return _mutate(project_root, mut)


def compact_context(project_root: str) -> dict:
    """The bounded-context summary hooks inject (never the whole board)."""
    board = read_board(project_root)
    hot_key = board.get("hot")
    hot_value = None
    if hot_key and hot_key in board["keys"]:
        entry = board["keys"][hot_key]
        hot_value = {"type": entry.get("type"), "updated": entry.get("updated")}
    return {
        "hot": hot_key,
        "hot_meta": hot_value,
        "tags": list(board["tags"]),
        "watchers": sorted(board["watchers"].keys()),
        "contributions": board["contributions"][-5:],
        "key_count": len(board["keys"]),
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
    return {
        "keys": len(board["keys"]),
        "tags": len(board["tags"]),
        "contributions": len(board["contributions"]),
        "watchers": len(board["watchers"]),
        "events": event_count,
        "hot": board.get("hot"),
        "snapshot": paths["snapshot"],
    }
