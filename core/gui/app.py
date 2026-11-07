"""The Qt application and how it shares the process with the terminal prompt.

The GUI and the htree> prompt run in one thread. While the prompt waits for a
line, Python calls PyOS_InputHook; ours runs the Qt event loop until a key is
typed, then returns to readline. So the window stays live, and commands typed
in the terminal use the same Tcl interpreter and database as the GUI, with no
locking. (IPython uses the same mechanism.) While a command runs, the window
does not repaint; it refreshes when the command finishes.
"""

import ctypes
import os
import select
import subprocess
import sys

_app = None
_window = None
_hook = None              # keeps the ctypes callback alive


class DisplayError(Exception):
    pass


def check_display():
    """Raise DisplayError if Qt cannot open a window. Qt aborts the whole process
    when the display is unreachable, which would lose the in-memory database, so
    a throwaway child process tries first."""
    platform = os.environ.get("QT_QPA_PLATFORM", "")
    if platform.startswith(("offscreen", "minimal")):
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise DisplayError("no display: DISPLAY is not set (use VNC or ssh -X)")
    probe = "from PySide6.QtGui import QGuiApplication; QGuiApplication([])"
    try:
        r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                           timeout=30)
    except subprocess.TimeoutExpired:
        raise DisplayError(f"display {os.environ.get('DISPLAY')} does not answer")
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise DisplayError(f"cannot open display {os.environ.get('DISPLAY')}: {last}")


def show(session):
    """Open (or raise) the main window. Returns the window."""
    global _app, _window
    from PySide6.QtWidgets import QApplication
    from core.gui.main_window import MainWindow
    if _app is None:
        _app = QApplication.instance() or QApplication([sys.argv[0]])
        _install_input_hook()
    if _window is not None and _window.session is not session:
        close()                               # a new session gets a new window
    if _window is None:
        _window = MainWindow(session)
        session.after_command.append(_refresh_if_changed(session))
        _window.refresh()
    _window.show()
    _window.raise_()
    _window.activateWindow()
    _app.processEvents()
    return _window


def window():
    return _window


def close():
    """Close and forget the window (the Qt application stays)."""
    global _window
    if _window is not None:
        _window.session.after_command[:] = [
            h for h in _window.session.after_command if not getattr(h, "gui_hook", False)]
        _window.close()
        _window.deleteLater()
        _window = None


def _refresh_if_changed(session):
    """After each command, reload the view if the database changed."""
    state = {"key": _db_key(session)}

    def hook():
        key = _db_key(session)
        if key != state["key"]:
            state["key"] = key
            if _window is not None:
                _window.refresh()
        if _app is not None:
            _app.processEvents()
    hook.gui_hook = True
    return hook


def _db_key(session):
    conn = session.db.conn            # read_db swaps the connection
    return id(conn), conn.total_changes


def _install_input_hook():
    global _hook
    from PySide6.QtCore import QEventLoop

    def run_qt_until_input():
        try:
            while not select.select([sys.stdin], [], [], 0.01)[0]:
                _app.processEvents(QEventLoop.AllEvents, 10)
        except (ValueError, OSError):         # stdin closed
            pass
        return 0

    _hook = ctypes.CFUNCTYPE(ctypes.c_int)(run_qt_until_input)
    ctypes.c_void_p.in_dll(ctypes.pythonapi, "PyOS_InputHook").value = \
        ctypes.cast(_hook, ctypes.c_void_p).value
