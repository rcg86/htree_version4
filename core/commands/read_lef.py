"""read_lef -file <lef>: parse a cell LEF into the physical library."""

import os
from collections import Counter

from core.lef import LefParseError, parse_cell_lef
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "read_lef"
SUMMARY = "Read a cell LEF file into the physical library"

FILE_NOT_FOUND = 60
PARSE_ERROR = 61
DUPLICATE_CELL = 62
NOT_MODELED = 63
LAYERS_NOT_IN_TECH = 64
NO_TECH_TO_CHECK = 65


def run(session, argv):
    opts, _ = parse_options(NAME, argv, {"-file": "value"})
    path = opts.get("-file")
    if not path:
        raise HtreeError(1, "read_lef: -file is required. Usage: read_lef -file <cells.lef>")
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"read_lef: file '{path}' not found")
    try:
        lib = parse_cell_lef(path)
    except LefParseError as exc:
        raise HtreeError(PARSE_ERROR, f"read_lef: {exc.file}, line {exc.line}: {exc.text}")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtreeError(PARSE_ERROR, f"read_lef: cannot read '{path}': {exc}")

    first_line = {}
    for extra in lib.extras:
        first_line.setdefault(extra.kind, extra.line)
    for kind, count in Counter(e.kind for e in lib.extras).items():
        warn(NOT_MODELED, f"{count} {kind} statement(s) not modeled, kept verbatim "
             f"(first at line {first_line[kind]})", session.out)
    skipped = session.db.add_cell_lef(lib)
    for name in skipped:
        warn(DUPLICATE_CELL, f"MACRO {name} is already in the library; "
             f"keeping the first definition", session.out)

    added = [m for m in lib.macros if m.name not in set(skipped)]
    pins = [p for m in added for p in m.pins]
    ports = [pt for p in pins for pt in p.ports]
    info(f"Reading cell LEF '{os.path.abspath(path)}'", session.out)
    info(f"  LEF version : {lib.lef_version or '(none)'}", session.out)
    info(f"  Cells       : {len(added)} added"
         + (f", {len(skipped)} duplicate(s) skipped" if skipped else ""), session.out)
    info(f"  Pins        : {len(pins)}, ports {len(ports)}, "
         f"shapes {sum(len(pt.shapes) for pt in ports)}", session.out)
    _report_layers(session, session.db.pin_shape_layer_counts(session.db.last_lef_file_id()))
    return None


def _report_layers(session, counts):
    """Pin shapes on every layer are kept; only tech layers are used in calculations."""
    if not counts:
        return
    db, out = session.db, session.out
    used = " ".join(f"{l}({n})" for l, n in counts.items())
    if not db.has_tech():
        info(f"  Pin layers  : {used}", out)
        warn(NO_TECH_TO_CHECK, "no tech data loaded, so pin layers cannot be checked; "
             "after read_tech, only shapes on tech layers are used in calculations "
             "(layer_shape .in_tech)", out)
        return
    tech = set(db.layer_names())
    inside = [l for l in counts if l in tech]
    outside = [l for l in counts if l not in tech]
    info(f"  Pin layers  : {used}", out)
    info(f"  In tech     : {' '.join(inside) or '(none)'}", out)
    if outside:
        n = sum(counts[l] for l in outside)
        warn(LAYERS_NOT_IN_TECH, f"{n} pin shape(s) on layers not in tech: {' '.join(outside)}. "
             f"They are kept but ignored in calculations", out)
