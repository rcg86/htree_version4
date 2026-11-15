"""get_obj_in_area -area {x1 y1 x2 y2} [-type {vias nets wires pins inst}]
[-enclosed | -touching]: the objects in an area.

    get_obj_in_area -area {0 0 10 20}                     everything fully inside
    get_obj_in_area -area {0 0 10 20} -type vias -touching
"""

from core import netlist, objects, vias
from core.messages import HtreeError
from core.options import parse_options
from core.placement import placed_bbox

NAME = "get_obj_in_area"
SUMMARY = "Return the vias, nets, wires, pins and instances in an area"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-area": "value", "-type": "value", "-touching": "flag", "-enclosed": "flag"}

USAGE = 1
BAD_AREA = 245
BAD_TYPE = 246
TOL = 1e-6
# -type word -> the kind of object, in the order they are returned.
TYPES = {"inst": "inst", "insts": "inst", "pin": "pin", "pins": "pin", "net": "net",
         "nets": "net", "wire": "wire", "wires": "wire", "via": "via", "vias": "via"}
ORDER = ("inst", "pin", "net", "wire", "via")


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    usage = "Usage: get_obj_in_area -area {x1 y1 x2 y2} [-type {vias nets wires pins inst}] " \
            "[-enclosed | -touching]"
    if "-area" not in opts:
        raise HtreeError(USAGE, f"get_obj_in_area: -area is required. {usage}")
    if opts["-touching"] and opts["-enclosed"]:
        raise HtreeError(USAGE, "get_obj_in_area: give -touching or -enclosed, not both")
    area = _area(session, opts["-area"])
    kinds = list(ORDER)
    if "-type" in opts:
        words = [w for w in opts["-type"].replace(",", " ").split() if w]
        bad = [w for w in words if w.lower() not in TYPES]
        if bad or not words:
            raise HtreeError(BAD_TYPE, f"get_obj_in_area: unknown -type "
                             f"'{' '.join(bad) or opts['-type']}'. "
                             f"Types: vias nets wires pins inst")
        kinds = list(dict.fromkeys(TYPES[w.lower()] for w in words))
    found = objects_in_area(session.db, area, kinds, touching=opts["-touching"])
    return tuple(h for kind in kinds for h in found[kind])


def _area(session, text):
    words = session.split_list(text)
    try:
        x1, y1, x2, y2 = (float(w) for w in words)
    except ValueError:
        raise HtreeError(BAD_AREA, f"get_obj_in_area: -area needs four numbers "
                         f"{{x1 y1 x2 y2}} (microns), got '{text}'")
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _touches(a, b):
    """Rects a and b overlap or share an edge or a corner."""
    return a[0] <= b[2] + TOL and b[0] <= a[2] + TOL and a[1] <= b[3] + TOL and \
        b[1] <= a[3] + TOL


def _inside(a, b):
    """Rect a lies in rect b (edges may coincide)."""
    return a[0] >= b[0] - TOL and a[1] >= b[1] - TOL and a[2] <= b[2] + TOL and \
        a[3] <= b[3] + TOL


def objects_in_area(db, area, kinds=ORDER, touching=False):
    """{kind: [handles]} of the objects in area (x1, y1, x2, y2): those that
    lie fully inside, or with touching those that overlap or touch it. An
    object of several shapes (a pin, a net) is inside when all its shapes
    are, and touches when one does."""
    hit = (lambda rect: _touches(rect, area)) if touching else \
        (lambda rect: _inside(rect, area))
    group = any if touching else all
    rect = lambda text: tuple(float(c) for c in text.split())
    found = {kind: [] for kind in ORDER}

    if "inst" in kinds or "pin" in kinds:
        cells = {}
        pin_boxes = vias._pin_boxes(db)
        for r in db.inst_rows():
            if r["ref_cell"] not in cells:
                cell = db.lib_cell_row(r["ref_cell"])
                cells[r["ref_cell"]] = (cell, db.lib_pin_names(cell["id"]) if cell else [])
            cell, pins = cells[r["ref_cell"]]
            if cell is None or r["x"] is None:
                continue
            box = placed_bbox(cell["size_x"], cell["size_y"], r["orient"], r["x"], r["y"])
            if "inst" in kinds and hit(box):
                found["inst"].append(f"inst:{r['name']}")
            if "pin" in kinds and _touches(box, area):
                for pin in pins:
                    boxes = [b for _, b in pin_boxes(r["name"], pin)]
                    if boxes and group(hit(b) for b in boxes):
                        found["pin"].append(f"pin:{r['name']}/{pin}")

    # Route shapes: (handle, electrical net, rect). Crossing boxes are not
    # wires: the vias stand for them.
    wires = []
    if "wire" in kinds or "net" in kinds:
        for r in db.strap_rows():
            wires.append((f"strap:{r['inst']}/{r['seq']}", r["net"], None, rect(r["rect"])))
        for r in db.pin_wire_rows():
            wires.append((f"pin_wire:{r['inst']}/{r['pin']}", r["net"], None, rect(r["rect"])))
        for r in db.net_wire_rows():
            if "/" not in r["layer"]:
                wires.append((f"net_wire:{r['net']}/{r['seq']}", r["shield_net"] or r["net"],
                              r["kind"], rect(r["rect"])))
    if "wire" in kinds:
        found["wire"] = [h for h, _, _, box in wires if hit(box)]
    via_rows = vias.rows(db) if "via" in kinds or "net" in kinds else []
    extent = vias.extents(db)
    if "via" in kinds:
        found["via"] = [vias.handle(r) for r in via_rows if hit(extent(r))]

    if "net" in kinds:
        # A net's shapes: the wires and vias that carry it (its shields carry
        # the power nets). A stub is the stub wire of its leaf net; the
        # leaf's net has the rest, the vias too.
        shapes, stub_shapes = {}, {}
        for _, net, kind, box in wires:
            (stub_shapes if (kind or "").startswith("stub") else shapes) \
                .setdefault(net, []).append(box)
        for r in via_rows:
            shapes.setdefault(r["net"], []).append(extent(r))
        for spine in db.spine_names():
            sid = db.spine_row(spine)["id"]
            leaf_of = {}
            for n in db.spine_net_rows(sid):
                leaf_of[n["loads"]] = n["name"]
                boxes = shapes.get(n["name"], [])
                if boxes and group(hit(b) for b in boxes):
                    found["net"].append(f"spine_net:{spine}/{n['name']}")
            for s in db.spine_stub_rows(sid):
                boxes = stub_shapes.get(leaf_of.get(s["name"]), [])
                if boxes and group(hit(b) for b in boxes):
                    found["net"].append(f"stub:{spine}/{s['name']}")
        for name in netlist.plain_nets(db):          # the nets of no spine
            boxes = shapes.get(name, [])
            if boxes and group(hit(b) for b in boxes):
                found["net"].append(f"net:{name}")
    return found
