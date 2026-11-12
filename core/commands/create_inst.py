"""create_inst -ref_cell <lib_cell> -location {x y} [-name <name>] [-orient <o>]:
place an instance of a library cell.

The location is the lower-left corner of the placed cell, as in DEF.
"""

from core import objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import ORIENT_NAMES, placed_bbox, rect_in_polygon, rects_overlap

NAME = "create_inst"
SUMMARY = "Place an instance of a library cell at a location"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-ref_cell": "value", "-location": "value", "-name": "value", "-orient": "value"}

USAGE = 1
NO_CELL = 120
NAME_TAKEN = 121
OUTSIDE = 122
OVERLAP = 123
OFF_GRID = 124


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-ref_cell" not in opts or "-location" not in opts:
        raise HtreeError(USAGE, "create_inst: -ref_cell and -location are required. Usage: "
                         "create_inst -ref_cell <lib_cell> -location {x y} [-name <name>] "
                         "[-orient N]")
    db = session.db
    loc = session.split_list(opts["-location"])
    try:
        x, y = (float(v) for v in loc)
    except ValueError:
        raise HtreeError(USAGE, f"create_inst: -location must be two numbers {{x y}}, "
                         f"got '{opts['-location']}'")
    orient = opts.get("-orient", "N").upper()
    if orient not in ORIENT_NAMES:
        raise HtreeError(USAGE, f"create_inst: -orient must be one of {' '.join(ORIENT_NAMES)}, "
                         f"got '{opts['-orient']}'")
    objects.require_library(db)
    ref = opts["-ref_cell"].removeprefix("lib_cell:")
    cell = db.lib_cell_row(ref)
    if cell is None:
        raise HtreeError(NO_CELL, f"create_inst: lib cell '{ref}' is not in the library "
                         f"(read_lef); cells: {' '.join(db.lib_cell_names())}")
    if cell["size_x"] is None:
        raise HtreeError(NO_CELL, f"create_inst: lib cell {ref} has no SIZE in its LEF")
    name = opts.get("-name") or _next_name(db)
    if "/" in name or any(c.isspace() for c in name) or not name:
        raise HtreeError(USAGE, f"create_inst: instance name '{name}' must not be empty or "
                         f"contain '/' or spaces")
    if db.inst_row(name) is not None:
        raise HtreeError(NAME_TAKEN, f"create_inst: instance '{name}' already exists")

    box = placed_bbox(cell["size_x"], cell["size_y"], orient, x, y)
    out = session.out
    if db.has_tech() and db.tech_row()["manufacturing_grid"]:
        grid = db.tech_row()["manufacturing_grid"]
        if any(abs(v / grid - round(v / grid)) > 1e-6 for v in (x, y)):
            warn(OFF_GRID, f"location {{{_num(x)} {_num(y)}}} is not on the manufacturing "
                 f"grid {_num(grid)}", out)
    if db.has_design() and db.design_row()["boundary"]:
        boundary = [float(v) for v in db.design_row()["boundary"].split()]
        if not rect_in_polygon(box, boundary):
            warn(OUTSIDE, f"{name} bbox {{{' '.join(_num(v) for v in box)}}} is not inside "
                 f"the design boundary", out)
    for other in db.inst_rows():
        other_box = objects.inst_bbox(db, other)
        if other_box and rects_overlap(box, other_box):
            warn(OVERLAP, f"{name} overlaps instance {other['name']}", out)

    db.add_inst(name, ref, x, y, orient)
    info(f"Created inst:{name} ({ref}) at {{{_num(x)} {_num(y)}}} {orient}, "
         f"bbox {{{' '.join(_num(v) for v in box)}}}", out)
    return f"inst:{name}"


def _next_name(db):
    taken = set(db.inst_names())
    n = len(taken) + 1
    while f"inst_{n}" in taken:
        n += 1
    return f"inst_{n}"
