"""Vias added by stretch_wire where a stretched wire newly crosses a wire of
its own net (root attribute route_auto_via_insertion_during_stretch: how
many routing layers apart the two may be).

Until vias get their own table, an auto via is a net_wire row of kind via,
kept under the wire it was made for: net auto_via:<wire handle>, layer
"<lower>/<upper>" (routing layer order), rect the crossing box, .shield_net
the electrical net. The GUI draws it as an outline, like the route_net
crossing boxes. It goes when its wire is stretched off it, moved, or
rebuilt (route_pin, route_net), and moves with its wire's instance or
spine.
"""

from core import objects, root_attrs
from core.db import _num

ATTR = "route_auto_via_insertion_during_stretch"
PREFIX = "auto_via:"
TOL = 1e-6


def owner(handle):
    """The net_wire net that holds the auto vias of a wire."""
    return PREFIX + handle


def routing_order(db):
    """{routing layer: index} in tech order (D12 0, H1 1, ... IB 6)."""
    return {r["name"]: k for k, r in enumerate(db.conn.execute(
        "SELECT name FROM layer WHERE lower(type) = 'routing' ORDER BY id"))}


def electrical(table, row):
    """The net a route shape carries: a strap's or pin wire's net, a net
    wire's shield net (shields, power extensions) or else its net. None for
    straps of unrouted signal pins (SIGNAL): they connect to nothing yet."""
    net = row["net"] if table != "net_wire" else (row["shield_net"] or row["net"])
    return None if net in (None, "SIGNAL") else net


def _shapes(db):
    """(handle, electrical net, layer, rect) of every route shape but crossing
    boxes and vias."""
    rect = lambda text: tuple(float(c) for c in text.split())
    for r in db.strap_rows():
        yield f"strap:{r['inst']}/{r['seq']}", electrical("strap", r), r["layer"], rect(r["rect"])
    for r in db.pin_wire_rows():
        yield (f"pin_wire:{r['inst']}/{r['pin']}", electrical("pin_wire", r), r["layer"],
               rect(r["rect"]))
    for r in db.net_wire_rows():
        if "/" in r["layer"] or r["kind"] == "via":
            continue
        yield (f"net_wire:{r['net']}/{r['seq']}", electrical("net_wire", r), r["layer"],
               rect(r["rect"]))


def _box(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[2] - box[0] > TOL and box[3] - box[1] > TOL else None


def after_stretch(db, handle, old, new):
    """Update the auto vias of the wire handle stretched from rect old to
    rect new: drop those it no longer covers, add one where the part it
    gained crosses a same-net wire on a routing layer within the attribute's
    depth that has no via or crossing box there yet. Returns (added, dropped)
    as lists of report texts."""
    table = objects.WIRE_TABLES[objects.obj_type(handle)]
    row = objects.wire_row(db, handle)
    net = electrical(table, row)
    mine = owner(handle)
    kept, dropped = [], []
    for r in db.net_wire_rows(mine):
        box = tuple(float(c) for c in r["rect"].split())
        if _box(box, new) == box:
            kept.append((r["kind"], r["layer"], r["rect"], r["shield_net"]))
        else:
            dropped.append(f"{r['layer']} {{{r['rect']}}}")
    depth = root_attrs.get(db, ATTR)
    order = routing_order(db)
    gained = [g for g in _gained(old, new) if g]
    added = []
    if net and depth > 0 and gained and row["layer"] in order:
        mine_k = order[row["layer"]]
        have = {(r["layer"], r["rect"]) for r in db.net_wire_rows()
                if "/" in r["layer"]}                 # crossing boxes and vias already there
        for other, other_net, layer, rect in _shapes(db):
            if other == handle or other_net != net or layer not in order or layer == row["layer"]:
                continue
            if abs(order[layer] - mine_k) > depth:
                continue
            box = _box(new, rect)
            if box is None or not any(_box(box, g) for g in gained):
                continue
            pair = "/".join(sorted((row["layer"], layer), key=order.get))
            text = " ".join(_num(round(c, 6)) for c in box)
            if (pair, text) in have:
                continue
            have.add((pair, text))
            kept.append(("via", pair, text, net))
            added.append(f"{pair} {{{text}}} to {other}")
    if added or dropped:
        db.set_net_wires(mine, kept)
    return added, dropped


def _gained(old, new):
    """The parts of rect new outside rect old, as rects (one per edge that
    moved out)."""
    x1, y1, x2, y2 = new
    a1, b1, a2, b2 = old
    parts = []
    if x1 < a1 - TOL:
        parts.append((x1, y1, min(a1, x2), y2))
    if x2 > a2 + TOL:
        parts.append((max(a2, x1), y1, x2, y2))
    if y1 < b1 - TOL:
        parts.append((x1, y1, x2, min(b1, y2)))
    if y2 > b2 + TOL:
        parts.append((x1, max(b2, y1), x2, y2))
    return parts


def drop(db, handles):
    """Remove the auto vias of these wires (moved wires: they are stale)."""
    with db.conn:
        for h in handles:
            db.conn.execute("DELETE FROM net_wire WHERE net = ?", (owner(h),))
