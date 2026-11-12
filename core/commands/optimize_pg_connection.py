"""optimize_pg_connection -inst <insts> [-extend <um>]: make more connections
from the cells' power straps to the power grid.

    optimize_pg_connection -inst [get_db insts] -extend 1

For every power strap of the instances (a route_pin strap on a power net:
not SIGNAL, not a routed net), the strap's reach is the strap with the
extensions it already has (route_net's to its shields, earlier runs of this
command). On each side the strap is extended up to -extend um further when
that reaches more of its power net: vertical power wires of the same net
crossing its band (route_net and route_final_stub shields), which it then
covers, or a same-net strap of a neighbouring cell on the same band, which it
then touches. It goes to the farthest such shape in reach, so it picks up every
one on the way, and only as far as the tech spacing to other nets' shapes on
the strap layer allows. Each new crossing gets a crossing box for the via.

The pieces are stored per instance (net_wire rows of net pg:<inst>, kind
pg_ext / pg_cross, .shield_net the power net): running it again replaces
them, move_obj moves them with their instance, write_def writes them as
stripes of the power net.
"""

from core.commands.route_net import _gap, _ia_shapes, strap_spacing
from core.db import _num
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
    signal = {r["name"] for s in db.spine_names()
              for r in db.spine_net_rows(db.spine_row(s)["id"])} | {"SIGNAL"}
    total_new, total_straps, done = 0, 0, []
    for name in names:
        db.set_net_wires(f"pg:{name}", [])          # this command's earlier pieces go
    for name in names:
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
            db.set_net_wires(f"pg:{name}", [(k, layer, " ".join(_num(round(c, 6)) for c in r),
                                             net) for k, layer, r, net in pieces])
            done.append(f"inst:{name}")
            total_new += sum(1 for p in pieces if p[0] == "pg_cross")
            info(f"  {name}: " + "; ".join(lines), out)
    if not total_straps:
        warn(NO_STRAPS, "optimize_pg_connection: the instances have no power straps "
             "(route_pin)", out)
    info(f"optimize_pg_connection: {total_new} new power connection(s) on {len(done)} "
         f"instance(s), straps extended up to {_num(extend)} um more on each side", out)
    return tuple(done)


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

