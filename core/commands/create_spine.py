"""create_spine -name <spine> -spec_name <spine_spec> -location {x y} [-build_direction +x|-x|+y|-y]
(-validate [-show] [-ref_cell <cell>] | -build -ref_cell <cell>):
place a spine spec's inverter tree and stubs as spine <spine>, whose
instances are named <spine>_<level>_<cell>.

    -validate   compute the placement and report every warning; the design
                is not changed. -show also draws a schematic tab in the GUI.
    -build      create the instances, stubs and nets in the design, ignoring
                the warnings (run -validate first to see them).

The root cell (L1_inv1) sits at -location; the stubs run from there up
(vertical spine) or right (horizontal spine). See core/spine_build.py.
"""

from core import objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import rect_in_polygon
from core.spine_build import SpecCell, SpecData, SpineError, plan

NAME = "create_spine"
SUMMARY = "Validate (and show) or build a spine spec at a location"

USAGE = 1
NO_QT = 100
NO_DISPLAY = 101
NO_SPEC = 150
BAD_SPEC = 151
NO_CELL = 152
EXISTS = 153
WARN_CODES = {"over": 154, "spread": 155, "depth": 156, "overlap": 157, "dummy": 158,
              "outside": 159}


def run(session, argv):
    opts, _ = parse_options(NAME, argv, {
        "-name": "value", "-spec_name": "value", "-location": "value", "-build_direction": "value",
        "-ref_cell": "value", "-validate": "flag", "-build": "flag", "-show": "flag"})
    usage = ("Usage: create_spine -name <spine> -spec_name <spine_spec> -location {x y} "
             "[-build_direction +x|-x|+y|-y] (-validate [-show] [-ref_cell <cell>] | "
             "-build -ref_cell <cell>)")
    if "-name" not in opts or "-spec_name" not in opts or "-location" not in opts:
        raise HtreeError(USAGE, f"create_spine: -name, -spec_name and -location are required. "
                         f"{usage}")
    if opts["-validate"] == opts["-build"]:
        raise HtreeError(USAGE, f"create_spine: give exactly one of -validate and -build. "
                         f"{usage}")
    if opts["-show"] and not opts["-validate"]:
        raise HtreeError(USAGE, "create_spine: -show works only with -validate; a built "
                         "spine shows in the layout tab (Spine checkbox)")
    if opts["-build"] and "-ref_cell" not in opts:
        raise HtreeError(USAGE, f"create_spine: -build needs -ref_cell, the inverter cell "
                         f"to place. {usage}")
    try:
        location = tuple(float(v) for v in session.split_list(opts["-location"]))
    except ValueError:
        location = ()
    if len(location) != 2:
        raise HtreeError(USAGE, f"create_spine: -location must be two numbers {{x y}}, "
                         f"got '{opts['-location']}'")

    name = opts["-name"].removeprefix("spine:")
    if not name or any(ch in name for ch in "/ \t{}"):
        raise HtreeError(USAGE, f"create_spine: -name '{opts['-name']}' must be a non-empty "
                         f"name without '/', spaces or braces")
    db = session.db
    spec = opts["-spec_name"].removeprefix("spine_spec:")
    objects.require_spine_specs(db)
    if db.spine_spec_row(spec) is None:
        raise HtreeError(NO_SPEC, f"create_spine: no spine spec '{spec}' (read_spine_spec); "
                         f"specs: {' '.join(db.spine_spec_names())}")
    cell = _ref_cell(db, opts.get("-ref_cell"))
    size = (cell["size_x"], cell["size_y"]) if cell is not None else None
    try:
        p = plan(spec_data(db, spec), name, location, opts.get("-build_direction"), size)
    except SpineError as exc:
        raise HtreeError(BAD_SPEC, f"create_spine: spine spec {spec}: {exc}")
    _check_boundary(db, p)

    out = session.out
    if opts["-build"]:
        return _build(session, p, cell)
    report(p, cell, out)
    for kind, text in p.warnings:
        warn(WARN_CODES[kind], text, out)
    info(f"create_spine: {len(p.warnings)} warning(s); {name} validated, the design is "
         f"not changed", out)
    if opts["-show"]:
        _show(session, p)
    return len(p.warnings)


def spec_data(db, name):
    row = db.spine_spec_row(name)
    levels = db.spine_level_names(row["id"])
    cells = []
    for level in levels:
        lrow = db.spine_level_row(name, level)
        for cname in db.spine_cell_names(lrow["id"]):
            c = db.spine_cell_row(lrow["id"], cname)
            location = None if c["location"] is None else float(c["location"])
            cells.append(SpecCell(level, cname, c["input"], c["output"], location))
    num = lambda v: None if v is None else float(v)
    return SpecData(name, row["orientation"], num(row["span"]), num(row["level_pitch"]),
                    num(row["max_drive_length"]), num(row["stub_gap"]), num(row["deviation"]),
                    row["root_net"], row["stub_tap"], row["stub_count"], levels, cells)


def _ref_cell(db, ref):
    if ref is None:
        return None
    objects.require_library(db)
    ref = ref.removeprefix("lib_cell:")
    cell = db.lib_cell_row(ref)
    if cell is None:
        raise HtreeError(NO_CELL, f"create_spine: lib cell '{ref}' is not in the library "
                         f"(read_lef)")
    if cell["size_x"] is None:
        raise HtreeError(NO_CELL, f"create_spine: lib cell {ref} has no SIZE in its LEF")
    return cell


def _xy(p, col, s):
    x, y = p.point(col, s)
    return round(x, 6), round(y, 6)


def _check_boundary(db, p):
    """Warn about cells and stubs outside the design boundary, if there is one."""
    if not db.has_design() or not db.design_row()["boundary"]:
        return
    boundary = [float(v) for v in db.design_row()["boundary"].split()]
    outside = []
    for c in p.cells.values():
        x, y = _xy(p, c.col, c.s)
        if not rect_in_polygon((x, y, x, y), boundary):
            outside.append(c.inst)
    for stub in p.stubs:
        a, b = _xy(p, p.stub_col, stub.lo), _xy(p, p.stub_col, stub.hi)
        if not rect_in_polygon((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]),
                                max(a[1], b[1])), boundary):
            outside.append(stub.name)
    if outside:
        more = f" and {len(outside) - 10} more" if len(outside) > 10 else ""
        p.warnings.append(("outside", f"{len(outside)} cell centre(s) or stub(s) outside "
                           f"the design boundary: {' '.join(outside[:10])}{more}"))


def report(p, cell, out):
    """What -validate prints: geometry, cells, nets, levels."""
    a, b = _xy(p, p.stub_col, p.stubs[0].lo), _xy(p, p.stub_col, p.stubs[-1].hi)
    side = {1: "+", -1: "-"}[p.direction] + ("x" if p.orientation == "vertical" else "y")
    info(f"Spine {p.name} (spec {p.spec}): {p.orientation}, built toward {side} from "
         f"{{{_num(p.x0)} {_num(p.y0)}}}", out)
    info(f"  Columns : {' '.join(p.levels)} and the stubs, level_pitch {_num(p.pitch)}", out)
    info(f"  Stubs   : {len(p.stubs)} x {p.stub_length:.3f} um, gap {_num(p.gap)}, from "
         f"{{{_num(a[0])} {_num(a[1])}}} to {{{_num(b[0])} {_num(b[1])}}}", out)
    info(f"  Limits  : net <= max_drive_length {_num(p.max_drive)} + deviation "
         f"{_num(p.deviation)} = {_num(p.limit)}; nets of a level within "
         f"{_num(p.deviation)} of each other", out)
    info(f"  Cell    : " + (f"{cell['name']} {_num(cell['size_x'])} x {_num(cell['size_y'])}"
                            if cell is not None else
                            "none given (-ref_cell): overlaps checked by position only"), out)
    width = max(len(c.inst) for c in p.cells.values())
    info("Cells (centre):", out)
    for c in p.cells.values():
        x, y = _xy(p, c.col, c.s)
        role = "root" if c.driver is None else (f"-> {c.stub}" if c.stub else
                                                 "dummy" if c.dummy else "")
        if c.location is not None:
            role = f"{role}  location {_num(c.location)} from {c.driver}".lstrip()
        info(f"  {c.inst:<{width}}  {c.level:<4} {x:12.3f} {y:12.3f}  {role}", out)
    nwidth = max(len(n.name) for n in p.nets)
    info("Nets (length = level_pitch per column crossed + trunks + detour):", out)
    for n in p.nets:
        loads = " ".join(n.loads if n.loads[0] not in p.cells else
                         (p.cells[k].inst for k in n.loads))
        flag = "  OVER" if n.length > p.limit + 1e-3 else ""
        info(f"  {n.name:<{nwidth}}  {n.group:<9} {n.length:10.3f}  detour {n.detour:9.3f}"
             f"  {loads}{flag}", out)
    info("Levels:", out)
    by_name = {n.name: n for n in p.nets}
    for label, names in p.groups:
        lengths = [by_name[n].length for n in names]
        spread = max(lengths) - min(lengths)
        state = "ok" if spread <= p.deviation + 1e-3 else "SPREAD"
        info(f"  {label:<9} {len(names)} net(s)  {min(lengths):10.3f} .. {max(lengths):10.3f}"
             f"  spread {spread:8.3f}  {state}", out)


def _build(session, p, cell):
    db = session.db
    out = session.out
    if db.spine_row(p.name) is not None:
        raise HtreeError(EXISTS, f"create_spine: spine {p.name} is already built")
    taken = [c.inst for c in p.cells.values() if db.inst_row(c.inst) is not None]
    if taken:
        raise HtreeError(EXISTS, f"create_spine: instance name(s) already in use: "
                         f"{' '.join(taken)}")
    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    snap = (lambda v: round(round(v / grid) * grid, 6)) if grid else (lambda v: round(v, 6))
    w, h = cell["size_x"], cell["size_y"]
    insts, members = [], []
    for c in p.cells.values():
        x, y = _xy(p, c.col, c.s)                  # centre (point: center)
        insts.append((c.inst, cell["name"], snap(x - w / 2), snap(y - h / 2), "N"))
        driver = p.cells[c.driver].inst if c.driver else ""
        members.append((c.inst, c.level, c.name, driver))
    stubs = []
    for stub in p.stubs:
        a, b = _xy(p, p.stub_col, stub.lo), _xy(p, p.stub_col, stub.hi)
        stubs.append((stub.name, p.cells[stub.driver].inst, _pts(a + b)))
    nets = []
    for n in p.nets:
        loads = n.loads if n.loads[0] not in p.cells else [p.cells[k].inst for k in n.loads]
        route = ";".join(_pts(_xy(p, c1, s1) + _xy(p, c2, s2)) for c1, s1, c2, s2 in n.segments)
        nets.append((n.name, p.cells[n.driver].inst, " ".join(loads), n.group, n.length,
                     n.detour, route))
    side = {1: "+", -1: "-"}[p.direction] + ("x" if p.orientation == "vertical" else "y")
    db.add_spine((p.name, p.spec, p.orientation, side, p.x0, p.y0, cell["name"], p.pitch,
                  p.deviation, p.max_drive, round(p.stub_length, 6)),
                 insts, members, stubs, nets)
    info(f"Built spine:{p.name}: {len(insts)} instances of {cell['name']}, {len(stubs)} stubs "
         f"of {p.stub_length:.3f} um, {len(nets)} nets", out)
    if p.warnings:
        info(f"  {len(p.warnings)} warning(s) ignored; run create_spine with -validate to see "
             f"them", out)
    return f"spine:{p.name}"


def _pts(values):
    return " ".join(_num(v) for v in values)


def _show(session, p):
    try:
        from core.gui import app
    except ImportError as exc:
        raise HtreeError(NO_QT, f"create_spine: -show needs PySide6 ({exc})")
    try:
        app.check_display()
    except app.DisplayError as exc:
        raise HtreeError(NO_DISPLAY, f"create_spine: -show: {exc}")
    app.show(session).show_schematic(p)
    info("Schematic shown in the GUI (Schematic tab).", session.out)
