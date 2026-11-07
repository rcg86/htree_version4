import tkinter

import pytest

from conftest import ROOT, TECH_LEF
from core.htree_builder import main


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


# -- read_tech --------------------------------------------------------------------

def test_read_tech_summary(session):
    session.eval(f"read_tech -file {{{TECH_LEF}}}")
    out = session.out.getvalue()
    assert "LEF version : 5.8" in out
    assert "Layers      : 6 (H1 H2 G1 G2 IA IB)" in out


def test_read_tech_errors(session, tmp_path):
    assert "HT4-001" in err(session, "read_tech")
    assert "HT4-001" in err(session, "read_tech -bogus x")
    assert "HT4-010" in err(session, f"read_tech -file {tmp_path}/missing.lef")


def test_read_tech_replace_warns(tech_session):
    tech_session.eval(f"read_tech -file {{{TECH_LEF}}}")
    assert "WARN: (HT4-012)" in tech_session.out.getvalue()


def test_parse_error_leaves_db_unchanged(tech_session, write_lef):
    bad = write_lef("LAYER M1\n  WIDTH abc ;\nEND M1\n")
    msg = err(tech_session, f"read_tech -file {bad}")
    assert "HT4-011" in msg and "line 2" in msg
    assert tech_session.eval("get_db layers.name") == "H1 H2 G1 G2 IA IB"


def test_unmodeled_warns(session, write_lef):
    lef = write_lef("VERSION 5.8 ;\nSITE core\n  SIZE 1 BY 1 ;\nEND core\nEND LIBRARY\n")
    session.eval(f"read_tech -file {lef}")
    assert "WARN: (HT4-013): 1 SITE statement(s) not modeled" in session.out.getvalue()
    assert session.eval("get_db tech .extra").startswith("{SITE core")


# -- write_db / read_db -----------------------------------------------------------

def test_round_trip(tech_session, tmp_path):
    db = tmp_path / "design.db"
    tech_session.eval(f"write_db {db}")
    before = tech_session.out.getvalue()
    tech_session.eval("get_db tech")
    dump_before = tech_session.out.getvalue()[len(before):]

    from core.htree_builder import Session
    import io
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {db}")
    mark = len(fresh.out.getvalue())
    fresh.eval("get_db tech")
    assert fresh.out.getvalue()[mark:] == dump_before
    assert fresh.eval("get_db [get_db tech.layer -if {.name == IA}] .min_width") == "0.36"


def test_write_db_refuses_overwrite(tech_session, tmp_path):
    db = tmp_path / "design.db"
    tech_session.eval(f"write_db {db}")
    assert "HT4-030" in err(tech_session, f"write_db {db}")
    tech_session.eval(f"write_db {db} -overwrite")
    assert not list(tmp_path.glob("*.tmp*"))


def test_write_db_errors(session):
    assert "HT4-001" in err(session, "write_db")
    assert "HT4-031" in err(session, "write_db /nonexistent_dir/x.db")


def test_read_db_errors(session, tmp_path):
    assert "HT4-001" in err(session, "read_db")
    assert "HT4-040" in err(session, f"read_db {tmp_path}/none.db")
    junk = tmp_path / "junk.db"
    junk.write_text("not sqlite")
    assert "HT4-041" in err(session, f"read_db {junk}")


# -- man / help -------------------------------------------------------------------

def test_every_command_has_a_man_page(session):
    missing = [n for n in session.commands if not (ROOT / "docs" / "man" / f"{n}.md").is_file()]
    assert missing == []


def test_man_and_help(session):
    session.eval("man get_db")
    assert "get_db - query objects" in session.out.getvalue()
    assert "HT4-050" in err(session, "man nosuch")
    session.eval("help")
    out = session.out.getvalue()
    for name in ("get_db", "read_tech", "write_db", "read_db", "man", "help"):
        assert f"  {name}" in out


# -- batch mode -------------------------------------------------------------------

def test_batch_mode(tmp_path, capfd):
    good = tmp_path / "good.tcl"
    good.write_text(f"read_tech -file {{{TECH_LEF}}}\nputs [get_db layers.name]\n")
    assert main(["-init", str(good), "-batch"]) == 0
    bad = tmp_path / "bad.tcl"
    bad.write_text("puts first\nget_db layer:XX .name\nputs never\n")
    assert main(["-init", str(bad), "-batch"]) == 1
    out = capfd.readouterr().out
    assert "first" in out and "never" not in out


# -- exit -------------------------------------------------------------------------

def test_exit_stops_script_with_code(tmp_path, capfd):
    script = tmp_path / "exit.tcl"
    script.write_text("puts before\nforeach i {1 2} { exit 3 }\nputs after\n")
    assert main(["-init", str(script)]) == 3
    out = capfd.readouterr().out
    assert "before" in out and "after" not in out


def test_exit_bad_code(session):
    assert "HT4-001" in err(session, "exit abc")
    assert session.exit_code is None


# -- select_obj / deselect_obj / get_db selected (no GUI needed) -------------------------

SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def test_select_obj_and_get_db_selected(session):
    session.eval(f"read_def -file {{{SMALL_DEF}}}")
    assert session.eval("get_db selected") == ""
    session.eval("select_obj port:top/a {port:top/b port:top/c}")
    session.eval("select_obj port:top/a")                          # no duplicates
    assert session.eval("get_db selected") == "port:top/a port:top/b port:top/c"
    assert session.eval("get_db selected .name -if {.direction == in}") == "a"
    session.eval("deselect_obj port:top/b")
    assert session.eval("get_db selected .name") == "a c"
    session.eval("select_obj [get_db ports -if {.direction == out}]")
    assert session.eval("get_db selected .name") == "a c {y[0]}"     # Tcl braces brackets
    session.eval("deselect_obj -all")
    assert session.eval("get_db selected") == ""


def test_select_obj_errors(session):
    session.eval(f"read_def -file {{{SMALL_DEF}}}")
    assert "HT4-001" in err(session, "select_obj")
    assert "HT4-001" in err(session, "select_obj notahandle")
    assert "HT4-022" in err(session, "select_obj port:top/zz")
    assert "HT4-001" in err(session, "deselect_obj")
    assert "HT4-001" in err(session, "deselect_obj -all port:top/a")
    assert session.eval("get_db selected") == ""                   # nothing half-done


def test_selection_is_not_saved(session, tmp_path):
    session.eval(f"read_def -file {{{SMALL_DEF}}}")
    session.eval("select_obj port:top/a")
    session.eval(f"write_db {tmp_path}/s.db")
    import io
    from core.htree_builder import Session
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path}/s.db")
    assert fresh.eval("get_db selected") == ""


def test_after_command_hook_error_does_not_fail_command(session):
    def broken():
        raise RuntimeError("boom")
    session.after_command.append(broken)
    assert session.eval("set x 5") == "5"
    session.eval("help")                                     # an htree command
    assert "internal error after help: RuntimeError: boom" in session.out.getvalue()
