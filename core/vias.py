"""Vias: where a route changes layer.

A via definition (via_def: a VIA of the tech LEF or of the DEF VIAS) joins
two layers through one cut layer. A via object is one cut layer at one
point. The routers and stretch_wire still write a layer change as a crossing
box (net_wire rows whose layer is "<layer>/<layer>") and route_pin implies
one where a pin wire lies over its pin and under its strap; the via table is
derived from those here and brought in step (sync) whenever the database
has changed:

    cross, stub_cross, pg_cross   a crossing box of route_net, route_final_stub,
                                  optimize_pg_connection
    auto                          a via stretch_wire added (kind via)
    pin                           a pin wire over the pin shape it starts from
    strap                         a pin wire under the strap it reaches

A change between two layers that are more than one cut apart is a stack: one
via per cut layer at the same point, bottom first. The cut layers between two
layers come from the via definitions (their bottom, cut and top layers), not
from the tech layer order. With no definitions to go by, the change is one
via with no cut layer. Which definition a via uses is the user's choice
(assign_via_for_route); a via without one keeps the box as its shape.
"""

from collections import Counter, deque

from core.db import _num

TOL = 1e-6
UNKNOWN = (None, None, None)


def tech_layers(db):
    """{layer: (index in tech order, type in lower case)}."""
    return {r["name"]: (k, (r["type"] or "").lower()) for k, r in enumerate(
        db.conn.execute("SELECT name, type FROM layer ORDER BY id"))}


def _stack(layers, tech):
    """(bottom, cut, top) of a definition with shapes on these layers, or
    UNKNOWN. The cut layer is the one of TYPE CUT; in a tech without cut
    layers, the one layer of three that the tech does not have."""
    cuts = [l for l in layers if tech.get(l, (0, ""))[1] == "cut"]
    if not cuts and len(layers) == 3:
        cuts = [l for l in layers if l not in tech]
    metals = [l for l in layers if l not in cuts]
    if len(cuts) != 1 or len(metals) != 2 or any(l not in tech for l in metals):
        return UNKNOWN
    bottom, top = sorted(metals, key=lambda l: tech[l][0])
    return bottom, cuts[0], top


def definition_layers(db, tech=None):
    """{via definition: (bottom, cut, top)}; UNKNOWN for one whose layers the
    tech cannot order."""
    tech = tech_layers(db) if tech is None else tech
    layers = {name: [] for name in db.via_def_names()}
    for r in db.all_via_def_shapes():
        if r["layer"] not in layers[r["name"]]:
            layers[r["name"]].append(r["layer"])
    return {name: _stack(ls, tech) for name, ls in layers.items()}


def graph(stacks):
    """{bottom: {top: cut}} of the layer pairs the definitions join."""
    up = {}
    for bottom, cut, top in stacks.values():
        if cut is not None:
            up.setdefault(bottom, {}).setdefault(top, cut)
    return up


def chain(up, tech, a, b):
    """The hops [(bottom, cut, top), ...] from layer a to layer b, lower one
    first, through the fewest cut layers. No definitions join them: one hop
    with no cut layer."""
    if a in tech and b in tech and tech[a][0] > tech[b][0]:
        a, b = b, a
    came, todo = {a: None}, deque([a])
    while todo and b not in came:
        layer = todo.popleft()
        for top in up.get(layer, {}):
            if top not in came:
                came[top] = layer
                todo.append(top)
    if b not in came or a == b:
        return [(a, None, b)]
    hops = []
    while came[b] is not None:
        hops.append((came[b], up[came[b]][b], b))
        b = came[b]
    return hops[::-1]


def hop_distance(db):
    """A function (layer, layer) -> how many vias apart the two are: cut
    layers when the via definitions join them, else routing layers in tech
    order (None: not comparable)."""
    tech = tech_layers(db)
    up = graph(definition_layers(db, tech))
    order = {name: k for k, name in enumerate(n for n, (_, kind) in tech.items()
                                              if kind == "routing")}

    def distance(a, b):
        hops = chain(up, tech, a, b)
        if hops[0][1] is not None:
            return len(hops)
        if a in order and b in order:
            return abs(order[a] - order[b])
        return None
    return distance


def _overlap(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[2] - box[0] > TOL and box[3] - box[1] > TOL else None


def _rect(text):
    return tuple(float(c) for c in text.split())


def _pin_boxes(db):
    """A function (inst, pin) -> [(layer, placed bbox)] of the pin's shapes."""
    from core.placement import placed_points, placer
    cells = {}

    def boxes(inst, pin):
        row = db.inst_row(inst)
        if row is None:
            return []
        if row["ref_cell"] not in cells:
            cell = db.lib_cell_row(row["ref_cell"])
            cells[row["ref_cell"]] = (cell, db.lib_cell_shapes(cell["name"]) if cell else [])
        cell, shapes = cells[row["ref_cell"]]
        if cell is None:
            return []
        place = placer(cell["size_x"], cell["size_y"], row["orient"], row["x"], row["y"])
        out = []
        for p, layer, _, pts in shapes:
            if p == pin:
                pts = placed_points([float(v) for v in pts.split()], place)
                out.append((layer, (min(pts[0::2]), min(pts[1::2]),
                                    max(pts[0::2]), max(pts[1::2]))))
        return out
    return boxes


def compute(db):
    """The rows of the via table for the present routing: (net, seq, kind,
    via_def, bottom, cut, top, x, y, rect, source)."""
    tech = tech_layers(db)
    stacks = definition_layers(db, tech)
    up = graph(stacks)
    assigned = {(r["bottom"], r["top"], r["net"]): r["via_def"]
                for r in db.via_assignment_rows()}
    rows, count, seen = [], Counter(), set()

    def add(net, kind, a, b, box, source):
        x, y = round((box[0] + box[2]) / 2, 6), round((box[1] + box[3]) / 2, 6)
        text = " ".join(_num(round(c, 6)) for c in box)
        hops = chain(up, tech, a, b)
        if (net, hops[0][0], hops[-1][2], text) in seen:
            return                          # one layer change, written twice
        seen.add((net, hops[0][0], hops[-1][2], text))
        for bottom, cut, top in hops:
            name = assigned.get((bottom, top, net)) or assigned.get((bottom, top, ""))
            if stacks.get(name) != (bottom, cut, top):
                name = None                 # none assigned, or its definition is gone
            count[net] += 1
            rows.append((net, count[net], kind, name, bottom, cut, top, x, y, text, source))

    def boxes_of(auto):
        for r in db.net_wire_rows():
            if "/" in r["layer"] and (r["kind"] == "via") == auto:
                a, b = r["layer"].split("/", 1)
                add(r["shield_net"] or r["net"], "auto" if auto else r["kind"],
                    a, b, _rect(r["rect"]), f"net_wire:{r['net']}/{r['seq']}")

    boxes_of(auto=False)
    straps = {(r["inst"], r["seq"]): r for r in db.strap_rows()}
    boxes = _pin_boxes(db)
    for r in db.pin_wire_rows():
        net, wire, source = r["net"] or "SIGNAL", _rect(r["rect"]), \
            f"pin_wire:{r['inst']}/{r['pin']}"
        found = _pin_overlap(boxes(r["inst"], r["pin"]), r["layer"], wire, tech)
        if found is not None:
            add(net, "pin", found[0], r["layer"], found[1], source)
        strap = straps.get((r["inst"], r["strap"]))
        box = _overlap(wire, _rect(strap["rect"])) if strap is not None else None
        if box is not None and strap["layer"] != r["layer"]:
            add(net, "strap", r["layer"], strap["layer"], box, source)
    boxes_of(auto=True)                     # last: one on a pin wire's own strap is that via
    return rows


def _pin_overlap(shapes, layer, wire, tech):
    """(pin layer, box) where a pin wire on layer lies over its pin: the
    largest overlap with a pin shape on the highest tech layer below the
    wire's (on any layer when the tech has none of the pin's). None when
    the pin has a shape on the wire's own layer under it: no via is needed."""
    over = [(l, box) for l, bbox in shapes if (box := _overlap(wire, bbox)) is not None]
    if not over or any(l == layer for l, _ in over):
        return None
    if layer in tech:
        below = [l for l, _ in over if l in tech and tech[l][0] < tech[layer][0]]
        if below:
            best = max(below, key=lambda l: tech[l][0])
            over = [o for o in over if o[0] == best]
        else:
            over = [o for o in over if o[0] not in tech]
    if not over:
        return None
    return max(over, key=lambda o: (o[1][2] - o[1][0]) * (o[1][3] - o[1][1]))


def sync(db):
    """Bring the via table in step with the routing, the via definitions and
    the assignments. Does nothing when the database has not changed since
    the last call."""
    stamp = (id(db.conn), db.conn.total_changes)
    if db.via_stamp == stamp:
        return
    want = compute(db)
    have = [tuple(r)[1:] for r in db.conn.execute("SELECT * FROM via ORDER BY id")]
    if have != want:
        db.set_vias(want)
    db.via_stamp = (id(db.conn), db.conn.total_changes)


def rows(db, net=None):
    sync(db)
    if net is None:
        return db.conn.execute("SELECT * FROM via ORDER BY id").fetchall()
    return db.conn.execute("SELECT * FROM via WHERE net = ? ORDER BY seq", (net,)).fetchall()


def row(db, net, seq):
    sync(db)
    return db.conn.execute("SELECT * FROM via WHERE net = ? AND seq = ?",
                           (net, seq)).fetchone()


def handle(r):
    return f"via:{r['net']}/{r['seq']}"


def on_wires(db, net, wires):
    """The vias of net that land on one of wires (rows with layer and rect):
    their box is on the wire and the wire's layer is one of their two."""
    wires = [(w["layer"], _rect(w["rect"])) for w in wires]
    return [r for r in rows(db, net)
            if any(layer in (r["bottom"], r["top"]) and _overlap(_rect(r["rect"]), box)
                   for layer, box in wires)]


def definition_shapes(db, name):
    """[(layer, type, [points])] of a via definition, about its origin."""
    d = db.via_def_row(name)
    if d is None:
        return []
    return [(s["layer"], s["type"], [float(v) for v in s["points"].split()])
            for s in db.via_def_shapes(d["id"])]


def placed_shapes(db, r):
    """[(layer, type, [points])] of a via: its definition's shapes at its
    point. None assigned: nothing."""
    if r["via_def"] is None:
        return []
    return [(layer, kind, [round(c + (r["x"], r["y"])[k % 2], 6) for k, c in enumerate(pts)])
            for layer, kind, pts in definition_shapes(db, r["via_def"])]


def bbox(shapes):
    xs = [c for _, _, pts in shapes for c in pts[0::2]]
    ys = [c for _, _, pts in shapes for c in pts[1::2]]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def extent(db, r):
    """The rect a via covers: its definition's shapes, or the box it stands
    for when it has none."""
    return bbox(placed_shapes(db, r)) or _rect(r["rect"])


def extents(db):
    """extent for many vias: a function (via row) -> rect that reads each
    definition once."""
    boxes = {}

    def of(r):
        name = r["via_def"]
        if name is None:
            return _rect(r["rect"])
        if name not in boxes:
            boxes[name] = bbox(definition_shapes(db, name))
        box = boxes[name]
        if box is None:
            return _rect(r["rect"])
        return (round(box[0] + r["x"], 6), round(box[1] + r["y"], 6),
                round(box[2] + r["x"], 6), round(box[3] + r["y"], 6))
    return of
