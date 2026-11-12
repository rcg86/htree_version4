"""source [-echo] <file>: run the commands in a file, one by one.

Replaces Tcl's source (kept as ::__tcl_source) so an error names the file and
line, and -echo prints each command before it runs. Commands run at global
level, as with Tcl's source; 'return' at the top of the file ends the file.
"""

import os

from core.messages import HtreeError
from core.options import parse_options

NAME = "source"
SUMMARY = "Run the commands in a script file"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-echo": "flag", "-encoding": "value"}

NOT_FOUND = 70
IN_FILE = 71
ECHO_PREFIX = "htree> "

# Runs one command at global level and reports its Tcl return code.
HELPER = """
proc ::__htree_eval {cmd} {
    set code [catch {uplevel #0 $cmd} result]
    return [list $code $result]
}
"""


def run(session, argv):
    # -encoding is accepted for Tcl packages that call 'source -encoding utf-8 f'.
    opts, pos = parse_options(NAME, argv, OPTIONS,
                              max_positionals=1)
    if not pos:
        raise HtreeError(1, "source: missing file name. Usage: source [-echo] <file>")
    path = pos[0]
    if not os.path.isfile(path):
        raise HtreeError(NOT_FOUND, f"source: file '{path}' not found")
    try:
        with open(path, encoding=opts.get("-encoding") or "utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError, LookupError) as exc:
        raise HtreeError(NOT_FOUND, f"source: cannot read '{path}': {exc}")

    tcl = session.tcl
    outer_script = tcl.call("info", "script")
    tcl.call("info", "script", path)
    try:
        return _run_text(session, path, text, opts["-echo"])
    finally:
        tcl.call("info", "script", outer_script)


def _run_text(session, path, text, echo):
    tcl = session.tcl
    result, buf, start = "", "", 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not buf:
            start = lineno
        buf += line + "\n"
        if _continues(line) or not tcl.call("info", "complete", buf):
            continue
        cmd, buf = buf, ""
        if not cmd.strip():
            continue
        if echo and not _only_comments(cmd):
            tcl.eval("flush stdout")          # keep echo after earlier puts output
            print(ECHO_PREFIX + cmd.rstrip("\n"), file=session.out, flush=True)
        code, value = tcl.splitlist(tcl.call("__htree_eval", cmd))
        code, value = int(code), str(value)
        if code == 0:
            result = value
        elif code == 2:                       # 'return' at file level ends the file
            return value
        elif session.exit_code is not None:   # exit: let the shell unwind
            return None
        elif code == 1:
            if value.startswith("**ERROR"):   # the command already printed it
                raise HtreeError(IN_FILE, f"source: stopped at {path} line {start}")
            raise HtreeError(IN_FILE, f"source: {path} line {start}: {value}")
        else:                                 # break / continue outside a loop
            word = "break" if code == 3 else "continue"
            raise HtreeError(IN_FILE, f"source: {path} line {start}: "
                             f"invoked \"{word}\" outside of a loop")
    if buf.strip():
        raise HtreeError(IN_FILE, f"source: {path} line {start}: command not complete "
                         f"(missing close brace, bracket or quote)")
    return result


def _continues(line: str) -> bool:
    """True when the line ends in a backslash continuation."""
    trailing = len(line) - len(line.rstrip("\\"))
    return trailing % 2 == 1


def _only_comments(cmd: str) -> bool:
    return all(not l.strip() or l.lstrip().startswith("#") for l in cmd.splitlines())
