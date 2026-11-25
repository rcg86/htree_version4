"""insert_vias -top_layer <layer> -bottom_layer <layer> [-area {x1 y1 x2 y2}]
[-via_ref {<via_def> ...}] [-nets {<net> ...}]: add vias where two wires of
one net cross on the two layers.

    insert_vias -bottom_layer IA -top_layer IB
    insert_vias -bottom_layer IA -top_layer IB -area {0 0 20 40}
    insert_vias -bottom_layer H2 -top_layer IA -area {0 0 20 40} -nets VSS \\
        -via_ref {V_H2_G1 V_G1_G2 V_G2_IA}

A crossing is where a wire on -bottom_layer and a wire on -top_layer of the
same net overlap (straps, pin wires, net wires and shields: a shield is on
its power net). Wires of different nets get no via: that would short them.
An instance pin is connected the same way: each of its rectangles on
-bottom_layer that a wire of the pin's net on -top_layer lies over is a
crossing, so a pin of two rectangles gets two vias.
Each crossing of the design, or with -area each one whose box lies in the
area, gets a via, a stack of one via per cut layer when the two layers are
more than one cut apart. One where a wire of another net lies on a layer in
between is not connected (HT4-277). Nor is one where no via fits: placed at
the middle of the crossing, its pads must lie on the two wires, so no pad
sticks out of the metal towards another net (HT4-311; the end of a strap a
wire only just overlaps).

Per layer pair the via is -via_ref's; else, when the tech has a VIARULE
GENERATE for the pair, the array of its cuts that fills the crossing
(vias.fit_array, a definition of source gen made by vias.generated); else
the one assign_via_for_route gives. Each run first removes the vias it made
before, of the nets given, between the two layers and in the area; an
inserted via takes the place of a via the routing derives at its crossing
(core/vias.py compute).

A via is kept as a net_wire row of kind insert_via under the wire on
-top_layer (net auto_via:<wire handle>, core/auto_via.py), so it moves and
goes with that wire as the auto vias of stretch_wire do. Its row names its
definitions; the via objects are derived from it (core/vias.py,
kind insert).
"""

import fnmatch
from bisect import bisect_left
from collections import Counter

from core import auto_via, netlist, objects, route_status, vias
from core.commands.get_obj_in_area import _area, _inside
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "insert_vias"
SUMMARY = "Insert vias where wires of one net cross on two layers"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-top_layer": "value", "-bottom_layer": "value", "-area": "value",
           "-via_ref": "value", "-nets": "value"}
USAGE = "insert_vias -top_layer <layer> -bottom_layer <layer> [-area {x1 y1 x2 y2}] " \
        "[-via_ref <via_defs>] [-nets <nets>]"

BAD_LAYER = 272
UNKNOWN_VIA = 273
NOT_BETWEEN = 274
SAME_LAYERS = 275
NO_NET = 276
BLOCKED = 277
NO_FIT = 311             # WARN: no via definition fits on the two wires of a crossing
KIND = "insert_via"      # the net_wire kind of an inserted via
LISTED = 10              # nets and blocked crossings printed
TOL = 1e-6


def run(session, argv, areas=None):
    """areas (route_pin: the instances it routed): [(x1 y1 x2 y2)] in place
    of -area, a crossing taken when its box lies in one of them."""
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    missing = [o for o in ("-top_layer", "-bottom_layer") if o not in opts]
    if missing:
        raise HtreeError(1, f"insert_vias: {' '.join(missing)} required. Usage: {USAGE}")
    tech = vias.tech_layers(db)
    bottom, top = opts["-bottom_layer"], opts["-top_layer"]
    for option, layer in (("-bottom_layer", bottom), ("-top_layer", top)):
        if tech.get(layer, (0, ""))[1] != "routing":
            raise HtreeError(BAD_LAYER, f"insert_vias: {option} '{layer}' is not a routing "
                             f"layer of the tech (get_db layers .name)")
    if tech[bottom][0] >= tech[top][0]:
        raise HtreeError(BAD_LAYER, f"insert_vias: -bottom_layer {bottom} is not below "
                         f"-top_layer {top} in the tech")
    # No -area: every crossing of the design.
    area = _area(session, opts["-area"], NAME) if "-area" in opts else None
    boxes = list(areas) if areas else ([area] if area is not None else None)
    stacks = vias.definition_layers(db, tech)
    up = vias.graph(stacks)
    hops = vias.chain(up, tech, bottom, top)
    given = _via_refs(session, opts["-via_ref"], stacks, hops) if "-via_ref" in opts else {}

    shapes = list(auto_via._shapes(db))
    nets = None
    if "-nets" in opts:
        nets = _nets(session, opts["-nets"], list(dict.fromkeys(
            net for _, net, _, _ in shapes if net is not None)))
    # The layers a via from bottom to top passes: a wire of another net there is in its way.
    if hops[0][1] is not None:
        inner = [t for _, _, t in hops[:-1]]
    else:
        inner = [l for l, (k, kind) in tech.items()
                 if kind == "routing" and tech[bottom][0] < k < tech[top][0]]
    wires, others = {}, []               # net -> (its wires on bottom, on top)
    for handle, net, layer, rect in shapes:
        if net is not None and layer in (bottom, top) and (nets is None or net in nets):
            wires.setdefault(net, ([], []))[layer == top].append((handle, rect))
        if layer in inner:
            others.append((handle, net, layer, rect))
    for handle, net, rect in _pin_shapes(db, bottom):
        if nets is None or net in nets:     # a pin rectangle: a shape of the pin's net
            wires.setdefault(net, ([], []))[0].append((handle, rect))
    fixed, held = db.fixed_nets(), {}    # a via on a wire of a fixed net is not added
    leaves = route_status._stubs_of_leaves(db) if fixed else {}

    def is_held(row):
        return bool(fixed) and route_status.shape_key(db, "net_wire", row, leaves) in fixed

    # The vias insert_vias made before, of the nets given, between the two layers and
    # in the area: removed, to be made again (those on wires of fixed nets stay).
    lo, hi = tech[bottom][0], tech[top][0]
    gone = []
    for r in db.net_wire_rows():
        if r["kind"] != KIND or "/" not in r["layer"]:
            continue
        ends = r["layer"].split("/", 1)
        if any(e not in tech or not lo <= tech[e][0] <= hi for e in ends):
            continue
        if nets is not None and (r["shield_net"] or r["net"]) not in nets:
            continue
        if boxes is not None and not any(_inside(vias._rect(r["rect"]), a) for a in boxes):
            continue
        if not is_held(r):
            gone.append(("net_wire", r["id"]))
    db.delete_wires(gone)

    choose = _chooser(db, stacks, hops, given)
    rows, blocked, done, small = [], [], {}, []
    count = Counter()                    # found, pins, partly; and vias per net
    for net, (lower, upper) in wires.items():
        lower.sort(key=lambda w: w[1][0])
        starts = [rect[0] for _, rect in lower]
        for handle, rect in upper:
            for under, below in lower[:bisect_left(starts, rect[2])]:
                box = auto_via._box(rect, below)
                if box is None:
                    continue
                if boxes is not None and not any(_inside(box, a) for a in boxes):
                    count["partly"] += any(auto_via._box(box, a) is not None for a in boxes)
                    continue
                text = " ".join(_num(round(c, 6)) for c in box)
                # two wires, one on the other: one crossing, one via
                if any(vias._overlap(box, b) for b in done.get(net, [])):
                    continue
                done.setdefault(net, []).append(box)
                count["found"] += 1
                count["pins"] += under.startswith("pin:")
                stop = next((o for o in others if o[2] in inner and o[1] != net
                             and auto_via._box(box, o[3])), None)
                if stop is not None:
                    blocked.append((net, text, stop))
                    continue
                names = choose(below, rect, box)
                if names is None:
                    small.append((net, text))
                    continue
                if is_held({"net": auto_via.owner(handle), "kind": KIND}):
                    held[handle] = held.get(handle, 0) + 1
                    continue
                rows.append((auto_via.owner(handle), KIND, f"{bottom}/{top}", text, net,
                             " ".join(n for n in names if n) or None))
                count[net, "crossings"] += 1

    route_status.skip(NAME, "wire(s) of fixed nets with crossings that would get a via",
                      list(held), out)
    made = {f"net_wire:{net}/{seq}" for net, seq in db.add_net_wires(rows)}
    new = [r for r in vias.rows(db) if r["source"] in made]
    _report(out, bottom, top, area if not areas else f"{len(areas)} area(s)", hops,
            count, new, blocked, len(gone),
            [n for n in wires if count[n, "crossings"]], only=nets is not None)
    if small:
        warn(NO_FIT, f"insert_vias: {len(small)} crossing(s) with no via: no via definition "
             f"of the layers fits on the two wires there (a pad would stick out of the metal, "
             f"towards other nets): " + ", ".join(f"{n} {{{t}}}" for n, t in small[:LISTED])
             + (" ..." if len(small) > LISTED else ""), out)
    return tuple(vias.handle(r) for r in new)


def _chooser(db, stacks, hops, given):
    """choose(lower, upper, box): the definitions of the vias of a crossing,
    one per hop of the stack (None: the one assign_via_for_route gives), or
    None when a hop has no via that fits. A via sits at the middle of box,
    its cuts inside box, its pad on the crossing's bottom layer inside the
    lower wire, on its top layer inside the upper one (a layer inside a stack
    has no wire of its own: inside box). Per hop: the -via_ref definition when
    it fits; else, when the tech has a VIARULE GENERATE for the hop, the
    generated via with the most cuts that fits (vias.fit_array, made by
    vias.generated); else, when a definition of the hop fits, None."""
    shapes, rules = {}, vias.via_rules(db)

    def pads(name):
        if name not in shapes:
            shapes[name] = vias.definition_shapes(db, name)
        return shapes[name]

    def inside(p, r):
        return r[0] - TOL <= p[0] and p[2] <= r[2] + TOL and \
            r[1] - TOL <= p[1] and p[3] <= r[3] + TOL

    def ok(name, hop, x, y, lower, upper, box):
        bottom, cut, top = hop
        for layer, _, pts in pads(name):
            p = (min(pts[0::2]) + x, min(pts[1::2]) + y, max(pts[0::2]) + x, max(pts[1::2]) + y)
            on = [w for lay, w in ((bottom, lower), (top, upper)) if w is not None and
                  (layer == lay or layer == cut)]
            if any(not inside(p, w) for w in on):
                return False
        return True

    def choose(lower, upper, box):
        x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        names = []
        for k, hop in enumerate(hops):
            lo = lower if k == 0 else None
            up = upper if k == len(hops) - 1 else None
            if hop[1] is None:               # no definition joins the layers: as before
                names.append(None)
            elif hop[::2] in given:
                if not ok(given[hop[::2]], hop, x, y, lo, up, box):
                    return None
                names.append(given[hop[::2]])
            elif hop in rules:
                arr = vias.fit_array(rules[hop], hop, box, lo, up)
                if arr is None:
                    return None
                names.append(vias.generated(db, rules[hop], hop, *arr))
            else:
                choices = [n for n, st in stacks.items() if st == hop]
                if choices and not any(ok(n, hop, x, y, lo, up, box) for n in choices):
                    return None
                names.append(None)
        return names
    return choose


def _pin_shapes(db, layer):
    """(pin handle, net, placed box) of the rectangles on layer of every
    instance pin that is on a net: the net its pin wire carries, else its
    net of the netlist. Every rectangle of a pin is one shape."""
    boxes = vias._pin_boxes(db)
    wired = {(r["inst"], r["pin"]): auto_via.electrical("pin_wire", r)
             for r in db.pin_wire_rows()}
    connected, pins = netlist.pins(db), {}
    for row in db.inst_rows():
        inst, cell = row["name"], row["ref_cell"]
        if cell not in pins:
            pins[cell] = list(dict.fromkeys(
                pin for pin, on, _, _ in db.lib_cell_shapes(cell) if on == layer))
        for pin in pins[cell]:
            net = wired.get((inst, pin)) or connected.get(inst, {}).get(pin)
            if net is None:
                continue
            for on, box in boxes(inst, pin):
                if on == layer:
                    yield f"pin:{inst}/{pin}", net, box


def _via_refs(session, text, stacks, hops):
    """{(bottom, top): via definition} of -via_ref: each one joins two layers
    of the way from -bottom_layer to -top_layer (hops)."""
    names = [objects.name_of(w) if w.startswith("via_def:") else w
             for w in session.split_list(text)]
    if not names:
        raise HtreeError(1, "insert_vias: -via_ref is empty")
    between = {(b, t): c for b, c, t in hops if c is not None}
    way = " ".join(f"{b}/{t}" for b, t in between) if between else None
    chosen = {}
    for name in names:
        if name not in stacks:
            raise HtreeError(UNKNOWN_VIA, f"insert_vias: no via definition '{name}' "
                             f"({len(stacks)} in the database; get_db via_defs lists them)")
        b, cut, t = stacks[name]
        if cut is None or between.get((b, t)) != cut:
            what = f"joins {b} and {t} through {cut}" if cut is not None else \
                "is not one cut layer between two layers of the tech"
            where = f"the vias from {hops[0][0]} to {hops[-1][2]} are {way}" if way else \
                f"no via definitions join {hops[0][0]} and {hops[-1][2]}"
            raise HtreeError(NOT_BETWEEN, f"insert_vias: via definition '{name}' {what}; "
                             f"{where}")
        if chosen.get((b, t), name) != name:
            raise HtreeError(SAME_LAYERS, f"insert_vias: '{chosen[b, t]}' and '{name}' both "
                             f"join {b} and {t}; name one of them")
        chosen[b, t] = name
    return chosen


def _nets(session, text, routed):
    """The nets of -nets among routed (the nets with route shapes): names,
    glob patterns, or net objects (net, spine_net, stub)."""
    db, found = session.db, []
    words = session.split_list(text)
    if not words:
        raise HtreeError(1, "insert_vias: -nets is empty")
    for word in words:
        name = word
        if name.startswith("stub:"):
            name = objects.get_attr(db, name, "net") or name
        if name.startswith("spine_net:"):
            objects.check_exists(db, name)
            name = objects.name_of(name)
        elif name.startswith("net:"):
            name = name[4:]
        hits = [name] if name in routed else [n for n in routed if fnmatch.fnmatchcase(n, name)]
        if not hits:
            raise HtreeError(NO_NET, f"insert_vias: no net '{word}' with route wires "
                             f"({len(routed)} nets have; get_db nets, and the power nets "
                             f"of straps and shields). Nothing is inserted")
        found += [n for n in hits if n not in found]
    return found


def _report(out, bottom, top, area, hops, count, new, blocked, removed, nets, only):
    where = "the design" if area is None else area if isinstance(area, str) else \
        "{" + " ".join(_num(c) for c in area) + "}"
    info(f"insert_vias: {bottom} to {top} in {where}: {count['found']} crossing(s) of "
         f"wires of one net", out)
    if count["pins"]:
        info(f"  On pins       : {count['pins']} of them a wire over a pin rectangle "
             f"on {bottom}", out)
    if removed:
        info(f"  Removed       : the vias insert_vias made before at {removed} crossing(s) "
             f"here, made again", out)
    made = sum(count[n, "crossings"] for n in nets)
    cuts = " ".join(c for _, c, _ in hops if c is not None)
    info(f"  Inserted      : {len(new)} via(s) at {made} crossing(s)"
         + (f" (cut layers {cuts})" if made and cuts else ""), out)
    if nets:
        more = f" ... (+{len(nets) - LISTED} more)" if len(nets) > LISTED else ""
        info("  Nets          : " + " ".join(f"{n}({count[n, 'crossings']})"
                                             for n in nets[:LISTED]) + more, out)
    if new:
        used = Counter(r["via_def"] for r in new)
        without = used.pop(None, 0)
        info("  Definitions   : " + (" ".join(f"{name}({n})" for name, n in used.items())
                                     or "none") +
             (f"; {without} via(s) have none (-via_ref, assign_via_for_route)"
              if without else ""), out)
    if count["partly"]:
        info(f"  Not in -area  : {count['partly']} crossing(s) partly inside, not inserted "
             f"(the whole box must lie in the area)", out)
    if blocked:
        info(f"  Blocked       : {len(blocked)} crossing(s)", out)
    for net, text, (handle, other, layer, _) in blocked[:LISTED]:
        warn(BLOCKED, f"insert_vias: net {net} at {{{text}}}: no via, {handle} "
             f"({'net ' + other if other else 'on no net yet'}) lies on {layer} "
             f"between {bottom} and {top} there", out)
    if len(blocked) > LISTED:
        info(f"  ... and {len(blocked) - LISTED} more blocked crossing(s)", out)
    if not count["found"]:
        info(f"  No wire or pin on {bottom} crosses a wire of its own net on {top} "
             + ("in the design" if area is None else "inside the area")
             + (", of the nets given" if only else ""), out)
