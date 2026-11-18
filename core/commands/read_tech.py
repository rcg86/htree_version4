"""read_tech -file <lef> [-min_layer <layer>] [-max_layer <layer>]: parse a
tech LEF into the database, all of it or the layers of a range with their
vias."""

import os
from collections import Counter

from core.lef import LefParseError, parse_tech_lef
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "read_tech"
SUMMARY = "Read a tech LEF file into the database"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-file": "value", "-min_layer": "value", "-max_layer": "value"}
USAGE = "read_tech -file <tech.lef> [-min_layer <layer>] [-max_layer <layer>]"

FILE_NOT_FOUND = 10
PARSE_ERROR = 11
REPLACING = 12
NOT_MODELED = 13
VIA_OF_DEF_KEPT = 14
LAYER_RANGE = 15
LAYER_IN_USE = 16


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    path = opts.get("-file")
    if not path:
        raise HtreeError(1, f"read_tech: -file is required. Usage: {USAGE}")
    lo, hi = opts.get("-min_layer"), opts.get("-max_layer")
    if "" in (lo, hi):
        raise HtreeError(1, f"read_tech: -min_layer and -max_layer take a layer name. "
                         f"Usage: {USAGE}")
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"read_tech: file '{path}' not found")
    try:
        tech = parse_tech_lef(path)
    except LefParseError as exc:
        raise HtreeError(PARSE_ERROR, f"read_tech: {exc.file}, line {exc.line}: {exc.text}")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtreeError(PARSE_ERROR, f"read_tech: cannot read '{path}': {exc}")
    in_file = len(tech.layers)
    out_layers, out_vias = _keep_range(tech, lo, hi)

    if session.db.has_tech():
        warn(REPLACING, f"replacing existing tech data with '{path}'", session.out)
    first_line = {}
    for extra in tech.extras:
        first_line.setdefault(extra.kind, extra.line)
    for kind, count in Counter(e.kind for e in tech.extras).items():
        warn(NOT_MODELED, f"{count} {kind} statement(s) not modeled, kept verbatim "
             f"(first at line {first_line[kind]})", session.out)
    for name in session.db.load_tech(tech, lo, hi):
        warn(VIA_OF_DEF_KEPT, f"via '{name}' is also defined by the DEF; the DEF's "
             f"definition is kept", session.out)

    info(f"Reading tech LEF '{os.path.abspath(path)}'", session.out)
    info(f"  LEF version : {tech.lef_version or '(none)'}", session.out)
    info(f"  DB units    : {tech.db_units if tech.db_units is not None else '(none)'}", session.out)
    if lo or hi:
        info(f"  Layer range : {tech.layers[0].name} .. {tech.layers[-1].name} ("
             + ", ".join(f"{opt} {name}" for opt, name in (("-min_layer", lo), ("-max_layer", hi))
                         if name)
             + f"); {len(out_layers)} of the {in_file} layers of the file left out", session.out)
    info(f"  Layers      : {len(tech.layers)} ({' '.join(l.name for l in tech.layers)})",
         session.out)
    if tech.vias or out_vias:
        default = sum(1 for v in tech.vias if v.default)
        info(f"  Vias        : {len(tech.vias)} ({default} DEFAULT)"
             + (f"; {len(out_vias)} left out, a layer of theirs is not in the range"
                if out_vias else ""), session.out)
    _warn_in_use(session.db, out_layers, session.out)
    return None


def _keep_range(tech, lo, hi):
    """Cut tech down to its layers from lo to hi, both included, in the order
    of the LAYER statements of the file (every type: the cut layers between
    two routing layers too), and to the vias whose shapes are all on them.
    None: from the first layer, to the last. Returns the names of the layers
    and of the vias left out."""
    if not (lo or hi):
        return [], []
    names = [layer.name for layer in tech.layers]
    for opt, name in (("-min_layer", lo), ("-max_layer", hi)):
        if name and name not in names:
            raise HtreeError(LAYER_RANGE, f"read_tech: {opt} '{name}' is not a layer of "
                             f"'{tech.file}' (its layers, in the order of the file: "
                             f"{' '.join(names) or 'none'})")
    first = names.index(lo) if lo else 0
    last = names.index(hi) if hi else len(names) - 1
    if first > last:
        raise HtreeError(LAYER_RANGE, f"read_tech: -min_layer '{lo}' comes after -max_layer "
                         f"'{hi}' in '{tech.file}' (layer {first + 1} and layer {last + 1} of "
                         f"{len(names)}): the range is taken in the order of the file")
    keep = set(names[first:last + 1])
    out_vias = [via.name for via in tech.vias if any(sh.layer not in keep for sh in via.shapes)]
    tech.layers = tech.layers[first:last + 1]
    tech.vias = [via for via in tech.vias if all(sh.layer in keep for sh in via.shapes)]
    return names[:first] + names[last + 1:], out_vias


def layers_in_use(db):
    """{layer: [what is on it]} for the layers that route rules, track
    assignments or route wires of the database are on."""
    used = {}
    for what, sql in (("route rule(s)", "SELECT DISTINCT layer FROM route_rule"),
                      ("track assignment(s)", "SELECT layer FROM track_assignment"),
                      ("route wire(s)", "SELECT layer FROM strap UNION SELECT layer FROM "
                                        "pin_wire UNION SELECT layer FROM net_wire")):
        for row in db.conn.execute(sql):
            for name in (row["layer"] or "").split("/"):     # a crossing box: IA/IB
                if what not in used.setdefault(name, []):
                    used[name].append(what)
    return used


def _warn_in_use(db, out_layers, out):
    """Warn of layers the range leaves out that stored data is on: they are
    no tech layers now, for any command."""
    used = layers_in_use(db)
    for name in out_layers:
        if name in used:
            warn(LAYER_IN_USE, f"layer {name} is left out by the layer range, and "
                 f"{', '.join(used[name])} of the database are on it: it is "
                 f"no tech layer now. Read the tech LEF again with a range that has it",
                 out)
