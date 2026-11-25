"""optimize_pg_connection -inst <insts> [-extend <um>]: make more connections
from the cells' power straps to the power grid.

    optimize_pg_connection -inst [get_db insts] -extend 1

A command of its own, run after the routing; route_pin does not run it.

For every power strap of the instances (a route_pin strap on a power net:
not SIGNAL, not a routed net), the strap's reach is the strap as it is now,
already lengthened by route_net to its shields and by earlier runs of this
command. On each side the strap is lengthened up to -extend um further when
that reaches more of its power net: vertical power wires of the same net
crossing its band (route_net and route_final_stub shields), which it then
covers, or a same-net strap of a neighbouring cell on the same band, which it
then touches. It goes to the farthest such shape in reach, so it picks up every
one on the way, and only as far as the tech spacing to other nets' shapes on
the strap layer allows. Each new crossing gets a crossing box for the via.

The strap itself is lengthened, one shape on its own y with no piece of metal
beside it (a strap stretch, owner pg:<inst>, kind pg_ext: core/db.py). Its
crossing boxes are net_wire rows of net pg:<inst> (kind pg_cross,
.shield_net the power net). Running the command again on an instance replaces
both; move_obj and legalize_placement move them with the instance; route_pin
on the instance, which makes its straps again, removes them. write_def writes
the strap as one RECT of its power net.
"""

from core import netlist
from core.commands.route_net import _gap, _ia_shapes, strap_spacing
from core.db import PIN_LAYER, _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "optimize_pg_connection"
SUMMARY = "Extend cells' power straps to reach more of the power grid"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-inst": "value", "-extend": "value"}

USAGE = 1
NO_INST = 215
NO_STRAPS = 216
EXTEND = 1.0                 # um a strap may grow on each side, by default
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-inst" not in opts:
        raise HtreeError(USAGE, "optimize_pg_connection: -inst is required. Usage: "
                         "optimize_pg_connection -inst <insts> [-extend <um>]")
    try:
        extend = float(opts.get("-extend", EXTEND))
    except ValueError:
        extend = -1.0
    if extend <= 0:
        raise HtreeError(USAGE, f"optimize_pg_connection: -extend must be a positive number "
                         f"of microns, got '{opts['-extend']}'")
    db = session.db
    from core.commands.route_pin import inst_names
    try:
        names = inst_names(session, opts["-inst"])
    except HtreeError as exc:
        raise HtreeError(NO_INST, str(exc).replace("route_pin:", "optimize_pg_connection:"))
    out = session.out
    signal = netlist.signal_nets(db) | {"SIGNAL"}
    total_new, total_straps, done = 0, 0, []
    # route_pin's pieces under the pin wires (pin_layer) stay with this command's new ones
    pin_layers = {name: [(r["kind"], r["layer"], r["rect"], r["shield_net"])
                         for r in db.net_wire_rows(f"pg:{name}") if r["kind"] == PIN_LAYER]
                  for name in names}
    for name in names:
        db.set_net_wires(f"pg:{name}", pin_layers[name])   # this command's earlier pieces go
    for name in names:
        kept = db.pin_spec(name)
        flat = kept is not None and (kept[0].get("routing_direction") == "horizontal" or
                                     kept[0]["pins"]["horizontal_layer"] is None)
        wires = [w for w in db.pin_wire_rows(name) if w["net"] not in signal]
        if flat or (wires and all(w["strap"] is None for w in wires)):
            # horizontal pin spec: no straps; the H2 power pin wires go up and down
            total_straps += len(wires)
            pieces, lines = _extend_pin_wires(db, name, wires, extend)
            if pieces:
                db.set_net_wires(f"pg:{name}", pin_layers[name] + [
                    (k, layer, " ".join(_num(round(c, 6)) for c in r), net)
                    for k, layer, r, net in pieces])
            if lines:
                done.append(f"inst:{name}")
                total_new += sum(1 for p in pieces if p[0] == "pg_cross")
                info(f"  {name}: " + "; ".join(lines), out)
            continue
        straps = [s for s in db.strap_rows(name) if s["net"] not in signal]
        if not straps:
            continue
        total_straps += len(straps)
        pieces, lines = [], []
        for strap in straps:
            new, text = _extend_strap(db, strap, extend, pieces)
            pieces += new
            if text:
                lines.append(text)
        if pieces:
            db.set_net_wires(f"pg:{name}", pin_layers[name] + [
                (k, layer, " ".join(_num(round(c, 6)) for c in r), net)
                for k, layer, r, net in pieces])
            done.append(f"inst:{name}")
            total_new += sum(1 for p in pieces if p[0] == "pg_cross")
            info(f"  {name}: " + "; ".join(lines), out)
    if not total_straps:
        warn(NO_STRAPS, "optimize_pg_connection: the instances have no power straps or "
             "power pin wires (route_pin)", out)
    info(f"optimize_pg_connection: {total_new} new power connection(s) on {len(done)} "
         f"instance(s), straps (vertical pin spec) extended up to {_num(extend)} um more on "
         f"each side, power pin wires (horizontal) up and down", out)
    return tuple(done)


BASE = "pg_pin_base:"         # meta key prefix: <inst>/<pin> -> the pin wire before


def _extend_pin_wires(db, name, wires, extend):
    """A cell of a horizontal pin spec (no straps): each power pin wire (on
    the vertical layer, H2) lengthened up and down, up to extend um past
    where route_pin left it, to the farthest power wire of its net on a
    horizontal layer it then covers (insert_pg_grid IA wires, shields, the
    straps of other cells) and so every one on the way; only as far as the
    wire layer's tech spacing to other nets' shapes allows. The pin wire
    itself is lengthened (its rect before is kept, so a run again starts
    from it); each new crossing gets a crossing box (net pg:<name>, kind
    pg_cross) for its via. Returns (pieces, report lines)."""
    from core.commands.route_net import strap_spacing
    rect_of = lambda text: tuple(float(c) for c in text.split())
    dirs = {r["name"]: (r["direction"] or "").lower()
            for r in db.conn.execute("SELECT name, direction FROM layer")}
    shapes = _ia_shapes(db, None)
    pieces, lines = [], []
    for w in wires:
        net, layer = w["net"], w["layer"]
        now = rect_of(w["rect"])
        key = f"{BASE}{name}/{w['pin']}"
        row = db.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        base = rect_of(row["value"]) if row else now
        if abs(base[0] - now[0]) > TOL or abs(base[2] - now[2]) > TOL or \
                base[1] < now[1] - TOL or base[3] > now[3] + TOL:
            base = now                   # route_pin made it again since: start from it
        x1, y1, _, y2 = base
        x2 = base[2]
        # the power wires of its net across it on a horizontal layer
        flat = [(lyr, r) for n, lyr, r in shapes if n == net and lyr != layer and
                "/" not in lyr and dirs.get(lyr) == "horizontal" and
                r[0] <= x1 + TOL and r[2] >= x2 - TOL]
        before = sum(1 for _, r in flat if r[1] < y2 - TOL and r[3] > y1 + TOL)
        spacing = strap_spacing(db, layer, x2 - x1)
        others = [r for n, lyr, r in shapes if n != net and lyr == layer] + \
            [rect_of(o["rect"]) for o in db.pin_wire_rows()
             if o["layer"] == layer and o["net"] != net and
             (o["inst"], o["pin"]) != (name, w["pin"])]
        lo, hi, said = y1, y2, []
        for side in ("down", "up"):
            edge = y1 if side == "down" else y2
            asks = sorted(edge - r[1] if side == "down" else r[3] - edge for _, r in flat
                          if (r[1] < edge - TOL if side == "down" else r[3] > edge + TOL))
            asks = [a for a in asks if TOL < a <= extend + TOL]
            for length in reversed(asks):        # the farthest first: most connections
                part = (x1, edge - length, x2, edge) if side == "down" else \
                    (x1, edge, x2, edge + length)
                if any(_gap(part, r) < spacing - TOL for r in others):
                    continue
                if side == "down":
                    lo = edge - length
                else:
                    hi = edge + length
                said.append(f"{_num(round(length, 6))} {side}")
                break
        grown = (x1, lo, x2, hi)
        got = [(lyr, r) for lyr, r in flat if r[1] >= lo - TOL and r[3] <= hi + TOL]
        new = [(lyr, r) for lyr, r in got if not (r[1] < y2 - TOL and r[3] > y1 + TOL)]
        for lyr, r in new:                       # a box where it crosses each new one
            pieces.append(("pg_cross", f"{layer}/{lyr}", (x1, r[1], x2, r[3]), net))
        with db.conn:
            if lo < y1 - TOL or hi > y2 + TOL:
                db.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                                (key, " ".join(_num(round(c, 6)) for c in base)))
            else:
                db.conn.execute("DELETE FROM meta WHERE key = ?", (key,))
        db.set_wire_rect("pin_wire", w["id"], " ".join(_num(round(c, 6)) for c in grown))
        if said:
            lines.append(f"pin wire {w['pin']} {net} ({before} connection(s) before): "
                         f"extended {', '.join(said)} +{len(new)} crossing(s)")
    return pieces, lines


def _extend_strap(db, strap, extend, pending):
    """New pieces [(kind, layer, rect, net)] for one power strap, and a line
    of report text ('' when nothing was added)."""
    net, layer = strap["net"], strap["layer"]
    sx1, sy1, sx2, sy2 = (float(c) for c in strap["rect"].split())
    rect_of = lambda text: tuple(float(c) for c in text.split())
    shapes = _ia_shapes(db, None) + [(p[3], p[1], p[2]) for p in pending]
    # what is already the strap: extensions on its band that touch it, in a chain
    x1, x2 = sx1, sx2
    pieces = sorted((r[0], r[2]) for n, lyr, r in shapes if n == net and lyr == layer
                    and abs(r[1] - sy1) < TOL and abs(r[3] - sy2) < TOL)
    grown = True
    while grown:
        grown = False
        for a, b in pieces:
            if a <= x2 + TOL and b > x2 + TOL:
                x2, grown = b, True
            if b >= x1 - TOL and a < x1 - TOL:
                x1, grown = a, True
    # the power net's shapes it could reach: vertical wires on another layer
    # across its whole band, and same-net straps on the same band
    crossing = {}                # one per track: shields of two nets may share one
    for n, lyr, r in shapes:
        if n == net and lyr != layer and "/" not in lyr and r[3] - r[1] > r[2] - r[0] \
                and r[1] <= sy1 + TOL and r[3] >= sy2 - TOL:
            crossing.setdefault((round(r[0], 6), round(r[2], 6), lyr), r)
    layers = {k[:2]: k[2] for k in crossing}
    crossing = list(crossing.values())
    abutting = [r for n, lyr, r in shapes if n == net and lyr == layer and r != (sx1, sy1, sx2, sy2)
                and abs(r[1] - sy1) < TOL and abs(r[3] - sy2) < TOL]
    before = sum(1 for r in crossing if r[0] >= x1 - TOL and r[2] <= x2 + TOL)
    spacing = strap_spacing(db, layer, sy2 - sy1)
    others = [(lyr, r) for n, lyr, r in shapes if n != net and lyr == layer]
    new, said = [], []
    for side in ("left", "right"):
        edge = x1 if side == "left" else x2
        # how far each target asks for: a crossing wire is covered, a strap touched
        asks = [(edge - r[0]) if side == "left" else (r[2] - edge) for r in crossing
                if (r[0] < edge - TOL if side == "left" else r[2] > edge + TOL)]
        asks += [(edge - r[2]) if side == "left" else (r[0] - edge) for r in abutting
                 if (r[2] < edge + TOL if side == "left" else r[0] > edge - TOL)]
        asks = sorted(a for a in asks if TOL < a <= extend + TOL)
        for length in reversed(asks):            # the farthest first: most connections
            rect = (edge - length, sy1, edge, sy2) if side == "left" else \
                (edge, sy1, edge + length, sy2)
            if any(_gap(rect, r) < spacing - TOL for _, r in others):
                continue
            new.append(("pg_ext", layer, rect, net))
            for r in crossing:                   # the wires it now covers: a box each
                if rect[0] - TOL <= r[0] and r[2] <= rect[2] + TOL:
                    new.append(("pg_cross", f"{layers[round(r[0], 6), round(r[2], 6)]}/{layer}",
                                (r[0], sy1, r[2], sy2), net))
            gained = sum(1 for r in crossing if rect[0] - TOL <= r[0] and r[2] <= rect[2] + TOL)
            touched = sum(1 for r in abutting if _gap(rect, r) < TOL)
            said.append(f"{_num(round(length, 6))} {side}"
                        + (f" +{gained} crossing(s)" if gained else "")
                        + (f" +{touched} strap(s)" if touched else ""))
            break
    if not new:
        return [], ""
    return new, (f"strap {strap['seq']} {net} ({before} connection(s) before): extended "
                 + ", ".join(said))

