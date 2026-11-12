"""route_net -net <nets> -rule <rule> [-via_weight <um>]: route spine nets on
the tracks of a route rule's horizontal and vertical layer, from the driver's
output pin to every load's input pin (or its stub).

    route_net -net temp_L1_inv1_Y -rule rule1
    route_net -net [get_db nets *L7*] -rule rule1 -via_weight 10

Lee maze routing (A* ordered) on the grid of track crossings: a step along a
track costs its length, a layer change costs -via_weight more. The tree grows
from the driver to the nearest unreached load, then the next, each time from
any point of the tree so far.

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

from core import objects, root_attrs
from core.commands.create_route_rule import DEFAULT, tech_spacing
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "route_net"
SUMMARY = "Route spine nets on a route rule's tracks (Lee, weighted layer changes)"
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

VIA_WEIGHT = 5.0      # um of wire one layer change is worth
# Shield nets left of / above and right of / below the signal, for a layer
# with no track assignment; with one, each shield takes its track's net.
SHIELD_NETS = ("VDD_SOC", "VSS")
MARGIN = 10           # tracks of room around the terminals
TOL = 1e-6
H, V = 0, 1           # grid layers: the rule's horizontal and vertical layer


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-net" not in opts or "-rule" not in opts:
        raise HtreeError(USAGE, "route_net: -net and -rule are required. Usage: route_net "
                         "-net <nets> -rule <route_rule> [-via_weight <um>]")
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
    nets = _nets(session, opts["-net"], session.out)
    layers = _rule_layers(db, opts["-rule"].removeprefix("route_rule:"))
    grid = Grid(db, layers)
    out = session.out
    h, v = layers
    info(f"route_net: rule {layers.rule}: {h.name} horizontal (width {_num(h.width)}, "
         f"spacing {_num(h.spacing)}), {v.name} vertical (width {_num(v.width)}, spacing "
         f"{_num(v.spacing)}); a layer change costs {_num(via_weight)} um", out)
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
        warn(REPLACED, f"route_net: removed the {cleared} old wires, extensions, crossing "
             f"boxes and shields of the {len(nets)} net(s) before routing them again", out)
    pre = _extend_pin_routes(db, grid, nets, out)
    for spine, row in nets:
        if route(db, grid, spine, row, via_weight, out, shield, pre):
            db.set_net_route_rule(row["name"], layers.rule)
            done.append(f"spine_net:{spine['name']}/{row['name']}")
    if shield:                   # every cell of these nets, after all of them are routed
        insts = dict.fromkeys(i for _, row in nets
                              for i in [row["driver"]] + row["loads"].split()
                              if db.inst_row(i) is not None and db.pin_wire_rows(i))
        pins = power_pins(db, insts, set(shield))
        bad = [f"{i}/{p} (strap {k})" for i, p, k, ok in pins if not ok]
        info(f"  power pins connected to shields: {len(pins) - len(bad)} of {len(pins)}", out)
        if bad:
            warn(NO_POWER, f"power pins not connected to a shield (their strap reaches no "
                 f"shield of its net within max_strap_extension): {' '.join(bad)}", out)
    return tuple(done)


def _nets(session, text, out=None):
    """[(spine row, spine_net row)] from names, glob patterns or handles.
    Stubs are nets too (get_db nets lists them), but route_final_stub routes
    them: they are left out, with a note."""
    db = session.db
    every = [(db.spine_row(s), r) for s in db.spine_names()
             for r in db.spine_net_rows(db.spine_row(s)["id"])]
    stubs = [(s, r["name"]) for s in db.spine_names()
             for r in db.spine_stub_rows(db.spine_row(s)["id"])]
    found, skipped = [], []
    for word in session.split_list(text):
        if word.startswith("spine_net:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits = [(s, r) for s, r in every if s["name"] == spine and r["name"] == name]
            stub_hits = []
        elif word.startswith("stub:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits, stub_hits = [], [f"{s}/{n}" for s, n in stubs if (s, n) == (spine, name)]
        else:
            hits = [(s, r) for s, r in every if fnmatch.fnmatchcase(r["name"], word)]
            stub_hits = [f"{s}/{n}" for s, n in stubs if fnmatch.fnmatchcase(n, word)]
        if not hits and not stub_hits:
            raise HtreeError(NO_NET, f"route_net: no spine net '{word}' (create_spine -build; "
                             f"get_db nets lists them)")
        found += [h for h in hits if h not in found]
        skipped += [h for h in stub_hits if h not in skipped]
    if skipped and out is not None:
        info(f"route_net: {len(skipped)} stub(s) left to route_final_stub: "
             f"{' '.join(skipped)}", out)
    return found


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

    def track_net(self, layer, tracks, j):
        """The assigned net of track j of layer ('-' signal, 'NA' blank), or
        None when the layer has no track assignment."""
        pattern = self.patterns.get(layer)
        return pattern[j % len(pattern)] if pattern else None


def _nearest(values, c):
    k = bisect.bisect_left(values, c)
    return min(values[max(0, k - 1):k + 1], key=lambda v: abs(v - c))


def _net_terminals(db, spine, row, pre=None):
    """The driver's terminal, then each load's (a pin or a stub)."""
    terms = [_terminal(db, spine, row["driver"], "out", pre)]
    stubs = {s["name"]: s for s in db.spine_stub_rows(spine["id"])}
    for load in row["loads"].split():
        terms.append(_stub_terminal(stubs[load]) if load in stubs
                     else _terminal(db, spine, load, "in", pre))
    return terms


def _extend_pin_routes(db, grid, nets, out):
    """Step a: extend the strap of every connected signal pin of the nets left
    and right to the nearest signal track of the vertical layer beyond each
    cell edge (the strap covers that track's wire), at most the strap's
    max_extension, keeping the strap layer's tech spacing to other nets'
    shapes. Returns {"pins": {(inst, pin): (net, [pieces], (x1, x2))},
    "shapes": [(net, layer, rect)]} of the pieces."""
    v, xs = grid.v, grid.all_xs
    routing = {row["name"] for _, row in nets}
    others = [(n, layer, r) for n, layer, r in _ia_shapes(db, None) if n not in routing]
    pins, shapes, lines = {}, [], []
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
            for side, x in (("left", left), ("right", right)):
                if x is None:
                    said.append(f"{side}: no signal track")
                    continue
                rect = (x - v.width / 2, sy1, sx1, sy2) if side == "left" else \
                    (sx2, sy1, x + v.width / 2, sy2)
                length = rect[2] - rect[0]
                if length > t.max_ext + TOL:
                    said.append(f"{side}: the signal track at x {_num(x)} is "
                                f"{_num(round(length, 6))} away, over {_num(t.max_ext)}")
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


def route(db, grid, spine, row, via_weight, out, shield=None, pre=None):
    """Route one net; store its wires. Returns True when it has wires."""
    name = row["name"]
    h, v = grid.h, grid.v
    pre = pre or {"pins": {}, "shapes": []}
    terms = _net_terminals(db, spine, row, pre)
    for t in terms:
        if t.kind == "pin":
            warn(NOT_PINNED, f"{name}: route_pin is not done on {t.inst} (pin {t.pin}); the "
                 f"route ends at the track crossing nearest the pin, not connected", out)

    # the grid: signal tracks around every terminal, MARGIN tracks more each side
    x1 = min(t.box[0] for t in terms)
    y1 = min(t.box[1] for t in terms)
    x2 = max(t.box[2] for t in terms)
    y2 = max(t.box[3] for t in terms)
    xs = _window(grid.all_xs, x1, x2)
    ys = _window(grid.all_ys, y1, y2)
    for t in terms:              # past the last track (outside the die): snapped to it
        tx1, ty1, tx2, ty2 = t.box
        far = [f"{h.name} y {_num(grid.all_ys[0])} .. {_num(grid.all_ys[-1])}"
               for lo, hi in ((ty1, ty2),) if hi < grid.all_ys[0] or lo > grid.all_ys[-1]]
        far += [f"{v.name} x {_num(grid.all_xs[0])} .. {_num(grid.all_xs[-1])}"
                for lo, hi in ((tx1, tx2),) if hi < grid.all_xs[0] or lo > grid.all_xs[-1]]
        if far:
            warn(OFF_TRACKS, f"{name}: {t.label} is beyond the signal tracks "
                 f"({'; '.join(far)}); its end is taken from the last track", out)
    shapes = _obstacles(db, name) + [(layer, r) for n, layer, r in pre["shapes"]
                                      if n != name]
    blocked = _blocked(shapes, xs, ys, h, v)
    targets = [t.nodes(xs, ys, h, v, shapes) for t in terms]
    for t, nodes in zip(terms, targets):
        for n in [n for n in nodes if n in blocked]:
            del nodes[n]
        if not nodes:
            warn(NO_PATH, f"{name}: every track crossing at {t.label} is blocked; not routed",
                 out)
            return False

    # Lee: grow the tree from the driver to the nearest unreached terminal
    tree, edges, reached = None, set(), {0: None}
    todo = set(range(1, len(terms)))
    while todo:
        found = _lee(tree if tree is not None else targets[0],
                     {k: targets[k] for k in todo}, xs, ys, blocked, via_weight)
        if found is None:
            warn(NO_PATH, f"{name}: no path to {', '.join(terms[k].label for k in todo)}; "
                 f"they are not routed", out)
            break
        k, path, _ = found
        todo.discard(k)
        if tree is None:
            tree = set()
            reached[0] = path[0]
        reached[k] = path[-1]
        tree.update(path)
        edges.update(zip(path, path[1:]))
    if tree is None:
        return False

    spans = {H: {}, V: {}}       # layer -> track index -> [(lo, hi)] (extended)
    crosses, extensions = [], []
    for node in tree:            # every node holds a box, so wire ends overlap fully
        layer, i, j = node
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
        node = reached.get(k)
        if node is None or t.kind != "strap":
            continue
        _, i, j = node           # a vertical wire from the crossing over the whole strap
        sx1, sy1, sx2, sy2 = t.strap
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
    wires += extensions
    wires += [("cross", layer, r) for layer, r in crosses]
    drops = sum(abs(ys[reached[k][2]] - (t.strap[1] + t.strap[3]) / 2)
                for k, t in enumerate(terms) if t.kind == "strap" and reached.get(k))
    _report(name, terms, reached, edges, xs, ys, wires, drops, out)
    if shield:
        stacks = []              # strap stacks of the cells, so shields cover them
        for inst in dict.fromkeys(t.inst for t in terms if t.kind == "strap"):
            rects = [tuple(float(c) for c in r["rect"].split()) for r in db.strap_rows(inst)]
            reach = max((r["max_extension"] or 0.0) for r in db.strap_rows(inst))
            stacks.append((min(r[0] for r in rects) - reach, max(r[2] for r in rects) + reach,
                           min(r[1] for r in rects), max(r[3] for r in rects)))
        electric = _ia_shapes(db, name) + [s for s in pre["shapes"] if s[0] != name]
        shields, cut, no_power, short = _shields(
            wires, electric, grid, shield, stacks,
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
        wires += _power_links(db, name, terms, wires, grid, out,
                              [s for s in pre["shapes"] if s[0] != name])
    old = db.set_net_wires(name, [(w[0], w[1], " ".join(_num(round(c, 6)) for c in w[2]))
                                  + tuple(w[3:]) for w in wires])
    if old:
        warn(REPLACED, f"{name}: replaced its {old} old wires and crossings", out)
    renamed = []                 # straps and pin wires now shorted to the net
    for k, t in enumerate(terms):
        if t.kind == "strap" and reached.get(k) is not None:
            db.set_pin_net(t.inst, t.pin, t.strap_seq, name)
            renamed.append(f"strap:{t.inst}/{t.strap_seq} pin_wire:{t.inst}/{t.pin}")
    if renamed:
        info(f"    now net {name}: {'  '.join(renamed)}", out)
    return True


def _report_short(short, db, out):
    if short:
        info(f"    not shielded: {len(short)} wire piece(s) shorter than "
             f"{_num(root_attrs.get(db, 'ignore_shield_less_than_routing_length'))} um "
             f"(ignore_shield_less_than_routing_length): "
             + ", ".join(f"{layer} {_num(round(n, 3))}" for layer, n in short), out)


def _along(r):
    return max(r[2] - r[0], r[3] - r[1])


def _shields(wires, shapes, grid, nets, stacks=(), min_length=0.0):
    # shapes: (electrical net, layer, rect) of everything else on the layers
    """([("shield", layer, rect, net)], length cut, tracks with no power net,
    wires left unshielded).
    Each wire of the net at least min_length long (root attribute
    ignore_shield_less_than_routing_length) gets one shield on each side, on the nearest track
    at least width + spacing from its centre, over its span. Its net is the
    track's net from the layer's track assignment (no shield on a signal or
    blank track); with no assignment, nets[0] left / above and nets[1] right /
    below. A vertical shield also runs over the
    whole strap stack of a cell at its wire (stacks: x1, x2 with the straps'
    reach, y1, y2), so every power strap of the cell can join one. Cut where
    another shape on the layer (other nets, straps, this net's wires, a shield
    of another net) is within spacing."""
    h, v = grid.h, grid.v
    own = [(layer, r) for kind, layer, r, *_ in wires if kind != "cross"]
    placed = []                  # (net, layer, rect)
    cut = 0.0
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
            pieces, start = [], lo
            for b1, b2 in _merge(blocked):
                if b1 > start:
                    pieces.append((start, min(b1, hi)))
                start = max(start, b2)
            if start < hi:
                pieces.append((start, hi))
            kept = [(p1, p2) for p1, p2 in pieces if p2 - p1 >= lay.width - TOL]
            cut += (hi - lo) - sum(p2 - p1 for p1, p2 in kept)
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
    return shields, cut, no_power, short


def _ia_shapes(db, net):
    """(electrical net, layer, rect) of every shape, on any layer, another
    route of net must keep clear of: straps, pin wires, and the other nets' wires, extensions,
    shields and shield extensions (shields under their power net)."""
    rect = lambda text: tuple(float(c) for c in text.split())
    found = [(r["net"], r["layer"], rect(r["rect"])) for r in db.strap_rows()]
    found += [(r["net"], r["layer"], rect(r["rect"])) for r in db.pin_wire_rows()]
    found += [(r["shield_net"] or r["net"], r["layer"], rect(r["rect"]))
              for r in db.net_wire_rows() if r["net"] != net and r["kind"] != "cross"]
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
    shapes on its layer by the rule spacing."""
    v = grid.v
    sx1, sy1, sx2, sy2 = (float(c) for c in strap["rect"].split())
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


def _window(values, lo, hi):
    """values within [lo, hi] plus MARGIN on each side."""
    a = max(0, bisect.bisect_left(values, lo - TOL) - MARGIN)
    b = min(len(values), bisect.bisect_right(values, hi + TOL) + MARGIN)
    if a >= b:                   # nothing inside: the nearest ones
        k = min(max(0, a), len(values) - 1)
        a, b = max(0, k - MARGIN), min(len(values), k + MARGIN + 1)
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
    """Where a route must end: a strap (route_pin done), a pin, or a stub tap."""

    def __init__(self, kind, label, box, inst="", pin="", strap=None, strap_layer="",
                 point=None, max_ext=0.0, strap_seq=None, strap_spacing=0.0, pieces=(),
                 span=None):
        self.kind, self.label, self.box = kind, label, box
        self.inst, self.pin, self.strap, self.strap_layer = inst, pin, strap, strap_layer
        self.point, self.max_ext, self.strap_seq = point, max_ext, strap_seq
        self.strap_spacing = strap_spacing   # tech spacing an extension keeps
        self.pieces = list(pieces)           # its pin route's extensions (step a)
        self.span = span or (strap and (strap[0], strap[2]))   # x of the extended strap

    def nodes(self, xs, ys, h, v, shapes):
        """{grid node: extra cost} of the nodes that reach it. On a strap: the
        vertical-layer crossings at the track nearest the strap centre, on
        every signal track the extended strap covers. Else the crossing
        nearest the point, on either layer."""
        if self.kind == "strap":
            sy1, sy2 = self.strap[1], self.strap[3]
            j = ys.index(_nearest(ys, (sy1 + sy2) / 2))
            x1, x2 = self.span
            return {(V, i, j): 0.0 for i, x in enumerate(xs)
                    if x1 + v.width / 2 - TOL <= x <= x2 - v.width / 2 + TOL}
        i = xs.index(_nearest(xs, self.point[0]))
        j = ys.index(_nearest(ys, self.point[1]))
        return {(H, i, j): 0.0, (V, i, j): 0.0}


def _gap(a, b):
    """Edge-to-edge distance of two rects (0 when they touch or overlap)."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5 if dx and dy else max(dx, dy)


def _terminal(db, spine, inst, direction, pre=None):
    """The terminal of an instance's input ('in') or output ('out') pin, with
    its pin route's extensions from pre (step a) when given."""
    row = db.inst_row(inst)
    cell = db.lib_cell_row(row["ref_cell"])
    pins = [p for p in db.lib_pin_names(cell["id"])
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
        return Terminal("strap", f"{inst}/{pin} (strap {wire['strap']})",
                        (span[0], rect[1], span[1], rect[3]), inst, pin, rect, strap["layer"],
                        max_ext=strap["max_extension"] or 0.0, strap_seq=wire["strap"],
                        strap_spacing=strap_spacing(db, strap["layer"], rect[3] - rect[1]),
                        pieces=pieces, span=span)
    pts = [c for _, _, p in objects.pin_shapes(db, f"pin:{inst}/{pin}") for c in p]
    if pts:
        box = (min(pts[0::2]), min(pts[1::2]), max(pts[0::2]), max(pts[1::2]))
    else:                        # no shapes: the cell's bbox
        box = objects.inst_bbox(db, row)
    point = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    return Terminal("pin", f"{inst}/{pin}", box, inst, pin, point=point)


def _stub_terminal(stub):
    from core.spine_snake import stub_middle, stub_points
    point = stub_middle(stub_points(stub["points"]))     # half way along, bends included
    return Terminal("stub", f"stub {stub['name']} (tap)", point + point, point=point)


def _obstacles(db, net):
    """(layer, rect) of every shape a route of net must keep clear of:
    route_pin straps and pin wires, and other nets' wires and extensions."""
    rect = lambda text: tuple(float(c) for c in text.split())
    shapes = [(r["layer"], rect(r["rect"])) for r in db.strap_rows()]
    shapes += [(r["layer"], rect(r["rect"])) for r in db.pin_wire_rows()]
    shapes += [(r["layer"], rect(r["rect"])) for r in db.net_wire_rows()
               if r["net"] != net and r["kind"] != "cross"]
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


def _lee(sources, targets, xs, ys, blocked, via_weight):
    """Cheapest path from any source node to any target: (target key, [nodes],
    cost) or None. sources and each target set map nodes to an extra cost
    there (a set: none). Steps cost their length, a layer change via_weight;
    ordered by cost + distance to the targets' bounding box (A*)."""
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
            steps += [((H, i + d, j), abs(xs[i + d] - xs[i])) for d in (-1, 1)
                      if 0 <= i + d < nx]
        else:
            steps += [((V, i, j + d), abs(ys[j + d] - ys[j])) for d in (-1, 1)
                      if 0 <= j + d < ny]
        for nxt, step in steps:
            if nxt in blocked:
                continue
            c = here + step
            if nxt not in done and c < cost.get(nxt, float("inf")) - TOL:
                cost[nxt] = c
                prev[nxt] = node
                heapq.heappush(heap, (c + guess(nxt), next(count), nxt, False))
    return None


def _report(name, terms, reached, edges, xs, ys, wires, drops, out):
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
        role = "driver" if k == 0 else "load"
        if node is None:
            info(f"    {role} {t.label}: not routed", out)
            continue
        _, i, j = node
        how = {"strap": "connected across the strap", "pin": "ends near the pin, not connected",
               "stub": "ends at the stub (the stub is not routed)"}[t.kind]
        if t.kind == "strap" and t.pieces:
            how += " (its pin route, extended " + " and ".join(
                f"{_num(round(r[2] - r[0], 6))} {'left' if r[2] == t.strap[0] else 'right'}"
                for r in t.pieces) + ")"
        info(f"    {role} {t.label}: {how} at {{{_num(xs[i])} {_num(ys[j])}}}", out)
