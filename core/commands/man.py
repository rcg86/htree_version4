"""man <command>: print a command's manual page from docs/man/<command>.md.

brief() gives the short form that '<command> -help' prints."""

import re

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


HEADING = re.compile(r"^[A-Z][A-Z ]*[A-Z]$")
EXAMPLE_LINES = 6        # output lines kept after the example command


def sections(text):
    """{heading: [lines]} of a manual page; headings are unindented capitals."""
    found, current = {}, None
    for line in text.splitlines():
        if HEADING.match(line):
            current = found.setdefault(line, [])
        elif current is not None:
            current.append(line)
    for lines in found.values():
        while lines and not lines[-1].strip():
            lines.pop()
    return found


def example(lines, name):
    """The first example that runs the command, with a few lines of its output."""
    prompts = [i for i, l in enumerate(lines) if l.strip().startswith("htree> ")]
    own = [i for i in prompts if re.match(rf"htree> {re.escape(name)}(\s|$)", lines[i].strip())]
    if not (own or prompts):
        return []
    start = (own or prompts)[0]
    shown = [lines[start]]
    for line in lines[start + 1:]:
        if not line.strip() or line.strip().startswith("htree> ") or \
                len(shown) > EXAMPLE_LINES:
            break
        shown.append(line)
    return shown


def brief(session, name):
    """Definition, usage, options and one example of a command (its -help)."""
    page = session.man_dir / f"{name}.md"
    if not page.is_file():
        return f"{name} - {session.commands[name].SUMMARY}\n(no manual page)"
    secs = sections(page.read_text())
    out = []
    for key in ("NAME", "SYNOPSIS"):
        if key in secs:
            out += [key] + secs[key] + [""]
    description = secs.get("DESCRIPTION", [])
    if description:
        end = next((i for i, l in enumerate(description) if not l.strip()), len(description))
        out += ["DESCRIPTION"] + description[:end] + [""]
    if "OPTIONS" in secs:
        out += ["OPTIONS"] + secs["OPTIONS"] + [""]
    shown = example(secs.get("EXAMPLES", []), name)
    if shown:
        out += ["EXAMPLE"] + shown + [""]
    out.append(f"Run 'man {name}' for the full manual page.")
    return "\n".join(out)
