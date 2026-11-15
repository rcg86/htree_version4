"""move_wire -wires <wires> -delta {dx dy} | -next_track <direction>: move
route shapes by hand.

    move_wire -wires net_wire:temp_L2_inv1_Y/3 -delta {0 1.44}
    move_wire -wires [get_db selected] -delta {-0.72 0}
    move_wire -wires [get_db selected] -next_track down

The wires are route shapes: route_net / route_final_stub / optimize_pg_connection
wires, shields and crossing boxes (net_wire:), route_pin straps (strap:) and
pin wires (pin_wire:). Each keeps its size, net and layer; only its place
changes. The GUI's Tools > Move runs this command. Nothing else follows the
wire: crossing boxes and the shapes it connected to stay, and a wire whose
centre line leaves its layer's tracks is reported (HT4-222). The wire's
auto vias (stretch_wire) are removed.

-next_track moves each wire across its length onto the next track of its own
kind in that direction (the GUI's Move tool: Shift+arrow): a signal wire onto
the next signal ('-') track of assign_track_for_route, a power wire onto the
next track of its net.
"""

import bisect

from core import auto_via, objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "move_wire"
SUMMARY = "Move route wires (net wires, straps, pin wires) by a distance or to the next track"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-wires": "value", "-delta": "value", "-next_track": "value"}

USAGE = 1
NOT_A_WIRE = 220
BAD_SIZE = 221
OFF_TRACK = 222
NO_TRACK = 226
TOL = 1e-6
# -next_track: the axis the wire moves along, and which way.
DIRECTIONS = {"up": ("y", 1), "down": ("y", -1), "left": ("x", -1), "right": ("x", 1)}
NOT_NETS = ("-", "NA")                   # track tokens that are not a net
SHIELD_OF = {"wire": "shield", "stub": "stub_shield"}   # a signal wire's kind: its shields'


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-wires" not in opts or ("-delta" in opts) == ("-next_track" in opts):
        raise HtreeError(USAGE, "move_wire: -wires and one of -delta, -next_track are required. "
                         "Usage: move_wire -wires <wires> -delta {dx dy}  |  "
                         "move_wire -wires <wires> -next_track up|down|left|right")
    db = session.db
    if "-next_track" in opts:
        direction = opts["-next_track"]
        if direction not in DIRECTIONS:
            raise HtreeError(USAGE, f"move_wire: -next_track must be up, down, left or right, "
                             f"got '{direction}'")
        moves, stay = next_track_moves(db, wire_rows(session, opts["-wires"], NAME), direction)
        stale = _move(db, moves)
        info(f"move_wire: moved {len(moves)} wire(s) to the next track {direction}" + stale,
             session.out)
        for _, _, _, _, text in moves:
            info(f"  {text}", session.out)
        if stay:
            warn(NO_TRACK, "move_wire: not moved: "
                 + "; ".join(f"{h} ({why})" for h, why in stay), session.out)
        return tuple(m[0] for m in moves)
    rows = wire_rows(session, opts["-wires"], NAME)
    deltas = _deltas(session, opts["-delta"], len(rows))
    stale = _move(db, [(h, table, row, d, "") for (h, table, row), d in zip(rows, deltas)])
    if len(set(deltas)) == 1:
        by = f"by {_num(deltas[0][0])} {_num(deltas[0][1])}"
    else:
        by = ", ".join(f"{h} by {_num(dx)} {_num(dy)}" for (h, _, _), (dx, dy) in zip(rows, deltas))
    info(f"move_wire: moved {len(rows)} wire(s) {by}{stale}", session.out)
    check_tracks(db, [h for h, _, _ in rows], session.out, NAME)
    return tuple(h for h, _, _ in rows)


def _deltas(session, text, count):
    """One (dx, dy) a wire: -delta {dx dy} moves them all alike, a list of
    count pairs {{dx dy} {dx dy} ...} each wire by its own."""
    words = session.split_list(text)
    try:
        if len(words) == 2:
            try:
                return [(round(float(words[0]), 6), round(float(words[1]), 6))] * count
            except ValueError:
                pass                          # two pairs, for two wires
        pairs = [tuple(round(float(v), 6) for v in session.split_list(w)) for w in words]
    except ValueError:
        pairs = []
    if len(pairs) != count or any(len(p) != 2 for p in pairs):
        raise HtreeError(USAGE, f"move_wire: -delta must be two numbers {{dx dy}} in microns, or "
                         f"one {{dx dy}} for each of the {count} wire(s), got '{text}'")
    return pairs


def _move(db, moves):
    """Move each wire of [(handle, table, row, (dx, dy), _)] and drop its auto
    vias; the text that says which had some."""
    for handle, table, row, (dx, dy), _ in moves:
        x1, y1, x2, y2 = rect_of(row)
        db.set_wire_rect(table, row["id"], rect_text((x1 + dx, y1 + dy, x2 + dx, y2 + dy)))
    stale = [m[0] for m in moves if db.net_wire_rows(auto_via.owner(m[0]))]
    auto_via.drop(db, [m[0] for m in moves])
    return f"; removed the auto vias of {' '.join(stale)}" if stale else ""


def next_track_moves(db, rows, direction):
    """Where -next_track takes the wires of rows [(handle, table, row)]:
    ([(handle, table, row, (dx, dy), text)], [(handle, why it stays)]).

    A wire moves across its length only, its centre line onto the next track
    of its layer in direction that carries its net: a power wire (a shield's
    .shield_net, a strap or pin wire of a net the track assignments name) onto
    the next track of that net, any other wire onto the next signal ('-')
    track. A layer with no assignment in that direction: its next DEF track.
    A signal wire with shields (shields_of) moves with them as a group, also
    when they are not in rows: onto the next signal track that has a track of
    each shield's net beside it, as far from it as the shield is now; the
    shields go there, changing sides where the power tracks do.
    A crossing box (two layers) has no track: it goes with the wires when
    they all move the same distance."""
    axis, sign = DIRECTIONS[direction]
    power = {token for layer in db.track_assignment_layers()
             for token in db.track_assignment_row(layer)["pattern"].split()} - set(NOT_NETS)
    layers = {}

    def tracks_of(layer):
        """(track coordinates, their assigned tokens or None) of layer along axis."""
        if layer not in layers:
            tracks = db.track_positions(layer, axis)
            assigned = db.track_assignment_row(layer)
            pattern = assigned["pattern"].split() \
                if assigned is not None and assigned["direction"] == axis else None
            layers[layer] = (tracks, pattern and [pattern[k % len(pattern)]
                                                  for k in range(len(tracks))])
        return layers[layer]

    def carries(layer, t, net):
        """True when t is a track of layer for net ('-': a signal); any place
        will do on a layer with no assignment."""
        tracks, tokens = tracks_of(layer)
        if tokens is None:
            return True
        i = bisect.bisect_left(tracks, t - TOL)
        return i < len(tracks) and abs(tracks[i] - t) <= TOL and tokens[i] == net

    across = [(h, table, row) for h, table, row in rows
              if "/" not in row["layer"] and _line(row)[0] == (axis == "y")]
    groups = {h: shields_of(db, row) for h, table, row in across if table == "net_wire"}
    grouped = {s["id"] for shields in groups.values() for s in shields}
    moves, steps, stay = [], set(), []
    for handle, table, row in rows:
        layer = row["layer"]
        if "/" in layer or (table == "net_wire" and row["id"] in grouped):
            continue                          # a box: below; a shield: with its wire
        horizontal, c = _line(row)[:2]
        if horizontal != (axis == "y"):
            stay.append((handle, "runs left to right: up or down moves it a track" if horizontal
                         else "runs up and down: left or right moves it a track"))
            continue
        net = (row["shield_net"] if table == "net_wire" else None) or \
            (row["net"] if row["net"] in power else None)
        kind = net or "signal"
        tracks, tokens = tracks_of(layer)
        if not tracks:
            stay.append((handle, f"{layer} has no DEF TRACKS {axis.upper()}"))
            continue
        if tokens is not None:
            tracks = [t for t, token in zip(tracks, tokens) if token == (net or "-")]
        ahead = sorted((t for t in tracks if (t - c) * sign > TOL), key=lambda t: abs(t - c))
        where = f"{layer} {direction} of {axis} {_num(round(c, 6))}"
        if not ahead:
            stay.append((handle, f"no {kind} track of {where}" if tracks
                         else f"{layer} has no {kind} track"))
            continue
        shields = groups.get(handle, [])
        to, places = ahead[0], []
        for to in ahead:                      # the first track its shields fit beside
            places = [next((t for t in (to + sc - c, to - sc + c)
                            if carries(layer, t, s["shield_net"])), None)
                      for s, sc in ((s, _line(s)[1]) for s in shields)]
            if None not in places:
                break
        else:
            stay.append((handle, f"no {kind} track of {where} with a track of each of its "
                         f"shields' nets beside it"))
            continue
        step = _delta(axis, to - c)
        steps.add(step)
        note = ""
        for s, t in zip(shields, places):
            name, sc = f"net_wire:{s['net']}/{s['seq']}", _line(s)[1]
            if abs(t - sc) <= TOL:
                note += f"; {name} ({s['shield_net']} shield) stays on {axis} {_num(round(sc, 6))}"
                continue
            moves.append((name, "net_wire", s, _delta(axis, t - sc),
                          f"{name} ({s['shield_net']} shield of {handle}): {layer} {axis} "
                          f"{_num(round(sc, 6))} -> {_num(round(t, 6))}"))
        moves.append((handle, table, row, step,
                      f"{handle} ({kind}): {layer} {axis} {_num(round(c, 6))} -> {_num(to)}{note}"))
    for handle, table, row in rows:
        if "/" not in row["layer"]:
            continue
        if len(steps) == 1:
            moves.append((handle, table, row, next(iter(steps)),
                          f"{handle} (crossing box): with the wire"))
        else:
            stay.append((handle, "a crossing box has no track: it moves with the wires when "
                         "they all move the same distance" if steps else
                         "a crossing box has no track: select it with its wire"))
    return moves, stay


def _delta(axis, d):
    return (0.0, round(d, 6)) if axis == "y" else (round(d, 6), 0.0)


def _line(row):
    """(horizontal, centre line, start, end) of a single layer wire: the
    coordinate across it, and its span along."""
    x1, y1, x2, y2 = rect_of(row)
    if x2 - x1 >= y2 - y1:
        return True, (y1 + y2) / 2, x1, x2
    return False, (x1 + x2) / 2, y1, y2


def shields_of(db, row):
    """The shields of a signal wire (a net_wire row of kind wire or stub): the
    net's shield wires on its layer that run beside it (they overlap along)
    and have no other wire of the net nearer. [] for any other shape."""
    kind = SHIELD_OF.get(row["kind"])
    if kind is None or "/" in row["layer"]:
        return []
    rows = [r for r in db.net_wire_rows(row["net"]) if r["layer"] == row["layer"]]
    horizontal, _, lo, hi = _line(row)
    wires = [(r, _line(r)) for r in rows if r["kind"] == row["kind"]]
    found = []
    for r in rows:
        flat, sc, slo, shi = _line(r)
        if r["kind"] != kind or flat != horizontal or min(hi, shi) - max(lo, slo) <= TOL:
            continue
        beside = [(abs(c - sc), w["id"]) for w, (f, c, a, b) in wires
                  if f == horizontal and min(b, shi) - max(a, slo) > TOL]
        if min(beside)[1] == row["id"]:
            found.append(r)
    return found


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
