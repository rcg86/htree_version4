import tkinter

import pytest

from conftest import TECH_LEF
from core.htree_builder import main


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def script(tmp_path):
    def _write(body, name="run.tcl"):
        path = tmp_path / name
        path.write_text(body)
        return str(path)
    return _write


def test_runs_tool_and_tcl_commands(session, script):
    path = script(f"read_tech -file {{{TECH_LEF}}}\n"
                  "set names [get_db layers .name]\n"
                  "proc twice {x} { return \"$x$x\" }\n")
    session.eval(f"source {path}")
    assert session.eval("set names") == "H1 H2 G1 G2 IA IB"
    assert session.eval("twice ab") == "abab"          # procs stay defined


def test_returns_last_result(session, script):
    path = script("set a 1\nset b 2\n")
    assert session.eval(f"source {path}") == "2"


def test_multiline_commands(session, script):
    path = script("set total 0\n"
                  "foreach x {1 2\n 3} {\n  incr total $x\n}\n"
                  "set s [string cat \\\n  a b]\n")
    session.eval(f"source {path}")
    assert session.eval("set total") == "6"
    assert session.eval("set s") == "ab"


def test_stops_at_tool_error_with_file_and_line(session, script):
    path = script("set a 1\n\nget_db layer:XX .name\nset never 1\n")
    msg = err(session, f"source {path}")
    assert msg == f"**ERROR: (HT4-071): source: stopped at {path} line 3"
    out = session.out.getvalue()
    assert "HT4-025" in out or "HT4-022" in out         # the command's own error first
    assert session.eval("info exists never") == "0"


def test_tcl_error_reports_line_and_message(session, script):
    path = script("set a 1\nnosuchcmd x\n")
    msg = err(session, f"source {path}")
    assert msg == f'**ERROR: (HT4-071): source: {path} line 2: invalid command name "nosuchcmd"'


def test_multiline_error_reports_first_line(session, script):
    path = script("set a 1\nif {1} {\n  nosuchcmd\n}\n")
    assert f"{path} line 2:" in err(session, f"source {path}")


def test_unclosed_brace(session, script):
    path = script("set a 1\nforeach x {1 2} {\n  puts $x\n")
    assert "line 2: command not complete" in err(session, f"source {path}")


def test_nested_sources_report_each_level(session, script):
    inner = script("set a 1\nnosuchcmd\n", "inner.tcl")
    outer = script(f"set b 1\nsource {inner}\n", "outer.tcl")
    msg = err(session, f"source {outer}")
    assert msg == f"**ERROR: (HT4-071): source: stopped at {outer} line 2"
    assert f"{inner} line 2: invalid command name" in session.out.getvalue()


def test_catch_keeps_going(session, script):
    path = script("catch {get_db layer:XX .name}\nset after 1\n")
    session.eval(f"source {path}")
    assert session.eval("set after") == "1"


def test_return_ends_file(session, script):
    path = script("set a 1\nreturn done\nset a 2\n")
    assert session.eval(f"source {path}") == "done"
    assert session.eval("set a") == "1"


def test_break_outside_loop(session, script):
    path = script("break\n")
    assert 'invoked "break" outside of a loop' in err(session, f"source {path}")


def test_info_script(session, script):
    path = script("set me [info script]\n")
    session.eval(f"source {path}")
    assert session.eval("set me") == path
    assert session.eval("info script") == ""


def test_echo(session, script, capfd):
    path = script("# a comment\nputs hello\nset x [expr {1 +\n 2}]\n")
    session.eval(f"source -echo {path}")
    session.eval("flush stdout")
    out = session.out.getvalue()
    assert "htree> puts hello\n" in out
    assert "htree> set x [expr {1 +\n 2}]\n" in out
    assert "a comment" not in out
    assert capfd.readouterr().out == "hello\n"


def test_errors(session, tmp_path):
    assert "HT4-001" in err(session, "source")
    assert "HT4-001" in err(session, "source -bogus x")
    assert "HT4-070" in err(session, f"source {tmp_path}/none.tcl")


def test_exit_inside_sourced_file(tmp_path, capfd):
    inner = tmp_path / "inner.tcl"
    inner.write_text("puts in\nexit 4\nputs never\n")
    outer = tmp_path / "outer.tcl"
    outer.write_text(f"source {inner}\nputs never2\n")
    assert main(["-init", str(outer)]) == 4
    out = capfd.readouterr().out
    assert "in" in out and "never" not in out and "HT4-071" not in out


def test_batch_error_names_line(tmp_path, capfd):
    bad = tmp_path / "bad.tcl"
    bad.write_text("puts first\nget_db layer:XX .name\n")
    assert main(["-init", str(bad), "-batch"]) == 1
    assert f"stopped at {bad} line 2" in capfd.readouterr().out
