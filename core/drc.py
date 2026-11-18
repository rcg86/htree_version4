"""The checks of check_drc, on what the tool made or placed: the route shapes
(straps, pin wires, net wires, extensions, shields, stub wires), the pads of
the vias that have a definition, and the pins of the placed cells.

    short     two shapes of different nets on a layer overlap or abut
    spacing   two shapes of different nets on a layer are closer than
                tech     the tech LEF asks (SPACING, SPACINGTABLE)
                custom   the route rule of either one asks
    width     a wire is narrower than
                tech     the layer's minimum width
                custom   the width of its route rule
    open      a net is not in one piece

The electrical net of a shape is its power net (shields, power straps and
pin wires) or its net. A strap and pin wire that route_net has not named yet
(SIGNAL) belong to the spine net of their pin. Shapes of one net are never
compared with each other; two pins are not compared either (library
geometry).

A via joins the shapes of its net on its two layers that lie over its box;
the vias of a stack join each other. So a net is in one piece when its pins,
wires and vias all hang together.
"""

import bisect
import itertools
from collections import namedtuple

from core import netlist, objects, vias
from core.db import CARRIED, STUB, _num

TOL = 1e-6
SIGNAL = "SIGNAL"
# Wires drawn with a route rule's width and spacing, and whose rule it is.
RULED = {"wire": "net", "shield": "net", "stub": "stub", "stub_shield": "stub"}
SHIELDS = {"shield", "stub_shield"}
SHORT, SPACING, WIDTH, OPEN = "short", "spacing", "width", "open"
TECH, CUSTOM = "tech", "custom"

# source: tech | custom for spacing and width, signal | power for an open.
# nets: the nets of the violation (two of a short or a spacing violation);
# handles: its shapes (of an open: the shapes and vias of the part cut off).
Violation = namedtuple("Violation", "check source layer bbox text nets handles",
                       defaults=((), ()))
# What a check_drc run found, kept for the table of the GUI (db.drc): the lines
# of what was checked and of the summary, and (section title, Violation) of
# every violation in the order of the report.
Report = namedtuple("Report", "head summary rows")
Via = namedtuple("Via", "handle net bottom top rect")
Net = namedtuple("Net", "name driver loads stubs")      # pins are (inst, pin)


class Shape:
    __slots__ = ("handle", "net", "layer", "rect", "what", "kind", "rule", "pin", "span")

    def __init__(self, handle, net, layer, rect, what, kind, rule=None, pin=None):
        self.handle, self.net, self.layer, self.rect = handle, net, layer, rect
        self.what, self.kind = what, kind        # what: wire | pad | pin
        self.rule, self.pin = rule, pin
        # (x, y) size; of a wire, once measured, of the run it is part of
        self.span = (rect[2] - rect[0], rect[3] - rect[1])

    @property
    def width(self):
        return min(self.span)


class Design:
    """The shapes and vias to check, the signal nets (the spine nets and the
    nets of no spine, netlist.plain_nets) with their pins, and the names of
    the power nets."""

    def __init__(self):
        self.shapes, self.vias, self.nets, self.power = [], [], {}, set()
        self.no_definition = 0               # vias without one: no pads to check


def _signal_pins(db):
    """A function (inst, 'in' | 'out') -> the pin a route goes to: the
    cell's first signal pin of that direction (as route_net), or None."""
    cells = {}

    def pin(inst, direction):
        row = db.inst_row(inst) if inst else None
        if row is None:
            return None
        key = (row["ref_cell"], direction)
        if key not in cells:
            cell = db.lib_cell_row(row["ref_cell"])
            names = []
            for p in db.lib_pin_names(cell["id"]) if cell is not None else []:
                lpin = db.lib_pin_row(cell["name"], p)
                if (lpin["direction"] or "").lower().startswith(direction) and \
                        (lpin["use"] or "signal").lower() == "signal":
                    names.append(p)
            cells[key] = names[0] if names else None
        return cells[key]
    return pin


def collect(db):
    """The Design of the database as it is now."""
    rect = lambda text: tuple(float(c) for c in text.split())
    d = Design()
    pin_of = _signal_pins(db)
    pin_net, stub_rule = {}, {}
    for spine in db.spine_names():
        sid = db.spine_row(spine)["id"]
        stubs = {s["name"]: s for s in db.spine_stub_rows(sid)}
        for n in db.spine_net_rows(sid):
            loads = n["loads"].split()
            pins = [(n["driver"], pin_of(n["driver"], "out"))] + \
                [(i, pin_of(i, "in")) for i in loads if i not in stubs]
            pins = [p if p[1] else None for p in pins]
            d.nets[n["name"]] = Net(n["name"], pins[0], [p for p in pins[1:] if p],
                                    [stubs[i] for i in loads if i in stubs])
            pin_net.update((p, n["name"]) for p in pins if p)
            for i in loads:
                if i in stubs:
                    stub_rule[n["name"]] = db.net_route_rule(objects.stub_key(spine, i))

    for name in netlist.plain_nets(db):      # the nets of no spine: a port's, connect_pin's
        ends = [e for e in netlist.ends(db, name) if e.kind == "pin"]
        driver = next(((e.inst, e.pin) for e in ends if e.drives), None)
        d.nets[name] = Net(name, driver, [(e.inst, e.pin) for e in ends if not e.drives], [])
        pin_net.update(((e.inst, e.pin), name) for e in ends)

    named = lambda net: net not in (None, "", SIGNAL)
    wire_net, strap_net = {}, {}
    for r in db.pin_wire_rows():
        pin = (r["inst"], r["pin"])
        if named(r["net"]):
            net = r["net"]
            if net not in d.nets:
                d.power.add(net)
        else:                                # not routed yet: the net of its pin
            net = pin_net.get(pin) or f"{r['inst']}/{r['pin']}"
            strap_net.setdefault((r["inst"], r["strap"]), net)
        wire_net[pin] = net
        d.shapes.append(Shape(f"pin_wire:{r['inst']}/{r['pin']}", net, r["layer"],
                              rect(r["rect"]), "wire", "pin_wire"))
    for r in db.strap_rows():
        if named(r["net"]):
            net = r["net"]
            if net not in d.nets:
                d.power.add(net)
        else:
            net = strap_net.get((r["inst"], r["seq"])) or f"{r['inst']}/strap{r['seq']}"
        d.shapes.append(Shape(f"strap:{r['inst']}/{r['seq']}", net, r["layer"],
                              rect(r["rect"]), "wire", "strap"))
    rules = {}
    for r in db.net_wire_rows():
        if "/" in r["layer"]:                # a crossing box: its vias stand for it
            continue
        if r["shield_net"] and r["kind"] not in CARRIED:     # a stub's: its signal net
            d.power.add(r["shield_net"])
        base = r["net"]                      # a stub's rows: under <leaf net>_stub
        if r["kind"].startswith("stub") and base.endswith(STUB):
            base = base[:-len(STUB)]
        if base not in rules:
            rules[base] = db.net_route_rule(base)
        whose = RULED.get(r["kind"])
        rule = None if whose is None else \
            (whose == "stub" and stub_rule.get(base)) or rules[base]
        d.shapes.append(Shape(f"net_wire:{r['net']}/{r['seq']}", r["shield_net"] or r["net"],
                              r["layer"], rect(r["rect"]), "wire", r["kind"], rule))

    definitions = {}
    for r in vias.rows(db):
        net = r["net"]
        if net == SIGNAL and (r["source"] or "").startswith("pin_wire:"):
            inst, _, pin = r["source"].partition(":")[2].partition("/")
            net = wire_net.get((inst, pin), net)
        via = Via(vias.handle(r), net, r["bottom"], r["top"], rect(r["rect"]))
        d.vias.append(via)
        if r["via_def"] is None:
            d.no_definition += 1
            continue
        if r["via_def"] not in definitions:
            definitions[r["via_def"]] = vias.definition_shapes(db, r["via_def"])
        for layer, _, pts in definitions[r["via_def"]]:
            if layer in (r["bottom"], r["top"]):         # a polygon by its bounding box
                box = (min(pts[0::2]) + r["x"], min(pts[1::2]) + r["y"],
                       max(pts[0::2]) + r["x"], max(pts[1::2]) + r["y"])
                d.shapes.append(Shape(via.handle, net, layer,
                                      tuple(round(c, 6) for c in box), "pad", "via"))

    boxes = vias._pin_boxes(db)
    cells = {}
    for row in db.inst_rows():
        if row["ref_cell"] not in cells:
            cell = db.lib_cell_row(row["ref_cell"])
            cells[row["ref_cell"]] = db.lib_pin_names(cell["id"]) if cell else []
        if row["x"] is None:
            continue
        for name in cells[row["ref_cell"]]:
            pin = (row["name"], name)
            net = wire_net.get(pin) or pin_net.get(pin) or f"{row['name']}/{name}"
            for layer, box in boxes(*pin):
                d.shapes.append(Shape(f"pin:{row['name']}/{name}", net, layer, box,
                                      "pin", "pin", pin=pin))
    return d


# -- the rules -------------------------------------------------------------------

class TechRule:
    """What the tech LEF asks on a routing layer: the minimum width, and
    the spacing of two shapes by their widths and parallel run length
    (SPACING, SPACINGTABLE PARALLELRUNLENGTH and TWOWIDTHS; a row or column
    is the last one whose width and PRL the shapes exceed). Tables of
    another kind and those in LEF58 properties are not applied; they are
    counted in skipped."""

    def __init__(self, db, row):
        self.direction = (row["direction"] or "").lower()
        self.min_width = row["min_width"] if row["min_width"] is not None else row["width"]
        self.spacing = row["min_spacing"]
        self.tables, self.skipped = [], 0
        for stmt in db.layer_extra(row["id"]):
            words = stmt.replace(";", " ").replace('"', " ").split()
            if "SPACINGTABLE" not in (w.upper() for w in words):
                continue
            table = _table(words) if words[0].upper() == "SPACINGTABLE" else None
            if table is None:
                self.skipped += 1
            else:
                self.tables.append(table)

    def required(self, w1, w2, prl):
        """(spacing, where it comes from) for two shapes w1 and w2 wide that
        run side by side over prl (<= 0: they do not), or (None, None)."""
        found = [(self.spacing, "SPACING")] if self.spacing is not None else []
        for kind, lengths, rows in self.tables:
            if kind == "PARALLELRUNLENGTH":
                i = _last(k for k, r in enumerate(rows) if max(w1, w2) > r[0] + TOL)
                j = _last(k for k, length in enumerate(lengths) if prl > length + TOL)
            else:
                i, j = (_last(k for k, r in enumerate(rows) if w > r[0] + TOL
                              and (r[1] is None or prl > r[1] + TOL)) for w in (w1, w2))
            found.append((rows[i][2][j], f"SPACINGTABLE {kind}"))
        return max(found) if found else (None, None)

    @property
    def reach(self):
        """The largest spacing the layer can ask."""
        values = [self.spacing or 0.0] + [v for _, _, rows in self.tables
                                           for r in rows for v in r[2]]
        return max(values)


def _last(indexes):
    return max(indexes, default=0)


def _table(words):
    """(kind, [run length], [(width, PRL or None, [spacing])]) of a
    SPACINGTABLE statement's words; None when it is not one of the two
    kinds read or its rows do not fit."""
    kind = words[1].upper() if len(words) > 1 else ""
    if kind not in ("PARALLELRUNLENGTH", "TWOWIDTHS"):
        return None
    lengths, rows, i = [], [], 2
    try:
        while i < len(words) and words[i].upper() != "WIDTH":
            lengths.append(float(words[i]))
            i += 1
        while i < len(words):
            if words[i].upper() != "WIDTH":
                return None
            width, prl, values = float(words[i + 1]), None, []
            i += 2
            if i < len(words) and words[i].upper() == "PRL":
                prl = float(words[i + 1])
                i += 2
            while i < len(words) and words[i].upper() != "WIDTH":
                values.append(float(words[i]))
                i += 1
            rows.append((width, prl, values))
    except (ValueError, IndexError):
        return None
    columns = len(lengths) if kind == "PARALLELRUNLENGTH" else len(rows)
    if not rows or not columns or (kind == "TWOWIDTHS" and lengths) or \
            any(len(r[2]) != columns for r in rows):
        return None
    return kind, lengths, rows


def tech_rules(db):
    """A function layer -> its TechRule; None for a layer that is not a
    routing layer of the tech."""
    found = {}

    def of(layer):
        if layer not in found:
            row = db.layer_row(layer)
            routing = row is not None and (row["type"] or "").lower() == "routing"
            found[layer] = TechRule(db, row) if routing else None
        return found[layer]
    return of


def custom_rules(db):
    """A function (route rule, layer) -> that rule's row (width, spacing) on
    the layer; None without a rule, for the default rule (it is the tech's)
    and for a layer the rule does not have."""
    found = {}

    def of(rule, layer):
        if rule is None:
            return None
        if (rule, layer) not in found:
            found[rule, layer] = db.route_rule_layer_row(rule, layer)
        return found[rule, layer]
    return of


# -- shorts, spacing and width ---------------------------------------------------

def box_text(rect):
    return "{" + " ".join(_num(round(c, 6)) for c in rect) + "}"


def _n(value):
    return _num(round(value, 6))


def _run(shape, group, axis):
    """How long the run of its net is that shape is part of along axis (0:
    x, 1: y): shape with the shapes of group that cover it across the axis
    and touch it, one after the other. A strap with its extensions is one
    wire as long as all of them."""
    o = 1 - axis
    lo, hi = shape.rect[axis], shape.rect[axis + 2]
    spans = [(g.rect[axis], g.rect[axis + 2]) for g in group if g is not shape
             and g.rect[o] <= shape.rect[o] + TOL and g.rect[o + 2] >= shape.rect[o + 2] - TOL]
    grown = True
    while grown:
        grown = False
        for a, b in spans:
            if a <= hi + TOL and b >= lo - TOL and (a < lo - TOL or b > hi + TOL):
                lo, hi, grown = min(lo, a), max(hi, b), True
    return hi - lo


def _pairs(movers, pins, reach):
    """Every two shapes that can be within reach of each other in x, one of
    them at least not a pin. movers and pins are sorted by their left edge."""
    for i, a in enumerate(movers):
        limit = a.rect[2] + reach
        for b in itertools.islice(movers, i + 1, None):
            if b.rect[0] > limit:
                break
            yield a, b
    if pins:
        starts = [p.rect[0] for p in pins]
        widest = max(p.rect[2] - p.rect[0] for p in pins)
        for a in movers:
            lo = bisect.bisect_left(starts, a.rect[0] - reach - widest)
            hi = bisect.bisect_right(starts, a.rect[2] + reach)
            for b in itertools.islice(pins, lo, hi):
                yield a, b


def check_geometry(design, tech, custom, layers=None, shorts=True, spacing=True):
    """[Violation]: the shorts, and with spacing the spacing and width
    violations, on the routing layers of layers (None: every one)."""
    found = []
    by_layer = {}
    for s in design.shapes:
        if layers is None or s.layer in layers:
            by_layer.setdefault(s.layer, []).append(s)
    for layer, shapes in by_layer.items():
        rule = tech(layer)
        movers = sorted((s for s in shapes if s.what != "pin"), key=lambda s: s.rect[0])
        if rule is None or not movers:
            continue
        pins = sorted((s for s in shapes if s.what == "pin"), key=lambda s: s.rect[0])
        reach = 0.0
        if spacing:
            nets = {}
            for s in shapes:
                nets.setdefault(s.net, []).append(s)
            for s in movers:
                if s.what == "wire":
                    s.span = (_run(s, nets[s.net], 0), _run(s, nets[s.net], 1))
            asked = [custom(s.rule, layer) for s in movers]
            reach = max([rule.reach] + [r["spacing"] for r in asked if r is not None])
            found += _widths(movers, rule, custom)
        for a, b in _pairs(movers, pins, reach + TOL):
            if a.net == b.net:
                continue
            ox = min(a.rect[2], b.rect[2]) - max(a.rect[0], b.rect[0])
            oy = min(a.rect[3], b.rect[3]) - max(a.rect[1], b.rect[1])
            if oy < -reach - TOL:
                continue
            between = (*sorted((max(a.rect[0], b.rect[0]), min(a.rect[2], b.rect[2]))),
                       *sorted((max(a.rect[1], b.rect[1]), min(a.rect[3], b.rect[3]))))
            between = (between[0], between[2], between[1], between[3])
            who = f"{a.handle} ({a.net}) and {b.handle} ({b.net})"
            two = ((a.net, b.net), (a.handle, b.handle))
            if (ox > TOL and oy > -TOL) or (oy > TOL and ox > -TOL):
                if shorts:
                    how = f"overlap {_n(ox)} x {_n(oy)}" if ox > TOL and oy > TOL else "abut"
                    found.append(Violation(SHORT, "", layer, between, f"{who} {how}", *two))
                continue
            if not spacing:
                continue
            dx, dy = max(-ox, 0.0), max(-oy, 0.0)
            gap = (dx * dx + dy * dy) ** 0.5
            prl = max(ox, oy)
            need, source = rule.required(a.width, b.width, prl)
            if need is not None and gap < need - TOL:
                found.append(Violation(
                    SPACING, TECH, layer, between,
                    f"{_n(gap)} < {_n(need)}  {who}  [{source}, widths {_n(a.width)} "
                    f"and {_n(b.width)}, parallel run {_n(max(prl, 0.0))}]", *two))
            asks = [(r["spacing"], s) for s in (a, b)
                    if (r := custom(s.rule, layer)) is not None]
            if asks:
                need, s = max(asks, key=lambda x: x[0])
                if gap < need - TOL:
                    found.append(Violation(
                        SPACING, CUSTOM, layer, between,
                        f"{_n(gap)} < {_n(need)}  {who}  [route rule {s.rule} of "
                        f"{s.handle}]", *two))
    return found


def _widths(shapes, rule, custom):
    """The width violations of the wires of one layer. Against the tech the
    smaller side of the wire counts; against its route rule the side across
    the layer's direction."""
    found = []
    for s in shapes:
        if s.what != "wire":
            continue
        if rule.min_width is not None and s.width < rule.min_width - TOL:
            found.append(Violation(WIDTH, TECH, s.layer, s.rect,
                                   f"{_n(s.width)} < {_n(rule.min_width)}  {s.handle} "
                                   f"({s.net})  [minimum width]", (s.net,), (s.handle,)))
        asked = custom(s.rule, s.layer)
        across = {"vertical": s.span[0], "horizontal": s.span[1]}.get(rule.direction, s.width)
        if asked is not None and across < asked["width"] - TOL:
            found.append(Violation(WIDTH, CUSTOM, s.layer, s.rect,
                                   f"{_n(across)} < {_n(asked['width'])}  {s.handle} "
                                   f"({s.net})  [route rule {s.rule}]", (s.net,),
                                   (s.handle,)))
    return found


# -- opens -----------------------------------------------------------------------

def _joined(a, b):
    """Two shapes or vias of one net are one piece of metal."""
    if isinstance(a, Via) and isinstance(b, Via):
        return bool({a.bottom, a.top} & {b.bottom, b.top}) and \
            vias._overlap(a.rect, b.rect) is not None
    if isinstance(a, Via):
        a, b = b, a
    if isinstance(b, Via):
        return a.layer in (b.bottom, b.top) and vias._overlap(a.rect, b.rect) is not None
    if a.pin is not None and a.pin == b.pin:
        return True                          # the shapes of a pin: joined in the cell
    if a.layer != b.layer:
        return False
    ox = min(a.rect[2], b.rect[2]) - max(a.rect[0], b.rect[0])
    oy = min(a.rect[3], b.rect[3]) - max(a.rect[1], b.rect[1])
    return (ox > TOL and oy > -TOL) or (oy > TOL and ox > -TOL)


def _pieces(nodes):
    """The nodes (shapes and vias of one net) in groups that hang together."""
    parent = list(range(len(nodes)))

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    pins = {}
    for k, node in enumerate(nodes):         # the shapes of a pin, wherever they are
        if not isinstance(node, Via) and node.pin is not None:
            parent[root(k)] = root(pins.setdefault(node.pin, k))
    order = sorted(range(len(nodes)), key=lambda k: nodes[k].rect[0])
    for at, i in enumerate(order):
        limit = nodes[i].rect[2] + TOL
        for j in itertools.islice(order, at + 1, None):
            if nodes[j].rect[0] > limit:
                break
            if root(i) != root(j) and _joined(nodes[i], nodes[j]):
                parent[root(j)] = root(i)
    groups = {}
    for k, node in enumerate(nodes):
        groups.setdefault(root(k), []).append(node)
    return list(groups.values())


def _piece_text(piece):
    """'pin u1/A, 2 wires, 3 vias' of a piece; one wire is named."""
    pins = list(dict.fromkeys(f"pin {s.pin[0]}/{s.pin[1]}" for s in piece
                              if not isinstance(s, Via) and s.pin))
    wires = [s for s in piece if not isinstance(s, Via) and not s.pin]
    n_vias = sum(isinstance(s, Via) for s in piece)
    words = pins[:4] + ([f"{len(pins) - 4} more pins"] if len(pins) > 4 else [])
    if len(wires) == 1:
        words.append(wires[0].handle)
    elif wires:
        words.append(f"{len(wires)} wires ({wires[0].handle} ...)")
    if n_vias:
        words.append(f"{n_vias} via{'s' if n_vias > 1 else ''}")
    return ", ".join(words)


def _handles(piece):
    return tuple(dict.fromkeys(s.handle for s in piece))


def _bbox(piece):
    rects = [s.rect for s in piece]
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def check_opens(design, order, layers=None):
    """[Violation]: the opens of the signal nets (source signal) and of the
    power nets (source power). order: {layer: index in tech order}.

    Every layer (layers None): a signal net must be one piece with its
    driver pin, its load pins and its stub wire in it (the net of a port:
    the port is not a shape, so its largest piece is taken). A power net is fed
    through its shields (the power grid as far as the database knows it,
    as for route_net and optimize_pg_connection): every piece of it must
    hold a strap, and when the net has shields, a shield. A layer range:
    only the shapes on those layers and the vias between them are looked
    at, and a net is open where a piece that has a shape on the net's
    lowest layer of the range has none on its
    highest."""
    found = []
    by_net = {}
    for s in design.shapes:
        if s.what != "pad" and (layers is None or s.layer in layers):
            by_net.setdefault(s.net, []).append(s)
    for v in design.vias:
        if layers is None or (v.bottom in layers and v.top in layers):
            by_net.setdefault(v.net, []).append(v)
    for name in list(design.nets) + sorted(design.power - set(design.nets)):
        net = design.nets.get(name)
        source = "signal" if net is not None else "power"
        pieces = _pieces(by_net.get(name, []))
        shapes_of = lambda piece: [s for s in piece if not isinstance(s, Via)]
        if layers is not None:
            on = sorted({s.layer for p in pieces for s in shapes_of(p)},
                        key=lambda layer: order.get(layer, -1))
            for piece in pieces if len(on) > 1 else []:
                have = {s.layer for s in shapes_of(piece)}
                if on[0] in have and on[-1] not in have:
                    found.append(Violation(
                        OPEN, source, "", _bbox(piece),
                        f"net {name}: no path to {on[-1]} from {_piece_text(piece)} on "
                        f"{on[0]}", (name,), _handles(piece)))
            continue
        if net is None:
            shielded = any(s.kind in SHIELDS for p in pieces for s in shapes_of(p))
            for piece in pieces:
                kinds = {s.kind for s in shapes_of(piece)}
                if "strap" not in kinds:
                    found.append(Violation(
                        OPEN, source, "", _bbox(piece),
                        f"net {name}: no path to a strap from {_piece_text(piece)}",
                        (name,), _handles(piece)))
                elif shielded and not kinds & SHIELDS:
                    found.append(Violation(
                        OPEN, source, "", _bbox(piece),
                        f"net {name}: no path to a shield from {_piece_text(piece)}",
                        (name,), _handles(piece)))
            continue
        home = next((p for p in pieces if any(s.pin == net.driver for s in shapes_of(p))),
                    None) if net.driver else None
        to = f"the driver {net.driver[0]}/{net.driver[1]}" if home is not None else \
            "the rest of the net"
        if home is None and pieces:
            home = max(pieces, key=len)
        for piece in pieces:
            if piece is not home:
                found.append(Violation(OPEN, source, "", _bbox(piece),
                                       f"net {name}: no path to {to} from {_piece_text(piece)}",
                                       (name,), _handles(piece)))
        wired = any(s.kind == "stub" for p in pieces for s in shapes_of(p))
        for stub in [] if wired else net.stubs:
            pts = [float(c) for c in stub["points"].split()]
            found.append(Violation(
                OPEN, source, "", (min(pts[0::2]), min(pts[1::2]), max(pts[0::2]),
                                   max(pts[1::2])),
                f"net {name}: stub {stub['name']} has no wire (route_final_stub)", (name,)))
    return found
