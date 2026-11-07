"""deselect_obj <objects>... | -all: remove objects from the selection."""

from core.commands.select_obj import handles_from
from core.messages import HtreeError

NAME = "deselect_obj"
SUMMARY = "Remove objects from the selection (-all clears it)"


def run(session, argv):
    sel = session.db.selection
    if argv == ["-all"]:
        sel.clear()
        return None
    if not argv or "-all" in argv:
        raise HtreeError(1, "deselect_obj: usage: deselect_obj <objects> | -all")
    for h in handles_from(session, argv, NAME):
        if h in sel:
            sel.remove(h)
    return None
