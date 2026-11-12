"""stretch_wire -wire <wire> -edge <left|right|bottom|top> -to <coordinate>:
move one edge of a route shape by hand.

    stretch_wire -wire net_wire:temp_L2_inv1_Y/3 -edge top -to 10120.5
    stretch_wire -wire strap:temp_L2_inv1/2 -edge left -to 5690.04

The edge moves to the coordinate (x for left / right, y for bottom / top);
the other edges stay, so the wire gets longer or shorter. The GUI's
Tools > Stretch runs this command. Wires are as for move_wire.

Where the part of the wire it gains crosses a wire of the same net on a
routing layer at most route_auto_via_insertion_during_stretch layers away
(root attribute, default 1: the next layer), a via is added (core.auto_via);
the wire's auto vias it no longer covers go.
"""

from core import auto_via
from core.commands.move_wire import (BAD_SIZE, USAGE, check_tracks, rect_of, rect_text,
                                     wire_rows)
from core.db import _num
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "stretch_wire"
SUMMARY = "Move one edge of a route wire to a coordinate (lengthen or shorten it)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-wire": "value", "-edge": "value", "-to": "value"}

EDGES = {"left": 0, "bottom": 1, "right": 2, "top": 3}
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    usage = "Usage: stretch_wire -wire <wire> -edge <left|right|bottom|top> -to <coordinate>"
    if not all(k in opts for k in ("-wire", "-edge", "-to")):
        raise HtreeError(USAGE, f"stretch_wire: -wire, -edge and -to are required. {usage}")
    edge = opts["-edge"].lower()
    if edge not in EDGES:
        raise HtreeError(USAGE, f"stretch_wire: -edge must be one of {' '.join(EDGES)}, "
                         f"got '{opts['-edge']}'")
    try:
        to = float(opts["-to"])
    except ValueError:
        raise HtreeError(USAGE, f"stretch_wire: -to must be a coordinate in microns, "
                         f"got '{opts['-to']}'")
    rows = wire_rows(session, opts["-wire"], NAME)
    if len(rows) != 1:
        raise HtreeError(USAGE, f"stretch_wire: one wire at a time, got {len(rows)}. {usage}")
    handle, table, row = rows[0]
    r = list(rect_of(row))
    k = EDGES[edge]
    old = r[k]
    r[k] = to
    if r[2] - r[0] < TOL or r[3] - r[1] < TOL:
        raise HtreeError(BAD_SIZE, f"stretch_wire: the {edge} edge of {handle} at {_num(to)} "
                         f"would pass its opposite edge ({row['rect']})")
    session.db.set_wire_rect(table, row["id"], rect_text(r))
    added, dropped = auto_via.after_stretch(session.db, handle, rect_of(row), tuple(r))
    info(f"stretch_wire: {handle} {edge} edge {_num(round(old, 6))} -> {_num(round(to, 6))} "
         f"({'longer' if (to - old) * (1 if k >= 2 else -1) > 0 else 'shorter'} by "
         f"{_num(round(abs(to - old), 6))})", session.out)
    for text in added:
        info(f"  auto via {text}", session.out)
    if dropped:
        info(f"  auto via(s) no longer on the wire removed: {'; '.join(dropped)}", session.out)
    check_tracks(session.db, [handle], session.out, NAME)
    return handle
