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

from core import auto_via, objects, route_status
from core.db import CARRIED, _num, base_rect
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
        moves = _not_fixed(db, moves, session.out)
        before = _shielded(db, moves)
        stale = _move(db, moves)
        info(f"move_wire: moved {len(moves)} wire(s) to the next track {direction}" + stale,
             session.out)
        for _, _, _, _, text in moves:
            info(f"  {text}", session.out)
        if stay:
            warn(NO_TRACK, "move_wire: not moved: "
                 + "; ".join(f"{h} ({why})" for h, why in stay), session.out)
        rebuild_shields(db, before, session.out)
        return tuple(m[0] for m in moves)
    rows = wire_rows(session, opts["-wires"], NAME)
    deltas = _deltas(session, opts["-delta"], len(rows))
    kept = _not_fixed(db, [(h, table, row, d, "") for (h, table, row), d in zip(rows, deltas)],
                      session.out)
    if not kept:
        return ()
    skip = set(rebuilt_shields(db, [m[:3] for m in kept]))   # made again, not moved
    kept = [m for m in kept if m[0] not in skip]
    rows, deltas = [m[:3] for m in kept], [m[3] for m in kept]
    moves = [(h, table, row, d, "") for (h, table, row), d in zip(rows, deltas)]
    before = _shielded(db, moves)
    stale = _move(db, moves)
    if len(set(deltas)) == 1:
        by = f"by {_num(deltas[0][0])} {_num(deltas[0][1])}"
    else:
        by = ", ".join(f"{h} by {_num(dx)} {_num(dy)}" for (h, _, _), (dx, dy) in zip(rows, deltas))
    info(f"move_wire: moved {len(rows)} wire(s) {by}{stale}", session.out)
    check_tracks(db, [h for h, _, _ in rows], session.out, NAME)
    rebuild_shields(db, before, session.out)
    return tuple(h for h, _, _ in rows)


def _not_fixed(db, moves, out):
    """The moves (handle, table, row, delta, text) of wires of nets that are
    not fixed; the others are reported."""
    held = {h for h, _, _ in route_status.fixed_shapes(db, [m[:3] for m in moves])}
    route_status.skip(NAME, "wire(s) of fixed nets", sorted(held), out)
    return [m for m in moves if m[0] not in held]


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
    A crossing box (two layers, a via's box) goes with the wires when they
    all move the same distance; selected with no wire, it moves by itself:
    its centre onto the next track, in direction, of the layer of the two
    whose tracks run across the move (left or right: the vertical layer),
    a signal track, or one of its net for a power box."""
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
        net = (row["shield_net"] if table == "net_wire" and row["kind"] not in CARRIED
               else None) or \
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
        for s, t in zip(shields if not rebuilds(db, row) else (), places):
            name, sc = f"net_wire:{s['net']}/{s['seq']}", _line(s)[1]
            if abs(t - sc) <= TOL:
                note += f"; {name} ({s['shield_net']} shield) stays on {axis} {_num(round(sc, 6))}"
                continue
            moves.append((name, "net_wire", s, _delta(axis, t - sc),
                          f"{name} ({s['shield_net']} shield of {handle}): {layer} {axis} "
                          f"{_num(round(sc, 6))} -> {_num(round(t, 6))}"))
        moves.append((handle, table, row, step,
                      f"{handle} ({kind}): {layer} {axis} {_num(round(c, 6))} -> {_num(to)}{note}"))
    alone = not any("/" not in row["layer"] for _, _, row in rows)
    for handle, table, row in rows:
        if "/" not in row["layer"]:
            continue
        if alone:                             # boxes only: each to the next track
            found = _box_step(db, handle, row, axis, sign, direction, power, tracks_of)
            if isinstance(found, str):
                stay.append((handle, found))
            else:
                moves.append(found)
            continue
        if len(steps) == 1:
            moves.append((handle, table, row, next(iter(steps)),
                          f"{handle} (crossing box): with the wire"))
        else:
            stay.append((handle, "a crossing box has no track: it moves with the wires when "
                         "they all move the same distance" if steps else
                         "a crossing box has no track: select it with its wire"))
    return moves, stay


def _box_step(db, handle, row, axis, sign, direction, power, tracks_of):
    """The move of a crossing box selected alone (see next_track_moves), or
    why it stays."""
    want = "vertical" if axis == "x" else "horizontal"
    layers = [l for l in row["layer"].split("/")
              if (db.layer_row(l) or {"direction": None})["direction"] == want]
    if not layers:
        return f"neither of its layers ({row['layer']}) is {want}: no track to step to"
    layer = layers[0]
    tracks, tokens = tracks_of(layer)
    if not tracks:
        return f"{layer} has no DEF TRACKS {axis.upper()}"
    net = row["shield_net"] if row["shield_net"] in power else None
    if tokens is not None:
        tracks = [t for t, token in zip(tracks, tokens) if token == (net or "-")]
    x1, y1, x2, y2 = rect_of(row)
    c = (x1 + x2) / 2 if axis == "x" else (y1 + y2) / 2
    ahead = sorted((t for t in tracks if (t - c) * sign > TOL), key=lambda t: abs(t - c))
    kind = net or "signal"
    if not ahead:
        return f"no {kind} track of {layer} {direction} of {axis} {_num(round(c, 6))}"
    return (handle, "net_wire", row, _delta(axis, ahead[0] - c),
            f"{handle} (crossing box, {layer} {kind} track): {axis} {_num(round(c, 6))} -> "
            f"{_num(ahead[0])}")


def rebuilds(db, row):
    """True when moving this net_wire row makes its shields again
    (rebuild_shields): a signal wire (kind wire) of a net that has shields and
    a route rule (route_net's) with a horizontal and a vertical layer, its
    layer one of them."""
    if "kind" not in row.keys() or row["kind"] != "wire":
        return False                          # a strap, pin wire, shield, box ...
    if not any(r["kind"] == "shield" for r in db.net_wire_rows(row["net"])):
        return False                          # routed with no shields: none are added
    return _shield_grid(db, row["net"], row["layer"]) is not None


def rebuilt_shields(db, rows):
    """The handles in rows [(handle, table, row)] of shields that a wire in
    rows has and makes again when moved: they are not moved themselves."""
    mine = {f"net_wire:{s['net']}/{s['seq']}" for _, table, row in rows
            if table == "net_wire" and rebuilds(db, row) for s in shields_of(db, row)}
    return [h for h, _, _ in rows if h in mine]


def _shield_grid(db, net, layer):
    """route_net's grid for the shields of net on layer, or None (no route
    rule, or layer not one of its two)."""
    from core.commands import route_net
    rule = db.net_route_rule(net)
    if rule is None:
        return None
    try:
        layers = route_net._rule_layers(db, rule)
    except HtreeError:
        return None
    return route_net.Grid(db, layers) if layer in (layers[0].name, layers[1].name) else None


def _shielded(db, moves):
    """[(handle, row before the move, its shield rows)] of the moved wires
    whose shields are made again after the move."""
    return [(h, row, shields_of(db, row)) for h, table, row, _, _ in moves
            if table == "net_wire" and rebuilds(db, row)]


def rebuild_shields(db, before, out):
    """Make the shields of moved signal wires again where they lie now, as
    route_net -shield does (the track's power net, clear of other shapes,
    inside the design boundary, over the strap stacks of the net's cells);
    their old shields go. Then the net's power links (the shield extensions
    of its cells' power straps and their crossing boxes) are made again
    against the shields as they are now, as route_net -shield makes them.
    before: _shielded, taken before the move. Records what it removed and
    added in db.redrawn (the GUI redraws them)."""
    from core import root_attrs
    from core.commands import route_net
    db.redrawn = []
    by_net = {}
    for h, row, shields in before:
        by_net.setdefault(row["net"], []).append((h, row, shields))
    for net, items in by_net.items():
        grid = _shield_grid(db, net, items[0][1]["layer"])
        old = {s["id"]: s for _, _, shields in items for s in shields}
        gone = [f"net_wire:{s['net']}/{s['seq']}" for s in old.values()]
        db.delete_wires([("net_wire", k) for k in old])
        auto_via.drop(db, gone)
        moved = {row["id"] for _, row, _ in items}
        rows = db.net_wire_rows(net)
        wires = [("wire" if r["id"] in moved else "own", r["layer"], rect_of(r))
                 for r in rows if r["kind"] not in ("cross", "shield", "shield_ext")] + \
            [("own", layer, r) for layer, r in db.stretch_pieces(net, ("extension",))]
        others = [(r["layer"], rect_of(r)) for r in rows if r["kind"] == "shield"]
        insts = {r["inst"] for r in db.strap_rows() if r["net"] == net}
        stacks = []
        for inst in sorted(insts):
            straps = db.strap_rows(inst)
            rects = [base_rect(r) for r in straps]          # as route_pin made them
            reach = max((r["max_extension"] or 0.0) for r in straps)
            stacks.append((min(r[0] for r in rects) - reach, max(r[2] for r in rects) + reach,
                           min(r[1] for r in rects), max(r[3] for r in rects)))
        made, cut, no_power, _, fenced = route_net._shields(
            wires, route_net._ia_shapes(db, net), grid, route_net.SHIELD_NETS, stacks,
            root_attrs.get(db, "ignore_shield_less_than_routing_length"))
        made = [s for s in made if not any(layer == s[1] and route_net._within(s[2], r)
                                           for layer, r in others)]     # one is there
        added = db.add_net_wires([(net, "shield", s[1], rect_text(s[2]), s[3], None)
                                  for s in made])
        new = [f"net_wire:{n}/{seq}" for n, seq in added]
        db.redrawn += gone + new
        where = "; ".join(f"{s[3]} {s[1]} {'y' if s[1] == grid.h.name else 'x'} "
                          f"{_num(round(_line_of(s[2], s[1] == grid.h.name), 6))} "
                          f"({_num(round(route_net._along(s[2]), 3))} um)" for s in made)
        info(f"  shields of {' '.join(h for h, _, _ in items)} made again where "
             f"{'it lies' if len(items) == 1 else 'they lie'} now: {where or 'none'}"
             f"; {len(gone)} old shield(s) removed", out)
        if no_power:
            warn(route_net.NO_POWER, f"{net}: no shield where the next track is not a power "
                 f"track: {'; '.join(no_power)}", out)
        if cut:
            info(f"    shields cut over {_num(round(cut, 3))} um where they would come closer "
                 f"than the rule spacing to another shape", out)
        if fenced:
            info(f"    shields cut over {_num(round(fenced, 3))} um at the design boundary", out)
        db.redrawn += _remake_power_links(db, net, grid, insts, out)


def _remake_power_links(db, net, grid, insts, out):
    """Remove net's power links and make them again (route_net._power_links)
    for the cells insts, against the net's shields as they are now. Returns
    the handles removed and added."""
    from types import SimpleNamespace
    from core.commands import route_net
    old = [r for r in db.net_wire_rows(net)
           if r["kind"] == "shield_ext" or (r["kind"] == "cross" and r["shield_net"])]
    gone = [f"net_wire:{net}/{r['seq']}" for r in old]
    db.delete_wires([("net_wire", r["id"]) for r in old])
    auto_via.drop(db, gone)
    stretched = {(r["inst"], r["seq"]) for r in db.stretch_rows(owner=net)
                 if r["kind"] == "shield_ext"}
    db.unstretch([net], ("shield_ext",))          # the power straps it lengthened
    gone += [f"strap:{i}/{k}" for i, k in stretched]
    wires = [("shield", r["layer"], rect_of(r), r["shield_net"]) if r["kind"] == "shield"
             else (r["kind"], r["layer"], rect_of(r)) for r in db.net_wire_rows(net)]
    terms = [SimpleNamespace(kind="strap", inst=i) for i in sorted(insts)]
    links = route_net._power_links(db, net, terms, wires, grid, out)
    added = db.add_net_wires([(net, kind, layer, rect_text(r), power, None)
                              for kind, layer, r, power in links])
    info(f"    power links made again: {len(links)} (power straps lengthened to the shields, "
         f"and their crossing boxes); {len(old) + len(stretched)} old one(s) removed", out)
    now = {(r["inst"], r["seq"]) for r in db.stretch_rows(owner=net) if r["kind"] == "shield_ext"}
    return gone + [f"net_wire:{n}/{seq}" for n, seq in added] + \
        [f"strap:{i}/{k}" for i, k in now]


def _line_of(r, horizontal):
    return (r[1] + r[3]) / 2 if horizontal else (r[0] + r[2]) / 2


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
    Tcl list). A via (via:<net>/<n>) stands for the crossing box it comes
    from (its .source). Every handle is checked before anything changes."""
    db = session.db
    handles = list(dict.fromkeys(_via_source(db, h, cmd) for h in session.split_list(text)))
    if not handles:
        raise HtreeError(NOT_A_WIRE, f"{cmd}: no wires given")
    found = []
    for handle in handles:
        kind = objects.obj_type(handle) if objects.is_handle(handle) else None
        row = objects.wire_row(db, handle) if kind in objects.WIRE_TABLES else None
        if row is None:
            raise HtreeError(NOT_A_WIRE, f"{cmd}: '{handle}' is not a route wire (net_wire:, "
                             f"strap:, pin_wire: or via: handles; get_db selected)")
        found.append((handle, objects.WIRE_TABLES[kind], row))
    return found


def _via_source(db, handle, cmd):
    """The crossing box a via comes from, for a via: handle; else handle."""
    if not handle.startswith("via:"):
        return handle
    from core import vias
    net, _, seq = handle[len("via:"):].rpartition("/")
    row = vias.row(db, net, int(seq)) if seq.isdigit() else None
    if row is None:
        raise HtreeError(NOT_A_WIRE, f"{cmd}: there is no via '{handle}' (get_db vias)")
    if not (row["source"] or "").startswith("net_wire:"):
        raise HtreeError(NOT_A_WIRE, f"{cmd}: via {handle} is the via of a pin "
                         f"({row['source']}): it is where its pin wire meets the pin, and "
                         f"moves with the pin wire or the instance")
    return row["source"]


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
