"""read_db -file <file>: load a database written by write_db, replacing the current
one, and carry on from there (get_db, create_inst, gui_show, ... see the loaded data)."""

import os
import sqlite3

from core.db import SchemaMismatch
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "read_db"
SUMMARY = "Read a design database written by write_db and continue from it"

NOT_FOUND = 40
BAD_DB = 41


def run(session, argv):
    opts, pos = parse_options(NAME, argv, {"-file": "value"}, max_positionals=1)
    if "-file" in opts and pos:
        raise HtreeError(1, "read_db: give the file once, with -file")
    path = opts.get("-file") or (pos[0] if pos else None)
    if not path:
        raise HtreeError(1, "read_db: missing file name. Usage: read_db -file <file>")
    if not os.path.isfile(path):
        raise HtreeError(NOT_FOUND, f"read_db: file '{path}' not found")
    try:
        session.db.read(path)
    except SchemaMismatch as exc:
        raise HtreeError(BAD_DB, f"read_db: '{path}': {exc}")
    except sqlite3.Error as exc:
        raise HtreeError(BAD_DB, f"read_db: '{path}' is not a readable database: {exc}")
    session.db.selection.clear()          # handles of the old database mean nothing now
    info(f"Database read from '{os.path.abspath(path)}'", session.out)
    for line in summary(session.db):
        info(line, session.out)
    return None


def summary(db):
    """One line per kind of data in the database, so the user sees where they are."""
    rows = []
    if db.has_tech():
        layers = db.layer_names()
        rows.append(("Tech", f"{os.path.basename(db.tech_row()['file'] or '')} "
                             f"({len(layers)} layers: {' '.join(layers)})"))
    if db.has_library():
        rows.append(("Library", f"{len(db.lef_files())} LEF file(s), "
                                f"{len(db.lib_cell_names())} cells"))
    if db.has_spine_specs():
        rows.append(("Spine specs", " ".join(db.spine_spec_names())))
    if db.has_design():
        d = db.design_row()
        rows.append(("Design", f"{d['name']} ({len(db.port_names())} ports, "
                               f"{len(db.track_pattern_ids())} track patterns)"))
    for label, names in (("Track assignments", db.track_assignment_layers()),
                         ("Route rules", db.route_rule_layers()),
                         ("Spines", db.spine_names())):
        if names:
            rows.append((label, " ".join(names)))
    if db.has_insts():
        rows.append(("Instances", str(len(db.inst_names()))))
    if not rows:
        return ["  (the database is empty)"]
    width = max(len(label) for label, _ in rows)
    return [f"  {label:<{width}} : {text}" for label, text in rows]
