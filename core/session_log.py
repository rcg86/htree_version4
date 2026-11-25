"""The log and command files of a run of the tool, in the directory log
under the directory it is started in (made when it is not there).

    log/htree.log    everything the tool prints: command output, messages,
                     Tcl puts, the commands typed (after the prompt)
    log/htree.cmd    the commands run: the -init script (source <file>),
                     each command typed at the prompt, each one the GUI runs

A run whose names are taken gets htree.log1 and htree.cmd1, then 2 ...: the
two files of one run have the same number, and nothing of an earlier run is
overwritten. Both are written as they go (flushed each line), so they are
complete up to a crash.
"""

import contextlib
import io
import os
import sys
import time

DIR = "log"                  # under the directory the tool is started in
BASE = "htree"


class Tee(io.TextIOBase):
    """A text stream that writes to a stream and to the log file."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, text):
        self.stream.write(text)
        self.log.write(text)
        if "\n" in text:
            self.log.flush()
        return len(text)

    def flush(self):
        self.stream.flush()
        self.log.flush()

    def isatty(self):
        return self.stream.isatty()

    def fileno(self):
        return self.stream.fileno()

    @property
    def encoding(self):
        return getattr(self.stream, "encoding", "utf-8")


class Log:
    """The two files of a run; start() makes them, stop() puts the streams
    back and closes them."""

    def __init__(self):
        self.log = self.cmd = None
        self.log_path = self.cmd_path = None
        self._streams = None

    def start(self, argv, where=None):
        folder = os.path.join(where or os.getcwd(), DIR)
        os.makedirs(folder, exist_ok=True)
        n = 0
        while True:
            suffix = str(n) if n else ""
            log_path = os.path.join(folder, f"{BASE}.log{suffix}")
            cmd_path = os.path.join(folder, f"{BASE}.cmd{suffix}")
            if not os.path.exists(log_path) and not os.path.exists(cmd_path):
                break
            n += 1
        self.log_path, self.cmd_path = log_path, cmd_path
        self.log = open(log_path, "w", encoding="utf-8")
        self.cmd = open(cmd_path, "w", encoding="utf-8")
        head = (f"# htree_builder {' '.join(argv)}\n# started {time.strftime('%Y-%m-%d %H:%M:%S')}"
                f" in {os.getcwd()}\n")
        for f in (self.log, self.cmd):
            f.write(head)
            f.flush()
        self._streams = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(sys.stdout, self.log), Tee(sys.stderr, self.log)
        print(f"Log: {log_path}\nCommands: {cmd_path}")
        return self

    def command(self, text):
        """Keep a command run (a script typed, given with -init, or run by the
        GUI) in the cmd file."""
        if self.cmd is None or not text.strip():
            return
        self.cmd.write(text.rstrip("\n") + "\n")
        self.cmd.flush()

    @contextlib.contextmanager
    def terminal(self):
        """The real sys.stdout and sys.stderr while in it: input() uses
        readline (line editing, history, <tab> completion) only when
        sys.stdout is the terminal's own stream, not the Tee."""
        if self._streams is None:
            yield
            return
        tees = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = self._streams
        try:
            yield
        finally:
            sys.stdout, sys.stderr = tees

    def typed(self, prompt, text):
        """A line typed at the prompt, into the log, after the prompt: input()
        writes neither to the log (it runs with the real streams, terminal())."""
        if self.log is not None:
            self.log.write(f"{prompt}{text}\n")
            self.log.flush()

    def stop(self):
        if self._streams is None:
            return
        for s in (sys.stdout, sys.stderr):
            try:
                s.flush()
            except (OSError, ValueError):
                pass
        sys.stdout, sys.stderr = self._streams
        self._streams = None
        stamp = f"# ended {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        for f in (self.log, self.cmd):
            f.write(stamp)
            f.close()
