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


def via_rules(db, tech=None):
    """{(bottom, cut, top): rule} of the tech's VIARULE ... GENERATE: rule a
    dict of name, enclosure {routing layer: (a, b)} (the two overhangs, either
    way round), cut (width, height) and pitch (x, y), centre to centre. The
    pitch is the rule's SPACING (centre to centre, as LEF has it), at least
    twice the cut: a cut as far from the next as it is wide (a SPACING no
    larger than the cut would make the cuts touch). Of two rules of one
    stack, the first."""
    tech = tech or tech_layers(db)
    out = {}
    for r in db.conn.execute("SELECT text FROM tech_extra WHERE kind = 'VIARULE' ORDER BY seq"):
        lines = [l.strip().rstrip(";").strip() for l in r["text"].splitlines()]
        head = lines[0].split()
        if "GENERATE" not in head[2:]:
            continue
        layer, enc, cut, spacing = None, {}, None, None
        for line in lines[1:]:
            w = line.split()
            if not w:
                continue
            if w[0] == "LAYER":
                layer = w[1]
            elif w[0] == "ENCLOSURE" and layer is not None:
                enc[layer] = (float(w[1]), float(w[2]))
            elif w[0] == "RECT" and layer is not None:
                v = [float(c) for c in w[1:5]]
                cut = (layer, round(v[2] - v[0], 6), round(v[3] - v[1], 6))
            elif w[0] == "SPACING" and "BY" in w:
                spacing = (float(w[1]), float(w[3]))
        if cut is None or spacing is None or len(enc) != 2 or \
                any(l not in tech for l in [*enc, cut[0]]):
            continue
        bottom, top = sorted(enc, key=lambda l: tech[l][0])
        stack = (bottom, cut[0], top)
        if stack not in out:
            out[stack] = {"name": head[1], "enclosure": enc, "cut": cut[1:],
                          "pitch": (max(spacing[0], 2 * cut[1]), max(spacing[1], 2 * cut[2]))}
    return out


def fit_array(rule, stack, box, lower=None, upper=None):
    """The generated via of rule with the most cuts that, centred on box,
    has its cuts inside box and its pad on the stack's bottom layer inside
    lower, on its top layer inside upper (None: inside box): (rows, columns,
    bottom enclosure (x, y), top enclosure (x, y)), or None when not one cut
    fits. Each layer's two overhangs are tried both ways round."""
    bottom, _, top = stack
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    half = lambda r: (min(cx - r[0], r[2] - cx), min(cy - r[1], r[3] - cy))
    room = [half(box), half(lower or box), half(upper or box)]
    (cw, ch), (px, py) = rule["cut"], rule["pitch"]

    def count(h, size, pitch):           # cuts in a row of half width h
        return int((2 * h - size) / pitch + 1e-6) + 1 if 2 * h >= size - TOL else 0
    best = None
    a, b = rule["enclosure"][bottom], rule["enclosure"][top]
    for eb in ((a[0], a[1]), (a[1], a[0])):
        for et in ((b[0], b[1]), (b[1], b[0])):
            hx = min(room[0][0], room[1][0] - eb[0], room[2][0] - et[0])
            hy = min(room[0][1], room[1][1] - eb[1], room[2][1] - et[1])
            cols, rows = count(hx, cw, px), count(hy, ch, py)
            if rows and cols and (best is None or rows * cols > best[0] * best[1]):
                best = (rows, cols, eb, et)
    return best


def generated(db, rule, stack, rows, cols, eb, et):
    """The name of the via definition of rule with rows x cols cuts and the
    enclosures eb (bottom) and et (top), made (source gen) when it is not
    there: <rule>_<rows>x<cols>_<enclosures in nm>, as a DEF VIARULE via."""
    from core.lef import generated_via_shapes
    nm = lambda v: str(int(round(v * 1000)))
    name = f"{rule['name']}_{rows}x{cols}_" + "_".join(nm(v) for v in (*eb, *et))
    if db.via_def_row(name) is None:
        (cw, ch), (px, py) = rule["cut"], rule["pitch"]
        spacing = (round(px - cw, 6), round(py - ch, 6))
        extra = (f"CUTSIZE {_num(cw)} {_num(ch)}\nLAYERS {' '.join(stack)}\n"
                 f"CUTSPACING {_num(spacing[0])} {_num(spacing[1])}\n"
                 f"ENCLOSURE {' '.join(_num(v) for v in (*eb, *et))}\nROWCOL {rows} {cols}")
        db.add_generated_via(name, rule["name"], extra, generated_via_shapes(
            stack, (cw, ch), spacing, (*eb, *et), (rows, cols)))
    return name


def compute(db):
    """The rows of the via table for the present routing: (net, seq, kind,
    via_def, bottom, cut, top, x, y, rect, source)."""
    tech = tech_layers(db)
    stacks = definition_layers(db, tech)
    up = graph(stacks)
    assigned = {(r["bottom"], r["top"], r["net"]): r["via_def"]
                for r in db.via_assignment_rows()}
    rows, count, seen = [], Counter(), set()
    # The vias of insert_vias come before the others at their crossing: a via
    # derived there (a crossing box of the router, a pin wire on its pin) is
    # not made for a layer change an inserted via makes.
    inserted = {}
    for r in db.net_wire_rows():
        if r["kind"] == "insert_via" and "/" in r["layer"]:
            a, b = r["layer"].split("/", 1)
            for h in chain(up, tech, a, b):
                inserted.setdefault((r["shield_net"] or r["net"], h[0], h[2]), []).append(
                    _rect(r["rect"]))

    def add(net, kind, a, b, box, source, given=""):
        x, y = round((box[0] + box[2]) / 2, 6), round((box[1] + box[3]) / 2, 6)
        text = " ".join(_num(round(c, 6)) for c in box)
        hops = chain(up, tech, a, b)
        if kind != "insert":
            hops = [h for h in hops if not any(
                _overlap(box, o) for o in inserted.get((net, h[0], h[2]), []))]
            if not hops:
                return
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


def square_crossings(db):
    """Make every crossing box the full crossing of its net's two wires: of
    the wire on its horizontal layer and the one on its vertical layer (the
    net's shapes that overlap the box most), the box becomes the vertical
    wire's x span by the horizontal wire's y span, so the via, at its
    centre, sits in the middle of the crossing. A routed wire (net_wire)
    that stops short of the other wire's far edge is lengthened to it, no
    further than the box is long; a strap, pin wire or pin shape is not.
    Boxes and wires of fixed nets (set_db .route_status) are left. Returns
    (boxes moved, wires lengthened)."""
    dirs = _directions(db)
    fixed = db.fixed_nets()
    shapes = {}                    # (net, layer) -> [[rect, net_wire row or None]]

    def add(net, layer, rect, row=None):
        shapes.setdefault((net, layer), []).append([rect, row])
    rows_ = db.net_wire_rows()
    for r in rows_:
        if "/" not in r["layer"]:
            add(r["shield_net"] or r["net"], r["layer"], _rect(r["rect"]),
                None if r["status"] == "fixed" or r["net"] in fixed else r)
    for net, per in net_shapes(db).items():   # straps, pin wires, pins: kept as they are
        for layer, rects in per.items():
            have = {tuple(s[0]) for s in shapes.get((net, layer), [])}
            for rect in rects:
                if tuple(rect) not in have:
                    add(net, layer, rect)
    moved, longer = 0, set()
    for r in rows_:
        if "/" not in r["layer"] or r["kind"] in ADDED or r["status"] == "fixed" or \
                r["net"] in fixed:
            continue
        net, box = r["shield_net"] or r["net"], _rect(r["rect"])
        wires = {}
        for layer in r["layer"].split("/", 1):
            near = [s for s in shapes.get((net, layer), [])
                    if s[0][0] <= box[2] + TOL and s[0][2] >= box[0] - TOL and
                    s[0][1] <= box[3] + TOL and s[0][3] >= box[1] - TOL]
            if not near:
                break

            def area(s):
                o = (max(s[0][0], box[0]), max(s[0][1], box[1]),
                     min(s[0][2], box[2]), min(s[0][3], box[3]))
                return max(o[2] - o[0], 0) * max(o[3] - o[1], 0)
            way = dirs.get(layer)
            if way not in ("horizontal", "vertical"):
                break
            if way in wires:               # two layers of one direction: no crossing
                break
            wires[way] = max(near, key=area)
        if len(wires) != 2:
            continue
        h, v = wires["horizontal"], wires["vertical"]
        full = (v[0][0], h[0][1], v[0][2], h[0][3])
        reach = max(box[2] - box[0], box[3] - box[1])
        for s, lo, hi in ((h, 0, 2), (v, 1, 3)):
            rect = list(s[0])
            want = (min(rect[lo], full[lo]), max(rect[hi], full[hi]))
            if (rect[lo], rect[hi]) == want:
                continue
            if s[1] is None or rect[lo] - want[0] > reach + TOL or want[1] - rect[hi] > reach + TOL:
                continue                   # not a routed wire of its own, or too far
            rect[lo], rect[hi] = want
            s[0] = tuple(rect)
            db.set_wire_rect("net_wire", s[1]["id"], " ".join(_num(round(c, 6)) for c in rect))
            longer.add(s[1]["id"])
        if any(abs(a - b) > TOL for a, b in zip(full, box)):
            db.set_wire_rect("net_wire", r["id"], " ".join(_num(round(c, 6)) for c in full))
            moved += 1
    return moved, len(longer)


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
    squared = square_crossings(db)
    tech = tech_layers(db)
    stacks = definition_layers(db, tech)
    have = {(r["bottom"], r["top"], r["net"]) for r in db.via_assignment_rows()}
    groups = {}
    for r in rows(db):
        if r["via_def"] is None and r["cut"] is not None and r["net"] != "SIGNAL" and \
                (r["bottom"], r["top"], r["net"]) not in have and \
                (r["bottom"], r["top"], "") not in have:
            groups.setdefault((r["net"], r["bottom"], r["cut"], r["top"]), []).append(r)
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
    if any(squared):
        made.append(("", "", "", "squared", *squared))
    for (bottom, top), n in sorted(own_misfits(db, shapes, rank, metal).items()):
        made.append(("", bottom, top, "", n, 0))    # vias given a definition of their own
    return made


def own_misfits(db, shapes=None, rank=None, metal=None):
    """Every via of a crossing box whose definition comes from its net's
    assignment and does not fit there (its pads past the metal) gets one of
    the same layers that fits, its own, kept on the box as insert_vias
    -via_ref keeps one: the best ranked of them (auto_assign's ranks). A
    definition the box names itself is left. Returns {(bottom, top): vias
    changed}."""
    stacks = definition_layers(db)
    if shapes is None:
        dirs = _directions(db)
        shapes, rank = {}, {}
        for name, stack in stacks.items():
            if stack != UNKNOWN:
                shapes[name] = definition_shapes(db, name)
                pads = [p for l, _, p in shapes[name] if l in (stack[0], stack[2])]
                area = sum((max(p[0::2]) - min(p[0::2])) * (max(p[1::2]) - min(p[1::2]))
                           for p in pads)
                cuts = sum(1 for l, _, _ in shapes[name] if l == stack[1])
                default = (db.via_def_row(name)["is_default"] or "").lower() == "true"
                rank[name] = (cuts, _along(shapes[name], dirs), -round(area, 9), default)
    if metal is None:
        metal = net_shapes(db)
    boxes = {}
    for r in db.net_wire_rows():
        boxes[f"net_wire:{r['net']}/{r['seq']}"] = r
    n = Counter()
    for v in rows(db):
        box = boxes.get(v["source"] or "")
        name = v["via_def"]
        if box is None or name not in shapes or name in (box["via_def"] or "").split():
            continue
        mine = metal.get(v["net"], {})
        if fits(shapes[name], mine, v["bottom"], v["cut"], v["top"], v["x"], v["y"]):
            continue
        ok = [m for m, st in stacks.items() if st == (v["bottom"], v["cut"], v["top"]) and
              m in shapes and fits(shapes[m], mine, v["bottom"], v["cut"], v["top"], v["x"], v["y"])]
        if not ok:
            continue
        keep = [m for m in (box["via_def"] or "").split()
                if stacks.get(m, UNKNOWN)[::2] != (v["bottom"], v["top"])]
        db.set_net_wire_via_def(box["id"], " ".join(keep + [max(sorted(ok), key=lambda m: rank[m])]))
        boxes[v["source"]] = db.net_wire_row(box["net"], box["seq"])
        n[v["bottom"], v["top"]] += 1
    return n


def report_assigned(made, cmd, out):
    """The lines a routing command prints for auto_assign: per layer pair
    and definition the nets given it, and the vias it does not fit."""
    from core.messages import info, warn
    if not made:
        return
    by, own = {}, Counter()
    for net, bottom, top, name, fit, total in made:
        if not net and name == "squared":   # square_crossings
            info(f"{cmd}: {fit} crossing box(es) made the full crossing of their two wires, "
                 f"{total} wire(s) lengthened to it: the vias in the middle", out)
            continue
        if not net:                      # vias given a definition of their own
            own[bottom, top] += fit
            continue
        k = by.setdefault((bottom, top, name), [0, 0, 0])
        k[0], k[1], k[2] = k[0] + 1, k[1] + fit, k[2] + total
    if by:
        info(f"{cmd}: via definitions given to {len({m[0] for m in made if m[0]})} net(s) "
             f"(assign_via_for_route lists them, and changes them):", out)
    for (bottom, top, name), (nets, fit, total) in sorted(by.items()):
        info(f"  {bottom}/{top}  {name}  {nets} net(s), {total} via(s)", out)
    for (bottom, top), n in sorted(own.items()):
        info(f"{cmd}: {n} {bottom}/{top} via(s) given a definition of their own: the one of "
             f"their net does not fit them, another does", out)
    for bottom, top in sorted({(b, t) for b, t, _ in by}):
        unfit = sum(total - fit for (b, t, _), (_, fit, total) in by.items()
                    if (b, t) == (bottom, top)) - own[bottom, top]
        if unfit > 0:
            warn(VIA_TOO_BIG, f"{cmd}: {unfit} {bottom}/{top} via(s) larger than the "
                 f"wires they join: no {bottom}/{top} definition fits them", out)


VIA_TOO_BIG = 297
