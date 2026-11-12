"""read_tech -file <lef>: parse a tech LEF into the database."""

import os
from collections import Counter

from core.lef import LefParseError, parse_tech_lef
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "read_tech"
SUMMARY = "Read a tech LEF file into the database"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-file": "value"}

FILE_NOT_FOUND = 10
PARSE_ERROR = 11
REPLACING = 12
NOT_MODELED = 13


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    path = opts.get("-file")
    if not path:
        raise HtreeError(1, "read_tech: -file is required. Usage: read_tech -file <tech.lef>")
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"read_tech: file '{path}' not found")
    try:
        tech = parse_tech_lef(path)
    except LefParseError as exc:
        raise HtreeError(PARSE_ERROR, f"read_tech: {exc.file}, line {exc.line}: {exc.text}")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtreeError(PARSE_ERROR, f"read_tech: cannot read '{path}': {exc}")

    if session.db.has_tech():
        warn(REPLACING, f"replacing existing tech data with '{path}'", session.out)
    first_line = {}
    for extra in tech.extras:
        first_line.setdefault(extra.kind, extra.line)
    for kind, count in Counter(e.kind for e in tech.extras).items():
        warn(NOT_MODELED, f"{count} {kind} statement(s) not modeled, kept verbatim "
             f"(first at line {first_line[kind]})", session.out)
    session.db.load_tech(tech)

    info(f"Reading tech LEF '{os.path.abspath(path)}'", session.out)
    info(f"  LEF version : {tech.lef_version or '(none)'}", session.out)
    info(f"  DB units    : {tech.db_units if tech.db_units is not None else '(none)'}", session.out)
    info(f"  Layers      : {len(tech.layers)} ({' '.join(l.name for l in tech.layers)})",
         session.out)
    return None
