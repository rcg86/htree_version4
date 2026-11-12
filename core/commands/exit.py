"""exit [<code>]: leave the tool. Python's embedded Tcl removes the built-in exit."""

from core.messages import HtreeError
from core.options import parse_options

NAME = "exit"
SUMMARY = "Exit the tool (the database is not saved; use write_db first)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {}


def run(session, argv):
    _, pos = parse_options(NAME, argv, OPTIONS, max_positionals=1)
    try:
        code = int(pos[0]) if pos else 0
    except ValueError:
        raise HtreeError(1, f"exit: exit code must be an integer, got '{pos[0]}'")
    session.exit_code = code
    return None
