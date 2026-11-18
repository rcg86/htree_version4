"""add_layer -layer <layers> [-file <lef>]: add layers of the tech LEF to the
tech data: those remove_layer took out, or those a layer range of read_tech
left out.

    add_layer -layer XM
    add_layer -layer {H1 H2}
    add_layer -layer [remove_layer -layer G*]

The layers are read from the tech LEF the tech data was read from (tech
.file; -file when it has moved) and take their place in the order of the
file. The vias of the file whose layers are then all in tech come with them.
"""

import os

from core import objects
from core.commands.read_tech import FILE_NOT_FOUND, PARSE_ERROR
from core.commands.remove_layer import NOT_A_LAYER, layer_words, match
from core.lef import LefParseError, parse_tech_lef
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "add_layer"
SUMMARY = "Add layers of the tech LEF to the tech data (those remove_layer removed)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-layer": "value", "-file": "value"}
USAGE = "add_layer -layer <layers> [-file <tech.lef>]"

OTHER_TECH = 19


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    words = layer_words(NAME, opts, USAGE)
    db = session.db
    objects.require_tech(db)
    path = opts.get("-file") or db.tech_row()["file"]
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"add_layer: tech LEF '{path}' not found"
                         + ("" if opts.get("-file") else ": the file the tech data was read "
                            "from. Give the file with -file if it has moved"))
    try:
        tech = parse_tech_lef(path)
    except LefParseError as exc:
        raise HtreeError(PARSE_ERROR, f"add_layer: {exc.file}, line {exc.line}: {exc.text}")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtreeError(PARSE_ERROR, f"add_layer: cannot read '{path}': {exc}")
    in_file = [layer.name for layer in tech.layers]
    have = db.layer_names()
    other = [n for n in have if n not in in_file]
    if other:
        raise HtreeError(OTHER_TECH, f"add_layer: tech layer(s) {' '.join(other)} of the "
                         f"database are not in '{path}': not the tech LEF the tech data was "
                         f"read from. Nothing is added")
    hits, missed = match(words, in_file)
    if missed:
        free = [n for n in in_file if n not in have]
        raise HtreeError(NOT_A_LAYER, f"add_layer: {' '.join(missed)}: not in '{path}' "
                         f"(its layers that are not in tech: {' '.join(free) or 'none'}). "
                         f"Nothing is added")
    new = [n for n in in_file if n in hits and n not in have]
    if not new:
        info(f"add_layer: nothing to add: {' '.join(n for n in in_file if n in hits)} "
             f"already in tech", session.out)
        return []

    keep = set(have) | set(new)
    before = {r["name"] for r in db.conn.execute("SELECT name FROM via_def")}
    tech.layers = [layer for layer in tech.layers if layer.name in keep]
    tech.vias = [via for via in tech.vias if all(sh.layer in keep for sh in via.shapes)]
    lo, hi = db.tech_layer_range()
    db.load_tech(tech, lo, hi, [n for n in db.removed_layers() if n not in new])
    vias = [via.name for via in tech.vias if via.name not in before]     # not the DEF's

    info(f"add_layer: added {len(new)} layer(s) to tech from '{os.path.abspath(path)}': "
         f"{' '.join(new)}", session.out)
    info(f"  Layers      : {len(tech.layers)} ({' '.join(l.name for l in tech.layers)})",
         session.out)
    if vias:
        info(f"  Vias        : {len(vias)} added, their layers are all in tech now "
             f"({' '.join(vias)})", session.out)
    return new
