"""move_wire -wires <wires> -delta {dx dy}: move route shapes by hand.

    move_wire -wires net_wire:temp_L2_inv1_Y/3 -delta {0 1.44}
    move_wire -wires [get_db selected] -delta {-0.72 0}

The wires are route shapes: route_net / route_final_stub / optimize_pg_connection
wires, shields and crossing boxes (net_wire:), route_pin straps (strap:) and
pin wires (pin_wire:). Each keeps its size, net and layer; only its place
changes. The GUI's Tools > Move runs this command. Nothing else follows the
wire: crossing boxes and the shapes it connected to stay, and a wire whose
centre line leaves its layer's tracks is reported (HT4-222). The wire's
auto vias (stretch_wire) are removed.
"""

from core import auto_via, objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "move_wire"
SUMMARY = "Move route wires (net wires, straps, pin wires) by a distance"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-wires": "value", "-delta": "value"}

USAGE = 1
NOT_A_WIRE = 220
BAD_SIZE = 221
OFF_TRACK = 222
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-wires" not in opts or "-delta" not in opts:
        raise HtreeError(USAGE, "move_wire: -wires and -delta are required. Usage: "
                         "move_wire -wires <wires> -delta {dx dy}")
    try:
        dx, dy = (float(v) for v in session.split_list(opts["-delta"]))
    except ValueError:
        raise HtreeError(USAGE, f"move_wire: -delta must be two numbers {{dx dy}} in microns, "
                         f"got '{opts['-delta']}'")
    db = session.db
    rows = wire_rows(session, opts["-wires"], NAME)
    for handle, table, row in rows:
        x1, y1, x2, y2 = rect_of(row)
        db.set_wire_rect(table, row["id"], rect_text((x1 + dx, y1 + dy, x2 + dx, y2 + dy)))
    stale = [h for h, _, _ in rows if db.net_wire_rows(auto_via.owner(h))]
    auto_via.drop(db, [h for h, _, _ in rows])
    info(f"move_wire: moved {len(rows)} wire(s) by {_num(round(dx, 6))} {_num(round(dy, 6))}"
         + (f"; removed the auto vias of {' '.join(stale)}" if stale else ""), session.out)
    check_tracks(db, [h for h, _, _ in rows], session.out, NAME)
    return tuple(h for h, _, _ in rows)


def wire_rows(session, text, cmd):
    """[(handle, table, row)] of the route shapes named in text (handles, as a
    Tcl list). Every handle is checked before anything changes."""
    db = session.db
    handles = list(dict.fromkeys(session.split_list(text)))
    if not handles:
        raise HtreeError(NOT_A_WIRE, f"{cmd}: no wires given")
    found = []
    for handle in handles:
        kind = objects.obj_type(handle) if objects.is_handle(handle) else None
        row = objects.wire_row(db, handle) if kind in objects.WIRE_TABLES else None
        if row is None:
            raise HtreeError(NOT_A_WIRE, f"{cmd}: '{handle}' is not a route wire (net_wire:, "
                             f"strap: or pin_wire: handles; get_db selected)")
        found.append((handle, objects.WIRE_TABLES[kind], row))
    return found


def rect_of(row):
    return tuple(float(c) for c in row["rect"].split())


def rect_text(r):
    return " ".join(_num(round(c, 6)) for c in r)


def check_tracks(db, handles, out, cmd):
    """Warn about wires whose centre line is off the tracks of their layer
    (a horizontal wire: TRACKS Y; a vertical one: TRACKS X). Crossing boxes
    (two layers) and layers without tracks are not checked."""
    off = []
    for handle in handles:
        row = objects.wire_row(db, handle)
        if "/" in row["layer"]:
            continue
        x1, y1, x2, y2 = rect_of(row)
        horizontal = x2 - x1 >= y2 - y1
        tracks = db.track_positions(row["layer"], "y" if horizontal else "x")
        if not tracks:
            continue
        c = (y1 + y2) / 2 if horizontal else (x1 + x2) / 2
        if min(abs(t - c) for t in tracks) > TOL:
            off.append(f"{handle} ({row['layer']} {'y' if horizontal else 'x'} {_num(round(c, 6))})")
    if off:
        warn(OFF_TRACK, f"{cmd}: off the tracks of their layer: {' '.join(off)}", out)
