"""route_net -net <nets> -rule <rule> [-via_weight <um>]: route nets on the
tracks of a route rule's horizontal and vertical layer, from the driver's
output pin to every load's input pin (or its stub).

    route_net -net temp_L1_inv1_Y -rule rule1
    route_net -net [get_db nets *L7*] -rule rule1 -via_weight 10
    route_net -net [get_db pin:buf1/A .net] -rule rule1

The nets: those of a built spine (spine_net:<spine>/<net>), and the nets of
no spine (net:<name>, core/netlist.py): the net of an input port of the
design, or one connect_pin or add_buffer_on_net made, with one driver (the
port, or an output pin) and the input pins on it. A port has no pin route:
the route ends at the track crossing nearest the centre of its shapes, and
is connected to it only where a wire of the route lies on a shape of the
port on its own layer; no wire or via is made down to a port on another
layer.

Lee maze routing (A* ordered) on the grid of track crossings: a step along a
track costs its length, a layer change costs -via_weight more. The tree grows
from the driver to the nearest unreached load, then the next, each time from
any point of the tree so far.

The design boundary (DEF DIEAREA) is a hard limit: a track crossing whose box
is not inside it is no part of the grid, and a step along a track is taken
only when its whole wire stays inside, so a route goes round a notch of the
boundary, never across it. The same holds for everything stored with the
route: the wire down to a strap, the pin route extensions, the shields (cut
at the boundary) and the power strap extensions. A pin or stub with no
crossing inside the boundary is not routed.

Pin routes first: before any net is routed, the strap of every connected
signal pin (route_pin done) is extended left and right to the nearest signal
track of the vertical layer beyond each cell edge, within its max_extension
(pin routing spec max_strap_extension) and the strap layer's tech spacing.
The route then only has to reach the extended strap: a vertical wire across
it on any signal track it covers (connected); it never goes to the pin. A pin
without route_pin: the route ends at the track crossing nearest the pin (not
connected) and a warning is given.

-shield: every wire of the net gets a power wire on each side, on the same
layer and span, on the nearest track that keeps the rule spacing: by default
VDD_SOC on the left of vertical wires and above horizontal ones, VSS on the
other side (-shield_nets {VDD_SOC VSS} sets the two nets). A shield is cut
where it would come closer than the rule spacing to any other shape on its
layer. Then the power straps route_pin made on the net's cells (VDD_SOC,
VSS) are extended left or right, up to their max_extension, to cover a
vertical shield of their net: the power pins reach the shields through pin
wire, strap and extension, as the signal pins reach the route through
theirs. The route never goes to a pin directly when it has a strap.

Wires overlap fully at a layer change: each wire end is extended by half the
other layer's width, so two wires that cross make a box of (vertical width) x
(horizontal width). These boxes are stored with the wires (kind cross).
"""

import bisect
import fnmatch
import heapq
import itertools
from types import SimpleNamespace

from core import netlist, objects, root_attrs, route_status, vias
from core.commands.create_route_rule import DEFAULT, tech_spacing
from core.db import _num, base_rect, stub_owner
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "route_net"
SUMMARY = "Route nets on a route rule's tracks (Lee, weighted layer changes)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-net": "value", "-rule": "value", "-via_weight": "value", "-shield": "flag",
           "-shield_nets": "value"}

USAGE = 1
NO_NET = 170
NO_RULE = 171
NOT_PINNED = 172
REPLACED = 173
NO_PATH = 174
NO_TRACKS = 175
OFF_TRACKS = 176
NO_POWER = 177
OUTSIDE = 178
SLANTED = 179
NO_ENDS = 265
OFF_PORT = 266
STALE_STUBS = 279
FIXED_APART = 287

VIA_WEIGHT = 5.0      # um of wire one layer change is worth
# Shield nets left of / above and right of / below the signal, for a layer
# with no track assignment; with one, each shield takes its track's net.
SHIELD_NETS = ("VDD_SOC", "VSS")
MARGIN = 10           # tracks of room around the terminals
OUT_WEIGHT = 0.25     # compact: more cost of a wire per track beyond its pins' tracks
TIE = 0.001           # compact: and per track away from the stub track (equal tracks only)
BAND_GAP = 2          # track table: empty signal tracks two used ones of a band may have between
TRUNK = 25.0          # track table: um of wire on a track that make its band worth a row
TOL = 1e-6
KEEP = 2              # signal-track pitches a strap's route costs more off the track the
                      # cell is crossed on: a straight net keeps one track through its cells
H, V = 0, 1           # grid layers: the rule's horizontal and vertical layer


def run(session, argv):
    return run_as(session, argv, NAME, OPTIONS)


def run_as(session, argv, cmd, options):
    """route_net, and route_track (the same router, with -compact and a table
    of the tracks used): cmd is the name its messages carry."""
    try:
        result = _run(session, argv, cmd, options)
        vias.report_assigned(vias.auto_assign(session.db), cmd, session.out)
        return result
    except HtreeError as e:
        if cmd == NAME:
            raise
        raise HtreeError(e.msg_id, e.text.replace(NAME, cmd)) from None


def _run(session, argv, cmd, options):
    opts, _ = parse_options(cmd, argv, options)
    compact = bool(opts.get("-compact"))
    if "-net" not in opts or "-rule" not in opts:
        raise HtreeError(USAGE, "route_net: -net and -rule are required. Usage: route_net "
                         "-net <nets> -rule <route_rule> [-via_weight <um>]"
                         + (" [-compact]" if "-compact" in options else ""))
    try:
        via_weight = float(opts.get("-via_weight", VIA_WEIGHT))
    except ValueError:
        via_weight = -1.0
    if via_weight < 0:
        raise HtreeError(USAGE, f"route_net: -via_weight must be a number >= 0 (um of wire "
                         f"a layer change costs), got '{opts['-via_weight']}'")
    shield = None
    if opts["-shield"] or "-shield_nets" in opts:
        shield = tuple(session.split_list(opts.get("-shield_nets", " ".join(SHIELD_NETS))))
        if len(shield) != 2:
            raise HtreeError(USAGE, f"route_net: -shield_nets takes two nets, left of / above "
                             f"and right of / below the signal, got '{opts['-shield_nets']}'")
    db = session.db
    objects.require_tech(db)
    nets = _nets(session, opts["-net"], session.out, cmd)
    fixed = db.fixed_nets()
    route_status.skip(cmd, "fixed net(s)", [row["name"] for _, row in nets
                                            if row["name"] in fixed], session.out)
    nets = [(spine, row) for spine, row in nets if row["name"] not in fixed]
    if not nets:
        return ()
    layers = _rule_layers(db, opts["-rule"].removeprefix("route_rule:"))
    grid = Grid(db, layers)
    grid.cmd = cmd
    out = session.out
    h, v = layers
    info(f"{cmd}: rule {layers.rule}: {h.name} horizontal (width {_num(h.width)}, "
         f"spacing {_num(h.spacing)}), {v.name} vertical (width {_num(v.width)}, spacing "
         f"{_num(v.spacing)}); a layer change costs {_num(via_weight)} um", out)
    if compact:
        info(f"  compact: every net on the tracks nearest its pins (a wire on a track beyond "
             f"them costs {_num(OUT_WEIGHT)} of its length more for every track further out); "
             f"of equal tracks, the one nearest the stubs of its spine", out)
    done = []
    if shield:
        for lay in layers:
            if lay.name in grid.patterns:
                info(f"  shields on {lay.name}: one each side, the net of its track "
                     f"(assign_track_for_route {' '.join(grid.patterns[lay.name])})", out)
            else:
                info(f"  shields on {lay.name}: one each side, {shield[0]} left of / above "
                     f"and {shield[1]} right of / below the signal (no track assignment)",
                     out)
    # the nets are routed again: their old routing goes first, so none of it
    # blocks another of them (their stub wires stay: route_final_stub's)
    cleared = sum(db.set_net_wires(row["name"], [], stub=False) for _, row in nets)
    for _, row in nets:
        db.unname_pins(row["name"])
    if cleared:
        warn(REPLACED, f"{cmd}: removed the {cleared} old wires, extensions, crossing "
             f"boxes and shields of the {len(nets)} net(s) before routing them again", out)
    nets = _flow_order(nets)             # a net before the nets its loads drive
    pre = _extend_pin_routes(db, grid, nets, out)
    from core import spine_tracks       # a spine whose spec gives tracks keeps its stubs'
    spec = [(s, r) for s, r in nets if s is not None and spine_tracks.cell_tracks(db, s["name"])]
    if compact or spec:
        pre["reserved"] = _stub_tracks(db, grid, nets if compact else spec, pre, out)
    for spine, row in nets:
        if route(db, grid, spine, row, via_weight, out, shield, pre, compact):
            db.set_net_route_rule(row["name"], layers.rule)
            done.append(f"spine_net:{spine['name']}/{row['name']}" if spine is not None
                        else f"net:{row['name']}")
    if shield:                   # every cell of these nets, after all of them are routed
        insts = dict.fromkeys(i for spine, row in nets for i in _insts(spine, row)
                              if db.inst_row(i) is not None and db.pin_wire_rows(i))
        pins = power_pins(db, insts, set(shield))
        bad = [f"{i}/{p} (strap {k})" for i, p, k, ok in pins if not ok]
        info(f"  power pins connected to shields: {len(pins) - len(bad)} of {len(pins)}", out)
        if bad:
            warn(NO_POWER, f"power pins not connected to a shield (their strap reaches no "
                 f"shield of its net within max_strap_extension): {' '.join(bad)}", out)
    if cmd != NAME:
        _report_tracks(db, grid, nets, pre.get("reserved", []), cmd, out)
    return tuple(done)


def _flow_order(nets):
    """The nets [(spine, row)] in the order the signal runs: a net of a
    spine before every net driven by one of its loads (so the next net
    keeps the track the cell is reached on); otherwise as given."""
    driven = {}                          # inst -> indices of the nets it drives
    for k, (spine, row) in enumerate(nets):
        if spine is not None:
            driven.setdefault(row["driver"], []).append(k)
    after = {k: set() for k in range(len(nets))}      # k -> the nets before it
    for k, (spine, row) in enumerate(nets):
        if spine is not None:
            for load in row["loads"].split():
                for m in driven.get(load, ()):
                    if m != k:
                        after[m].add(k)
    order, done = [], set()
    while len(order) < len(nets):
        ready = [k for k in range(len(nets)) if k not in done and after[k] <= done]
        k = ready[0] if ready else min(k for k in range(len(nets)) if k not in done)   # a loop
        order.append(k)
        done.add(k)
    return [nets[k] for k in order]


def _stub_tracks(db, grid, nets, pre, out):
    """compact: [(net, layer, rect)] of the wires route_final_stub gives the
    stubs of the nets' spines (_stub_plan, made before any net is routed: the
    track nearest each centre line). No other net is routed on them, so the
    stubs keep the track next to the cells. A stub routed before keeps its
    wires when they are these; else they are removed, with a warning, as the
    old wires of the nets are: they would take a second track, and
    route_final_stub routes the stub again."""
    key = lambda r: tuple(round(c, 6) for c in r)
    shapes, said, stale, kept, gone = [], {}, [], [], 0
    pre["anchor"] = {}               # spine id -> {(H | V, the track of a stub wire)}
    for spine in {s["id"]: s for s, _ in nets if s is not None}.values():
        plan = _stub_plan(db, grid, spine, pre)
        for stub in plan.tracks:
            net = plan.net[stub] or stub
            rects = plan.rects(grid, stub)
            for lay, r in rects:
                shapes.append((net, lay.name, r))
                at = (r[1] + r[3]) / 2 if lay is grid.h else (r[0] + r[2]) / 2
                pre["anchor"].setdefault(spine["id"], set()).add((H if lay is grid.h else V, at))
                said.setdefault((lay.name, "y" if lay is grid.h else "x", round(at, 6)),
                                []).append(stub)
            stored = {key(float(c) for c in r["rect"].split())
                      for r in db.stub_wire_rows(net) if r["kind"] == "stub"}
            if stored and stored != {key(r) for _, r in rects}:
                if route_status.is_fixed(db, route_status.stub_key(spine["name"], stub)):
                    kept.append(f"stub:{spine['name']}/{stub}")     # its wires block
                    continue
                stale.append(f"stub:{spine['name']}/{stub}")
                gone += db.set_net_wires(net, [], stub=True)
    if said:
        info("  compact: tracks kept free for the stubs (route_final_stub): "
             + "; ".join(f"{layer} {axis} {_num(at)} ({len(dict.fromkeys(stubs))} stub(s))"
                         for (layer, axis, at), stubs in sorted(said.items())), out)
    if stale:
        warn(STALE_STUBS, f"{grid.cmd}: removed the {gone} wires, crossing boxes and shields "
             f"of {len(stale)} stub(s) routed before on another track than the one kept "
             f"free for them; route_final_stub routes them again: {' '.join(stale)}", out)
    route_status.skip(grid.cmd, "fixed stub(s) routed on another track than the one kept "
                      "free for them", kept, out)
    return shapes


def _report_tracks(db, grid, nets, reserved, cmd, out):
    """The table of route_track: the signal tracks the nets' wires lie on, in
    bands (used tracks next to each other, at most BAND_GAP empty ones
    between two), every track of a band with the wire on it. A band with no
    track of TRUNK um of wire or more (the short hops across the other
    layer) is left out. reserved: the stub wires to come (_stub_tracks)."""
    names = {row["name"] for _, row in nets}
    rect = lambda text: tuple(float(c) for c in text.split())
    shapes = [(name, r["layer"], rect(r["rect"]), r["kind"] == "stub") for name in names
              for r in db.net_wire_rows(name) + db.stub_wire_rows(name)
              if r["kind"] in ("wire", "stub")]
    shapes += [(net, layer, r, None) for net, layer, r in reserved]
    lines = []
    for lay, tracks, axis in ((grid.h, grid.all_ys, 1), (grid.v, grid.all_xs, 0)):
        use = {}                     # track index -> [(lo, hi, net, stub)]
        for net, layer, r, stub in shapes:
            along = (r[2] - r[0], r[3] - r[1])[1 - axis]
            if layer != lay.name or along < (r[2] - r[0], r[3] - r[1])[axis] - TOL:
                continue             # of the other layer, or a wire across the tracks
            k = bisect.bisect_left(tracks, (r[axis] + r[axis + 2]) / 2 - TOL)
            if k < len(tracks) and abs(tracks[k] - (r[axis] + r[axis + 2]) / 2) < TOL:
                use.setdefault(k, []).append((r[1 - axis], r[3 - axis], net, stub))
        bands, band = [], []
        for k in sorted(use):
            if band and k - band[-1] > BAND_GAP + 1:
                bands.append(band)
                band = []
            band.append(k)
        if band:
            bands.append(band)
        length = lambda k: sum(hi - lo for lo, hi in _merge([(a, b) for a, b, _, _ in use[k]]))
        for band in bands:
            if max(length(k) for k in band) < TRUNK:
                continue
            lo = min(a for k in band for a, _, _, _ in use[k])
            hi = max(b for k in band for _, b, _, _ in use[k])
            inside = range(band[0], band[-1] + 1)
            empty = [k for k in inside if k not in use]
            way = "xy"[axis]
            lines.append(f"  {lay.name} {way} {_num(tracks[band[0]])} .. {_num(tracks[band[-1]])}"
                         f" ({'yx'[axis]} {_num(round(lo, 3))} .. {_num(round(hi, 3))}): "
                         f"{len(inside)} signal track(s), {len(empty)} empty")
            lines.append(f"    {'Track ' + way:<12} {'Wire um':>10} {'Filled':>7}  Nets")
            for k in inside:
                if k not in use:
                    lines.append(f"    {_num(tracks[k]):<12} {'0':>10} {'0%':>7}  (empty)")
                    continue
                who = {}
                for _, _, net, stub in use[k]:
                    who[net] = who.get(net) or ("" if stub is False else " (stub)" if stub
                                                else " (stub, kept free)")
                lines.append(f"    {_num(tracks[k]):<12} {_num(round(length(k), 3)):>10} "
                             f"{round(100 * length(k) / (hi - lo)) if hi > lo else 100:>6}%  "
                             + " ".join(net + note for net, note in who.items()))
    info(f"{cmd}: signal tracks of the {len(names)} net(s) (bands of tracks next to each "
         f"other with {_num(TRUNK)} um of wire or more on one; Filled: of the band's "
         f"length)" + ("" if lines else ": none"), out)
    for line in lines:
        info(line, out)


def _nets(session, text, out=None, cmd=NAME):
    """[(spine row, spine_net row)] from names, glob patterns or handles; a
    net of no spine (net:<name>) as (None, {"name", "ends"}), see _plain.
    Stubs are nets too (get_db nets lists them), but route_final_stub routes
    them: they are left out, with a note."""
    db = session.db
    every = [(db.spine_row(s), r) for s in db.spine_names()
             for r in db.spine_net_rows(db.spine_row(s)["id"])]
    stubs = [(s, r["name"]) for s in db.spine_names()
             for r in db.spine_stub_rows(db.spine_row(s)["id"])]
    mine = {r["name"] for _, r in every}
    others = [n for n in netlist.by_net(db) if n not in mine]    # with a pin on them
    found, skipped = [], []
    for word in session.split_list(text):
        plain, stub_hits = [], []
        if word.startswith("spine_net:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits = [(s, r) for s, r in every if s["name"] == spine and r["name"] == name]
        elif word.startswith("stub:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits, stub_hits = [], [f"{s}/{n}" for s, n in stubs if (s, n) == (spine, name)]
        elif word.startswith("net:"):
            hits, plain = [], [(n, True) for n in others if n == word[4:]]
        else:
            hits = [(s, r) for s, r in every if fnmatch.fnmatchcase(r["name"], word)]
            stub_hits = [f"{s}/{n}" for s, n in stubs if fnmatch.fnmatchcase(n, word)]
            # a pattern takes the nets that can be routed; a name says why not
            plain = [(n, n == word) for n in others if fnmatch.fnmatchcase(n, word)]
        name = word[4:] if word.startswith("net:") else word
        if not hits and not stub_hits and not plain and db.port_of_net(name) is not None:
            plain = [(name, True)]           # a port's net with no pin on it: _plain says so
        if not hits and not stub_hits and not plain:
            raise HtreeError(NO_NET, f"route_net: no net '{word}' (get_db nets lists the "
                             f"nets of the spines; the net of a pin: get_db pin:<inst>/<pin> "
                             f".net)")
        found += [h for h in hits if h not in found]
        skipped += [h for h in stub_hits if h not in skipped]
        for name, named in plain:
            hit = _plain(db, name, out if named else None, cmd)
            if hit is not None and all(row["name"] != name for _, row in found):
                found.append(hit)
    if skipped and out is not None:
        info(f"{cmd}: {len(skipped)} stub(s) left to route_final_stub: "
             f"{' '.join(skipped)}", out)
    return found


def _plain(db, name, out=None, cmd=NAME):
    """A net of no spine as (None, row): row["ends"] holds its driver (an
    output pin or an input port, netlist.End) and then its input pins. None,
    with a warning when out is given, for a net without one driver, without
    an input pin, or of a port that is nowhere."""
    ends = netlist.ends(db, name)
    drivers = [e for e in ends if e.drives]
    loads = [e for e in ends if e.is_load]
    why = None
    if len(drivers) != 1:
        why = "it has no driver (an output pin, or an input port of the design)" \
            if not drivers else f"it has {len(drivers)} drivers " \
            f"({', '.join(e.text for e in drivers)})"
    elif not loads:
        why = "no input pin of an instance is on it"
    elif drivers[0].kind == "port" and objects.port_centre(db, drivers[0].pin) is None:
        why = f"{drivers[0].text} has no shapes and no location (DEF PINS)"
    if why is None:
        return None, {"name": name, "ends": drivers + loads}
    if out is not None:
        warn(NO_ENDS, f"{cmd}: net {name} is not routed: {why}", out)
    return None


def _insts(spine, row):
    """The instances a net goes to (stubs of a spine net among them)."""
    if spine is None:
        return [e.inst for e in row["ends"] if e.kind == "pin"]
    return [row["driver"]] + row["loads"].split()


class Layer:
    def __init__(self, name, width, spacing):
        self.name, self.width, self.spacing = name, width, spacing


class Layers(tuple):
    rule = ""


def _rule_layers(db, rule):
    """(horizontal Layer, vertical Layer) of a route rule: the first of each
    direction in the rule's layer order."""
    if rule == DEFAULT:
        raise HtreeError(NO_RULE, "route_net: give a named rule (create_route_rule) with one "
                         "horizontal and one vertical layer; 'default' has every layer")
    names = db.route_rule_layers(rule)
    if not names:
        raise HtreeError(NO_RULE, f"route_net: there is no route rule '{rule}' (rules: "
                         f"{' '.join(db.route_rule_names()) or 'none'})")
    picked = {}
    for name in names:
        direction = (db.layer_row(name)["direction"] or "").lower()
        if direction in ("horizontal", "vertical") and direction not in picked:
            r = db.route_rule_layer_row(rule, name)
            picked[direction] = Layer(name, r["width"], r["spacing"])
    if len(picked) < 2:
        raise HtreeError(NO_RULE, f"route_net: route rule {rule} ({' '.join(names)}) needs a "
                         f"horizontal and a vertical layer; add one with create_route_rule "
                         f"-append")
    layers = Layers((picked["horizontal"], picked["vertical"]))
    layers.rule = rule
    return layers


def _signal_tracks(db, layer, direction):
    """Track coordinates a signal may use: all of the layer's DEF tracks in
    direction, or only the '-' ones when assign_track_for_route set a pattern."""
    positions = db.track_positions(layer, direction)
    if not positions:
        raise HtreeError(NO_TRACKS, f"route_net: {layer} has no DEF TRACKS "
                         f"{direction.upper()} (read_def)")
    row = db.track_assignment_row(layer)
    if row is not None and row["direction"] == direction:
        pattern = row["pattern"].split()
        positions = [p for k, p in enumerate(positions) if pattern[k % len(pattern)] == "-"]
        if not positions:
            raise HtreeError(NO_TRACKS, f"route_net: the {layer} track assignment leaves no "
                             f"signal ('-') track")
    return positions


class Grid:
    """All signal tracks: ys of the horizontal layer, xs of the vertical one."""

    def __init__(self, db, layers):
        self.h, self.v = layers
        self.all_ys = _signal_tracks(db, self.h.name, "y")
        self.all_xs = _signal_tracks(db, self.v.name, "x")
        self.raw_ys = db.track_positions(self.h.name, "y")   # shields may use any track
        self.raw_xs = db.track_positions(self.v.name, "x")
        self.patterns = {}       # layer -> assign_track_for_route pattern over raw tracks
        for lay, direction in ((self.h, "y"), (self.v, "x")):
            row = db.track_assignment_row(lay.name)
            if row is not None and row["direction"] == direction:
                self.patterns[lay.name] = row["pattern"].split()
        self.stub_plans = {}     # spine id -> the tracks of its stubs (_stub_plan)
        self.cmd = NAME          # the command the messages name (route_track: its own)
        self.fence = None        # the design boundary: nothing is routed outside it
        if db.has_design() and db.design_row()["boundary"]:
            self.fence = Fence([float(c) for c in db.design_row()["boundary"].split()])

    def track_net(self, layer, tracks, j):
        """The assigned net of track j of layer ('-' signal, 'NA' blank), or
        None when the layer has no track assignment."""
        pattern = self.patterns.get(layer)
        return pattern[j % len(pattern)] if pattern else None


class Fence:
    """The design boundary (DEF DIEAREA, rectilinear) as the hard limit of the
    routing: the x intervals that are inside it over a whole horizontal band,
    the y intervals over a whole vertical one."""

    def __init__(self, polygon):
        pts = list(zip(polygon[0::2], polygon[1::2]))
        self.upright, self.flat = [], []     # edges: (x, y1, y2) and (y, x1, x2)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            if abs(x1 - x2) < TOL and abs(y1 - y2) < TOL:
                continue
            if abs(x1 - x2) < TOL:
                self.upright.append((x1, min(y1, y2), max(y1, y2)))
            elif abs(y1 - y2) < TOL:
                self.flat.append((y1, min(x1, x2), max(x1, x2)))
            else:
                raise HtreeError(SLANTED, f"the design boundary has a slanted edge ({_num(x1)} "
                                 f"{_num(y1)}) ({_num(x2)} {_num(y2)}): routes are kept "
                                 f"inside a rectilinear boundary only")
        self.xs = sorted({x for x, _, _ in self.upright})    # where the boundary turns
        self.ys = sorted({y for y, _, _ in self.flat})
        self._bands = {}

    def row(self, y1, y2):
        """[(x1, x2)] of the x inside the boundary all the way from y1 to y2."""
        return self._band(self.upright, self.ys, y1, y2, "y")

    def col(self, x1, x2):
        """[(y1, y2)] of the y inside the boundary all the way from x1 to x2."""
        return self._band(self.flat, self.xs, x1, x2, "x")

    def _band(self, edges, turns, lo, hi, axis):
        key = (axis, round(lo, 6), round(hi, 6))
        if key not in self._bands:
            # the boundary is the same between two turns: a scan line in each part
            cuts = [lo] + turns[bisect.bisect_right(turns, lo + TOL):
                                bisect.bisect_left(turns, hi - TOL)] + [hi]
            found = None
            for a, b in zip(cuts, cuts[1:]):
                at = (a + b) / 2
                hits = sorted(c for c, e1, e2 in edges if e1 < at < e2)
                spans = _merge(list(zip(hits[0::2], hits[1::2])))
                found = spans if found is None else _both(found, spans)
            self._bands[key] = found
        return self._bands[key]

    def holds(self, rect):
        """True when the rect lies inside the boundary (on it counts)."""
        x1, y1, x2, y2 = rect
        if y2 - y1 < 2 * TOL:                # no height: the line through it
            y1, y2 = y1 - TOL, y2 + TOL
        return any(lo - TOL <= x1 and x2 <= hi + TOL for lo, hi in self.row(y1, y2))

    def spans(self, lo, hi, a1, a2, horizontal):
        """The parts of lo .. hi a wire across a1 .. a2 may use: [(lo, hi)]."""
        inside = self.row(a1, a2) if horizontal else self.col(a1, a2)
        return [(max(lo, p1), min(hi, p2)) for p1, p2 in inside
                if min(hi, p2) - max(lo, p1) > TOL]


def _both(a, b):
    """The parts two sorted lists of spans have in common."""
    found, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi - lo > TOL:
            found.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return found


class Inside:
    """The fence on one route's grid: the crossings whose box (v.width x
    h.width) is inside the boundary, and the steps along a track whose wire
    stays inside (both ends in the same inside stretch of the track)."""

    def __init__(self, fence, xs, ys, h, v):
        self.fence, self.xs, self.ys, self.h, self.v = fence, xs, ys, h, v
        self.rows, self.cols = {}, {}        # track index -> {crossing index: stretch}

    def _stretches(self, found, k, horizontal):
        if k not in found:
            lay, other = (self.h, self.v) if horizontal else (self.v, self.h)
            c = (self.ys if horizontal else self.xs)[k]
            across = self.xs if horizontal else self.ys
            band = (self.fence.row if horizontal else self.fence.col)(c - lay.width / 2,
                                                                      c + lay.width / 2)
            found[k] = {}
            for n, (lo, hi) in enumerate(band):
                a = bisect.bisect_left(across, lo + other.width / 2 - TOL)
                b = bisect.bisect_right(across, hi - other.width / 2 + TOL)
                found[k].update((m, n) for m in range(a, b))
        return found[k]

    def node(self, i, j):
        return i in self._stretches(self.rows, j, True)

    def step(self, a, b):
        """True when the wire from node a to its neighbour b on the same
        track stays inside the boundary."""
        layer, i, j = a
        _, i2, j2 = b
        if layer == H:
            row = self._stretches(self.rows, j, True)
            return i in row and row[i] == row.get(i2)
        col = self._stretches(self.cols, i, False)
        return j in col and col[j] == col.get(j2)


def _nearest(values, c):
    k = bisect.bisect_left(values, c)
    return min(values[max(0, k - 1):k + 1], key=lambda v: abs(v - c))


def _net_terminals(db, spine, row, pre=None, grid=None):
    """The driver's terminal, then each load's (a pin or a stub); of a net of
    no spine, its driver's (a pin or a port) and its input pins'. With grid a
    stub that is not routed yet ends on the track route_final_stub gives it."""
    if spine is None:
        return [_port_terminal(db, e.pin) if e.kind == "port"
                else _terminal(db, None, e.inst, "out" if e.drives else "in", pre, e.pin)
                for e in row["ends"]]
    terms = [_terminal(db, spine, row["driver"], "out", pre)]
    stubs = {s["name"]: s for s in db.spine_stub_rows(spine["id"])}
    for load in row["loads"].split():
        if load in stubs:
            plan = _stub_plan(db, grid, spine, pre) if grid is not None else None
            terms.append(_stub_terminal(db, stubs[load], row["name"], grid, plan))
        else:
            terms.append(_terminal(db, spine, load, "in", pre))
    return terms


def _stub_plan(db, grid, spine, pre=None):
    """The tracks route_final_stub gives the stubs of the spine as things are
    (its plan_stubs): the stubs on one centre line share a track, which need
    not be the nearest of each. Made once a run, so all the nets of the spine
    aim at the same tracks."""
    from core.commands.route_final_stub import plan_stubs    # it imports this module
    if spine["id"] not in grid.stub_plans:
        more = [(layer, r, net) for net, layer, r in (pre or {}).get("shapes", ())]
        grid.stub_plans[spine["id"]] = plan_stubs(db, grid, spine, more=more)
    return grid.stub_plans[spine["id"]]


def _extend_pin_routes(db, grid, nets, out):
    """Step a: extend the strap of every connected signal pin of the nets left
    and right to the nearest signal track of the vertical layer beyond each
    cell edge (the strap covers that track's wire), at most the strap's
    max_extension, keeping the strap layer's tech spacing to other nets'
    shapes and inside the design boundary. A pin of a cell the spine spec
    gives tracks (core/spine_tracks.py) is extended to its own track
    instead, the input pin to its input track, the output to its output
    track (no piece when the strap covers it already). Returns {"pins": {(inst, pin): (net, [pieces], (x1, x2))},
    "shapes": [(net, layer, rect)]} of the pieces."""
    v, xs = grid.v, grid.all_xs
    routing = {row["name"] for _, row in nets}
    others = [(n, layer, r) for n, layer, r in _ia_shapes(db, None) if n not in routing]
    pins, shapes, lines = {}, [], []
    spec = _spec_pin_tracks(db, nets)
    for spine, row in nets:
        for t in _net_terminals(db, spine, row):
            if t.kind != "strap" or (t.inst, t.pin) in pins:
                continue
            sx1, sy1, sx2, sy2 = t.strap
            pieces, x1, x2, said = [], sx1, sx2, []
            k = bisect.bisect_left(xs, sx1 + v.width / 2 - TOL) - 1   # first left of it
            left = xs[k] if k >= 0 else None
            k = bisect.bisect_right(xs, sx2 - v.width / 2 + TOL)       # first right of it
            right = xs[k] if k < len(xs) else None
            own = spec.get((t.inst, t.pin))
            if own is not None:          # the spine spec's track only
                left, right = (own, None) if own < sx1 + v.width / 2 - TOL else \
                    (None, own) if own > sx2 - v.width / 2 + TOL else (None, None)
                if left is None and right is None:
                    said.append(f"its spine spec track x {_num(own)} is over the strap")
            for side, x in (("left", left), ("right", right)):
                if x is None:
                    if own is None:
                        said.append(f"{side}: no signal track")
                    continue
                rect = (x - v.width / 2, sy1, sx1, sy2) if side == "left" else \
                    (sx2, sy1, x + v.width / 2, sy2)
                length = rect[2] - rect[0]
                if length > t.max_ext + TOL:
                    said.append(f"{side}: the signal track at x {_num(x)} is "
                                f"{_num(round(length, 6))} away, over {_num(t.max_ext)}")
                    continue
                if grid.fence is not None and not grid.fence.holds(rect):
                    said.append(f"{side}: the signal track at x {_num(x)} is outside the "
                                f"design boundary")
                    continue
                if any(n != row["name"] and layer == t.strap_layer and r != t.strap
                       and _gap(rect, r) < t.strap_spacing - TOL
                       for n, layer, r in others + shapes):
                    said.append(f"{side}: blocked (another net within "
                                f"{_num(t.strap_spacing)})")
                    continue
                pieces.append(rect)
                shapes.append((row["name"], t.strap_layer, rect))
                x1, x2 = min(x1, rect[0]), max(x2, rect[2])
                said.append(f"{_num(round(length, 6))} {side} to x {_num(x)}")
            pins[t.inst, t.pin] = (row["name"], pieces, (x1, x2))
            lines.append(f"{t.inst}/{t.pin} strap {t.strap_seq}: {', '.join(said)}")
    if lines:
        info(f"  pin routes extended to the signal tracks ({v.name}): " + "; ".join(lines),
             out)
    return {"pins": pins, "shapes": shapes}


def _spec_pin_tracks(db, nets):
    """{(inst, pin): x} of the signal pins of the nets' spine cells that the
    spine spec gives a track on a vertical stretch: the input pin its input
    track, the output pin its output track."""
    from core import spine_tracks
    from core.commands.write_def import cell_pin
    found = {}
    for spine in {s["name"]: s for s, _ in nets if s is not None}:
        for inst, (st, cin, cout, _, _) in spine_tracks.placed(db, spine).items():
            if not st.vertical:
                continue
            ref = db.inst_row(inst)["ref_cell"]
            for direction, x in (("in", cin), ("out", cout)):
                pin = cell_pin(db, ref, direction)
                if pin and x is not None:
                    found[inst, pin] = x
    return found


def route(db, grid, spine, row, via_weight, out, shield=None, pre=None, compact=False):
    """Route one net; store its wires. Returns True when it has wires.
    compact (route_track -compact): on the tracks nearest its pins, see
    _search."""
    name = row["name"]
    h, v = grid.h, grid.v
    pre = pre or {"pins": {}, "shapes": []}
    terms = _net_terminals(db, spine, row, pre, grid)
    for t in terms:
        if t.kind == "pin":
            warn(NOT_PINNED, f"{name}: route_pin is not done on {t.inst} (pin {t.pin}); the "
                 f"route ends at the track crossing nearest the pin, not connected", out)

    for t in terms:              # past the last track (outside the die): snapped to it
        tx1, ty1, tx2, ty2 = t.box
        far = [f"{h.name} y {_num(grid.all_ys[0])} .. {_num(grid.all_ys[-1])}"
               for lo, hi in ((ty1, ty2),) if hi < grid.all_ys[0] or lo > grid.all_ys[-1]]
        far += [f"{v.name} x {_num(grid.all_xs[0])} .. {_num(grid.all_xs[-1])}"
                for lo, hi in ((tx1, tx2),) if hi < grid.all_xs[0] or lo > grid.all_xs[-1]]
        if far:
            warn(OFF_TRACKS, f"{name}: {t.label} is beyond the signal tracks "
                 f"({'; '.join(far)}); its end is taken from the last track", out)
    fixed = [r for r in db.fixed_wire_rows(name) if r["kind"] == "wire"]
    terms += [FixedWire(r, name) for r in fixed]     # kept; the rest of the net joins them
    shapes = _obstacles(db, name) + [(layer, r) for n, layer, r in
                                     pre["shapes"] + pre.get("reserved", []) if n != name]
    # the grid: signal tracks around every terminal, MARGIN tracks more each side
    anchor = pre.get("anchor", {}).get(spine["id"], ()) if spine is not None else ()
    lanes = _spec_lanes(db, grid, spine, row, pre) if spine is not None else None
    lee = _search(grid, terms, shapes, via_weight, compact, anchor, lanes)
    xs, ys = lee.xs, lee.ys
    tree, edges, reached, taps = lee.tree, lee.edges, lee.reached, lee.taps
    for k in lee.apart:
        warn(FIXED_APART, f"{name}: fixed wire {terms[k].label} is not on a signal track of {h.name} or "
             f"{v.name} (or every track crossing on it is blocked): the route does not join "
             f"it; it stays as it is", out)
    if lee.stop is not None:
        warn(lee.stop[0], f"{name}: {lee.stop[1]}", out)
        return False
    if lee.todo:
        warn(NO_PATH, f"{name}: no path {'inside the design boundary ' if lee.fenced else ''}"
             f"to {', '.join(terms[k].label for k in lee.todo)}; they are not routed", out)
    if tree is None:
        return False

    spans = {H: {}, V: {}}       # layer -> track index -> [(lo, hi)] (extended)
    crosses, extensions = [], []
    for node in tree:            # every node holds a box, so wire ends overlap fully
        if node not in lee.fixed_nodes:          # a fixed wire is there already
            _node_span(spans, node, xs, ys, h, v)
    for a, b in edges:
        if a[0] != b[0]:         # layer change at one crossing: a box of v x h width
            _, i, j = a
            crosses.append((f"{h.name}/{v.name}", _box(xs[i], ys[j], v.width, h.width)))
            continue
        layer, i, j = a
        _, i2, j2 = b
        if layer == H:
            lo, hi = sorted((xs[i], xs[i2]))
            spans[H].setdefault(j, []).append((lo - v.width / 2, hi + v.width / 2))
        else:
            lo, hi = sorted((ys[j], ys[j2]))
            spans[V].setdefault(i, []).append((lo - h.width / 2, hi + h.width / 2))
    for k, t in enumerate(terms):
        if reached.get(k) is None or t.kind != "strap":
            continue
        sx1, sy1, sx2, sy2 = t.strap
        for _, i, j in sorted(taps[k]):  # a vertical wire from the crossing over the whole strap
            spans[V].setdefault(i, []).append((min(ys[j] - h.width / 2, sy1),
                                               max(ys[j] + h.width / 2, sy2)))
            crosses.append((f"{v.name}/{t.strap_layer}",
                            (xs[i] - v.width / 2, sy1, xs[i] + v.width / 2, sy2)))
    for t in terms:              # the pin routes' extensions (step a) go with the net
        extensions += [("extension", t.strap_layer, r) for r in t.pieces]

    wires = []
    for j, found in sorted(spans[H].items()):
        for lo, hi in _merge(found):
            wires.append(("wire", h.name, (lo, ys[j] - h.width / 2, hi, ys[j] + h.width / 2)))
    for i, found in sorted(spans[V].items()):
        for lo, hi in _merge(found):
            wires.append(("wire", v.name, (xs[i] - v.width / 2, lo, xs[i] + v.width / 2, hi)))
    held = [(r["layer"], tuple(float(c) for c in r["rect"].split())) for r in fixed]
    wires = [w for w in wires if not any(          # a piece on a fixed wire is there already
        layer == w[1] and _within(w[2], r) for layer, r in held)]
    wires += extensions
    wires += [("cross", layer, r) for layer, r in crosses]
    drops = sum(abs(ys[j] - (t.strap[1] + t.strap[3]) / 2)
                for k, t in enumerate(terms) if t.kind == "strap" and reached.get(k)
                for _, _, j in taps[k])
    for k, t in enumerate(terms):
        if t.kind != "port" or reached.get(k) is None:
            continue
        # connected where a wire lies on a shape of the port, on its layer
        t.joined = next((layer for layer, box in t.shapes for w in wires
                         if w[0] == "wire" and w[1] == layer and _gap(w[2], box) < TOL), None)
        if t.joined is None:
            _, i, j = reached[k]
            off = abs(xs[i] - t.point[0]) + abs(ys[j] - t.point[1])
            where = ", ".join(dict.fromkeys(layer for layer, _ in t.shapes)) or "no layer"
            warn(OFF_PORT, f"{name}: the route ends at the track crossing nearest {t.label}, "
                 f"{{{_num(xs[i])} {_num(ys[j])}}} on {h.name} and {v.name}, "
                 f"{_num(round(off, 3))} um from the centre of the port (shapes on {where}); "
                 f"it is not connected to the port: {grid.cmd} makes no wire or via down to "
                 f"a port", out)
    _report(name, terms, reached, edges, xs, ys, wires, drops, out, taps)
    if shield:
        stacks = []              # strap stacks of the cells, so shields cover them
        for inst in dict.fromkeys(t.inst for t in terms if t.kind == "strap"):
            rects = [base_rect(r) for r in db.strap_rows(inst)]       # as route_pin made them
            reach = max((r["max_extension"] or 0.0) for r in db.strap_rows(inst))
            stacks.append((min(r[0] for r in rects) - reach, max(r[2] for r in rects) + reach,
                           min(r[1] for r in rects), max(r[3] for r in rects)))
        electric = _ia_shapes(db, name) + [s for s in pre["shapes"] if s[0] != name]
        kept = [("wire", r["layer"], tuple(float(c) for c in r["rect"].split())) for r in fixed]
        shields, cut, no_power, short, fenced = _shields(
            wires + kept, electric, grid, shield, stacks,
            root_attrs.get(db, "ignore_shield_less_than_routing_length"))
        wires += shields
        _report_short(short, db, out)
        if no_power:
            warn(NO_POWER, f"{name}: no shield where the next track is not a power track: "
                 f"{'; '.join(no_power)}", out)
        for net in dict.fromkeys(w[3] for w in shields):
            mine = [w for w in shields if w[3] == net]
            info(f"    shield {net}: {len(mine)} wire(s), "
                 f"{_num(round(sum(_along(w[2]) for w in mine), 3))} um", out)
        if cut:
            info(f"    shields cut over {_num(round(cut, 3))} um where they would come "
                 f"closer than the rule spacing to another shape", out)
        _report_fenced(fenced, out)
        wires += _power_links(db, name, terms, wires, grid, out,
                              [s for s in pre["shapes"] if s[0] != name])
    renamed = []                 # straps and pin wires now shorted to the net: named
    for k, t in enumerate(terms):        # first, so the route lengthens its own straps
        if t.kind == "strap" and reached.get(k) is not None:
            db.set_pin_net(t.inst, t.pin, t.strap_seq, name)
            renamed.append(f"strap:{t.inst}/{t.strap_seq} pin_wire:{t.inst}/{t.pin}")
    old = db.set_net_wires(name, [(w[0], w[1], " ".join(_num(round(c, 6)) for c in w[2]))
                                  + tuple(w[3:]) for w in wires])
    if old:
        warn(REPLACED, f"{name}: replaced its {old} old wires and crossings", out)
    if renamed:
        info(f"    now net {name}: {'  '.join(renamed)}", out)
    return True


def _spec_lanes(db, grid, spine, row, pre):
    """The tracks the spine spec gives this net (track: {input, output},
    core/spine_tracks.py), or None: SimpleNamespace(stretches, own {stretch
    index: set of coordinates}, out {stretch index: coordinate}, ks). Its
    driver's output track and its loads' input tracks, by number: on every
    stretch of the spine, those tracks."""
    from core import spine_tracks
    cache = pre.setdefault("lanes", {})
    if spine["id"] not in cache:
        cells = spine_tracks.placed(db, spine["name"])
        cache[spine["id"]] = (spine_tracks.stretches(db, spine["name"]), cells,
                              _exits(db, grid, spine, cells))
    found, cells, exits = cache[spine["id"]]
    if not found or row["driver"] not in cells:
        return None
    kout = cells[row["driver"]][4]
    kins = {cells[n][3] for n in row["loads"].split() if n in cells and cells[n][3]}
    ks = ({kout} if kout else set()) | kins
    if not ks:
        return None
    own = {s.index: {c for c in (s.coord(k) for k in ks) if c is not None} for s in found}
    out = {s.index: s.coord(kout) for s in found} if kout else {}
    return SimpleNamespace(stretches=found, own=own, out=out, ks=sorted(ks), kout=kout,
                           exits=[e for e in exits if e[3] != row["name"]])


def _exits(db, grid, spine, cells):
    """[(x, y1, y2, net)]: where a cell's input and output share a spec track,
    the piece of that track from its input strap (not included) to the
    crossing on the outer side of its output strap: its output net's, no
    other net may lie there (the net coming in stops at the input)."""
    from core.commands.write_def import cell_pin
    drives = {r["driver"]: r["name"] for r in db.spine_net_rows(spine["id"])}
    ys = grid.all_ys
    found = []
    for inst, (st, cin, cout, _, _) in cells.items():
        if not st.vertical or cin is None or cout is None or abs(cin - cout) > TOL:
            continue
        ref = db.inst_row(inst)["ref_cell"]
        centre = {}
        for direction in ("in", "out"):
            w = db.pin_wire_row(inst, cell_pin(db, ref, direction) or "")
            s = db.strap_row(inst, w["strap"]) if w is not None else None
            if s is not None:
                r = [float(c) for c in s["rect"].split()]
                centre[direction] = (r[1] + r[3]) / 2
        if len(centre) < 2 or inst not in drives:
            continue
        a, y = centre["in"], centre["out"]
        up = 1 if y > a else -1
        beyond = [t for t in ys if (t - y) * up > TOL]
        outer = min(beyond, key=lambda t: abs(t - y)) if beyond else y
        found.append((cin, min(a, outer), max(a, outer), drives[inst]))
    return found


def _search(grid, terms, shapes, via_weight, compact=False, anchor=(), lanes=None):
    """One Lee run for a net, on the signal tracks around its terminals: the
    tree grown from the driver to the nearest unreached terminal, then the
    next. Returns xs, ys (the tracks of the run), tree, edges, reached
    {terminal: its node}, taps {terminal: the nodes its strap is crossed at},
    todo (the terminals not reached), stop ((message number, text) when a
    terminal has no crossing to end on) and fenced (only the design boundary
    keeps the ones in todo away).
    compact: the net keeps to the tracks of its pins. A wire on a track
    beyond them costs OUT_WEIGHT more of its length for every track further
    out, so a long run comes back to the nearest free track after it has
    passed what blocks it. And the driver's strap is part of the tree: a
    branch may leave it on any signal track it covers (the other side of the
    cell), not only where the first branch left it; another place costs one
    layer change (its crossing box), so it is taken only when it saves wire.
    anchor ({(H | V, track)}: the stub tracks of the net's spine): of tracks
    that are equal otherwise, the one nearest a stub track is taken, so the
    nets lie against the stubs and the free tracks are the outer ones."""
    h, v = grid.h, grid.v
    xs = _window(grid.all_xs, min(t.box[0] for t in terms), max(t.box[2] for t in terms))
    ys = _window(grid.all_ys, min(t.box[1] for t in terms), max(t.box[3] for t in terms))
    blocked = _blocked(shapes, xs, ys, h, v)
    # the design boundary: a hard limit of every node, step and wire
    inside = Inside(grid.fence, xs, ys, h, v) if grid.fence is not None else None
    found = SimpleNamespace(xs=xs, ys=ys, tree=None, edges=set(),
                            reached={0: None}, taps={}, todo=set(range(1, len(terms))),
                            stop=None, fenced=False, fixed_nodes=set(), apart=[])
    if lanes is not None:        # the spine spec's tracks: none other along the spine
        blocked = set(blocked) | _off_lanes(lanes, xs, ys, h, v)
        for x, y1, y2, _ in lanes.exits:     # another cell's way out on its own track
            blocked |= {(V, i, j) for i, xi in enumerate(xs) if abs(xi - x) < TOL
                        for j, yj in enumerate(ys) if y1 + TOL < yj <= y2 + TOL}
    targets = [t.nodes(xs, ys, h, v, shapes, inside) for t in terms]
    for k, (t, nodes) in enumerate(zip(terms, targets)):
        if t.kind == "fixed":            # a fixed wire off the tracks is left apart
            for n in [n for n in nodes if n in blocked]:
                del nodes[n]
            if not nodes:
                found.apart.append(k)
                found.todo.discard(k)
            continue
        if not nodes and inside is not None:
            found.stop = (OUTSIDE, f"{t.label} is outside the design boundary (no track "
                          f"crossing at it holds a wire inside it); not routed")
            return found
        for n in [n for n in nodes if n in blocked]:
            del nodes[n]
        if not nodes:
            what = f"every track crossing at {t.label} is blocked" if lanes is None else \
                f"no track crossing at {t.label} on its spine spec track (track " \
                f"{', '.join(map(str, lanes.ks))}) is free and in reach"
            found.stop = (NO_PATH, f"{what}; not routed")
            return found

    weights = None
    if compact:              # the cost of a micron of wire on each track
        ends = [n for nodes in targets for n in nodes]
        weights = (_out_weights(ys, [j for _, _, j in ends], [c for a, c in anchor if a == H]),
                   _out_weights(xs, [i for _, i, _ in ends], [c for a, c in anchor if a == V]))

    if lanes is not None and lanes.out:      # on the output track as long as it can: the
        outs = set(lanes.out.values())           # change of track comes near the load
        weights = ([1.0] * len(ys), [1.0 if any(abs(x - c) < TOL for c in outs if c)
                                     else 1.01 for x in xs])

    # Lee: grow the tree from the driver to the nearest unreached terminal
    tree, reached, todo = None, found.reached, found.todo
    while todo:
        sources = tree if tree is not None else targets[0]
        if compact and tree is not None and terms[0].kind == "strap":
            sources = {n: 0.0 if n in tree else via_weight for n in tree.union(targets[0])}
        rest = {k: targets[k] for k in todo}
        hit = _lee(sources, rest, xs, ys, blocked, via_weight, inside, weights)
        if hit is None:
            found.fenced = inside is not None and \
                _lee(sources, rest, xs, ys, blocked, via_weight, None, weights) is not None
            break
        k, path, _ = hit
        todo.discard(k)
        if tree is None:
            tree = found.tree = set()
            reached[0] = path[0]
        reached[k] = path[-1]
        tree.update(path)
        if terms[k].kind == "fixed":     # the whole wire is the net's now: branch anywhere
            tree.update(targets[k])
            found.fixed_nodes.update(targets[k])
        found.edges.update(zip(path, path[1:]))
        if compact and path[0] in targets[0]:    # where the branch leaves the driver's strap
            found.taps.setdefault(0, set()).add(path[0])
    for k, node in reached.items():
        if node is not None:
            found.taps.setdefault(k, set()).add(node)
    return found


def _off_lanes(lanes, xs, ys, h, v):
    """The nodes along the spine off the net's spec tracks: on a vertical
    stretch the vertical-layer crossings off its tracks, on a horizontal one
    the horizontal-layer ones (hops across on the other layer stay free)."""
    from core import spine_tracks
    off = set()
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            s = spine_tracks.stretch_at(lanes.stretches, x, y)
            if s is None or s.layer not in (h.name, v.name):
                continue
            own = lanes.own.get(s.index, ())
            if s.vertical and not any(abs(x - c) < TOL for c in own):
                off.add((V, i, j))
            elif not s.vertical and not any(abs(y - c) < TOL for c in own):
                off.add((H, i, j))
    return off


def _out_weights(tracks, used, anchor=()):
    """Per track index: 1 on the tracks from the lowest to the highest of
    used (the indices of the tracks of the net's pins), OUT_WEIGHT more for
    every track further out; and TIE more for every track away from the
    nearest of anchor (track coordinates), to choose between equal tracks."""
    lo, hi = min(used), max(used)
    near = [bisect.bisect_left(tracks, c - TOL) for c in anchor]
    return [1.0 + OUT_WEIGHT * max(lo - k, 0, k - hi)
            + TIE * min((abs(k - n) for n in near), default=0) for k in range(len(tracks))]


def _report_short(short, db, out):
    if short:
        info(f"    not shielded: {len(short)} wire piece(s) shorter than "
             f"{_num(root_attrs.get(db, 'ignore_shield_less_than_routing_length'))} um "
             f"(ignore_shield_less_than_routing_length): "
             + ", ".join(f"{layer} {_num(round(n, 3))}" for layer, n in short), out)


def _report_fenced(fenced, out):
    if fenced:
        info(f"    shields cut over {_num(round(fenced, 3))} um where they would leave the "
             f"design boundary", out)


def _along(r):
    return max(r[2] - r[0], r[3] - r[1])


def _shields(wires, shapes, grid, nets, stacks=(), min_length=0.0):
    # shapes: (electrical net, layer, rect) of everything else on the layers
    """([("shield", layer, rect, net)], length cut, tracks with no power net,
    wires left unshielded, length cut at the design boundary).
    Each wire of the net at least min_length long (root attribute
    ignore_shield_less_than_routing_length) gets one shield on each side, on the nearest track
    at least width + spacing from its centre, over its span. Its net is the
    track's net from the layer's track assignment (no shield on a signal or
    blank track); with no assignment, nets[0] left / above and nets[1] right /
    below. A vertical shield also runs over the
    whole strap stack of a cell at its wire (stacks: x1, x2 with the straps'
    reach, y1, y2), so every power strap of the cell can join one. Cut where
    another shape on the layer (other nets, straps, this net's wires, a shield
    of another net) is within spacing, and where it would leave the design
    boundary (grid.fence)."""
    h, v = grid.h, grid.v
    own = [(layer, r) for kind, layer, r, *_ in wires if kind != "cross"]
    placed = []                  # (net, layer, rect)
    cut = fenced = 0.0
    no_power = []
    short = []                   # (layer, length) of the wires too short to shield
    for kind, layer, r, *_ in wires:
        if kind != "wire":
            continue
        if _along(r) < min_length - TOL:
            short.append((layer, _along(r)))
            continue
        horizontal = layer == h.name
        lay = h if horizontal else v
        tracks = grid.raw_ys if horizontal else grid.raw_xs
        if not tracks:
            continue
        c = (r[1] + r[3]) / 2 if horizontal else (r[0] + r[2]) / 2
        lo, hi = (r[0], r[2]) if horizontal else (r[1], r[3])
        need = lay.width + lay.spacing
        sides = ((1, nets[0]), (-1, nets[1])) if horizontal else ((-1, nets[0]), (1, nets[1]))
        for side, net in sides:
            if side > 0:
                j = bisect.bisect_left(tracks, c + need - TOL)
                t = tracks[j] if j < len(tracks) else None
            else:
                j = bisect.bisect_right(tracks, c - need + TOL) - 1
                t = tracks[j] if j >= 0 else None
            if t is None:
                continue
            assigned = grid.track_net(layer, tracks, j)
            if assigned is not None:     # follow the track: VDD_SOC or VSS track
                if assigned in ("-", "NA"):
                    no_power.append(f"{layer} {'x' if not horizontal else 'y'} {_num(t)} "
                                    f"({'signal' if assigned == '-' else 'blank'})")
                    continue
                net = assigned
            lo, hi = (r[0], r[2]) if horizontal else (r[1], r[3])
            if not horizontal:           # over the strap stacks this wire reaches
                for x1, x2, y1, y2 in stacks:
                    if x1 - TOL <= t <= x2 + TOL and y1 <= hi + TOL and y2 >= lo - TOL:
                        lo, hi = min(lo, y1), max(hi, y2)
            a1, a2 = t - lay.width / 2, t + lay.width / 2       # across the shield
            runs = [(lo, hi)]            # what of it is inside the design boundary
            if grid.fence is not None:
                runs = grid.fence.spans(lo, hi, a1, a2, horizontal)
                fenced += (hi - lo) - sum(p2 - p1 for p1, p2 in runs)
            blocked = []
            # shapes of the shield's own power net may touch it (same net)
            others = [(lyr, rr) for n, lyr, rr in shapes if n != net] + own + \
                [(lyr, rr) for n, lyr, rr in placed if n != net]
            for olayer, o in others:
                if olayer != layer:
                    continue
                o_a1, o_a2, o_l1, o_l2 = ((o[1], o[3], o[0], o[2]) if horizontal
                                          else (o[0], o[2], o[1], o[3]))
                if max(o_a1 - a2, a1 - o_a2) < lay.spacing - TOL and \
                        o_l2 + lay.spacing > lo and o_l1 - lay.spacing < hi:
                    blocked.append((o_l1 - lay.spacing, o_l2 + lay.spacing))
            pieces = []
            for lo, hi in runs:
                start = lo
                for b1, b2 in _merge(blocked):
                    if b1 > start:
                        pieces.append((start, min(b1, hi)))
                    start = max(start, b2)
                if start < hi:
                    pieces.append((start, hi))
            pieces = [(p1, p2) for p1, p2 in pieces if p2 > p1]
            kept = [(p1, p2) for p1, p2 in pieces if p2 - p1 >= lay.width - TOL]
            cut += sum(p2 - p1 for p1, p2 in runs) - sum(p2 - p1 for p1, p2 in kept)
            for p1, p2 in kept:
                rect = (p1, a1, p2, a2) if horizontal else (a1, p1, a2, p2)
                placed.append((net, layer, rect))
    merged = {}                  # same net, layer and track: one wire per run
    for net, layer, rect in placed:
        horizontal = layer == h.name
        key = (net, layer, (rect[1], rect[3]) if horizontal else (rect[0], rect[2]))
        merged.setdefault(key, []).append((rect[0], rect[2]) if horizontal else (rect[1], rect[3]))
    shields = []
    for (net, layer, (a1, a2)), spans in merged.items():
        for p1, p2 in _merge(spans):
            rect = (p1, a1, p2, a2) if layer == h.name else (a1, p1, a2, p2)
            shields.append(("shield", layer, rect, net))
    return shields, cut, no_power, short, fenced


def _ia_shapes(db, net):
    """(electrical net, layer, rect) of every shape, on any layer, another
    route of net must keep clear of: straps, pin wires, and the other nets' wires, extensions,
    shields and shield extensions (shields under their power net)."""
    rect = lambda text: tuple(float(c) for c in text.split())
    found = [(r["net"], r["layer"], rect(r["rect"])) for r in db.strap_rows()]
    found += [(r["net"], r["layer"], rect(r["rect"])) for r in db.pin_wire_rows()]
    own = {net, stub_owner(net)} if net else set()     # its stub's are its own
    found += [(r["shield_net"] or r["net"], r["layer"], rect(r["rect"]))
              for r in db.net_wire_rows() if r["net"] not in own and r["kind"] != "cross"]
    return found


def _power_links(db, name, terms, wires, grid, out, pending=()):
    """Connect the power straps of the net's cells to its shields: for each
    VDD_SOC / VSS strap of a cell the route reached through its straps, the
    vertical shield of that net needing the shortest extension (none when the
    shield already runs over the strap) within the strap's max_extension, and
    clear of other nets' shapes on the strap layer by the rule spacing.
    Returns [("shield_ext" | "cross", layer, rect, power net)]."""
    v = grid.v
    shields = [(w[3], w[2]) for w in wires if w[0] == "shield" and w[1] == v.name]
    nets = {n for n, _ in shields}
    others = _ia_shapes(db, name) + list(pending) + \
        [(w[3] if w[0] == "shield" else name, w[1], w[2]) for w in wires if w[0] != "cross"]
    links, lines, missed, linked = [], [], [], set()
    insts = list(dict.fromkeys(t.inst for t in terms if t.kind == "strap"))
    joined = _joined_straps(db, name)
    already = []
    for inst in insts:
        groups = {}              # power net -> its straps on this cell
        for strap in db.strap_rows(inst):
            if strap["net"] in nets and (inst, strap["seq"]) in joined:
                already.append(f"strap:{inst}/{strap['seq']} ({joined[inst, strap['seq']]})")
            elif strap["net"] in nets:
                groups.setdefault(strap["net"], []).append(strap)
        for net, straps in groups.items():
            straps = [dict(s, spacing=strap_spacing(db, s["layer"], _height(s["rect"])))
                      for s in straps]
            options = [_strap_options(strap, shields, others, grid) for strap in straps]
            pick = _assign(options)
            for strap, choice in zip(straps, pick):
                label = f"strap:{inst}/{strap['seq']} {strap['net']}"
                if choice is None:
                    missed.append(label)
                    continue
                length, ext, box, _ = choice
                sx2 = float(strap["rect"].split()[2])
                if ext is not None:
                    links.append(("shield_ext", strap["layer"], ext, strap["net"]))
                    others.append((strap["net"], strap["layer"], ext))
                links.append(("cross", f"{v.name}/{strap['layer']}", box, strap["net"]))
                linked.add((inst, strap["seq"]))
                side = f" (shield x {_num(choice[3])} over it)" if ext is None else \
                    f", extended {_num(round(length, 6))} {'right' if ext[0] == sx2 else 'left'}" \
                    f" to the shield at x {_num(choice[3])}"
                lines.append(f"{label}{side}")
    if lines:
        info(f"    power straps to shields: {'; '.join(lines)}", out)
    if already:
        info(f"    power straps already joined by another net: {'; '.join(already)}", out)
    if missed:
        info(f"    power straps not reaching a shield of their net: {'; '.join(missed)}", out)
    return links


def _strap_options(strap, shields, others, grid):
    """[(extension length, extension rect or None, crossing box, shield track)]
    of the shields of the strap's net it can join: one running over it, or one
    beside it within its max_extension, the extension clear of other nets'
    shapes on its layer by the rule spacing and inside the design boundary."""
    v = grid.v
    sx1, sy1, sx2, sy2 = base_rect(strap)    # another net's stretch of it is not this link's
    reach = strap["max_extension"] or 0.0
    spacing = strap["spacing"]
    found = []
    for k, (net, (x1, y1, x2, y2)) in enumerate(shields):
        if net != strap["net"] or y1 > sy1 + TOL or y2 < sy2 - TOL:
            continue                 # another net, or not across the whole strap
        if x1 >= sx1 - TOL and x2 <= sx2 + TOL:
            ext = None               # the shield runs over the strap
        elif x2 > sx2:
            ext = (sx2, sy1, x2, sy2)
        else:
            ext = (x1, sy1, sx1, sy2)
        length = 0.0 if ext is None else ext[2] - ext[0]
        if length > reach + TOL:
            continue
        if ext is not None and grid.fence is not None and not grid.fence.holds(ext):
            continue                 # the extension would leave the design boundary
        if ext is not None and any(n != strap["net"] and layer == strap["layer"]
                                   and _gap(ext, r) < spacing - TOL for n, layer, r in others):
            continue
        found.append((length, ext, (x1, sy1, x2, sy2), round((x1 + x2) / 2, 6)))
    return found


def _assign(options):
    """One option (or None) per strap of a net on one cell: every strap that
    can be joined is, on as many different shield tracks as possible (two
    straps: one left, one right), then with the least total extension."""
    best = None
    for combo in itertools.product(*[opts or [None] for opts in options]):
        used = [c for c in combo if c is not None]
        key = (-len(used), -len({c[3] for c in used}), sum(c[0] for c in used))
        if best is None or key < best[0]:
            best = (key, combo)
    return list(best[1])


def strap_spacing(db, layer, width):
    """The spacing a strap extension keeps to other nets' shapes: the strap
    layer's tech spacing for a wire of the strap's width. Straps are drawn
    by the pin routing spec, not the net's route rule, so the rule spacing
    (often wider) does not apply to them."""
    row = db.layer_row(layer)
    return (tech_spacing(db, row, width)[0] or 0.0) if row is not None else 0.0


def _height(rect):
    y1, y2 = (float(c) for c in rect.split()[1::2])
    return y2 - y1


def _joined_straps(db, net):
    """{(inst, strap seq): net} of the power straps that a routed net other
    than net has joined to one of its shields."""
    found = {}
    for r in db.net_wire_rows():
        if r["kind"] != "cross" or not r["shield_net"] or r["net"] == net:
            continue
        x1, y1, x2, y2 = (float(c) for c in r["rect"].split())
        for s in db.strap_rows():
            if s["net"] != r["shield_net"]:
                continue
            sx1, sy1, sx2, sy2 = (float(c) for c in s["rect"].split())
            reach = (s["max_extension"] or 0.0) + TOL
            if abs(y1 - sy1) < TOL and abs(y2 - sy2) < TOL and x1 >= sx1 - reach \
                    and x2 <= sx2 + reach:
                found.setdefault((s["inst"], s["seq"]), r["net"])
    return found


def power_pins(db, insts, nets):
    """[(inst, pin, strap seq, connected)] of the power pins (pin wires on a
    shield net) of insts: connected when a shield of that net crosses their
    strap or its extension, in any routed net."""
    crosses = [(r["shield_net"], tuple(float(c) for c in r["rect"].split()))
               for r in db.net_wire_rows() if r["kind"] == "cross" and r["shield_net"]]
    found = []
    for inst in insts:
        for w in db.pin_wire_rows(inst):
            if w["net"] not in nets:
                continue
            s = db.strap_row(inst, w["strap"])
            sx1, sy1, sx2, sy2 = (float(c) for c in s["rect"].split())
            reach = (s["max_extension"] or 0.0) + TOL
            ok = any(n == s["net"] and abs(r[1] - sy1) < TOL and abs(r[3] - sy2) < TOL
                     and r[0] >= sx1 - reach and r[2] <= sx2 + reach for n, r in crosses)
            found.append((inst, w["pin"], w["strap"], ok))
    return found


def _window(values, lo, hi, margin=MARGIN):
    """values within [lo, hi] plus margin on each side."""
    a = max(0, bisect.bisect_left(values, lo - TOL) - margin)
    b = min(len(values), bisect.bisect_right(values, hi + TOL) + margin)
    if a >= b:                   # nothing inside: the nearest ones
        k = min(max(0, a), len(values) - 1)
        a, b = max(0, k - margin), min(len(values), k + margin + 1)
    return values[a:b]


def _box(x, y, w, h):
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def _node_span(spans, node, xs, ys, h, v):
    layer, i, j = node
    if layer == H:
        spans[H].setdefault(j, []).append((xs[i] - v.width / 2, xs[i] + v.width / 2))
    else:
        spans[V].setdefault(i, []).append((ys[j] - h.width / 2, ys[j] + h.width / 2))


def _merge(spans):
    merged = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1] + TOL:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


class Terminal:
    """Where a route must end: a strap (route_pin done), a pin, a stub tap, or
    a port of the design."""

    def __init__(self, kind, label, box, inst="", pin="", strap=None, strap_layer="",
                 point=None, max_ext=0.0, strap_seq=None, strap_spacing=0.0, pieces=(),
                 span=None, routed=False, shapes=()):
        self.kind, self.label, self.box = kind, label, box
        self.routed = routed                 # a stub with its wire (route_final_stub)
        self.shapes = list(shapes)           # of a port: [(layer, box)]
        self.joined = None                   # a port: the layer a wire lies on it on
        self.inst, self.pin, self.strap, self.strap_layer = inst, pin, strap, strap_layer
        self.point, self.max_ext, self.strap_seq = point, max_ext, strap_seq
        self.strap_spacing = strap_spacing   # tech spacing an extension keeps
        self.pieces = list(pieces)           # its pin route's extensions (step a)
        self.span = span or (strap and (strap[0], strap[2]))   # x of the extended strap
        self.outer = 0                       # a strap: the side it is reached from
        self.keep_x = None                   # ... and the track it is best reached on

    def nodes(self, xs, ys, h, v, shapes, inside=None):
        """{grid node: extra cost} of the nodes that reach it. On a strap: the
        vertical-layer crossings at the track nearest the strap centre, on
        every signal track the extended strap covers; for a strap of a
        cell with another signal strap (_outer_side), also those of the
        track on its outer side (away from the other) when that is not the
        nearest, dearer by how much longer its drop to the strap centre is,
        so a route can leave or reach it there (a straight net then passes
        the cell on one track); and KEEP signal-track pitches
        dearer off the track a route already crosses the cell's other
        signal strap on (worth a jog of up to that much). Else the crossing nearest the point, on either layer. With inside (the design boundary
        on this grid) only crossings whose wire to the terminal stays inside
        it: on a strap the wire from the track over the whole strap, the
        track on the other side of the strap centre when the nearest has
        none; else the nearest of the crossings round the point that is
        inside. Empty when there is none."""
        if self.kind == "strap":
            c = (self.strap[1] + self.strap[3]) / 2
            k = bisect.bisect_left(ys, c)
            near = sorted(range(max(0, k - 1), min(len(ys), k + 1)), key=lambda j: abs(ys[j] - c))
            pitch = min((b - a for a, b in zip(xs, xs[1:])), default=0.0)
            keep = lambda n: 0.0 if self.keep_x is None or abs(xs[n[1]] - self.keep_x) < TOL \
                else KEEP * pitch            # off the track the cell is crossed on
            if self.outer and near:      # the nearest track, and its outer side's if other
                found, least = {}, abs(ys[near[0]] - c)
                for j in near:
                    if j == near[0] or (ys[j] - c) * self.outer > 0:
                        found.update({n: abs(ys[j] - c) - least + keep(n)
                                      for n in self._at(j, xs, ys, h, v, inside)})
                return found
            for j in near:
                found = self._at(j, xs, ys, h, v, inside)
                if found or inside is None:
                    return {n: keep(n) for n in found}
            return {}
        return self._point_nodes(xs, ys, inside)

    def _at(self, j, xs, ys, h, v, inside):
        """{node: 0} of the crossings on horizontal track j over the strap."""
        sy1, sy2 = self.strap[1], self.strap[3]
        x1, x2 = self.span
        drop = (min(ys[j] - h.width / 2, sy1), max(ys[j] + h.width / 2, sy2))
        return {(V, i, j): 0.0 for i, x in enumerate(xs)
                if x1 + v.width / 2 - TOL <= x <= x2 - v.width / 2 + TOL
                and (inside is None or (inside.node(i, j) and inside.fence.holds(
                    (x - v.width / 2, drop[0], x + v.width / 2, drop[1]))))}

    def _point_nodes(self, xs, ys, inside):
        round_it = lambda values, c: range(max(0, bisect.bisect_left(values, c) - 1),
                                           min(len(values), bisect.bisect_left(values, c) + 1))
        for _, i, j in sorted((abs(xs[i] - self.point[0]) + abs(ys[j] - self.point[1]), i, j)
                              for i in round_it(xs, self.point[0])
                              for j in round_it(ys, self.point[1])):
            if inside is None or inside.node(i, j):
                return {(H, i, j): 0.0, (V, i, j): 0.0}
        return {}


class FixedWire(Terminal):
    """A wire of the net fixed alone (set_db <net_wire> .route_status fixed).
    The route must reach it; then every track crossing on it is part of the
    tree. It is not drawn again: only the crossing boxes where the route
    joins it, and its shields (-shield), are made."""

    def __init__(self, row, net):
        rect = tuple(float(c) for c in row["rect"].split())
        super().__init__("fixed", f"net_wire:{net}/{row['seq']}", rect)
        self.layer = row["layer"]

    def nodes(self, xs, ys, h, v, shapes, inside=None):
        """{node: 0} of the track crossings on the wire's centre line, on its
        layer (H for the rule's horizontal layer, V for the vertical); empty
        when the centre line is not on a signal track of this grid."""
        x1, y1, x2, y2 = self.box
        if self.layer == h.name:
            js = [j for j, y in enumerate(ys) if abs(y - (y1 + y2) / 2) < TOL]
            found = {(H, i, j): 0.0 for j in js for i, x in enumerate(xs)
                     if x1 + v.width / 2 - TOL <= x <= x2 - v.width / 2 + TOL}
        elif self.layer == v.name:
            is_ = [i for i, x in enumerate(xs) if abs(x - (x1 + x2) / 2) < TOL]
            found = {(V, i, j): 0.0 for i in is_ for j, y in enumerate(ys)
                     if y1 + h.width / 2 - TOL <= y <= y2 - h.width / 2 + TOL}
        else:
            found = {}
        return {n: c for n, c in found.items() if inside is None or inside.node(n[1], n[2])}


def _within(a, b):
    """True when rect a lies inside rect b."""
    return b[0] - TOL <= a[0] and b[1] - TOL <= a[1] and a[2] <= b[2] + TOL and a[3] <= b[3] + TOL


def _gap(a, b):
    """Edge-to-edge distance of two rects (0 when they touch or overlap)."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5 if dx and dy else max(dx, dy)


def _terminal(db, spine, inst, direction, pre=None, pin=None):
    """The terminal of an instance's input ('in') or output ('out') pin, the
    first signal one of its cell unless pin names it, with its pin route's
    extensions from pre (step a) when given."""
    row = db.inst_row(inst)
    cell = db.lib_cell_row(row["ref_cell"])
    pins = [pin] if pin else \
        [p for p in db.lib_pin_names(cell["id"])
         if (db.lib_pin_row(cell["name"], p)["direction"] or "").lower().startswith(direction)
         and (db.lib_pin_row(cell["name"], p)["use"] or "signal").lower() == "signal"]
    if not pins:
        raise HtreeError(NO_NET, f"route_net: cell {cell['name']} of {inst} has no signal "
                         f"{direction}put pin")
    pin = pins[0]
    wire = db.pin_wire_row(inst, pin)
    strap = db.strap_row(inst, wire["strap"]) if wire is not None else None
    if strap is not None:
        rect = tuple(float(c) for c in strap["rect"].split())
        _, pieces, span = (pre or {}).get("pins", {}).get((inst, pin), (None, [], None))
        span = span or (rect[0], rect[2])
        term = Terminal("strap", f"{inst}/{pin} (strap {wire['strap']})",
                        (span[0], rect[1], span[1], rect[3]), inst, pin, rect, strap["layer"],
                        max_ext=strap["max_extension"] or 0.0, strap_seq=wire["strap"],
                        strap_spacing=strap_spacing(db, strap["layer"], rect[3] - rect[1]),
                        pieces=pieces, span=span)
        term.outer, term.keep_x = _outer_side(db, inst, cell, pin, rect)
        return term
    pts = [c for _, _, p in objects.pin_shapes(db, f"pin:{inst}/{pin}") for c in p]
    if pts:
        box = (min(pts[0::2]), min(pts[1::2]), max(pts[0::2]), max(pts[1::2]))
    else:                        # no shapes: the cell's bbox
        box = objects.inst_bbox(db, row)
    point = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    return Terminal("pin", f"{inst}/{pin}", box, inst, pin, point=point)


def _outer_side(db, inst, cell, pin, rect):
    """(side, x): side +1 when the strap of pin lies above the straps of the
    cell's other signal pins, -1 below them, 0 between them or with no other:
    the side a route reaches it from, so that the net of the other pin can
    leave its strap on the same track from the other side; x the track
    where a route already crosses the strap of the other signal pin (a
    straight net keeps that track through the cell), or None."""
    centre = (rect[1] + rect[3]) / 2
    others, keep = [], None
    for w in db.pin_wire_rows(inst):
        lp = db.lib_pin_row(cell["name"], w["pin"])
        if w["pin"] == pin or lp is None or (lp["use"] or "signal").lower() != "signal" or \
                not (lp["direction"] or "").lower().startswith(("in", "out")):
            continue
        s = db.strap_row(inst, w["strap"])
        if s is not None:
            r = [float(c) for c in s["rect"].split()]
            others.append((r[1] + r[3]) / 2)
            for c in db.net_wire_rows(s["net"]) if keep is None else ():
                b = [float(v) for v in c["rect"].split()]
                if c["kind"] == "cross" and abs(b[1] - r[1]) < TOL and abs(b[3] - r[3]) < TOL:
                    keep = round((b[0] + b[2]) / 2, 6)      # its crossing box on the strap
    if not others:
        return 0, keep
    return (1 if centre > max(others) + TOL else -1 if centre < min(others) - TOL else 0), keep


def _port_terminal(db, port):
    """The terminal of a port of the design: the centre of its shapes (where
    it is placed, when it has none). shapes: [(layer, box)] of them."""
    shapes = []
    for s in db.port_shape_rows(db.port_row(port)["id"]):
        v = [float(c) for c in s["points"].split()]
        shapes.append((s["layer"], (min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2]))))
    point = objects.port_centre(db, port)
    box = (min(b[0] for _, b in shapes), min(b[1] for _, b in shapes),
           max(b[2] for _, b in shapes), max(b[3] for _, b in shapes)) if shapes \
        else point + point
    return Terminal("port", f"port {port}", box, pin=port, point=point, shapes=shapes)


def _stub_terminal(db, stub, net=None, grid=None, plan=None):
    """The tap of a stub: half way along it. Once the stub is routed
    (route_final_stub, wires of kind stub stored under <leaf net>_stub) the point
    of those wires' centre lines nearest the tap, so the route ends on the
    wire also when it took another track than the nearest. Before that, with
    a plan (_stub_plan), the point nearest the tap of the wires the stub will
    get: on the track it shares with the other stubs of its spine."""
    from core.spine_snake import stub_middle, stub_points
    point = stub_middle(stub_points(stub["points"]))     # half way along, bends included

    def nearest(rects):
        on_wire = None
        for x1, y1, x2, y2 in rects:
            at = (((x1 + x2) / 2, min(max(point[1], y1), y2)) if y2 - y1 >= x2 - x1
                  else (min(max(point[0], x1), x2), (y1 + y2) / 2))
            off = abs(at[0] - point[0]) + abs(at[1] - point[1])
            if on_wire is None or off < on_wire[0] - TOL:
                on_wire = (off, at)
        return on_wire and on_wire[1]

    at = nearest(tuple(float(c) for c in r["rect"].split())
                 for r in (db.stub_wire_rows(net) if net else []) if r["kind"] == "stub")
    if at:
        return Terminal("stub", f"stub {stub['name']} (tap, on its wire)", at * 2,
                        point=at, routed=True)
    if plan is not None:
        point = nearest(box for _, box in plan.rects(grid, stub["name"])) or point
    return Terminal("stub", f"stub {stub['name']} (tap)", point + point, point=point)


def _obstacles(db, net):
    """(layer, rect) of every shape a route of net must keep clear of:
    route_pin straps and pin wires, and other nets' wires and extensions."""
    rect = lambda text: tuple(float(c) for c in text.split())
    shapes = [(r["layer"], rect(r["rect"])) for r in db.strap_rows()]
    shapes += [(r["layer"], rect(r["rect"])) for r in db.pin_wire_rows()]
    own = {net, stub_owner(net)} if net else set()     # its stub's are its own
    shapes += [(r["layer"], rect(r["rect"])) for r in db.net_wire_rows()
               if r["net"] not in own and r["kind"] != "cross"]
    return shapes


def _blocked(shapes, xs, ys, h, v):
    """Grid nodes too close to a shape on their layer. A node holds a box of
    v.width x h.width, which must keep the layer's rule spacing."""
    blocked = set()
    for layer_name, rect in shapes:
        for layer, lay in ((H, h), (V, v)):
            if layer_name != lay.name:
                continue
            x1, y1, x2, y2 = rect
            gx = v.width / 2 + lay.spacing
            gy = h.width / 2 + lay.spacing
            ia = bisect.bisect_right(xs, x1 - gx + TOL)
            ib = bisect.bisect_left(xs, x2 + gx - TOL)
            ja = bisect.bisect_right(ys, y1 - gy + TOL)
            jb = bisect.bisect_left(ys, y2 + gy - TOL)
            blocked.update((layer, i, j) for i in range(ia, ib) for j in range(ja, jb))
    return blocked


def _lee(sources, targets, xs, ys, blocked, via_weight, inside=None, weights=None):
    """Cheapest path from any source node to any target: (target key, [nodes],
    cost) or None. sources and each target set map nodes to an extra cost
    there (a set: none). Steps cost their length, a layer change via_weight;
    ordered by cost + distance to the targets' bounding box (A*). inside (the
    design boundary on this grid): a hard limit, no step along a track is
    taken unless its wire stays inside; the sources are inside already.
    weights ([per horizontal track], [per vertical track], each 1 or more):
    a step along a track costs its length times the track's weight."""
    goal = {}
    for k, nodes in targets.items():
        for n in nodes:
            extra = nodes[n] if isinstance(nodes, dict) else 0.0
            if n not in goal or extra < goal[n][1]:
                goal[n] = (k, extra)
    gx1 = min(xs[i] for _, i, _ in goal)
    gx2 = max(xs[i] for _, i, _ in goal)
    gy1 = min(ys[j] for _, _, j in goal)
    gy2 = max(ys[j] for _, _, j in goal)

    def guess(node):
        _, i, j = node
        x, y = xs[i], ys[j]
        return max(gx1 - x, 0, x - gx2) + max(gy1 - y, 0, y - gy2)

    cost, prev, heap, count = {}, {}, [], itertools.count()
    for n in sources:
        if n not in blocked:
            cost[n] = sources[n] if isinstance(sources, dict) else 0.0
            heapq.heappush(heap, (cost[n] + guess(n), next(count), n, False))
    nx, ny = len(xs), len(ys)
    hw, vw = weights or ([1.0] * ny, [1.0] * nx)
    done = set()
    while heap:
        f, _, node, final = heapq.heappop(heap)
        if final:                # a target, its extra cost paid: the cheapest
            path = [node]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return goal[node][0], path[::-1], f
        if node in done:
            continue
        done.add(node)
        here = cost[node]
        if node in goal:         # finish once its extra cost is the cheapest left
            heapq.heappush(heap, (here + goal[node][1], next(count), node, True))
        layer, i, j = node
        steps = [((1 - layer, i, j), via_weight)]
        if layer == H:
            steps += [((H, i + d, j), abs(xs[i + d] - xs[i]) * hw[j]) for d in (-1, 1)
                      if 0 <= i + d < nx]
        else:
            steps += [((V, i, j + d), abs(ys[j + d] - ys[j]) * vw[i]) for d in (-1, 1)
                      if 0 <= j + d < ny]
        for nxt, step in steps:
            if nxt in blocked:
                continue
            if inside is not None and nxt[0] == layer and not inside.step(node, nxt):
                continue             # the wire of this step would leave the boundary
            c = here + step
            if nxt not in done and c < cost.get(nxt, float("inf")) - TOL:
                cost[nxt] = c
                prev[nxt] = node
                heapq.heappush(heap, (c + guess(nxt), next(count), nxt, False))
    return None


def _report(name, terms, reached, edges, xs, ys, wires, drops, out, taps=None):
    length = sum(abs(xs[a[1]] - xs[b[1]]) + abs(ys[a[2]] - ys[b[2]])
                 for a, b in edges if a[0] == b[0])
    vias = sum(1 for a, b in edges if a[0] != b[0])
    count = sum(1 for w in wires if w[0] == "wire")
    crosses = [w for w in wires if w[0] == "cross"]
    info(f"  {name}: {count} wires, track length {_num(round(length, 3))} um + "
         f"{_num(round(drops, 3))} um from the tracks to the strap centres, {vias} layer "
         f"change(s), {len(crosses)} crossing box(es)", out)
    for k, t in enumerate(terms):
        node = reached.get(k)
        role = "driver" if k == 0 else "fixed wire" if t.kind == "fixed" else "load"
        if node is None:
            info(f"    {role} {t.label}: not routed", out)
            continue
        _, i, j = node
        how = {"strap": "connected across the strap", "pin": "ends near the pin, not connected",
               "stub": "ends on the stub wire" if t.routed
               else "ends at the stub (the stub is not routed)",
               "port": f"connected on {t.joined}" if t.joined
               else "ends near the port, not connected",
               "fixed": "kept; the route joins it"}[t.kind]
        if t.kind == "strap" and t.pieces:
            how += " (its pin route, extended " + " and ".join(
                f"{_num(round(r[2] - r[0], 6))} {'left' if r[2] == t.strap[0] else 'right'}"
                for r in t.pieces) + ")"
        more = "".join(f" and {{{_num(xs[i2])} {_num(ys[j2])}}}"
                       for _, i2, j2 in sorted((taps or {}).get(k, ())) if (i2, j2) != (i, j))
        info(f"    {role} {t.label}: {how} at {{{_num(xs[i])} {_num(ys[j])}}}{more}", out)
