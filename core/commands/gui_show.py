"""gui_show: open the layout window. The htree> prompt keeps working."""

from core.messages import HtreeError, info
from core.options import parse_options

NAME = "gui_show"
SUMMARY = "Open the layout GUI (the terminal prompt stays usable)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {}

NO_QT = 100
NO_DISPLAY = 101


def run(session, argv):
    parse_options(NAME, argv, OPTIONS)
    try:
        from core.gui import app
    except ImportError as exc:
        raise HtreeError(NO_QT, f"gui_show: PySide6 is not available ({exc}); "
                         f"install it with: pip install -r requirements.txt")
    try:
        app.check_display()
    except app.DisplayError as exc:
        raise HtreeError(NO_DISPLAY, f"gui_show: {exc}")
    first = app.window() is None
    app.show(session)
    if first:
        info("GUI opened. Commands typed here update the layout.", session.out)
    return None
