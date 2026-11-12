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
"""

import fnmatch
import itertools
import os

import yaml

from core import objects
from core.commands.create_route_rule import tech_min_width, tech_spacing
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "route_pin"
SUMMARY = "Add horizontal straps over an instance (net stack, width, spacing)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-inst": "value", "-spec": "value", "-layer": "value", "-nets": "value",
           "-width": "value", "-spacing": "value", "-dump": "value", "-overwrite": "flag"}

USAGE = 1
NO_INST = 160
NO_LAYER = 161
REPLACED = 162
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
DEFAULTS = {"width": 0.72, "spacing": 0.72, "max_strap_extension": 3.0,
            "nets": ["VSS", "VDD_SOC", "SIGNAL", "VSS", "SIGNAL", "VDD_SOC", "VDD_SOC"],
            "pins": {"layer": "D12", "horizontal_layer": "IA", "vertical_layer": "H2",
                     "nets": {"VDD": "VDD_SOC", "VSS": "VSS", "A": "SIGNAL", "Y": "SIGNAL"}}}
SIGNAL = "SIGNAL"            # a signal strap: each pin on it is a net of its own
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    spec = load_spec(opts["-spec"]) if "-spec" in opts else DEFAULTS
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
                         "[-spec <yaml>] [-layer <layer>] [-nets {net ...}] [-width <w>] "
                         "[-spacing <s>], or route_pin -dump <yaml> [-overwrite]")
    db = session.db
    objects.require_tech(db)
    for layer in (spec["pins"]["horizontal_layer"], spec["pins"]["vertical_layer"]):
        _tech_layer(db, layer)
    names = inst_names(session, opts["-inst"])
    for name in names:           # every instance is checked before any is routed
        row = db.inst_row(name)
        if objects.inst_bbox(db, row) is None:
            raise HtreeError(NO_INST, f"route_pin: cell {row['ref_cell']} of {name} has no "
                             f"SIZE")
    handles = []
    for name in names:
        handles += _route_inst(session, name, spec, opts)
    if len(names) > 1:
        info(f"route_pin: {len(names)} instances routed", session.out)
    return tuple(handles)


def inst_names(session, text):
    """Instance names from a Tcl list of names, glob patterns (*temp_*) and
    inst: handles, in database order for patterns; each word must match."""
    every = session.db.inst_names()
    names = []
    for word in session.split_list(text):
        word = word.removeprefix("inst:")
        hits = [n for n in every if fnmatch.fnmatchcase(n, word)]
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
    ext = spec["max_strap_extension"]
    info(f"  route_net may extend each strap up to {_num(ext)} past each instance edge "
         f"(max_strap_extension) to reach its route", out)
    replaced = db.set_straps(name, [(n, layer, " ".join(_num(v) for v in r)) for n, r in straps],
                             [(p, n, vrow["name"], " ".join(_num(v) for v in r), k)
                              for p, n, r, k in wires], ext)
    if replaced:
        warn(REPLACED, f"replaced the {replaced} straps {name} had, and its pin wires", out)
    return ([f"strap:{name}/{k}" for k in range(1, len(straps) + 1)]
            + [f"pin_wire:{name}/{p}" for p, _, _, _ in wires])


def _tech_layer(db, layer):
    row = db.layer_row(layer)
    if row is None:
        raise HtreeError(NO_LAYER, f"route_pin: layer '{layer}' is not in tech (tech layers: "
                         f"{' '.join(db.layer_names())})")
    return row


def load_spec(path):
    """The spec in a YAML file, on top of DEFAULTS: every key under
    'pin_routing' is optional, unknown keys are errors."""
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

    def bad(key, text):
        return HtreeError(BAD_SPEC, f"route_pin: {path}: pin_routing.{key} {text}")

    _known(data, DEFAULTS, "", bad)
    spec = {k: v for k, v in DEFAULTS.items() if k != "pins"}
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
            if not isinstance(pins[key], str) or not pins[key]:
                raise bad(f"pins.{key}", f"must be a layer name, got {pins[key]!r}")
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
        best = min(itertools.permutations(ks, len(signal_pins)),
                   key=lambda pick: sum(wire(p, k)[1] for p, k in zip(signal_pins, pick)))
        choice.update(zip(signal_pins, best))

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
