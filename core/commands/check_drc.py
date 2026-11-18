"""check_drc [-check_shorts_only | -check_spacing_only | -check_open_only]
[-layer_range <bottom>:<top>] [-file <file> [-overwrite]]: check the routing
the tool made for shorts, spacing and width violations, and opens.

    check_drc
    check_drc -check_shorts_only -layer_range H2:IA
    check_drc -file drc.rpt -overwrite

Spacing and width are checked twice and reported apart: against the tech LEF
(tech) and against the route rule of each wire (custom). A summary table is
printed, then one line per violation with its box. The run is kept for the
GUI (db.drc), which lists the violations in its DRC table.
"""

import os
from collections import Counter

from core import drc, objects, vias
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "check_drc"
SUMMARY = "Check the routing for shorts, spacing and width violations, and opens"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-check_shorts_only": "flag", "-check_spacing_only": "flag",
           "-check_open_only": "flag", "-layer_range": "value",
           "-file": "value", "-overwrite": "flag"}

USAGE = 1
BAD_RANGE = 247
EXISTS = 248
WRITE_FAILED = 249
VIOLATIONS = 250

ONLY = ("-check_shorts_only", "-check_spacing_only", "-check_open_only")
# The rows of the summary, and the heading of each one's violations.
ROWS = [(drc.SHORT, "", "Shorts"),
        (drc.SPACING, drc.TECH, "Tech spacing (tech LEF)"),
        (drc.WIDTH, drc.TECH, "Tech width (tech LEF)"),
        (drc.SPACING, drc.CUSTOM, "Custom spacing (route rules)"),
        (drc.WIDTH, drc.CUSTOM, "Custom width (route rules)"),
        (drc.OPEN, "signal", "Opens, signal nets"),
        (drc.OPEN, "power", "Opens, power nets")]


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    only = [o for o in ONLY if opts[o]]
    if len(only) > 1:
        raise HtreeError(USAGE, f"check_drc: give one of {' '.join(only)}, not "
                         f"{'both' if len(only) == 2 else 'all'}")
    if opts["-overwrite"] and "-file" not in opts:
        raise HtreeError(USAGE, "check_drc: -overwrite needs -file")
    objects.require_tech(db)
    order = {name: k for name, (k, _) in vias.tech_layers(db).items()}
    layers = _range(opts["-layer_range"], order) if "-layer_range" in opts else None
    path = opts.get("-file")
    if path is not None and os.path.exists(path) and not opts["-overwrite"]:
        raise HtreeError(EXISTS, f"check_drc: '{path}' exists; use -overwrite to replace it")
    shorts = not only or only == ["-check_shorts_only"]
    spacing = not only or only == ["-check_spacing_only"]
    opens = not only or only == ["-check_open_only"]

    design = drc.collect(db)
    tech = drc.tech_rules(db)
    found = []
    if shorts or spacing:
        found += drc.check_geometry(design, tech, drc.custom_rules(db), layers,
                                    shorts=shorts, spacing=spacing)
    if opens:
        found += drc.check_opens(design, order, layers)
    ran = [r for r in ROWS if {drc.SHORT: shorts, drc.OPEN: opens}.get(r[0], spacing)]

    head = _checked(design, tech, order, layers, shorts or spacing, opens)
    table = _summary(found, ran, order)
    sections = _sections(found, ran, order)
    detail = _detail(sections)
    # For the DRC table of the GUI.
    db.drc = drc.Report(head, table, [(title, v) for title, mine in sections for v in mine])
    if path is None:
        for line in head + table + detail:
            info(line, out)
    else:
        try:
            with open(path, "w") as f:
                f.write("\n".join(head + table + detail) + "\n")
        except OSError as exc:
            raise HtreeError(WRITE_FAILED, f"check_drc: cannot write '{path}': {exc}")
        for line in head + table:
            info(line, out)
        info(f"Report written to '{os.path.abspath(path)}'", out)
    if found:
        warn(VIOLATIONS, f"check_drc: {len(found)} violation(s)", out)
    else:
        info("check_drc: no violations", out)
    return str(len(found))


def _range(text, order):
    """The layers of '<bottom>:<top>' (either order; one layer: that one):
    every layer of the tech from the one to the other."""
    names = [w.strip() for w in text.split(":")]
    if len(names) > 2 or not all(names):
        raise HtreeError(BAD_RANGE, f"check_drc: -layer_range '{text}' is not "
                         f"<bottom>:<top>, as in H2:IA")
    for name in names:
        if name not in order:
            raise HtreeError(BAD_RANGE, f"check_drc: -layer_range: no layer '{name}' in "
                             f"the tech")
    low, high = sorted(order[n] for n in (names[0], names[-1]))
    return {name for name, k in order.items() if low <= k <= high}


def _checked(design, tech, order, layers, geometry, opens):
    """The lines that say what was looked at, and what was not."""
    inside = lambda s: layers is None or s.layer in layers
    shapes = [s for s in design.shapes if inside(s)]
    count = Counter(s.what for s in shapes)
    used = sorted({s.layer for s in shapes}, key=lambda name: order.get(name, -1))
    lines = ["check_drc: " + ("every layer" if layers is None else "layers "
             + " ".join(sorted(layers, key=order.get))),
             f"  Shapes: {count['wire']} wires, {count['pad']} via pads, {count['pin']} pin "
             f"shapes on {' '.join(used) or 'no layer'}",
             f"  Vias  : {len(design.vias)}"
             + (f", {design.no_definition} without a definition (no pads: checked as "
                f"connections only)" if design.no_definition else ""),
             f"  Nets  : {len(design.nets)} signal nets, {len(design.power - set(design.nets))} "
             f"power nets"]
    if geometry:
        routed = sorted({s.layer for s in shapes if s.what != "pin"},
                        key=lambda name: order.get(name, -1))
        unknown = [name for name in routed if tech(name) is None]
        if unknown:
            lines.append(f"  Not checked (no routing layer of the tech): {' '.join(unknown)}")
        skipped = [f"{name}({tech(name).skipped})" for name in routed
                   if tech(name) is not None and tech(name).skipped]
        if skipped:
            lines.append("  Spacing tables not applied (LEF58 or of a kind not read): "
                         + " ".join(skipped))
    return lines


def _layer_key(order):
    return lambda v: (order.get(v.layer, -1), v.bbox)


def _summary(found, ran, order):
    count = Counter((v.check, v.source, v.layer) for v in found)
    lines = [f"  {'Check':<9} {'Rule':<7} {'Layer':<7} Violations",
             f"  {'-' * 9} {'-' * 7} {'-' * 7} ----------"]
    for check, source, _ in ran:
        mine = sorted((layer for c, s, layer in count if (c, s) == (check, source)),
                      key=lambda name: order.get(name, -1))
        for layer in mine or ["-"]:
            lines.append(f"  {check:<9} {source or '-':<7} {layer or '-':<7} "
                         f"{count[check, source, layer] if mine else 0}")
    lines.append(f"  {'Total':<25} {len(found)}")
    return lines


def _sections(found, ran, order):
    """[(title, its violations)] of the checks that found any, in the order
    of the report."""
    sections = []
    for check, source, title in ran:
        mine = sorted((v for v in found if (v.check, v.source) == (check, source)),
                      key=_layer_key(order))
        if mine:
            sections.append((title, mine))
    return sections


def _detail(sections):
    """One line per violation: layer, box, what is wrong."""
    lines = []
    for title, mine in sections:
        lines.append(f"{title}: {len(mine)}")
        for v in mine:
            lines.append(f"  {v.layer + ' ' if v.layer else ''}{drc.box_text(v.bbox)}  {v.text}")
    return lines
