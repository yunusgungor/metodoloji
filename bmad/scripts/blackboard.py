#!/usr/bin/env python3
"""Blackboard CLI — read/write the project's dynamic working context.

Usage:
    python3 blackboard.py read   [--key K] [--context] [--project-root R]
    python3 blackboard.py write  --key K --value V [--type T] [--hot] [--project-root R]
    python3 blackboard.py tag    --tag T [--project-root R]
    python3 blackboard.py untag  --tag T [--project-root R]
    python3 blackboard.py contribute --who W --what X [--project-root R]
    python3 blackboard.py hot    --key K | --clear [--project-root R]
    python3 blackboard.py stats  [--project-root R]

Writes print a one-line JSON ack ({"ok": true, ...}). Reads print JSON;
`read --context` prints the compact bounded-context summary hooks inject.
Fail-open: missing/corrupt state yields an empty result and exit 0.
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE = os.path.join(_HERE, "..", "..", "hooks", "engine")
sys.path.insert(0, _ENGINE)

from modules import blackboard as bb  # noqa: E402


def _root(args) -> str:
    return getattr(args, "project_root", None) or os.getcwd()


def _emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_read(args) -> int:
    root = _root(args)
    if args.context:
        _emit(bb.compact_context(root))
        return 0
    board = bb.read_board(root)
    if args.key:
        entry = board["keys"].get(args.key)
        if entry is None:
            _emit({"ok": True, "key": args.key, "value": None})
        else:
            _emit({"ok": True, "key": args.key, "value": entry.get("value"),
                   "type": entry.get("type"), "updated": entry.get("updated")})
        return 0
    _emit({"ok": True, "hot": board.get("hot"), "keys": board["keys"],
           "tags": board["tags"], "contributions": board["contributions"],
           "watchers": board["watchers"]})
    return 0


def cmd_write(args) -> int:
    ack = bb.write_key(_root(args), args.key, args.value,
                       type_=args.type, hot=args.hot)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_tag(args) -> int:
    _emit(bb.add_tag(_root(args), args.tag))
    return 0


def cmd_untag(args) -> int:
    _emit(bb.remove_tag(_root(args), args.tag))
    return 0


def cmd_contribute(args) -> int:
    ack = bb.add_contribution(_root(args), args.who, args.what)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_hot(args) -> int:
    key = None if args.clear else args.key
    if key is None and not args.clear:
        _emit({"ok": False, "error": "hot requires --key or --clear"})
        return 1
    _emit(bb.set_hot(_root(args), key))
    return 0


def cmd_stats(args) -> int:
    _emit(bb.stats(_root(args)))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="blackboard.py",
                                description="Methodology blackboard CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--project-root", default=None,
                        help="Project root (default: cwd)")

    r = sub.add_parser("read", help="Read the board")
    r.add_argument("--key", default=None, help="Read one key")
    r.add_argument("--context", action="store_true",
                   help="Compact bounded-context summary")
    common(r)
    r.set_defaults(fn=cmd_read)

    w = sub.add_parser("write", help="Write one key")
    w.add_argument("--key", required=True)
    w.add_argument("--value", required=True)
    w.add_argument("--type", default="note",
                   help="free-form type tag (note|decision|state|...)")
    w.add_argument("--hot", action="store_true",
                   help="Also focus this key as the board's hot key")
    common(w)
    w.set_defaults(fn=cmd_write)

    t = sub.add_parser("tag", help="Add a project tag")
    t.add_argument("--tag", required=True)
    common(t)
    t.set_defaults(fn=cmd_tag)

    u = sub.add_parser("untag", help="Remove a project tag")
    u.add_argument("--tag", required=True)
    common(u)
    u.set_defaults(fn=cmd_untag)

    c = sub.add_parser("contribute", help="Record a contribution")
    c.add_argument("--who", required=True)
    c.add_argument("--what", required=True)
    common(c)
    c.set_defaults(fn=cmd_contribute)

    h = sub.add_parser("hot", help="Focus one key / clear focus")
    h.add_argument("--key", default=None)
    h.add_argument("--clear", action="store_true")
    common(h)
    h.set_defaults(fn=cmd_hot)

    s = sub.add_parser("stats", help="Board statistics")
    common(s)
    s.set_defaults(fn=cmd_stats)

    args = p.parse_args()
    try:
        return args.fn(args)
    except Exception as exc:  # fail-open: never crash on board errors
        _emit({"ok": False, "error": str(exc)})
        return 0


if __name__ == "__main__":
    sys.exit(main())
