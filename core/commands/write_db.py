"""write_db -file <file> [-overwrite]: save the in-memory database to a SQLite file."""

import os
import sqlite3

from core.messages import HtreeError, info
from core.options import parse_options

NAME = "write_db"
SUMMARY = "Write the design database to a SQLite file"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-file": "value", "-overwrite": "flag"}

EXISTS = 30
WRITE_FAILED = 31


def run(session, argv):
    opts, pos = parse_options(NAME, argv, OPTIONS,
                              max_positionals=1)
    if "-file" in opts and pos:
        raise HtreeError(1, "write_db: give the file once, with -file")
    path = opts.get("-file") or (pos[0] if pos else None)
    if not path:
        raise HtreeError(1, "write_db: missing file name. "
                         "Usage: write_db -file <file> [-overwrite]")
    if os.path.exists(path) and not opts["-overwrite"]:
        raise HtreeError(EXISTS, f"write_db: '{path}' exists; use -overwrite to replace it")
    # Write beside the target and rename, so a failed write never loses the old file.
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        session.db.write(tmp)
        os.replace(tmp, path)
    except (OSError, sqlite3.Error) as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise HtreeError(WRITE_FAILED, f"write_db: cannot write '{path}': {exc}")
    info(f"Database written to '{os.path.abspath(path)}'", session.out)
    return None
