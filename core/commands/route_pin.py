"""route_pin -inst <inst> [-spec <yaml>] [-layer <layer>] [-nets {...}] [-width <w>]
[-spacing <s>]: horizontal straps over an instance, one per net, stacked top to
bottom, and a vertical wire from each pin to a strap of its net.
route_pin -dump <yaml> [-overwrite] writes the spec in force to a file to edit.

    route_pin -inst inst_1 -spec pin_routing_spec.yaml
    route_pin -dump pin_routing_spec.yaml
    route_pin -inst inst_1 -nets {VSS VDD_SOC SIGNAL VSS SIGNAL VDD_SOC} -width 0.36

Each strap is exactly as long as the instance is wide. The stack is centred
on the instance in y. Values come from DEFAULTS (the pin_connect spec: 7
straps, 0.72 wide, 0.72 apart, on IA), then the -spec file, then the options.
Running it again on an instance replaces its straps and pin wires.
Pin wires are as wide as the pin (its widest shape) and cross every strap;
vias are not made.
The spec's cell_pattern (a glob, or a list of them, on the library cell
name; default *) says which cells it is for: an instance of another cell is
not routed (listed, HT4-306 when none is left).
"""

import fnmatch
import json
import os

import yaml

from core import objects, route_status, vias
from core.commands.create_route_rule import tech_min_width, tech_spacing
from core.db import PIN_LAYER, _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "route_pin"
SUMMARY = "Add horizontal straps over an instance (net stack, width, spacing)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-inst": "value", "-spec": "value", "-spec_name": "value", "-layer": "value",
           "-nets": "value",
           "-width": "value", "-spacing": "value", "-dump": "value", "-overwrite": "flag"}

USAGE = 1
NO_INST = 160
NO_LAYER = 161
REPLACED = 162
NO_PIN_VIAS = 301       # WARN: insert_vias failed over an instance
NO_CELL_MATCH = 306     # WARN: no instance's cell matches the spec's cell_pattern
INSERT_PIN_VIAS = True  # insert_vias pin wire layer to strap layer after routing
SIDE_PINS = True        # a pin whose net comes from the side: no strap (_side_pins)
BELOW_TECH = 163
OFF_GRID = 164
OFF_TRACK = 165
NO_PIN = 166
BAD_SPEC = 167
DUMP_EXISTS = 168

# The spec, as in a -spec file under 'pin_routing'. pins.layer holds the cell
# pin shapes; straps go on pins.horizontal_layer, and each pin reaches its
# strap by a wire on pins.vertical_layer. pins.nets maps a cell pin to the
# strap net it connects to; pins not listed (VNW, VPW) are not connected.
DEFAULTS = {"cell_pattern": ["*"], "routing_direction": None, "width": 0.72, "spacing": 0.72, "max_strap_extension": 3.0,
            "nets": ["VSS", "VDD_SOC", "SIGNAL", "VSS", "SIGNAL", "VDD_SOC", "VDD_SOC"],
            "pins": {"layer": "D12", "horizontal_layer": "IA", "vertical_layer": "H2",
                     "nets": {"VDD": "VDD_SOC", "VSS": "VSS", "A": "SIGNAL", "Y": "SIGNAL"}}}
SIGNAL = "SIGNAL"            # a signal strap: each pin on it is a net of its own
TOL = 1e-6


def run(session, argv):
    result = _route(session, argv)
    vias.report_assigned(vias.auto_assign(session.db), NAME, session.out)
    return result


def _route(session, argv, given=None):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if given is None and opts.get("-spec_name") == AUTO and "-inst" in opts:
        handles = []
        for name, spec, names in _auto_specs(session, opts):
            handles += _route(session, _with_inst(argv, names), given=(spec, name))
        return tuple(handles)
    if given is None and "-inst" in opts and "-dump" not in opts and \
            "-spec" not in opts and "-spec_name" not in opts:
        # no spec given: each instance its own (set_db .pin_spec, or the one it
        # was routed with), the built-in one for those with none
        db = session.db
        groups = {}
        for name in inst_names(session, opts["-inst"]):
            kept = db.pin_spec(name) or (DEFAULTS, None)
            key = json.dumps(kept, sort_keys=True)
            groups.setdefault(key, (kept, []))[1].append(name)
        if len(groups) > 1 or any(kept[1] is not None or kept[0] != DEFAULTS
                                  for kept, _ in groups.values()):
            handles = []
            for kept, names in groups.values():
                handles += _route(session, _with_inst(argv, names), given=tuple(kept))
            return tuple(handles)
    spec, label = given if given is not None else spec_of(session.db, opts)
    if label:                            # the report and the instances name it
        opts = dict(opts, **{"-spec": label})
    spec = dict(spec, pins=dict(spec["pins"]))
    if "-nets" in opts:
        spec["nets"] = list(session.split_list(opts["-nets"]))
        if not spec["nets"]:
            raise HtreeError(USAGE, "route_pin: -nets must list at least one net")
    spec["width"] = _positive(opts.get("-width"), "-width", spec["width"])
    spec["spacing"] = _positive(opts.get("-spacing"), "-spacing", spec["spacing"])
    if "-layer" in opts:
        spec["pins"]["horizontal_layer"] = opts["-layer"].removeprefix("layer:")
    if "-dump" in opts:
        return dump_spec(spec, opts["-dump"], opts["-overwrite"], session.out)
    if "-inst" not in opts:
        raise HtreeError(USAGE, "route_pin: -inst is required. Usage: route_pin -inst <insts> "
                         "[-spec_name <name> | -spec <yaml> [-spec_name <name>]] [-layer "
                         "<layer>] [-nets {net ...}] [-width <w>] [-spacing <s>], or route_pin "
                         "-dump <yaml> [-overwrite]")
    db = session.db
    objects.require_tech(db)
    for layer in (spec["pins"]["horizontal_layer"], spec["pins"]["vertical_layer"]):
        if layer is not None:            # none: no straps
            _tech_layer(db, layer)
    names = inst_names(session, opts["-inst"])
    for name in names:           # every instance is checked before any is routed
        row = db.inst_row(name)
        if objects.inst_bbox(db, row) is None:
            raise HtreeError(NO_INST, f"route_pin: cell {row['ref_cell']} of {name} has no "
                             f"SIZE")
    fixed = db.fixed_nets()            # their straps and pin wires are routes of a fixed net
    held = [n for n in names if fixed and any(
        r["net"] in fixed for r in db.strap_rows(n) + db.pin_wire_rows(n))]
    route_status.skip(NAME, "instance(s) with pin routes on fixed nets", held, session.out)
    patterns = spec.get("cell_pattern") or ["*"]
    other = [n for n in names if n not in held and not any(
        fnmatch.fnmatchcase(db.inst_row(n)["ref_cell"], p) for p in patterns)]
    if other:
        refs = sorted({db.inst_row(n)["ref_cell"] for n in other})
        info(f"route_pin: {len(other)} instance(s) not routed, their cell matches no "
             f"cell_pattern of the spec ({' '.join(patterns)}): "
             + " ".join(other[:10]) + (" ..." if len(other) > 10 else "")
             + f" (cells: {' '.join(refs[:5])}{' ...' if len(refs) > 5 else ''})", session.out)
        if len(other) == len(names) - len(held):
            warn(NO_CELL_MATCH, f"route_pin: no instance routed: the cell of none of them "
                 f"matches cell_pattern {' '.join(patterns)}", session.out)
        held = held + other
    handles = []
    for name in names:
        if name not in held:
            handles += _route_inst(session, name, spec, opts)
            db.set_pin_spec(name, spec, opts.get("-spec"))     # to make them again (rebuild)
    routed = [n for n in names if n not in held]
    if len(routed) > 1:
        info(f"route_pin: {len(routed)} instances routed", session.out)
    if INSERT_PIN_VIAS:
        _insert_pin_vias(session, routed, spec)
    return tuple(handles)


def rebuild(session, names):
    """Make the pin routes of instances again, each with the spec route_pin
    last routed it with (db.pin_spec), and their pin vias: after
    legalize_placement turned them (their old routes were upside down).
    Returns (the names rebuilt, the names with no spec kept: route_pin was
    not run on them since specs are kept)."""
    db = session.db
    done, unknown = [], []
    groups = {}
    for name in names:
        kept = db.pin_spec(name)
        if kept is None:
            unknown.append(name)
            continue
        groups.setdefault(json.dumps(kept[0], sort_keys=True), (kept[0], kept[1], []))[2].append(
            name)
    for spec, source, insts in groups.values():
        opts = {"-spec": source} if source else {}
        for name in insts:
            _route_inst(session, name, spec, opts)
        done += insts
        if INSERT_PIN_VIAS:
            _insert_pin_vias(session, insts, spec)
    if done:
        vias.report_assigned(vias.auto_assign(db), NAME, session.out)
    return done, unknown


def _insert_pin_vias(session, names, spec):
    """insert_vias from the pin wire layer to the strap layer (H2 to IA)
    over each instance routed: a via where a pin wire crosses a strap of its
    net, over its own strap or another (a power pin wire under both straps
    of its net). One line of report for them all."""
    import io
    from core.commands import insert_vias
    db = session.db
    tech = vias.tech_layers(db)
    a, b = spec["pins"]["vertical_layer"], spec["pins"]["horizontal_layer"]
    if b is None:                        # no straps: to the horizontal signal layer, where
        from core.pin_access import _signal_tracks     # a pin wire meets its net's wires
        b = next(iter(_signal_tracks(db, "y")), None)
    if a not in tech or b not in tech:
        return
    bottom, top = sorted((a, b), key=lambda l: tech[l][0])
    if not names:
        return
    boxes = []
    for name in names:
        rects = [tuple(float(c) for c in r["rect"].split())
                 for r in db.strap_rows(name) + db.pin_wire_rows(name)]
        if rects:
            boxes.append((min(r[0] for r in rects), min(r[1] for r in rects),
                          max(r[2] for r in rects), max(r[3] for r in rects)))
    if not boxes:
        return
    made, there, where = 0, 0, []
    out = session.out
    session.out = io.StringIO()          # its report, summed up below
    try:                                 # one run over them all: the shapes read once
        insert_vias.run(session, ["-bottom_layer", bottom, "-top_layer", top], areas=boxes)
        text = session.out.getvalue()
    except HtreeError as exc:
        text = ""
        where.append(str(exc))
    finally:
        session.out = out
    for line in text.splitlines():
        if "Inserted      :" in line:
            made += int(line.split(":")[1].split()[0])
        elif "Already there :" in line:
            there += int(line.split(":")[1].split()[0])
    info(f"route_pin: insert_vias -bottom_layer {bottom} -top_layer {top} over the "
         f"instance(s): {made} via(s) inserted, {there} crossing(s) with their via already",
         out)
    for w in where:
        warn(NO_PIN_VIAS, f"route_pin: insert_vias not done: {w}", out)


def inst_names(session, text):
    """Instance names from a Tcl list of names, glob patterns (*temp_*) and
    inst: handles, in database order for patterns; each word must match. A
    word that is the name of an instance is that instance (d[3] is no
    pattern then)."""
    every = session.db.inst_names()
    exact = set(every)
    names = []
    for word in session.split_list(text):
        word = word.removeprefix("inst:")
        hits = [word] if word in exact else [n for n in every if fnmatch.fnmatchcase(n, word)]
        if not hits:
            raise HtreeError(NO_INST, f"route_pin: no instance '{word}' (create_inst; "
                             f"get_db insts lists them)")
        names += [n for n in hits if n not in names]
    return names


def _route_inst(session, name, spec, opts):
    """Straps and pin wires over one instance; returns their handles."""
    db = session.db
    row = db.inst_row(name)
    box = objects.inst_bbox(db, row)
    nets, width, spacing = spec["nets"], spec["width"], spec["spacing"]
    layer = spec["pins"]["horizontal_layer"]
    if layer is None:                    # pins.horizontal_layer none: no straps
        return _route_strapless(session, row, spec, opts)
    lrow, vrow = (_tech_layer(db, l) for l in (layer, spec["pins"]["vertical_layer"]))

    out = session.out
    x1, y1, x2, y2 = box
    height = len(nets) * width + (len(nets) - 1) * spacing
    top = (y1 + y2) / 2 + height / 2
    straps = []                                  # (net, (x1, y1, x2, y2)), top first
    for k, net in enumerate(nets):
        hi = round(top - k * (width + spacing), 6)
        straps.append((net, tuple(round(v, 6) for v in (x1, hi - width, x2, hi))))

    info(f"Straps over inst:{name} ({row['ref_cell']}) on {layer}: {len(nets)} nets, width "
         f"{_num(width)}, spacing {_num(spacing)}, pitch {_num(round(width + spacing, 6))}"
         f"{' (spec ' + opts['-spec'] + ')' if '-spec' in opts else ''}", out)
    info(f"  length {_num(round(x2 - x1, 6))} (instance width, x {_num(x1)} .. {_num(x2)}); "
         f"height {_num(round(height, 6))} edge to edge, "
         f"{_num(round(len(nets) * (width + spacing), 6))} tileable; centred on the instance "
         f"(y {_num(y1)} .. {_num(y2)})", out)
    _check_tech(db, lrow, nets, width, spacing, out)
    _check_grid(db, straps, out)
    track_lines = _check_tracks(db, layer, straps, out)
    for k, (net, r) in enumerate(straps, start=1):
        info(f"  strap:{name}/{k:<2} {net:<10} y {_num(r[1])} .. {_num(r[3])}"
             f"{track_lines[k - 1]}", out)
    wires = _route_pins(db, row, straps, spec["pins"], vrow, out)
    if SIDE_PINS and spec.get("routing_direction") != "vertical":    # vertical: from above
        straps, wires = _side_pins(db, row, straps, wires, layer, out, (width, spacing))
    ext = spec["max_strap_extension"]
    info(f"  route_net may extend each strap up to {_num(ext)} past each instance edge "
         f"(max_strap_extension) to reach its route", out)
    straps, wires = _named(db, name, straps, wires, out)
    replaced = db.set_straps(name, [(n, layer, " ".join(_num(v) for v in r)) for n, r in straps],
                             [(p, n, vrow["name"], " ".join(_num(v) for v in r), k)
                              for p, n, r, k in wires], ext)
    _pin_layers(db, name, box, spec["pins"], out)
    if replaced:
        warn(REPLACED, f"replaced the {replaced} straps {name} had, and its pin wires", out)
    if db.dropped_stretches:     # their routes reached the old straps: not these
        warn(REPLACED, f"the old straps of {name} were lengthened by the routes of "
             f"{' '.join(db.dropped_stretches)}: route them again (route_net -net "
             f"{{{' '.join(db.dropped_stretches)}}})", out)
    return ([f"strap:{name}/{k}" for k in range(1, len(straps) + 1)]
            + [f"pin_wire:{name}/{p}" for p, _, _, _ in wires])


def _route_strapless(session, row, spec, opts):
    """pins.horizontal_layer none (a net reached from the left or the right,
    horizontal_routing): no straps, a pin wire on the vertical layer over
    each pin of pins.nets alone. A signal pin's wire goes on to the nearest
    signal track of the horizontal signal layer (the track assignment's)
    that is free across the cell and out past its edge on the side the net
    comes from (_other_end; both sides tried when that is not known), as a
    side pin's: route_net brings the net in along that track onto it. A
    power pin's wire goes on to the nearest track the track assignment gives
    its net (VDD_SOC, VSS) on that layer: insert_pg_grid lays the power
    wire there, insert_vias joins the two. Either extension keeps clear of
    other nets' shapes on the pin wire layer by its spacing; with no such
    track near (two cell heights + 10 um), the wire covers the pin only.
    Returns the handles."""
    from core import netlist
    from core.pin_access import _rule, _signal_tracks
    db, out, name = session.db, session.out, row["name"]
    pin_spec = spec["pins"]
    vrow = _tech_layer(db, pin_spec["vertical_layer"])
    box = objects.inst_bbox(db, row)
    cell = db.lib_cell_row(row["ref_cell"])
    have = db.lib_pin_names(cell["id"])
    rows = _signal_tracks(db, "y")
    layer = next(iter(rows), None)       # the horizontal signal layer (IA)
    tracks = rows.get(layer, [])
    columns = next(iter(_signal_tracks(db, "x").values()), [])
    info(f"Pin wires of inst:{name} ({row['ref_cell']}) on {vrow['name']}, no straps "
         f"(pins.horizontal_layer none)"
         f"{' (spec ' + opts['-spec'] + ')' if '-spec' in opts else ''}", out)
    others = [] if layer is None else \
        [tuple(float(c) for c in r["rect"].split()) for r in db.strap_rows()
         if r["inst"] != name and r["layer"] == layer] + \
        [tuple(float(c) for c in r["rect"].split()) for r in db.net_wire_rows()
         if r["layer"] == layer and r["kind"] != "cross"] + \
        _side_ways(db, name, tracks, columns, layer)
    vname = vrow["name"]
    vgap = strap_spacing_of(db, vname)
    blocks = [tuple(float(c) for c in r["rect"].split()) + (r["net"],)
              for r in db.pin_wire_rows() if r["inst"] != name and r["layer"] == vname] + \
        [tuple(float(c) for c in r["rect"].split()) + (r["shield_net"] or r["net"],)
         for r in db.net_wire_rows() if r["layer"] == vname]
    power = {}                           # net -> its tracks on the layer (track assignment)
    assign = db.track_assignment_row(layer) if layer is not None else None
    if assign is not None and assign["direction"] == "y":
        pattern = assign["pattern"].split()
        for k, c in enumerate(db.track_positions(layer, "y")):
            power.setdefault(pattern[k % len(pattern)], []).append(c)
    reach = (box[3] - box[1]) * 2 + 10   # no long pin wire

    def clear(rect, net):
        """No shape of another net on the pin wire layer within its spacing."""
        return not any(n != net and b[0] < rect[2] + vgap - TOL and b[2] > rect[0] - vgap + TOL
                       and b[1] < rect[3] + vgap - TOL and b[3] > rect[1] - vgap + TOL
                       for *b, n in blocks)

    wires, taken, lines = [], [], []

    def pin_rect(pin):
        shapes = [_bbox(pts) for lyr, _, pts in objects.pin_shapes(db, f"pin:{name}/{pin}")
                  if lyr == pin_spec["layer"]]
        if not shapes:
            return None
        wide = max(shapes, key=lambda r: r[2] - r[0])
        return (wide[0], min(s[1] for s in shapes), wide[2], max(s[3] for s in shapes))

    # the tracks the stubs crossing the cell will be routed on are theirs: no other pin
    # of it lands there (the one that drives the stub goes on to it, below)
    stubs = _stub_bands(db, box, tracks, reach, layer) if layer is not None else []
    # first the pins whose net has a wire (or the track of its stub) to go on to: their
    # tracks are taken before any other pin of the cell looks for one
    targets = {}
    for pin, net in pin_spec["nets"].items():
        rect = pin_rect(pin) if pin in have else None
        if rect is None or net != SIGNAL or layer is None:
            continue
        real = netlist.pin_net(db, name, pin)
        own = _own_wire(db, real, layer, rect, reach, clear) or \
            _stub_track(db, name, real, rect, tracks, reach, clear, spec)
        if own is not None and not any(own[0][3] + TOL > r[1] and own[0][1] - TOL < r[3]
                                       for r in taken):
            targets[pin] = own
            taken.append((rect[0], own[0][1], rect[2], own[0][3]))
    taken += [b for driver, b in stubs if driver != name]      # others' stubs: not to land
    for pin, net in pin_spec["nets"].items():
        if pin not in have:
            warn(NO_PIN, f"{row['ref_cell']} has no pin {pin}", out)
            continue
        rect = pin_rect(pin)
        if rect is None:
            warn(NO_PIN, f"pin {pin} has no {pin_spec['layer']} shape", out)
            continue
        own = targets.get(pin)
        if own is not None:              # its net's wire on the layer across it: onto that
            q, what = own
            rect = (rect[0], min(rect[1], q[1]), rect[2], max(rect[3], q[3]))
            lines.append(f"{pin}: pin wire on to its net's {what} on {layer} at y "
                         f"{_num(round((q[1] + q[3]) / 2, 6))} (joined there, no route)")
        elif net == SIGNAL and layer is not None:
            real = netlist.pin_net(db, name, pin)
            w, s = (max(a, b) for a, b in zip(_rule(db, real, layer),
                                               (spec["width"], spec["spacing"])))
            at = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
            other = _other_end(db, name, pin)
            sides = (["left"] if other is not None and other[0] < at[0] - TOL else
                     ["right"] if other is not None and other[0] > at[0] + TOL else
                     ["left", "right"])
            best = None
            for side in sides:
                past = [c for c in columns if (c < box[0] - TOL if side == "left"
                                               else c > box[2] + TOL)]
                if not past:
                    continue
                way = (max(past) - w / 2, at[0]) if side == "left" else \
                    (at[0], min(past) + w / 2)
                for y in sorted(tracks, key=lambda c: abs(c - at[1])):
                    if abs(y - at[1]) > reach:
                        break                # no long pin wire
                    if not clear((rect[0], min(rect[1], y - w / 2), rect[2],
                                  max(rect[3], y + w / 2)), real):
                        continue
                    if any(y + w / 2 + s > r[1] + TOL and y - w / 2 - s < r[3] - TOL
                           for r in taken):
                        continue
                    if any(y + w / 2 + s > r[1] + TOL and y - w / 2 - s < r[3] - TOL and
                           way[1] + s > r[0] + TOL and way[0] - s < r[2] - TOL
                           for r in others):
                        continue
                    if best is None or abs(y - at[1]) < abs(best[0] - at[1]):
                        best = (y, side)
                    break
            if best is None:
                lines.append(f"{pin}: no {layer} signal track free out past the cell's edge: "
                             f"its pin wire covers the pin only, route_net cannot reach it")
            else:
                y, side = best
                taken.append((rect[0], y - w / 2, rect[2], y + w / 2))
                rect = (rect[0], min(rect[1], y - w / 2), rect[2], max(rect[3], y + w / 2))
                lines.append(f"{pin} (from the {side}): pin wire on to {layer} y "
                             f"{_num(round(y, 6))}")
        elif net != SIGNAL and layer is not None:    # on to a track of its power net
            at = (rect[1] + rect[3]) / 2
            w = _rule(db, net, layer)[0] or spec["width"]
            y = next((c for c in sorted(power.get(net, []), key=lambda c: abs(c - at))
                      if abs(c - at) <= reach and
                      clear((rect[0], min(rect[1], c - w / 2), rect[2], max(rect[3], c + w / 2)),
                            net)), None)
            if y is None:
                lines.append(f"{pin}: no {layer} {net} track near"
                             + ("" if power.get(net) else f" (the {layer} track assignment "
                                                          f"has none)")
                             + ": its pin wire covers the pin only")
            else:
                rect = (rect[0], min(rect[1], y - w / 2), rect[2], max(rect[3], y + w / 2))
                lines.append(f"{pin}: pin wire on to the {net} track {layer} y "
                             f"{_num(round(y, 6))} (insert_pg_grid, insert_vias join it)")
        rect = tuple(round(v, 6) for v in rect)
        wires.append((pin, net, rect))
        info(f"    pin_wire:{name}/{pin:<4} {net:<8} x {_num(rect[0])} .. {_num(rect[2])}, "
             f"y {_num(rect[1])} .. {_num(rect[3])}", out)
    if lines:
        info(f"  pins on to {layer} tracks: " + "; ".join(lines), out)
    _, named = _named(db, name, [], [(p, n, r, None) for p, n, r in wires], out)
    wires = [(p, n, r) for p, n, r, _ in named]
    replaced = db.set_straps(name, [], [(p, n, vrow["name"], " ".join(_num(v) for v in r), None)
                                        for p, n, r in wires], 0.0)
    _pin_layers(db, name, box, spec["pins"], out)
    if replaced:
        warn(REPLACED, f"replaced the {replaced} straps {name} had, and its pin wires", out)
    if db.dropped_stretches:
        warn(REPLACED, f"the old straps of {name} were lengthened by the routes of "
             f"{' '.join(db.dropped_stretches)}: route them again (route_net -net "
             f"{{{' '.join(db.dropped_stretches)}}})", out)
    return [f"pin_wire:{name}/{p}" for p, _, _ in wires]


def _pin_layers(db, name, box, pins, out):
    """Under each pin wire of the instance, a piece of every routing layer
    between the pin layer and the pin wire layer (H1, between D12 and H2):
    as wide as the pin wire, the cell's height (box), on the pin's net. The
    vias from the pin up to its pin wire then land on metal of each layer
    they join. Kept as net_wire rows of kind pin_layer under pg:<inst>, so
    they move with the instance; set_straps took the old ones away."""
    tech = vias.tech_layers(db)
    low, high = pins["layer"], pins["vertical_layer"]
    if low not in tech or high not in tech:
        return
    between = sorted((l for l, (k, kind) in tech.items() if kind == "routing" and
                      tech[low][0] < k < tech[high][0]), key=lambda l: tech[l][0])
    wires = db.pin_wire_rows(name)
    if not between or not wires:
        return
    rows = []
    for w in wires:
        x1, _, x2, _ = (float(c) for c in w["rect"].split())
        rows += [(PIN_LAYER, layer, " ".join(_num(round(v, 6)) for v in (x1, box[1], x2, box[3])),
                  w["net"]) for layer in between]
    keep = [(r["kind"], r["layer"], r["rect"], r["shield_net"])
            for r in db.net_wire_rows(f"pg:{name}") if r["kind"] != PIN_LAYER]
    db.set_net_wires(f"pg:{name}", keep + rows)
    info(f"  {' '.join(between)} under each of the {len(wires)} pin wire(s), the cell's height "
         f"(y {_num(box[1])} .. {_num(box[3])}): {' '.join(between)} between {low} and {high}",
         out)


def _own_wire(db, net, layer, rect, reach, clear):
    """(rect, what) of the nearest wire of net on layer (its route, or the
    stub wire of a leaf's net) that runs across the pin wire rect (its x
    span over the wire's) within reach in y of it, and that the pin wire can
    go on to (clear of other nets on its own layer), or None."""
    if not net:
        return None
    rows = [(r, "route") for r in db.net_wire_rows(net) if r["kind"] == "wire"] + \
        [(r, "stub") for r in db.stub_wire_rows(net) if r["kind"] == "stub"]
    mid = (rect[1] + rect[3]) / 2
    best = None
    for r, what in rows:
        if r["layer"] != layer:
            continue
        q = tuple(float(c) for c in r["rect"].split())
        if q[0] > rect[0] + TOL or q[2] < rect[2] - TOL:
            continue                     # not across the pin wire
        d = abs((q[1] + q[3]) / 2 - mid)
        if d > reach + TOL:
            continue
        grown = (rect[0], min(rect[1], q[1]), rect[2], max(rect[3], q[3]))
        if not clear(grown, net):
            continue
        if best is None or d < best[0]:
            best = (d, q, f"{what} wire")
    return None if best is None else (best[1], best[2])


def _planned(db, spine, stub, line):
    """The track route_final_stub would lay a stub's stretch on (its centre
    line at line), as things are now (plan_stubs, with the first route rule
    there is), or None."""
    from core.commands import route_net
    from core.commands.route_final_stub import plan_stubs
    rules = db.route_rule_names()
    if not rules:
        return None
    try:
        grid = route_net.Grid(db, route_net._rule_layers(db, rules[0]))
        plan = plan_stubs(db, grid, db.spine_row(spine))
    except HtreeError:
        return None
    found = plan.tracks.get(stub)
    if not found:
        return None
    for k, run_line in enumerate(plan.line.get(stub, ())):
        vertical, centre = plan.lines[run_line]
        if not vertical and abs(centre - line) < TOL and k < len(found):
            return found[k]
    return None


def _stub_bands(db, box, tracks, reach, layer):
    """[(driver, band)] of the stubs whose line runs along the layer across
    the cell box within reach: the band of the signal track nearest the line
    (where route_final_stub lays it), the route's wire wide."""
    from core.pin_access import _rule
    found = []
    for s in db.spine_names():
        for st in db.spine_stub_rows(db.spine_row(s)["id"]):
            if not st["points"]:
                continue
            pts = [float(c) for c in st["points"].split()]
            for (x1, y1), (x2, y2) in zip(zip(pts[0::2], pts[1::2]), zip(pts[2::2], pts[3::2])):
                if abs(y1 - y2) > TOL or max(x1, x2) < box[0] - TOL or min(x1, x2) > box[2] + TOL:
                    continue
                y = _planned(db, s, st["name"], y1) or min(tracks, key=lambda c: abs(c - y1))
                if abs(y - (box[1] + box[3]) / 2) > reach + TOL:
                    continue
                w = _rule(db, None, layer)[0]
                found.append((st["driver"], (box[0], y - w / 2, box[2], y + w / 2)))
    return found


def _stub_track(db, inst, net, rect, tracks, reach, clear, spec):
    """(rect, what) of the signal track a stub the instance drives (a leaf's
    output) will be routed on, when the stub's line runs along the layer
    across the pin wire within reach: the signal track nearest that line
    (route_final_stub lays the stub there; it is not routed yet), as wide as
    the route's wire (route_net then takes that track inside the pin wire). None when there is no such stub or the pin wire
    cannot go on to it."""
    if not net or not tracks:
        return None
    from core.pin_access import _rule
    from core.pin_access import _signal_tracks
    layer = next(iter(_signal_tracks(db, "y")), None)
    x = (rect[0] + rect[2]) / 2
    mid = (rect[1] + rect[3]) / 2
    w = max(_rule(db, net, layer)[0] if layer else 0.0, spec["width"])   # the route's wire
    best = None
    for s in db.spine_names():
        sid = db.spine_row(s)["id"]
        leaf = {r["loads"]: r["name"] for r in db.spine_net_rows(sid)}     # stub -> its net
        for st in db.spine_stub_rows(sid):
            if st["driver"] != inst or not st["points"] or leaf.get(st["name"]) != net:
                continue                 # only the pin on the stub's net (the leaf's output)
            pts = [float(c) for c in st["points"].split()]
            for (x1, y1), (x2, y2) in zip(zip(pts[0::2], pts[1::2]), zip(pts[2::2], pts[3::2])):
                if abs(y1 - y2) > TOL or not (min(x1, x2) - TOL <= x <= max(x1, x2) + TOL):
                    continue             # a horizontal stretch of the stub across the pin
                y = _planned(db, s, st["name"], y1) or min(tracks, key=lambda c: abs(c - y1))
                if abs(y - mid) > reach + TOL:
                    continue
                q = (rect[0], y - w / 2, rect[2], y + w / 2)
                grown = (rect[0], min(rect[1], q[1]), rect[2], max(rect[3], q[3]))
                if clear(grown, net) and (best is None or abs(y - mid) < best[0]):
                    best = (abs(y - mid), q, f"stub {st['name']} track")
    return None if best is None else (best[1], best[2])


def strap_spacing_of(db, layer):
    """The tech spacing of a layer (a minimum-width shape)."""
    row = db.layer_row(layer)
    return (tech_spacing(db, row, row["width"] or 0.0)[0] or 0.0) if row is not None else 0.0


def _named(db, name, straps, wires, out):
    """The signal pin wires (net SIGNAL), and the straps they land on, on
    the net their pin is on in the netlist: the connection is known, so the
    pin routes and their vias are the net's from the start (route_net need
    not name them). A pin on no net stays SIGNAL. Returns (straps, wires)."""
    from core import netlist
    straps = list(straps)
    found, said = [], []
    for pin, net, rect, k in wires:
        real = netlist.pin_net(db, name, pin) if net == SIGNAL else None
        if real:
            net = real
            if k is not None and straps[k - 1][0] == SIGNAL:
                straps[k - 1] = (real, straps[k - 1][1])
            said.append(f"{pin} {real}")
        found.append((pin, net, rect, k))
    if said:
        info(f"  on their nets (netlist): {', '.join(said)}", out)
    return straps, found


def _other_end(db, inst, pin, reach=0.0):
    """(x, y) of where the net of a pin comes from, the nearest of: for an
    input pin its driver (a pin or a port), the stubs its driver drives and
    the net's routed wires (the route comes to it from there); for an
    output pin its loads (pins, a port) and the stubs it drives. None when
    not known. A vertical stub or wire that runs past the pin, or ends
    within reach of its y (reach: the strap stack's height: it lands on a
    strap), is (x, y, "v"): the route comes along it, from above or below,
    however near it is in x."""
    from core import netlist
    net = netlist.pin_net(db, inst, pin)
    at = objects.pin_centre(db, inst, pin)
    if net is None or at is None:
        return None
    ends = [e for e in netlist.ends(db, net) if (e.inst, e.pin) != (inst, pin)]
    mine = next((e for e in netlist.ends(db, net) if (e.inst, e.pin) == (inst, pin)), None)
    drives = mine is not None and mine.drives
    spots = []
    for e in ends:
        if e.drives == drives:
            continue                     # an input wants its driver, an output its loads
        p = objects.port_centre(db, e.pin) if e.kind == "port" else \
            objects.pin_centre(db, e.inst, e.pin)
        if p is not None:
            spots.append(p)
    driver = inst if drives else next((e.inst for e in ends if e.drives and e.kind == "pin"),
                                      None)
    for s in db.spine_names():           # the stubs of the net (its leaf drives them)
        for r in db.spine_stub_rows(db.spine_row(s)["id"]):
            if driver is not None and r["driver"] == driver and r["points"]:
                pts = [float(c) for c in r["points"].split()]
                spots.append(_nearest_on(at, list(zip(pts[0::2], pts[1::2]))))
                spots += [(x1, at[1], "v") for (x1, y1), (x2, y2) in zip(
                    zip(pts[0::2], pts[1::2]), zip(pts[2::2], pts[3::2]))
                    if abs(x1 - x2) < TOL and
                    min(y1, y2) - reach - TOL <= at[1] <= max(y1, y2) + reach + TOL]
    if not drives:                       # its route there is: the wires of the net
        for r in db.net_wire_rows(net) + db.stub_wire_rows(net):
            if r["kind"] in ("wire", "stub") and "/" not in r["layer"]:
                x1, y1, x2, y2 = (float(c) for c in r["rect"].split())
                spot = (min(max(at[0], x1), x2), min(max(at[1], y1), y2))
                if y2 - y1 > x2 - x1 and y1 - reach - TOL <= at[1] <= y2 + reach + TOL:
                    spot += ("v",)
                spots.append(spot)
    if not spots:
        return None
    near = lambda p: abs(p[0] - at[0]) + abs(p[1] - at[1]) - (TOL if len(p) > 2 else 0.0)
    return min(spots, key=near)


def _nearest_on(at, points):
    x, y = at
    spots = [(min(max(x, min(x1, x2)), max(x1, x2)), min(max(y, min(y1, y2)), max(y1, y2)))
             for (x1, y1), (x2, y2) in zip(points, points[1:])] or points
    return min(spots, key=lambda p: abs(x - p[0]) + abs(y - p[1]))


def _side_pins(db, row, straps, wires, layer, out, least=(0.0, 0.0)):
    """A signal pin whose net comes from the left or the right (_other_end:
    farther along x than along y from the pin) gets no strap: its pin wire
    is extended to the nearest signal track of the strap layer with room
    for the route's wire across the cell (the rule's width and spacing
    clear of the straps left), and route_net brings that wire in along the
    track onto it (the wire as wide and as far from the straps as the route
    rule says, at least as the straps are: least), from the first vertical
    signal track past the cell's edge
    on that side: that way must be clear too (other cells' straps, other
    nets' wires on the layer, by the rule's spacing), else the pin keeps its
    strap (no access from the side). The track is one within the strap
    stack's height of the stack: no long pin wire. The other pins keep
    their straps (a
    route from above or below crosses them). Returns (straps, wires): the
    straps left, renumbered top first; a side pin's wire with strap None."""
    from core import netlist
    from core.pin_access import _rule, _signal_tracks
    tracks = next(iter(_signal_tracks(db, "y").values()), [])
    columns = next(iter(_signal_tracks(db, "x").values()), [])
    box = objects.inst_bbox(db, row)
    others = [tuple(float(c) for c in r["rect"].split()) for r in db.strap_rows()
              if r["inst"] != row["name"] and r["layer"] == layer] + \
        [tuple(float(c) for c in r["rect"].split()) for r in db.net_wire_rows()
         if r["layer"] == layer and r["kind"] != "cross"] + \
        _side_ways(db, row["name"], tracks, columns, layer)      # other cells' side pins
    side = {}
    height = max(r[3] for _, r in straps) - min(r[1] for _, r in straps) if straps else 0.0
    for pin, net, rect, k in wires:
        if net != SIGNAL:
            continue
        other = _other_end(db, row["name"], pin, height)
        at = objects.pin_centre(db, row["name"], pin)
        if other is not None and len(other) == 2 and \
                abs(other[0] - at[0]) > abs(other[1] - at[1]):
            side[pin] = "left" if other[0] < at[0] else "right"
    if not side or not tracks:
        return straps, wires
    strap_of = {pin: k for pin, _, _, k in wires}
    stack = (min(r[0] for _, r in straps), min(r[1] for _, r in straps),
             max(r[2] for _, r in straps), max(r[3] for _, r in straps))
    near = stack[3] - stack[1]
    gone = {strap_of[p] for p in side}
    taken = [r for k, (_, r) in enumerate(straps, start=1) if k not in gone]
    on, lines = {}, []                   # pin -> (track y, wire width)
    for pin, _, rect, k in wires:
        if pin not in side:
            continue
        net = netlist.pin_net(db, row["name"], pin)
        w, s = (max(a, b) for a, b in zip(_rule(db, net, layer), least))
        slot = (straps[k - 1][1][1] + straps[k - 1][1][3]) / 2
        x = (rect[0] + rect[2]) / 2
        if side[pin] == "left":          # out to the first vertical track past the edge
            past = [c for c in columns if c < box[0] - TOL]
            way = (max(past) - w / 2, x) if past else None
        else:
            past = [c for c in columns if c > box[2] + TOL]
            way = (x, min(past) + w / 2) if past else None
        free = [y for y in tracks if way is not None and
                stack[1] - near - TOL <= y <= stack[3] + near + TOL and
                not any(y + w / 2 + s > r[1] + TOL and y - w / 2 - s < r[3] - TOL
                        for r in taken) and
                not any(y + w / 2 + s > r[1] + TOL and y - w / 2 - s < r[3] - TOL and
                        way[1] + s > r[0] + TOL and way[0] - s < r[2] - TOL for r in others)]
        if not free:
            gone.discard(k)              # no room: it keeps its strap
            lines.append(f"{pin} (net {net} from the {side[pin]}): no {layer} signal track "
                         f"free from it out past the cell's {side[pin]} edge, keeps its strap")
            continue
        y = min(free, key=lambda c: abs(c - slot))
        taken.append((rect[0], y - w / 2, rect[2], y + w / 2))
        on[pin] = (y, w)
        lines.append(f"{pin} (net {net} from the {side[pin]}): no strap, its pin wire on to "
                     f"{layer} y {_num(round(y, 6))}")
    keep = [(n, r) for k, (n, r) in enumerate(straps, start=1) if k not in gone]
    seq = {k: j for j, k in enumerate([k for k in range(1, len(straps) + 1)
                                        if k not in gone], start=1)}
    found = []
    for pin, net, rect, k in wires:
        if pin in on:
            y, w = on[pin]
            lo, hi = _pin_span(db, row, pin)
            found.append((pin, net, tuple(round(v, 6) for v in
                                          (rect[0], min(lo, y - w / 2), rect[2],
                                           max(hi, y + w / 2))), None))
        else:
            found.append((pin, net, rect, seq[k]))
    info(f"  pins reached from the side, on {layer} directly: " + "; ".join(lines), out)
    return keep, found


def _side_ways(db, skip, tracks, columns, layer):
    """[rect] of the ways out of the side pins of the other instances (not
    skip): on the track the pin wire was extended to, from the first vertical
    signal track left of the cell to the first right of it, as wide as the
    route's wire (as route_net.side_ways)."""
    import bisect
    from core import netlist
    from core.pin_access import _rule
    found = []
    for w in db.pin_wire_rows():
        if w["strap"] is not None or w["inst"] == skip:
            continue
        row = db.inst_row(w["inst"])
        box = objects.inst_bbox(db, row) if row is not None else None
        at = objects.pin_centre(db, w["inst"], w["pin"])
        if box is None or at is None:
            continue
        width, _ = _rule(db, netlist.pin_net(db, w["inst"], w["pin"]), layer)
        x1, y1, x2, y2 = (float(c) for c in w["rect"].split())
        ys = [c for c in tracks if y1 + width / 2 - TOL <= c <= y2 - width / 2 + TOL]
        if not ys:
            continue
        y = max(ys, key=lambda c: abs(c - at[1]))
        k = bisect.bisect_left(columns, box[0] - TOL)
        lo = columns[k - 1] if k > 0 else box[0]
        k = bisect.bisect_right(columns, box[2] + TOL)
        hi = columns[k] if k < len(columns) else box[2]
        found.append((lo - width / 2, y - width / 2, hi + width / 2, y + width / 2))
    return found


def _pin_span(db, row, pin):
    """(lo, hi) y of the pin's shapes on any layer, placed."""
    ys = [c for _, _, pts in objects.pin_shapes(db, f"pin:{row['name']}/{pin}")
          for c in pts[1::2]]
    return min(ys), max(ys)


def _tech_layer(db, layer):
    row = db.layer_row(layer)
    if row is None:
        raise HtreeError(NO_LAYER, f"route_pin: layer '{layer}' is not in tech (tech layers: "
                         f"{' '.join(db.layer_names())})")
    return row


AUTO = "auto"           # -spec_name auto: each instance the spec its nets' way picks


def _auto_specs(session, opts):
    """-spec_name auto: [(spec name, spec, [instances])]. Of the named specs
    (-spec's file, else those read_pin_spec read), the one whose
    routing_direction is the way the instance's nets run there: from the
    middle of the cell to every other pin and port on the nets of its pins
    (the cell before it, the cells after it), the x distances summed against
    the y ones; horizontal when x is more, else vertical (also for a cell on
    no net). The first spec of each direction is taken."""
    db, out = session.db, session.out
    if "-spec" in opts:
        specs = [(n, s) for n, s in load_specs(opts["-spec"]).items() if n]
    else:
        specs = [(n, db.pin_spec_def(n)[0]) for n in db.pin_spec_def_names()]
    by_way = {}
    for name, spec in specs:
        way = spec.get("routing_direction")
        if way in ("horizontal", "vertical") and way not in by_way:
            by_way[way] = (name, spec)
    if not by_way:
        raise HtreeError(BAD_SPEC, "route_pin: -spec_name auto: no named spec has a "
                         "routing_direction (horizontal or vertical) to pick from "
                         "(read_pin_spec -file <yaml>)")
    from core import netlist
    pins = netlist.pins(db)
    groups, picks = {}, {}
    for inst in inst_names(session, opts["-inst"]):
        box = objects.inst_bbox(db, db.inst_row(inst))
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        dx = dy = 0.0
        for pin, net in pins.get(inst, {}).items():
            for e in netlist.ends(db, net):
                if e.kind == "pin" and e.inst == inst:
                    continue
                at = objects.pin_centre(db, e.inst, e.pin) if e.kind == "pin" else \
                    objects.port_centre(db, e.pin)
                if at is not None:
                    dx, dy = dx + abs(at[0] - cx), dy + abs(at[1] - cy)
        way = "horizontal" if dx > dy else "vertical"
        if way not in by_way:
            raise HtreeError(BAD_SPEC, f"route_pin: -spec_name auto: {inst}'s nets run "
                             f"{way}ly and no named spec has routing_direction {way} "
                             f"(have: {' '.join(n for n, _ in by_way.values())})")
        name, spec = by_way[way]
        key = (name, json.dumps(spec, sort_keys=True))
        groups.setdefault(key, (name, spec, []))[2].append(inst)
        picks.setdefault(name, []).append(inst)
    for name, insts in picks.items():
        way = next(w for w, (n, _) in by_way.items() if n == name)
        info(f"route_pin: -spec_name auto: {name} for {len(insts)} instance(s), their nets "
             f"run {way}ly: " + " ".join(insts[:8]) + (" ..." if len(insts) > 8 else ""), out)
    return list(groups.values())


def _with_inst(argv, names):
    """argv with -inst giving names."""
    out, skip = [], False
    for k, word in enumerate(argv):
        if skip:
            skip = False
            continue
        if word == "-inst":
            skip = True
            continue
        out.append(word)
    return ["-inst", " ".join(names)] + out


def spec_of(db, opts):
    """(spec, its name or file, or None for the built-in one) of route_pin's
    -spec_name / -spec: a spec read_pin_spec loaded, by name; or one of a
    -spec file (by -spec_name when the file names more than one)."""
    name = opts.get("-spec_name")
    if "-spec" in opts:
        specs = load_specs(opts["-spec"])
        if name is not None:
            if name not in specs:
                have = " ".join(n for n in specs if n) or "one, not named"
                raise HtreeError(BAD_SPEC, f"route_pin: {opts['-spec']} has no spec named "
                                 f"'{name}' (specs: {have})")
            return specs[name], name
        if len(specs) > 1:
            raise HtreeError(BAD_SPEC, f"route_pin: {opts['-spec']} names {len(specs)} specs "
                             f"({' '.join(specs)}): give -spec_name, or read_pin_spec -file "
                             f"{opts['-spec']} and -spec_name alone")
        (only, spec), = specs.items()
        return spec, only or opts["-spec"]
    if name is not None:
        kept = db.pin_spec_def(name)
        if kept is None:
            names = db.pin_spec_def_names()
            raise HtreeError(BAD_SPEC, f"route_pin: no pin routing spec named '{name}' "
                             + (f"(read: {' '.join(names)})" if names else
                                "(read_pin_spec -file <yaml> reads them)"))
        return kept[0], name
    return DEFAULTS, None


def load_specs(path):
    """{name: spec} of a YAML file: under 'pin_routing', named specs (each
    a mapping of spec keys: vertical_routing: {width: ..., ...}), or the keys
    of one spec, not named ({None: spec})."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        raise HtreeError(BAD_SPEC, f"route_pin: cannot read -spec '{path}': {exc.strerror}")
    except yaml.YAMLError as exc:
        raise HtreeError(BAD_SPEC, f"route_pin: {path} is not valid YAML: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("pin_routing"), dict):
        raise HtreeError(BAD_SPEC, f"route_pin: {path} must have a 'pin_routing:' section")
    data = data["pin_routing"]
    if not data or any(k in DEFAULTS for k in data):        # one spec, its keys
        return {None: _parse_spec(path, data, "pin_routing")}
    found = {}
    for name, body in data.items():
        if not isinstance(name, str) or not name or any(c.isspace() for c in name):
            raise HtreeError(BAD_SPEC, f"route_pin: {path}: pin_routing: spec name {name!r} "
                             f"must be one word")
        if not isinstance(body, dict):
            raise HtreeError(BAD_SPEC, f"route_pin: {path}: pin_routing.{name} is not a spec "
                             f"key (keys: {', '.join(DEFAULTS)}) nor a named spec (a mapping "
                             f"of those keys)")
        found[name] = _parse_spec(path, body, f"pin_routing.{name}")
    return found


def load_spec(path, name=None):
    """The spec in a YAML file, on top of DEFAULTS: every key is optional,
    unknown keys are errors. A file of named specs: the one named (name), or
    its only one."""
    specs = load_specs(path)
    if name is not None:
        return specs[name]
    if len(specs) > 1:
        raise HtreeError(BAD_SPEC, f"route_pin: {path} names {len(specs)} specs "
                         f"({' '.join(specs)}): give -spec_name")
    return next(iter(specs.values()))


def _parse_spec(path, data, where):
    """One spec (a mapping of spec keys) on top of DEFAULTS."""
    def bad(key, text):
        return HtreeError(BAD_SPEC, f"route_pin: {path}: {where}.{key} {text}")

    _known(data, DEFAULTS, "", bad)
    spec = {k: v for k, v in DEFAULTS.items() if k != "pins"}
    if "cell_pattern" in data:
        value = data["cell_pattern"]
        found = [value] if isinstance(value, str) else value
        if not isinstance(found, list) or not found or \
                not all(isinstance(p, str) and p.strip() for p in found):
            raise bad("cell_pattern", f"must be a library cell name or glob (INV*_D*), or a "
                      f"list of them, got {value!r}")
        spec["cell_pattern"] = [p.strip() for p in found]
    if "routing_direction" in data:
        value = data["routing_direction"]
        if value is not None and str(value).lower() not in ("vertical", "horizontal"):
            raise bad("routing_direction", f"must be vertical (the net comes from above or "
                      f"below) or horizontal (from the left or the right), got {value!r}")
        spec["routing_direction"] = None if value is None else str(value).lower()
    for key in ("width", "spacing"):
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise bad(key, f"must be a positive number in microns, got {value!r}")
            spec[key] = float(value)
    if "max_strap_extension" in data:
        value = data["max_strap_extension"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise bad("max_strap_extension", f"must be a number >= 0 in microns, got {value!r}")
        spec["max_strap_extension"] = float(value)
    if "nets" in data:
        nets = data["nets"]
        if not isinstance(nets, list) or not nets or \
                not all(isinstance(n, str) and n for n in nets):
            raise bad("nets", f"must be a list of net names, top to bottom, got {nets!r}")
        spec["nets"] = nets
    pins = data.get("pins") or {}
    if not isinstance(pins, dict):
        raise bad("pins", "must hold layer, horizontal_layer, vertical_layer and nets")
    _known(pins, DEFAULTS["pins"], "pins.", bad)
    spec["pins"] = dict(DEFAULTS["pins"])
    for key in ("layer", "horizontal_layer", "vertical_layer"):
        if key in pins:
            if key == "horizontal_layer" and (pins[key] is None or
                                              str(pins[key]).lower() == "none"):
                spec["pins"][key] = None         # no straps: the pin wires alone
                continue
            if not isinstance(pins[key], str) or not pins[key]:
                raise bad(f"pins.{key}", f"must be a layer name"
                          + (" or none (no straps)" if key == "horizontal_layer" else "")
                          + f", got {pins[key]!r}")
            spec["pins"][key] = pins[key]
    if "nets" in pins:
        pin_nets = pins["nets"]
        if not isinstance(pin_nets, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in pin_nets.items()):
            raise bad("pins.nets", f"must map pin names to nets ({{VDD: VDD_SOC, ...}}), "
                      f"got {pin_nets!r}")
        spec["pins"]["nets"] = pin_nets
    return spec


def dump_spec(spec, path, overwrite, out):
    """Write spec as a -spec file, laid out and commented for editing."""
    if os.path.exists(path) and not overwrite:
        raise HtreeError(DUMP_EXISTS, f"route_pin: '{path}' exists; use -overwrite to replace it")
    pins = spec["pins"]
    lines = [
        "# Pin routing spec for route_pin, written by route_pin -dump.",
        f"#   route_pin -inst <inst> -spec {os.path.basename(path)}",
        "# Every key is optional; a missing key keeps the built-in value.",
        "# Options given on the route_pin command line override this file.",
        "# Units: microns.",
        "",
        "pin_routing:",
        "  # The cells this spec is for (a glob on the library cell name, or a list",
        "  # of them): an instance of another cell is not routed.",
        "  cell_pattern: " + (_scalar(spec["cell_pattern"][0]) if len(spec["cell_pattern"]) == 1
                              else "[" + ", ".join(_scalar(p) for p in spec["cell_pattern"]) + "]"),
        "  # The way the nets come to the cells: vertical (from above or below, onto the",
        "  # straps) or horizontal (from the left or the right); route_net keeps to it.",
        "  # null: either way.",
        "  routing_direction: " + (spec.get("routing_direction") or "null"),
        f"  width: {_num(spec['width'])}            # strap width, every net",
        f"  spacing: {_num(spec['spacing'])}          # edge-to-edge gap between straps "
        "(pitch = width + spacing)",
        f"  max_strap_extension: {_num(spec['max_strap_extension'])}   # route_net may extend "
        "a strap this far past",
        "                         # each instance edge to reach the net's route",
        "",
        "  # One horizontal strap per entry, top to bottom. A net may repeat.",
        "  # Straps run the instance width and the stack is centred on the instance.",
        "  nets:",
        *(f"    - {_scalar(n)}" for n in spec["nets"]),
        "",
        "  # Cell pins to connect: pin -> strap net. Pins not listed (VNW, VPW) are",
        "  # not connected. Only the pin shapes on 'layer' are used.",
        "  # Straps run on horizontal_layer. Each pin reaches a strap of its net by a",
        "  # wire on vertical_layer, as wide as the pin (the widest of its shapes).",
        "  # Signal pins (SIGNAL) each get their own strap; power pins share.",
        "  pins:",
        *(f"    {key}: {_scalar(pins[key])}"
          for key in ("layer", "horizontal_layer", "vertical_layer")),
        "    nets:",
        *(f"      {_scalar(p)}: {_scalar(n)}" for p, n in pins["nets"].items()),
    ]
    try:
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as exc:
        raise HtreeError(BAD_SPEC, f"route_pin: cannot write '{path}': {exc.strerror}")
    info(f"Pin routing spec written to '{os.path.abspath(path)}'", out)
    return path


def _scalar(text):
    """text as a YAML scalar, quoted only when it has to be."""
    return yaml.safe_dump(text, default_flow_style=True).removesuffix("\n...\n").strip()


def _known(data, allowed, prefix, bad):
    unknown = [k for k in data if k not in allowed]
    if unknown:
        raise bad(f"{prefix}{unknown[0]}", f"is not a spec key (keys: "
                  f"{', '.join(prefix + k for k in allowed)})")


def _positive(text, option, default):
    if text is None:
        return default
    try:
        value = float(text)
    except ValueError:
        value = None
    if value is None or value <= 0:
        raise HtreeError(USAGE, f"route_pin: {option} must be a positive number in microns, "
                         f"got '{text}'")
    return value


def _check_tech(db, lrow, nets, width, spacing, out):
    """Width and spacing against the tech rules of the layer."""
    layer = lrow["name"]
    if (lrow["direction"] or "").upper() not in ("", "HORIZONTAL"):
        warn(BELOW_TECH, f"{layer} is a {lrow['direction'].lower()} layer; the straps are "
             f"horizontal", out)
    min_width = tech_min_width(lrow)
    if min_width is not None and width < min_width - TOL:
        warn(BELOW_TECH, f"width {_num(width)} is below the {layer} minimum width "
             f"{_num(min_width)}", out)
    needed, source = tech_spacing(db, lrow, width)
    if needed is None:
        info(f"  {layer} has no spacing rule in tech; spacing {_num(spacing)} not checked", out)
    elif spacing < needed - TOL:
        warn(BELOW_TECH, f"spacing {_num(spacing)} is below the {layer} tech spacing "
             f"{_num(needed)} for a {_num(width)} wide wire ({source})", out)
    else:
        info(f"  tech: {layer} min width {_num(min_width) if min_width is not None else 'none'}, "
             f"spacing for width {_num(width)} is {_num(needed)} ({source}): OK", out)
    for k in range(1, len(nets)):                # adjacent straps of one net could merge
        if nets[k] == nets[k - 1]:
            merged = round(2 * width + spacing, 6)
            m_needed, _ = tech_spacing(db, lrow, merged)
            note = "" if m_needed is None else \
                f"; merged, the tech spacing to it would be {_num(m_needed)}"
            info(f"  straps {k} and {k + 1} are both {nets[k]} and adjacent: kept as two "
                 f"straps (one merged strap would be {_num(merged)} wide{note})", out)


def _check_grid(db, shapes, out, what="straps"):
    """shapes: (name, rect); straps are named by their number."""
    grid = db.tech_row()["manufacturing_grid"]
    if not grid:
        return
    off = [str(k if what == "straps" else n) for k, (n, r) in enumerate(shapes, start=1)
           if any(abs(v / grid - round(v / grid)) > 1e-6 for v in r)]
    if off:
        warn(OFF_GRID, f"{what} {' '.join(off)} have edges off the manufacturing "
             f"grid {_num(grid)}", out)


def _check_tracks(db, layer, straps, out):
    """Per strap, ' on track <y>' or ' off track by <d>' against the layer's
    DEF TRACKS Y; empty text when there are no such tracks."""
    tracks = db.track_positions(layer, "y") if db.has_design() else []
    if not tracks:
        info(f"  no DEF TRACKS Y on {layer}: track alignment not checked", out)
        return [""] * len(straps)
    lines, shifts = [], []
    for _, r in straps:
        c = (r[1] + r[3]) / 2
        nearest = min(tracks, key=lambda t: abs(t - c))
        d = round(c - nearest, 6)
        shifts.append(d)
        lines.append(f"  centre {_num(round(c, 6))} on track" if abs(d) <= TOL else
                     f"  centre {_num(round(c, 6))} off track {_num(nearest)} by {_num(d)}")
    if any(abs(d) > TOL for d in shifts):
        same = all(abs(d - shifts[0]) <= TOL for d in shifts)
        hint = f"; moving the stack by {_num(-shifts[0])} puts every strap on a track" \
            if same else ""
        warn(OFF_TRACK, f"{sum(abs(d) > TOL for d in shifts)} of {len(straps)} strap centres "
             f"are not on {layer} tracks{hint}", out)
    return lines


def _route_pins(db, row, straps, pin_spec, vrow, out):
    """A vertical wire on the vertical layer from each connected pin over the
    whole strap stack, so it crosses every strap (vias come later). The wire
    is as wide as the pin's widest shape on the pin layer, takes that shape's
    x span, and covers all the pin's shapes. Each wire is also given the strap
    of its net it is to connect to, the nearest one; pins of SIGNAL each need
    a strap of their own (they are different nets), the other nets share.
    The SIGNAL straps go by where the pins lie in the placed cell: the
    higher pin (the centre of its shapes) takes the higher strap; of pins
    as high, the input first. Flipping the cell about the x axis (N to FS)
    so swaps their straps (legalize_placement picks the orientation that
    puts the input on the side its net comes from).
    Returns (pin, net, rect, strap seq) per wire."""
    cell = db.lib_cell_row(row["ref_cell"])
    pins = db.lib_pin_names(cell["id"])
    pin_layer, vlayer = pin_spec["layer"], vrow["name"]
    skipped = [p for p in pins if p not in pin_spec["nets"]]
    info(f"  pin wires on {vlayer} from the {pin_layer} pins"
         + (f" ({', '.join(skipped)} not connected):" if skipped else ":"), out)
    found = {}                                   # pin -> (net, [shape rects])
    for pin, net in pin_spec["nets"].items():
        if pin not in pins:
            warn(NO_PIN, f"{row['ref_cell']} has no pin {pin}", out)
            continue
        shapes = [_bbox(pts) for layer, _, pts in
                  objects.pin_shapes(db, f"pin:{row['name']}/{pin}") if layer == pin_layer]
        if not shapes:
            warn(NO_PIN, f"pin {pin} has no {pin_layer} shape", out)
            continue
        if not any(n == net for n, _ in straps):
            warn(NO_PIN, f"pin {pin} needs a {net} strap; the stack has none", out)
            continue
        found[pin] = (net, shapes)

    def wire(pin, k):
        """(rect, length) of a wire from pin to strap k: picks the strap."""
        shapes = found[pin][1]
        wide = max(shapes, key=lambda r: r[2] - r[0])
        r = straps[k - 1][1]
        lo = min(min(s[1] for s in shapes), r[1])
        hi = max(max(s[3] for s in shapes), r[3])
        return tuple(round(v, 6) for v in (wide[0], lo, wide[2], hi)), hi - lo

    stack_lo = min(r[1] for _, r in straps)
    stack_hi = max(r[3] for _, r in straps)

    choice = {}                                  # pin -> strap seq
    signal_pins = [p for p, (n, _) in found.items() if n == SIGNAL]
    for pin, (net, _) in found.items():
        if net != SIGNAL:
            ks = [k for k, (n, _) in enumerate(straps, start=1) if n == net]
            choice[pin] = min(ks, key=lambda k: wire(pin, k)[1])
    if signal_pins:
        ks = [k for k, (n, _) in enumerate(straps, start=1) if n == SIGNAL]
        if len(ks) < len(signal_pins):
            warn(NO_PIN, f"{len(signal_pins)} signal pins ({' '.join(signal_pins)}) but only "
                 f"{len(ks)} {SIGNAL} straps: each signal pin needs its own; "
                 f"{' '.join(signal_pins[len(ks):])} not routed", out)
            signal_pins = signal_pins[:len(ks)]
        def height(p):                           # the centre of its shapes, placed
            shapes = found[p][1]
            return round((min(s[1] for s in shapes) + max(s[3] for s in shapes)) / 2, 6)
        order = sorted(signal_pins, key=lambda p: (-height(p),
                                                   _direction_rank(db, row["ref_cell"], p)))
        choice.update(zip(order, sorted(ks)[:len(order)]))     # strap 1 is the top

    wires = []
    for pin, (net, shapes) in found.items():
        if pin not in choice:
            continue
        k = choice[pin]
        x1, lo, x2, hi = wire(pin, k)[0]
        rect = (x1, min(lo, stack_lo), x2, max(hi, stack_hi))     # over every strap
        length = rect[3] - rect[1]
        wires.append((pin, net, rect, k))
        info(f"    pin_wire:{row['name']}/{pin:<4} {net:<8} -> strap {k}: x {_num(rect[0])} .. "
             f"{_num(rect[2])} (width {_num(round(rect[2] - rect[0], 6))}), y {_num(rect[1])} "
             f".. {_num(rect[3])} (length {_num(round(length, 6))}), {len(shapes)} pin "
             f"shape(s)", out)
        missed = [s for s in shapes if s[2] <= rect[0] + TOL or s[0] >= rect[2] - TOL]
        if missed:
            warn(NO_PIN, f"pin {pin}: {len(missed)} of its {pin_layer} shapes are not under "
                 f"the {vlayer} wire (it takes the widest shape's x span)", out)
    _check_wires(db, vrow, wires, out)
    return wires


def _direction_rank(db, ref_cell, pin):
    """0 for an input pin, 1 for an output, 2 for any other."""
    lp = db.lib_pin_row(ref_cell, pin)
    direction = (lp["direction"] or "").lower() if lp is not None else ""
    return 0 if direction.startswith("in") else 1 if direction.startswith("out") else 2


def _bbox(pts):
    return min(pts[0::2]), min(pts[1::2]), max(pts[0::2]), max(pts[1::2])


def _check_wires(db, vrow, wires, out):
    """Pin wires against the vertical layer: direction, minimum width, and
    the tech spacing between wires that run side by side."""
    layer = vrow["name"]
    if (vrow["direction"] or "").upper() not in ("", "VERTICAL"):
        warn(BELOW_TECH, f"{layer} is a {vrow['direction'].lower()} layer; the pin wires are "
             f"vertical", out)
    min_width = tech_min_width(vrow)
    for pin, _, r, _ in wires:
        if min_width is not None and r[2] - r[0] < min_width - TOL:
            warn(BELOW_TECH, f"pin wire {pin} width {_num(round(r[2] - r[0], 6))} is below the "
                 f"{layer} minimum width {_num(min_width)}", out)
    for i, (p, _, a, _) in enumerate(wires):
        for q, _, b, _ in wires[i + 1:]:
            if a[1] >= b[3] or b[1] >= a[3]:
                continue                         # not side by side
            gap = max(b[0] - a[2], a[0] - b[2])
            needed, _ = tech_spacing(db, vrow, max(a[2] - a[0], b[2] - b[0]))
            if needed is not None and gap < needed - TOL:
                warn(BELOW_TECH, f"pin wires {p} and {q} are {_num(round(gap, 6))} apart; "
                     f"{layer} needs {_num(needed)}", out)
    _check_grid(db, [(p, r) for p, _, r, _ in wires], out, "pin wires")
