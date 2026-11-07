"""select_obj <objects>...: add objects to the selection (shown in the GUI)."""

from core import objects
from core.messages import HtreeError

NAME = "select_obj"
SUMMARY = "Add objects to the selection (get_db selected; highlighted in the GUI)"

USAGE = 1


def handles_from(session, argv, cmd):
    """Handles from one or more Tcl lists of handles; each must exist."""
    handles = []
    for word in argv:
        for h in session.split_list(word):
            if not objects.is_handle(h):
                raise HtreeError(USAGE, f"{cmd}: '{h}' is not an object handle")
            objects.check_exists(session.db, h)
            if h not in handles:
                handles.append(h)
    return handles


def run(session, argv):
    if not argv:
        raise HtreeError(USAGE, "select_obj: missing objects. Usage: select_obj <objects>")
    sel = session.db.selection
    for h in handles_from(session, argv, NAME):
        if h not in sel:
            sel.append(h)
    return None
