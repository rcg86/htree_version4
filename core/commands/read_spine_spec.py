"""read_spine_spec -file <yaml>: read spine specs into the database."""

import os

from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.spine_spec import SpineSpecError, parse_spine_spec

NAME = "read_spine_spec"
SUMMARY = "Read spine specs from a YAML file"

FILE_NOT_FOUND = 80
PARSE_ERROR = 81
REPLACED = 82
IGNORED_KEY = 83


def run(session, argv):
    opts, _ = parse_options(NAME, argv, {"-file": "value"})
    path = opts.get("-file")
    if not path:
        raise HtreeError(1, "read_spine_spec: -file is required. "
                         "Usage: read_spine_spec -file <spec.yaml>")
    if not os.path.isfile(path):
        raise HtreeError(FILE_NOT_FOUND, f"read_spine_spec: file '{path}' not found")
    try:
        parsed = parse_spine_spec(path)
    except SpineSpecError as exc:
        raise HtreeError(PARSE_ERROR, f"read_spine_spec: {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtreeError(PARSE_ERROR, f"read_spine_spec: cannot read '{path}': {exc}")

    for key, line in parsed.ignored:
        warn(IGNORED_KEY, f"top-level key '{key}' is not a spine_spec; ignored"
             + (f" (document at line {line})" if line else ""), session.out)
    replaced = session.db.add_spine_specs(
        path, parsed.specs,
        lambda items: session.tcl.call("format", "%s", tuple(items)))  # Tcl list text
    for name in replaced:
        warn(REPLACED, f"spine_spec {name} replaced with the definition in '{path}'", session.out)

    info(f"Reading spine spec '{os.path.abspath(path)}'", session.out)
    for spec in parsed.specs:
        cells = sum(len(l.cells) for l in spec.levels)
        levels = " ".join(f"{l.name}({len(l.cells)})" for l in spec.levels) or "(none)"
        info(f"  {spec.name:<24}: line {spec.line}, levels {levels}, {cells} cells"
             + (f", {len(spec.extra)} unmodeled key(s) in .extra" if spec.extra else ""),
             session.out)
    return None
