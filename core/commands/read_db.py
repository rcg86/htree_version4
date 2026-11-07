"""read_db <file>: load a database written by write_db, replacing the current one."""

import os
import sqlite3

from core.db import SchemaMismatch
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "read_db"
SUMMARY = "Read a design database written by write_db"

NOT_FOUND = 40
BAD_DB = 41


def run(session, argv):
    _, pos = parse_options(NAME, argv, {}, max_positionals=1)
    if not pos:
        raise HtreeError(1, "read_db: missing file name. Usage: read_db <file>")
    path = pos[0]
    if not os.path.isfile(path):
        raise HtreeError(NOT_FOUND, f"read_db: file '{path}' not found")
    try:
        session.db.read(path)
    except SchemaMismatch as exc:
        raise HtreeError(BAD_DB, f"read_db: '{path}': {exc}")
    except sqlite3.Error as exc:
        raise HtreeError(BAD_DB, f"read_db: '{path}' is not a readable database: {exc}")
    info(f"Database read from '{os.path.abspath(path)}'", session.out)
    return None
