#!/usr/bin/env python3
"""Blackboard CLI — read/write the project's dynamic working context.

The board is a project-wide network: text keys, ordered lists, dynamic
canvases (real-time surfaces), graph links, subscriptions and alerts.

Usage:
    python3 blackboard.py read    [--key K] [--context] [--project-root R]
    python3 blackboard.py write   --key K --value V [--type T] [--hot]
    python3 blackboard.py list-add    --key K --item X   (append)
    python3 blackboard.py list-remove --key K (--item X | --index N)
    python3 blackboard.py canvas-create  --name N [--grid WxH] [--focus]
    python3 blackboard.py canvas-set     --name N --cell C --content X [--kind K] [--x N --y N]
    python3 blackboard.py canvas-remove  --name N --cell C
    python3 blackboard.py canvas-move    --name N --cell C --to D [--x N --y N]
    python3 blackboard.py canvas-resize  --name N --grid WxH
    python3 blackboard.py canvas-clear   --name N
    python3 blackboard.py canvas-focus   --name N | --clear
    python3 blackboard.py canvas-watch   --name N --path P [--remove]
    python3 blackboard.py canvas-read    --name N
    python3 blackboard.py link      --a A --b B [--relation R]
    python3 blackboard.py unlink    --a A --b B [--relation R]
    python3 blackboard.py neighbors --node N [--relation R]
    python3 blackboard.py subscribe   --watcher W --pattern P [--channel C]
    python3 blackboard.py unsubscribe --watcher W --pattern P
    python3 blackboard.py alerts   [--channel C]        (read-only peek)
    python3 blackboard.py consume  --channel C          (take and clear)
    python3 blackboard.py notify   --channel C --kind K --text X
    python3 blackboard.py tag/untag --tag T
    python3 blackboard.py contribute --who W --what X
    python3 blackboard.py hot --key K | --clear
    python3 blackboard.py stats

All commands accept --project-root R (default: cwd). Writes print a one-line
JSON ack ({"ok": true, ...}). Reads print JSON; `read --context` prints the
compact bounded-context summary hooks inject. Fail-open: missing/corrupt
state yields an empty result and exit 0.
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


# --- reads -------------------------------------------------------------------
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
    _emit({"ok": True, "hot": board.get("hot"), "hot_canvas": board.get("hot_canvas"),
           "keys": board["keys"], "tags": board["tags"],
           "contributions": board["contributions"], "links": board["links"],
           "canvases": board["canvases"], "subscriptions": board["subscriptions"],
           "alerts": board["alerts"], "watchers": board["watchers"]})
    return 0


def cmd_canvas_read(args) -> int:
    _emit(bb.read_canvas(_root(args), args.name))
    return 0


def cmd_alerts(args) -> int:
    _emit({"ok": True, "alerts": bb.pending_alerts(_root(args), args.channel)})
    return 0


def cmd_consume(args) -> int:
    _emit({"ok": True, "channel": args.channel,
           "alerts": bb.consume_alerts(_root(args), args.channel)})
    return 0


def cmd_neighbors(args) -> int:
    _emit({"ok": True, "node": args.node,
           "neighbors": bb.neighbors(_root(args), args.node, args.relation)})
    return 0


# --- writes -------------------------------------------------------------------
def cmd_write(args) -> int:
    ack = bb.write_key(_root(args), args.key, args.value,
                       type_=args.type, hot=args.hot)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_list_add(args) -> int:
    ack = bb.list_add(_root(args), args.key, args.item)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_list_remove(args) -> int:
    ack = bb.list_remove(_root(args), args.key, item=args.item, index=args.index)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_canvas(args) -> int:
    root = _root(args)
    if args.action == "create":
        ack = bb.canvas_create(root, args.name, grid=args.grid, focus=args.focus)
    elif args.action == "set":
        ack = bb.canvas_set(root, args.name, args.cell, args.content,
                            kind=args.kind, x=args.x, y=args.y)
    elif args.action == "remove":
        ack = bb.canvas_remove(root, args.name, args.cell)
    elif args.action == "move":
        ack = bb.canvas_move(root, args.name, args.cell, args.to, x=args.x, y=args.y)
    elif args.action == "resize":
        ack = bb.canvas_resize(root, args.name, args.grid)
    elif args.action == "clear":
        ack = bb.canvas_clear(root, args.name)
    elif args.action == "focus":
        name = None if args.clear else args.name
        if name is None and not args.clear:
            _emit({"ok": False, "error": "canvas-focus requires --name or --clear"})
            return 1
        ack = bb.canvas_focus(root, name)
    elif args.action == "watch":
        ack = bb.canvas_watch(root, args.name, args.path, remove=args.remove)
    else:
        ack = {"ok": False, "error": f"unknown canvas action: {args.action}"}
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_link(args) -> int:
    ack = bb.link(_root(args), args.a, args.b, relation=args.relation)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_unlink(args) -> int:
    _emit(bb.unlink(_root(args), args.a, args.b, relation=args.relation))
    return 0


def cmd_subscribe(args) -> int:
    ack = bb.subscribe(_root(args), args.watcher, args.pattern, channel=args.channel)
    _emit(ack)
    return 0 if ack.get("ok") else 1


def cmd_unsubscribe(args) -> int:
    _emit(bb.unsubscribe(_root(args), args.watcher, args.pattern))
    return 0


def cmd_notify(args) -> int:
    ack = bb.post_alert(_root(args), args.channel, args.kind, args.text)
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

    la = sub.add_parser("list-add", help="Append one item to a list key")
    la.add_argument("--key", required=True)
    la.add_argument("--item", required=True)
    common(la)
    la.set_defaults(fn=cmd_list_add)

    lr = sub.add_parser("list-remove", help="Remove by --item or --index")
    lr.add_argument("--key", required=True)
    lr.add_argument("--item", default=None)
    lr.add_argument("--index", type=int, default=None)
    common(lr)
    lr.set_defaults(fn=cmd_list_remove)

    cv = sub.add_parser("canvas", help="Dynamic canvas surface")
    csub = cv.add_subparsers(dest="action", required=True)

    def cvcommon(sp):
        sp.add_argument("--name", required=True)
        common(sp)

    ccreate = csub.add_parser("create", help="Create a canvas")
    ccreate.add_argument("--name", required=True)
    ccreate.add_argument("--grid", default=None, help="Grid size, e.g. 8x8")
    ccreate.add_argument("--focus", action="store_true")
    common(ccreate)
    ccreate.set_defaults(fn=cmd_canvas)

    cset = csub.add_parser("set", help="Set one cell (real-time)")
    cset.add_argument("--name", required=True)
    cset.add_argument("--cell", required=True)
    cset.add_argument("--content", required=True)
    cset.add_argument("--kind", default="note", help="note|decision|risk|auto|...")
    cset.add_argument("--x", type=int, default=None)
    cset.add_argument("--y", type=int, default=None)
    common(cset)
    cset.set_defaults(fn=cmd_canvas)

    crem = csub.add_parser("remove", help="Remove one cell")
    crem.add_argument("--name", required=True)
    crem.add_argument("--cell", required=True)
    common(crem)
    crem.set_defaults(fn=cmd_canvas)

    cmove = csub.add_parser("move", help="Rename/reposition a cell")
    cmove.add_argument("--name", required=True)
    cmove.add_argument("--cell", required=True)
    cmove.add_argument("--to", required=True)
    cmove.add_argument("--x", type=int, default=None)
    cmove.add_argument("--y", type=int, default=None)
    common(cmove)
    cmove.set_defaults(fn=cmd_canvas)

    cres = csub.add_parser("resize", help="Resize grid (or free it)")
    cres.add_argument("--name", required=True)
    cres.add_argument("--grid", default=None)
    common(cres)
    cres.set_defaults(fn=cmd_canvas)

    cclear = csub.add_parser("clear", help="Clear all cells")
    cclear.add_argument("--name", required=True)
    common(cclear)
    cclear.set_defaults(fn=cmd_canvas)

    cfocus = csub.add_parser("focus", help="Focus one canvas / clear focus")
    cfocus.add_argument("--name", default=None)
    cfocus.add_argument("--clear", action="store_true")
    common(cfocus)
    cfocus.set_defaults(fn=cmd_canvas)

    cwatch = csub.add_parser("watch", help="Feed canvas from a path prefix")
    cwatch.add_argument("--name", required=True)
    cwatch.add_argument("--path", required=True)
    cwatch.add_argument("--remove", action="store_true")
    common(cwatch)
    cwatch.set_defaults(fn=cmd_canvas)

    cread = sub.add_parser("canvas-read", help="Read one canvas whole")
    cread.add_argument("--name", required=True)
    common(cread)
    cread.set_defaults(fn=cmd_canvas_read)

    lk = sub.add_parser("link", help="Link two nodes (graph edge)")
    lk.add_argument("--a", required=True)
    lk.add_argument("--b", required=True)
    lk.add_argument("--relation", default="related")
    common(lk)
    lk.set_defaults(fn=cmd_link)

    ulk = sub.add_parser("unlink", help="Remove graph edges")
    ulk.add_argument("--a", required=True)
    ulk.add_argument("--b", required=True)
    ulk.add_argument("--relation", default=None)
    common(ulk)
    ulk.set_defaults(fn=cmd_unlink)

    nb = sub.add_parser("neighbors", help="One-hop graph neighborhood")
    nb.add_argument("--node", required=True)
    nb.add_argument("--relation", default=None)
    common(nb)
    nb.set_defaults(fn=cmd_neighbors)

    sb = sub.add_parser("subscribe", help="Watch a key/canvas pattern for alerts")
    sb.add_argument("--watcher", required=True)
    sb.add_argument("--pattern", required=True)
    sb.add_argument("--channel", default="session")
    common(sb)
    sb.set_defaults(fn=cmd_subscribe)

    us = sub.add_parser("unsubscribe", help="Remove a subscription")
    us.add_argument("--watcher", required=True)
    us.add_argument("--pattern", required=True)
    common(us)
    us.set_defaults(fn=cmd_unsubscribe)

    al = sub.add_parser("alerts", help="Peek pending alerts (read-only)")
    al.add_argument("--channel", default=None)
    common(al)
    al.set_defaults(fn=cmd_alerts)

    cn = sub.add_parser("consume", help="Take and clear a channel's alerts")
    cn.add_argument("--channel", required=True)
    common(cn)
    cn.set_defaults(fn=cmd_consume)

    no = sub.add_parser("notify", help="Post a manual alert")
    no.add_argument("--channel", required=True)
    no.add_argument("--kind", default="info")
    no.add_argument("--text", required=True)
    common(no)
    no.set_defaults(fn=cmd_notify)

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
