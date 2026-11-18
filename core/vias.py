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
    insert                        a via insert_vias added (kind insert_via)
    pin                           a pin wire over a pin shape it starts from: one
                                  per rectangle of the pin under the wire
    strap                         a pin wire under the strap it reaches

A change between two layers that are more than one cut apart is a stack: one
via per cut layer at the same point, bottom first. The cut layers between two
layers come from the via definitions (their bottom, cut and top layers), not
from the tech layer order. With no definitions to go by, the change is one
via with no cut layer. Which definition a via uses is set by
assign_via_for_route; route_pin, route_net, route_track and route_final_stub
give each net the best fitting definition of each layer pair it has none
for (auto_assign). A via without one keeps the box as its shape.
"""

from collections import Counter, deque

from core.db import _num

TOL = 1e-6
UNKNOWN = (None, None, None)
# net_wire kinds of the vias added to the routing after it was made -> their via kind.
ADDED = {"via": "auto", "insert_via": "insert"}


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

    def add(net, kind, a, b, box, source, given=""):
        x, y = round((box[0] + box[2]) / 2, 6), round((box[1] + box[3]) / 2, 6)
        text = " ".join(_num(round(c, 6)) for c in box)
        hops = chain(up, tech, a, b)
        if (net, hops[0][0], hops[-1][2], text) in seen:
            return                          # one layer change, written twice
        seen.add((net, hops[0][0], hops[-1][2], text))
        # The definitions the box names itself (insert_vias -via_ref) come first.
        own = {stacks[n][::2]: n for n in (given or "").split() if n in stacks}
        for bottom, cut, top in hops:
            name = own.get((bottom, top)) or assigned.get((bottom, top, net)) or \
                assigned.get((bottom, top, ""))
            if stacks.get(name) != (bottom, cut, top):
                name = None                 # none assigned, or its definition is gone
            count[net] += 1
            rows.append((net, count[net], kind, name, bottom, cut, top, x, y, text, source))

    def boxes_of(added):
        for r in db.net_wire_rows():
            if "/" in r["layer"] and (r["kind"] in ADDED) == added:
                a, b = r["layer"].split("/", 1)
                add(r["shield_net"] or r["net"], ADDED.get(r["kind"], r["kind"]),
                    a, b, _rect(r["rect"]), f"net_wire:{r['net']}/{r['seq']}", r["via_def"])

    boxes_of(added=False)
    straps = {(r["inst"], r["seq"]): r for r in db.strap_rows()}
    boxes = _pin_boxes(db)
    for r in db.pin_wire_rows():
        net, wire, source = r["net"] or "SIGNAL", _rect(r["rect"]), \
            f"pin_wire:{r['inst']}/{r['pin']}"
        for layer, box in _pin_overlaps(boxes(r["inst"], r["pin"]), r["layer"], wire, tech):
            add(net, "pin", layer, r["layer"], box, source)
        strap = straps.get((r["inst"], r["strap"]))
        box = _overlap(wire, _rect(strap["rect"])) if strap is not None else None
        if box is not None and strap["layer"] != r["layer"]:
            add(net, "strap", r["layer"], strap["layer"], box, source)
    boxes_of(added=True)                    # last: one on a pin wire's own strap is that via
    return rows


def _pin_overlaps(shapes, layer, wire, tech):
    """[(pin layer, box)] where a pin wire on layer lies over its pin: its
    overlap with every pin shape on the highest tech layer below the wire's,
    so a pin of two rectangles is connected at both. When the tech has none
    of the pin's layers the layer is the one of the largest overlap. Empty
    when the pin has a shape on the wire's own layer under it: no via is
    needed."""
    over = [(l, box) for l, bbox in shapes if (box := _overlap(wire, bbox)) is not None]
    if not over or any(l == layer for l, _ in over):
        return []
    if layer in tech:
        below = [l for l, _ in over if l in tech and tech[l][0] < tech[layer][0]]
        if below:
            best = max(below, key=lambda l: tech[l][0])
            over = [o for o in over if o[0] == best]
        else:
            over = [o for o in over if o[0] not in tech]
    if not over:
        return []
    best = max(over, key=lambda o: (o[1][2] - o[1][0]) * (o[1][3] - o[1][1]))[0]
    return [o for o in over if o[0] == best]


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


# -- the definitions the routing commands give the vias -----------------------------

def net_shapes(db):
    """{net: {layer: [rect]}}: the metal of every net, as the vias see it:
    its wires (a shield's, a power link's: its power net; a stub's: its leaf
    net), the route_pin straps and pin wires on it, and the pin shapes
    (bounding boxes) of the pin wires on it."""
    found = {}

    def add(net, layer, rect):
        found.setdefault(net, {}).setdefault(layer, []).append(rect)
    for r in db.net_wire_rows():
        if "/" not in r["layer"]:            # a crossing box: the wires are there
            add(r["shield_net"] or r["net"], r["layer"], _rect(r["rect"]))
    for r in db.strap_rows():
        add(r["net"], r["layer"], _rect(r["rect"]))
    boxes = _pin_boxes(db)
    for r in db.pin_wire_rows():
        add(r["net"], r["layer"], _rect(r["rect"]))
        for layer, box in boxes(r["inst"], r["pin"]):
            add(r["net"], layer, box)
    return found


def _covered(rect, shapes):
    """Is rect inside the union of shapes; None when no shape touches it."""
    near = [s for s in shapes if s[0] < rect[2] - TOL and s[2] > rect[0] + TOL
            and s[1] < rect[3] - TOL and s[3] > rect[1] + TOL]
    if not near:
        return None
    xs = sorted({rect[0], rect[2]} | {c for s in near for c in (s[0], s[2])
                                      if rect[0] < c < rect[2]})
    ys = sorted({rect[1], rect[3]} | {c for s in near for c in (s[1], s[3])
                                      if rect[1] < c < rect[3]})
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not any(s[0] - TOL <= cx <= s[2] + TOL and s[1] - TOL <= cy <= s[3] + TOL
                       for s in near):
                return False
    return True


def fits(shapes, metal, bottom, cut, top, x, y):
    """Does a definition (its shapes about its origin) placed at (x, y) lie
    on the metal of its net (net_shapes: {layer: [rect]}): each pad on the
    bottom and top layer inside that layer's shapes, each cut inside both.
    A layer where the net has no metal under the shape is the inside of a
    stack (a pin wire down to a strap two layers below): not looked at."""
    for layer, _, pts in shapes:
        box = (min(pts[0::2]) + x, min(pts[1::2]) + y, max(pts[0::2]) + x, max(pts[1::2]) + y)
        for on in ((bottom, top) if layer == cut else (layer,) if layer in (bottom, top) else ()):
            if _covered(box, metal.get(on, [])) is False:
                return False
    return True


def _along(shapes, dirs):
    """How many pads of a definition run the way their layer does."""
    n = 0
    for layer, _, pts in shapes:
        w, h = max(pts[0::2]) - min(pts[0::2]), max(pts[1::2]) - min(pts[1::2])
        n += (dirs.get(layer) == "horizontal" and w > h + TOL) or \
            (dirs.get(layer) == "vertical" and h > w + TOL)
    return n


def _directions(db):
    """{layer: 'horizontal' | 'vertical' | ''} of the tech layers."""
    return {r["name"]: (r["direction"] or "").lower()
            for r in db.conn.execute("SELECT name, direction FROM layer")}


def auto_assign(db):
    """Give the vias with no definition one: for each net and layer pair
    that has no assignment (assign_via_for_route), neither of its own nor
    for every net, the definition of those layers that fits the most of its
    vias (fits); a DEFAULT one of the tech LEF before another (a DEF's
    generated power via is not for a signal route); of those that fit them
    all the one with the most cuts; then the one whose pads run the way
    their layers do, the smallest pads, by name. Vias of net SIGNAL (straps no route_net
    connected yet) are left. Returns [(net, bottom, top, definition, vias
    it fits, vias)] of the assignments made."""
    tech = tech_layers(db)
    stacks = definition_layers(db, tech)
    have = {(r["bottom"], r["top"], r["net"]) for r in db.via_assignment_rows()}
    groups = {}
    for r in rows(db):
        if r["via_def"] is None and r["cut"] is not None and r["net"] != "SIGNAL" and \
                (r["bottom"], r["top"], r["net"]) not in have and \
                (r["bottom"], r["top"], "") not in have:
            groups.setdefault((r["net"], r["bottom"], r["cut"], r["top"]), []).append(r)
    if not groups:
        return []
    dirs = _directions(db)
    metal = net_shapes(db)
    shapes, rank = {}, {}
    for name, stack in stacks.items():
        if stack != UNKNOWN:
            shapes[name] = definition_shapes(db, name)
            pads = [pts for layer, _, pts in shapes[name] if layer in (stack[0], stack[2])]
            area = sum((max(p[0::2]) - min(p[0::2])) * (max(p[1::2]) - min(p[1::2]))
                       for p in pads)
            cuts = sum(1 for layer, _, _ in shapes[name] if layer == stack[1])
            default = (db.via_def_row(name)["is_default"] or "").lower() == "true"
            rank[name] = (cuts, _along(shapes[name], dirs), -round(area, 9), default)
    made = []
    for (net, bottom, cut, top), vs in groups.items():
        names = [n for n, st in stacks.items() if st == (bottom, cut, top) and n in shapes]
        if not names:
            continue
        mine = metal.get(net, {})

        def score(name):
            n = sum(1 for v in vs if fits(shapes[name], mine, bottom, cut, top, v["x"], v["y"]))
            cuts, along, area, default = rank[name]
            return (n, default, cuts if n == len(vs) else 0, along, area)
        best = max(sorted(names), key=score)
        db.set_via_assignment(bottom, cut, top, net, best)
        made.append((net, bottom, top, best, score(best)[0], len(vs)))
    return made


def report_assigned(made, cmd, out):
    """The lines a routing command prints for auto_assign: per layer pair
    and definition the nets given it, and the vias it does not fit."""
    from core.messages import info, warn
    if not made:
        return
    by = {}
    for net, bottom, top, name, fit, total in made:
        k = by.setdefault((bottom, top, name), [0, 0, 0])
        k[0], k[1], k[2] = k[0] + 1, k[1] + fit, k[2] + total
    info(f"{cmd}: via definitions given to {len({m[0] for m in made})} net(s) "
         f"(assign_via_for_route lists them, and changes them):", out)
    for (bottom, top, name), (nets, fit, total) in sorted(by.items()):
        info(f"  {bottom}/{top}  {name}  {nets} net(s), {total} via(s)", out)
        if fit < total:
            warn(VIA_TOO_BIG, f"{cmd}: {total - fit} {bottom}/{top} via(s) larger than the "
                 f"wires they join: no {bottom}/{top} definition fits them ({name} given)",
                 out)


VIA_TOO_BIG = 297
