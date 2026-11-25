"""htree_builder: Tcl command shell (CUI) over the htree design database.

    python core/htree_builder.py                    interactive prompt
    python core/htree_builder.py -init run.tcl      run a script, then prompt
    python core/htree_builder.py -init run.tcl -batch   run a script, then exit

Each run writes log/htree.log (all output) and log/htree.cmd (the commands)
under the directory it is started in, the directory made when it is not
there (core/session_log.py); -no_log turns that off.
"""

import argparse
import sys
import tkinter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:      # allow "python core/htree_builder.py"
    sys.path.insert(0, str(ROOT))

from core import commands as command_pkg  # noqa: E402
from core.commands import source as source_cmd  # noqa: E402
from core.db import Database  # noqa: E402
from core.messages import HtreeError  # noqa: E402

PROMPT = "htree> "
EXIT_MARK = "__htree_exit__"
MAN_DIR = ROOT / "docs" / "man"

# Each command is a Tcl proc around the Python dispatcher, so command errors
# carry their message into Tcl ('catch' sees it, scripts stop on it).
_WRAPPER = """
proc ::{name} {{args}} {{
    set r [::__htree_dispatch {name} {{*}}$args]
    if {{[lindex $r 0] eq "error"}} {{ return -code error [lindex $r 1] }}
    return [lindex $r 1]
}}
"""


class Session:
    def __init__(self, out=None):
        self.out = out or sys.stdout
        self.db = Database()
        self.man_dir = MAN_DIR
        self.exit_code = None          # set by the exit command
        self.after_command = []        # callables run after every command (GUI refresh)
        self._at_prompt = False        # True while the REPL waits for a line
        self.log = None                # core/session_log.Log of this run, if any
        self.tcl = tkinter.Tcl()
        # Tcl's puts writes to the terminal itself; to stdout and stderr it goes
        # through Python here, so the log file gets it (and the GUI's terminal).
        self.tcl.eval("rename ::puts ::__tcl_puts")
        self.tcl.createcommand("puts", self._puts)
        self.commands = command_pkg.discover()
        self.tcl.createcommand("__htree_dispatch", self._dispatch)
        # The source command replaces Tcl's; keep the original under another name.
        self.tcl.eval("rename ::source ::__tcl_source")
        self.tcl.eval(source_cmd.HELPER)
        for name in self.commands:
            self.tcl.eval(_WRAPPER.format(name=name))

    def _puts(self, *args):
        words = list(args)
        newline = not (words and words[0] == "-nonewline")
        if not newline:
            words = words[1:]
        channel, text = ("stdout", words[0]) if len(words) == 1 else \
            (words[0], words[1]) if len(words) == 2 else (None, None)
        if channel not in ("stdout", "stderr"):      # a file, a socket, a usage error
            return self.tcl.call("__tcl_puts", *args)
        stream = self.out if channel == "stdout" else sys.stderr
        stream.write(text + ("\n" if newline else ""))
        stream.flush()
        return ""

    def log_command(self, text: str):
        """Keep a command run (typed, given with -init, run by the GUI) in the
        cmd file of the run."""
        if self.log is not None:
            self.log.command(text)

    def split_list(self, text: str):
        return self.tcl.splitlist(text)

    def _dispatch(self, name, *argv):
        # Tcl 'puts' and Python print use separate buffers; flush both so
        # output stays in order when stdout is a pipe or a file.
        self.tcl.eval("flush stdout")
        try:
            return self._run(name, argv)
        finally:
            self.out.flush()
            for hook in self.after_command:
                try:
                    hook()
                except Exception as exc:  # a GUI bug must not fail the command
                    print(f"**ERROR: (HT4-999): internal error after {name}: "
                          f"{type(exc).__name__}: {exc}", file=self.out)

    def _run(self, name, argv):
        if "-help" in argv:               # every command: usage, options, an example
            from core.commands import man
            print(man.brief(self, name), file=self.out)
            return ("ok", "")
        try:
            result = self.commands[name].run(self, list(argv))
        except HtreeError as exc:
            print(exc.formatted(), file=self.out)
            return ("error", exc.formatted())
        except Exception as exc:  # a bug in a command, not a user error
            msg = f"**ERROR: (HT4-999): internal error in {name}: {type(exc).__name__}: {exc}"
            print(msg, file=self.out)
            return ("error", msg)
        if self.exit_code is not None:
            # Unwind the whole Tcl stack (scripts, loops); the caller exits.
            return ("error", EXIT_MARK)
        if result is None:
            result = ""
        if isinstance(result, list):
            result = tuple(result)
        return ("ok", result)

    def notify(self, text: str):
        """Print a message from outside a command (e.g. a GUI selection). At the
        prompt, it goes above the line being typed, which is then redrawn."""
        if not self._at_prompt:
            print(text, file=self.out, flush=True)
            return
        print(f"\r\033[K{text}", file=self.out, flush=True)
        try:
            from core import complete
            if complete._FORCED_REDISPLAY is not None:
                complete._FORCED_REDISPLAY()
                return
            import readline
            print(PROMPT + readline.get_line_buffer(), end="", file=self.out, flush=True)
        except ImportError:
            pass

    def eval(self, script: str) -> str:
        """Evaluate Tcl. Raises tkinter.TclError on error."""
        return self.tcl.eval(script)

    def source(self, path: str):
        self.tcl.call("source", path)

    def repl(self):
        prompt = PROMPT
        try:
            import readline  # noqa: F401  (history and line editing)
            from core import complete
            complete.install(self, lambda: prompt)
        except ImportError:
            pass
        buffer = ""
        while True:
            prompt = PROMPT if not buffer else "> "
            self._at_prompt = True
            try:
                if self.log is not None:     # readline needs the terminal's own stdout
                    with self.log.terminal():
                        line = input(prompt)
                else:
                    line = input(prompt)
            except EOFError:
                print(file=self.out)
                return
            except KeyboardInterrupt:
                print(file=self.out)
                buffer = ""
                continue
            finally:
                self._at_prompt = False
            if self.log is not None:
                self.log.typed(prompt, line)
            buffer = f"{buffer}\n{line}" if buffer else line
            if not self.tcl.call("info", "complete", buffer):
                continue
            script, buffer = buffer, ""
            if not script.strip():
                continue
            self.log_command(script)
            try:
                result = self.eval(script)
            except tkinter.TclError as exc:
                if self.exit_code is not None:
                    return
                text = str(exc)
                if not text.startswith("**ERROR"):   # command errors are already printed
                    print(f"**ERROR: {text}", file=self.out)
                continue
            if result:
                print(result, file=self.out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="htree_builder", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-init", metavar="SCRIPT", help="Tcl script to run at startup")
    parser.add_argument("-batch", action="store_true", help="exit after the -init script")
    parser.add_argument("-no_log", action="store_true",
                        help="write no log/htree.log and log/htree.cmd")
    args = parser.parse_args(argv)

    from core.session_log import Log
    log = None if args.no_log else Log().start(sys.argv[1:] if argv is None else list(argv))
    try:
        return _main(args, log)
    finally:
        if log is not None:
            log.stop()


def _main(args, log):
    session = Session()
    session.log = log
    if args.init:
        session.log_command(f"source {args.init}")
        try:
            session.source(args.init)
        except tkinter.TclError as exc:
            if session.exit_code is not None:
                return session.exit_code
            text = str(exc)
            if not text.startswith("**ERROR"):
                print(f"**ERROR: {text}", file=session.out)
            if args.batch:
                return 1
    if args.batch:
        return 0
    session.repl()
    return session.exit_code or 0


if __name__ == "__main__":
    sys.exit(main())
