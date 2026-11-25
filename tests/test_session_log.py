"""Each run of the tool writes log/htree.log (all it prints) and log/htree.cmd
(the commands), the directory made when it is not there; a later run gets
htree.log1 / htree.cmd1 ...; -no_log writes neither."""

import sys

import pytest

from core.htree_builder import main


def test_a_run_writes_its_log_and_cmd_files(log_dir, tmp_path, capsys):
    script = tmp_path / "run.tcl"
    script.write_text("puts hello\nputs -nonewline stdout {no line}\nputs stdout {}\n"
                      "set x [get_db root_attributes]\nnot_a_command\n")
    assert not log_dir.exists()
    assert main(["-init", str(script), "-batch"]) == 1         # stops on the bad command
    log, cmd = (log_dir / "htree.log").read_text(), (log_dir / "htree.cmd").read_text()
    assert log.startswith("# htree_builder -init ") and cmd.startswith("# htree_builder -init ")
    assert "hello\n" in log and "no line\n" in log                # Tcl puts, both forms
    assert "ignore_shield_less_than_routing_length" in log         # a command's output
    assert 'invalid command name "not_a_command"' in log            # the error
    assert f"source {script}\n" in cmd and "# ended " in cmd
    # the terminal still shows it all
    shown = capsys.readouterr().out
    assert "hello" in shown and f"Log: {log_dir / 'htree.log'}" in shown
    assert sys.stdout is not None and not hasattr(sys.stdout, "log")   # streams put back


def test_a_later_run_does_not_overwrite(log_dir, tmp_path):
    script = tmp_path / "run.tcl"
    script.write_text("puts first\n")
    main(["-init", str(script), "-batch"])
    script.write_text("puts second\n")
    main(["-init", str(script), "-batch"])
    assert "first" in (log_dir / "htree.log").read_text()
    assert "second" in (log_dir / "htree.log1").read_text()
    assert (log_dir / "htree.cmd1").exists()


def test_no_log(log_dir, tmp_path):
    script = tmp_path / "run.tcl"
    script.write_text("puts x\n")
    assert main(["-init", str(script), "-batch", "-no_log"]) == 0
    assert not log_dir.exists()


def test_puts_to_a_file_still_works(log_dir, tmp_path):
    out = tmp_path / "o.txt"
    script = tmp_path / "run.tcl"
    script.write_text(f"set f [open {out} w]\nputs $f inside\nclose $f\n")
    assert main(["-init", str(script), "-batch"]) == 0
    assert out.read_text() == "inside\n"
    assert "inside" not in (log_dir / "htree.log").read_text()


def test_tab_completes_at_the_prompt_with_the_log_on(tmp_path):
    # input() uses readline only with the terminal's own sys.stdout: the log's Tee
    # is taken off while the prompt waits (it once broke <tab>, history, editing)
    pty = pytest.importorskip("pty")
    pytest.importorskip("readline")
    import os
    import select
    import time
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pid, fd = pty.fork()
    if pid == 0:                          # the tool, at a terminal, in tmp_path
        os.chdir(tmp_path)
        env = dict(os.environ, HTREE4_SHORTCUTS=str(tmp_path / "sc.json"))
        os.execve(sys.executable, [sys.executable, os.path.join(root, "core",
                                                                "htree_builder.py")], env)
    got = b""

    def read(until, seconds=20):
        nonlocal got
        end = time.time() + seconds
        while until not in got and time.time() < end:
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    got += os.read(fd, 65536)
                except OSError:
                    return
    try:
        read(b"htree> ")
        os.write(fd, b"check_drc -check_o\t")
        read(b"-check_open_only")
        os.write(fd, b"\x15exit\n")       # clear the line, leave
        read(b"\x00", 5)
    finally:
        os.waitpid(pid, 0)
    assert b"check_drc -check_open_only" in got
    assert (tmp_path / "log" / "htree.log").exists()
