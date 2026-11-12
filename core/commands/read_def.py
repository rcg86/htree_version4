"""read_def -file <def>: read the design boundary (DIEAREA), TRACKS and PINS."""

import os

from core.db import _num
from core.def_parser import DefParseError, parse_def
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "read_def"
SUMMARY = "Read the boundary, tracks and pins of a DEF file"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-file": "value"}

FILE_NOT_FOUND = 90
PARSE_ERROR = 91
REPLACING = 92
LAYERS_NOT_IN_TECH = 93
NO_TECH_TO_CHECK = 94
NO_BOUNDARY = 95


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    path = opts.get("-file")
    if not path:
        raise HtreeError(1, "read_def: -file is required. Usage: read_def -file <design.def>")
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"read_def: file '{path}' not found")
    try:
        design = parse_def(path)
    except DefParseError as exc:
        raise HtreeError(PARSE_ERROR, f"read_def: {exc.file}, line {exc.line}: {exc.text}")
    except (OSError, UnicodeDecodeError, EOFError) as exc:
        raise HtreeError(PARSE_ERROR, f"read_def: cannot read '{path}': {exc}")
    if design.name is None:
        raise HtreeError(PARSE_ERROR, f"read_def: '{path}' has no DESIGN statement")

    db, out = session.db, session.out
    if db.has_design():
        warn(REPLACING, f"replacing design {db.design_row()['name']} with '{path}'", out)
    if not design.boundary:
        warn(NO_BOUNDARY, "no DIEAREA in the DEF; the design has no boundary", out)
    db.load_def(design)

    shapes = sum(len(p.shapes) for p in design.ports)
    info(f"Reading DEF '{os.path.abspath(path)}'", out)
    info(f"  Design      : {design.name} (DEF {design.version or '?'}, "
         f"{design.units} units/micron)", out)
    if design.boundary:
        xs, ys = design.boundary[0::2], design.boundary[1::2]
        kind = "rectangle" if len(xs) == 4 else f"polygon, {len(xs)} points"
        bbox = " ".join(_num(v) for v in (min(xs), min(ys), max(xs), max(ys)))
        info(f"  Boundary    : {kind}, bbox {bbox}", out)
    info(f"  Pins        : {len(design.ports)}, shapes {shapes}", out)
    if design.rows:
        sites = sorted({r.site for r in design.rows})
        info(f"  Rows        : {len(design.rows)} ({' '.join(sites)})", out)
    track_layers = list(dict.fromkeys(l for t in design.tracks for l in t.layers))
    info(f"  Tracks      : {len(design.tracks)} patterns on {len(track_layers)} layers"
         + (f" ({' '.join(track_layers)})" if track_layers else ""), out)
    if track_layers and db.has_tech():
        tech = set(db.layer_names())
        info(f"  Tracks tech : {' '.join(l for l in track_layers if l in tech) or '(none)'}"
             + (", tech layers without tracks: " + " ".join(missing)
                if (missing := [l for l in db.layer_names() if l not in track_layers]) else ""),
             out)
    if design.skipped:
        info("  Skipped     : " + " ".join(f"{k}({n})" if n > 1 else k
                                          for k, n in design.skipped.items()), out)
    _report_layers(session, db.port_shape_layer_counts())
    return None


def _report_layers(session, counts):
    """Pin shapes on every layer are kept; only tech layers are used in calculations."""
    if not counts:
        return
    db, out = session.db, session.out
    info(f"  Pin layers  : {' '.join(f'{l}({n})' for l, n in counts.items())}", out)
    if not db.has_tech():
        warn(NO_TECH_TO_CHECK, "no tech data loaded, so pin layers cannot be checked; "
             "after read_tech, only shapes on tech layers are used in calculations "
             "(port_shape .in_tech)", out)
        return
    tech = set(db.layer_names())
    inside = [l for l in counts if l in tech]
    outside = [l for l in counts if l not in tech]
    info(f"  In tech     : {' '.join(inside) or '(none)'}", out)
    if outside:
        n = sum(counts[l] for l in outside)
        warn(LAYERS_NOT_IN_TECH, f"{n} pin shape(s) on layers not in tech: {' '.join(outside)}. "
             f"They are kept but ignored in calculations", out)
