"""man <command>: print a command's manual page from docs/man/<command>.md."""

from core.messages import HtreeError, info
from core.options import parse_options

NAME = "man"
SUMMARY = "Show the manual page for a command"

NO_PAGE = 50


def run(session, argv):
    _, pos = parse_options(NAME, argv, {}, max_positionals=1)
    if not pos:
        raise HtreeError(1, "man: missing command name. Usage: man <command>")
    page = session.man_dir / f"{pos[0]}.md"
    if not page.is_file():
        raise HtreeError(NO_PAGE, f"man: no manual page for '{pos[0]}'. Run 'help' for commands")
    info(page.read_text().rstrip(), session.out)
    return None
