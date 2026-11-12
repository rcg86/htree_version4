"""set_place_constraint -ref_name <cells> -space_x <um> -space_y <um>: keep
instances of a lib cell apart.

    set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -space_x 1 -space_y 2
    set_place_constraint -ref_name INV12* -remove
    set_place_constraint                       ;# lists the constraints

Two instances are too close when the gap between their boxes is less than
space_x in x and less than space_y in y at the same time (the box of one,
grown by space_x left and right and space_y below and above, overlaps the
other). A pair is checked when either cell has a constraint; with both,
the larger spacing of each axis counts. legalize_placement moves cells
apart; kept in the database (meta table), so write_db saves them.
"""

import fnmatch

from core.db import _num
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "set_place_constraint"
SUMMARY = "Keep instances of a lib cell at least space_x / space_y apart (legalize_placement)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-ref_name": "value", "-space_x": "value", "-space_y": "value", "-remove": "flag"}

USAGE = 1
NO_CELL = 225
PREFIX = "place_constraint:"


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db = session.db
    out = session.out
    if "-ref_name" not in opts:
        if opts.get("-space_x") or opts.get("-space_y") or opts["-remove"]:
            raise HtreeError(USAGE, "set_place_constraint: -ref_name is required. Usage: "
                             "set_place_constraint -ref_name <cells> -space_x <um> -space_y <um>"
                             " | -remove")
        found = spacings(db)
        for ref, (sx, sy) in found.items():
            info(f"{ref}: space_x {_num(sx)} space_y {_num(sy)}", out)
        if not found:
            info("set_place_constraint: no placement constraints", out)
        return tuple(found)
    refs = _cells(session, opts["-ref_name"])
    with db.conn:
        if opts["-remove"]:
            for ref in refs:
                db.conn.execute("DELETE FROM meta WHERE key = ?", (PREFIX + ref,))
            info(f"set_place_constraint: removed the constraint of {' '.join(refs)}", out)
            return tuple(refs)
        if "-space_x" not in opts and "-space_y" not in opts:
            raise HtreeError(USAGE, "set_place_constraint: give -space_x and/or -space_y "
                             "(or -remove)")
        sx, sy = (_space(opts.get(k, "0"), k) for k in ("-space_x", "-space_y"))
        for ref in refs:
            db.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                            (PREFIX + ref, f"{sx!r} {sy!r}"))
    info(f"set_place_constraint: {' '.join(refs)}: instances at least {_num(sx)} um apart in x "
         f"or {_num(sy)} um in y (legalize_placement)", out)
    return tuple(refs)


def spacings(db):
    """{lib cell: (space_x, space_y)} of every constraint."""
    rows = db.conn.execute("SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
                           (PREFIX + "%",))
    return {k[len(PREFIX):]: tuple(float(v) for v in value.split()) for k, value in rows}


def _cells(session, text):
    db = session.db
    names = [r[0] for r in db.conn.execute("SELECT name FROM lib_cell ORDER BY id")]
    found = []
    for word in session.split_list(text):
        word = word.removeprefix("lib_cell:")
        hits = [n for n in names if fnmatch.fnmatchcase(n, word)]
        if not hits:
            raise HtreeError(NO_CELL, f"set_place_constraint: no lib cell '{word}' (read_lef; "
                             f"get_db lib_cells)")
        found += [n for n in hits if n not in found]
    return found


def _space(text, option):
    try:
        v = float(text)
    except ValueError:
        v = -1.0
    if v < 0:
        raise HtreeError(USAGE, f"set_place_constraint: {option} must be a number of microns "
                         f">= 0, got '{text}'")
    return v
