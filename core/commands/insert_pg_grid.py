"""insert_pg_grid -layer <layer> [-pull_back_distance <um>]: a power grid on
the power tracks of a layer, from boundary to boundary.

    insert_pg_grid -layer IA -pull_back_distance 1

The power tracks are those the layer's track assignment gives a power net
(assign_track_for_route -layer IA -net {VDD_SOC NA - NA VSS NA - NA}: the
VDD_SOC and VSS tracks; '-' and NA tracks get nothing). Each one gets a wire
of its net across the whole design: from the design boundary to the
boundary, -pull_back_distance um (default 1) short of it at each end, along
each part of the track that is inside a rectilinear boundary. The wire is
broken where a shape of another net is on the layer (straps and pin routes
of the cells, signal wires, shields of the other power net, vias), clear of
it by the spacing, as route_net's shields are: no short. Shapes of the same
net may touch it. A piece shorter than the wire is wide is left out.

The wire is as wide, and keeps as far from other nets, as the route rule
with the layer says (the first that has it; the tech width and spacing
without one), at least the tech spacing for the widths. The wires are
net_wire rows of net pg_grid:<layer>, kind pg_grid, .shield_net the power
net; running the command again on the layer replaces them. write_def writes
them under their power net. No via is made: assign_via_for_route or
insert_vias for those.
"""

import bisect

from core import drc, objects
from core.commands.route_net import Fence, _merge, strap_spacing
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "insert_pg_grid"
SUMMARY = "Lay power wires on a layer's power tracks from boundary to boundary"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-layer": "value", "-pull_back_distance": "value"}

USAGE = 1
NO_ASSIGNMENT = 309          # the layer has no track assignment with a power net
NO_GRID = 310                # WARN: a power track got no wire (all blocked or outside)
PULL_BACK = 1.0              # um short of the boundary, by default
OWNER = "pg_grid:"           # net_wire rows: net pg_grid:<layer>
KIND = "pg_grid"
BUCKET = 5.0                 # um: the blocking shapes, binned across the tracks
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-layer" not in opts:
        raise HtreeError(USAGE, f"{NAME}: -layer is required. Usage: {NAME} -layer <layer> "
                         f"[-pull_back_distance <um>]")
    try:
        pull = float(opts.get("-pull_back_distance", PULL_BACK))
    except ValueError:
        pull = -1.0
    if not 0 <= pull < float("inf"):
        raise HtreeError(USAGE, f"{NAME}: -pull_back_distance must be a distance in um, 0 or "
                         f"more, got '{opts['-pull_back_distance']}'")
    db, out = session.db, session.out
    objects.require_tech(db)
    objects.require_design(db)
    layer = opts["-layer"].removeprefix("layer:")
    if db.layer_row(layer) is None:
        raise HtreeError(USAGE, f"{NAME}: layer '{layer}' is not in tech (tech layers: "
                         f"{' '.join(db.layer_names())})")
    row = db.track_assignment_row(layer)
    if row is None:
        raise HtreeError(NO_ASSIGNMENT, f"{NAME}: {layer} has no track assignment: give its "
                         f"power tracks with assign_track_for_route -layer {layer} -net {{...}}")
    axis = row["direction"]              # y: horizontal tracks at those y
    horizontal = axis == "y"
    pattern = row["pattern"].split()
    positions = db.track_positions(layer, axis)
    tracks = [(c, pattern[k % len(pattern)]) for k, c in enumerate(positions)]
    tracks = [(c, net) for c, net in tracks if net not in ("-", "NA")]
    if not tracks:
        raise HtreeError(NO_ASSIGNMENT, f"{NAME}: the {layer} track assignment "
                         f"({row['pattern']}) gives no track a power net")
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()]
    if len(boundary) < 6:
        raise HtreeError(USAGE, f"{NAME}: the design has no boundary (DEF DIEAREA)")
    fence = Fence(boundary)
    from core.pin_access import _rule
    width, spacing = _rule(db, None, layer)
    if width <= 0:
        raise HtreeError(USAGE, f"{NAME}: no width for {layer}: give a route rule with it "
                         f"(create_route_rule) or a WIDTH in the tech LEF")

    # what is on the layer now, but this command's earlier grid on it
    owner = OWNER + layer
    design = drc.collect(db)
    shapes = [s for s in design.shapes if s.layer == layer
              and not s.handle.startswith(f"net_wire:{owner}/")]
    bins = {}                            # across-the-track bucket -> [(net, a1, a2, l1, l2, gap)]
    for s in shapes:
        x1, y1, x2, y2 = s.rect
        a1, a2, l1, l2 = (y1, y2, x1, x2) if horizontal else (x1, x2, y1, y2)
        gap = max(spacing, strap_spacing(db, layer, max(width, min(x2 - x1, y2 - y1))))
        item = (s.net, a1, a2, l1, l2, gap)
        for k in range(int((a1 - gap) // BUCKET), int((a2 + gap) // BUCKET) + 1):
            bins.setdefault(k, []).append(item)

    wires, empty = [], []
    cut = laid = 0.0
    per_net = {}
    for c, net in tracks:
        a1, a2 = c - width / 2, c + width / 2
        runs = fence.row(a1, a2) if horizontal else fence.col(a1, a2)
        runs = [(lo + pull, hi - pull) for lo, hi in runs if hi - lo - 2 * pull > TOL]
        if not runs:
            continue
        blocked = []
        seen = set()
        for k in range(int(a1 // BUCKET) - 1, int(a2 // BUCKET) + 2):
            for item in bins.get(k, ()):
                if id(item) in seen:
                    continue
                seen.add(id(item))
                o_net, o_a1, o_a2, o_l1, o_l2, gap = item
                if o_net == net:         # its own net may touch it
                    continue
                if max(o_a1 - a2, a1 - o_a2) < gap - TOL:
                    blocked.append((o_l1 - gap, o_l2 + gap))
        blocked = _merge(blocked)
        pieces = []
        for lo, hi in runs:
            start = lo
            j = bisect.bisect_left([b[1] for b in blocked], lo)
            for b1, b2 in blocked[j:]:
                if b1 >= hi:
                    break
                if b1 > start:
                    pieces.append((start, b1))
                start = max(start, b2)
            if start < hi:
                pieces.append((start, hi))
        kept = [(p1, p2) for p1, p2 in pieces if p2 - p1 >= width - TOL]
        total = sum(hi - lo for lo, hi in runs)
        length = sum(p2 - p1 for p1, p2 in kept)
        cut += total - length
        laid += length
        if not kept:
            empty.append(f"{_num(round(c, 6))} ({net})")
            continue
        n = per_net.setdefault(net, [0, 0, 0.0])
        n[0] += 1
        n[1] += len(kept)
        n[2] += length
        for p1, p2 in kept:
            rect = (p1, a1, p2, a2) if horizontal else (a1, p1, a2, p2)
            wires.append((KIND, layer, " ".join(_num(round(v, 6)) for v in rect), net))

    replaced = len(db.net_wire_rows(owner))
    db.set_net_wires(owner, wires)
    info(f"{NAME}: {layer} {'horizontal' if horizontal else 'vertical'} power tracks, "
         f"{_num(width)} wide, {_num(spacing)} (at least the tech spacing) from other nets, "
         f"{_num(pull)} um short of the boundary: {len(wires)} wire(s), "
         f"{_num(round(laid, 3))} um" + (f" (replacing {replaced})" if replaced else ""), out)
    for net, (count, pieces, length) in sorted(per_net.items()):
        info(f"  {net}: {count} track(s), {pieces} piece(s), {_num(round(length, 3))} um", out)
    if cut > TOL:
        info(f"  {_num(round(cut, 3))} um left out where shapes of other nets are on {layer} "
             f"(the spine cells' straps and routes): no short", out)
    if empty:
        warn(NO_GRID, f"{NAME}: {len(empty)} power track(s) got no wire (blocked all the way "
             f"or too short): {layer} {axis} " + ", ".join(empty[:10])
             + (" ..." if len(empty) > 10 else ""), out)
    info("  no via is made: assign_via_for_route or insert_vias to join it to the crossing "
         "power wires", out)
    return tuple(f"net_wire:{owner}/{r['seq']}" for r in db.net_wire_rows(owner))
