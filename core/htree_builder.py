"""htree_builder: Tcl command shell (CUI) over the htree design database.

    python core/htree_builder.py                    interactive prompt
    python core/htree_builder.py -init run.tcl      run a script, then prompt
    python core/htree_builder.py -init run.tcl -batch   run a script, then exit
"""

import argparse
import sys
import tkinter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:      # allow "python core/htree_builder.py"
    sys.path.insert(0, str(ROOT))

from core import commands as command_pkg  # noqa: E402
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
        self.tcl = tkinter.Tcl()
        self.commands = command_pkg.discover()
        self.tcl.createcommand("__htree_dispatch", self._dispatch)
        for name in self.commands:
            self.tcl.eval(_WRAPPER.format(name=name))

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

    def _run(self, name, argv):
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
            try:
                line = input(prompt)
            except EOFError:
                print(file=self.out)
                return
            except KeyboardInterrupt:
                print(file=self.out)
                buffer = ""
                continue
            buffer = f"{buffer}\n{line}" if buffer else line
            if not self.tcl.call("info", "complete", buffer):
                continue
            script, buffer = buffer, ""
            if not script.strip():
                continue
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
    args = parser.parse_args(argv)

    session = Session()
    if args.init:
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
