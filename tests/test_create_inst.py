import io
import tkinter

import pytest

from conftest import ROOT
from core.htree_builder import Session
from core.placement import placed_bbox, placer, point_in_polygon, rect_in_polygon

CELLS_LEF = ROOT / "tests" / "data" / "cells.lef"
SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def lib(tech_session):
    tech_session.eval(f"read_lef -file {{{CELLS_LEF}}}")
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


# -- placement geometry ------------------------------------------------------------------

@pytest.mark.parametrize("orient, bbox", [
    ("N", (10, 20, 12, 21)), ("S", (10, 20, 12, 21)), ("FN", (10, 20, 12, 21)),
    ("FS", (10, 20, 12, 21)), ("W", (10, 20, 11, 22)), ("E", (10, 20, 11, 22)),
    ("FW", (10, 20, 11, 22)), ("FE", (10, 20, 11, 22)),
])
def test_location_is_lower_left_for_every_orient(orient, bbox):
    assert placed_bbox(2, 1, orient, 10, 20) == bbox


def test_placer_maps_cell_corners():
    place = placer(2, 1, "S", 10, 20)            # rotated 180: (0,0) -> top right
    assert place(0, 0) == (12, 21) and place(2, 1) == (10, 20)
    place = placer(2, 1, "FN", 10, 20)           # mirrored in x
    assert place(0, 0) == (12, 20)


def test_inside_polygon():
    L = [0, 0, 10, 0, 10, 5, 4, 5, 4, 10, 0, 10]     # L shape
    assert point_in_polygon(2, 8, L) and not point_in_polygon(8, 8, L)
    assert point_in_polygon(10, 2, L)                 # on an edge
    assert rect_in_polygon((1, 1, 3, 9), L)
    assert not rect_in_polygon((3, 3, 6, 7), L)       # crosses the notch corner
    assert not rect_in_polygon((-1, 1, 3, 3), L)


# -- create_inst --------------------------------------------------------------------------

def test_create_inst(lib):
    h = lib.eval("create_inst -ref_cell INV_D1 -location {50 40}")
    assert h == "inst:inst_1"
    ev = lib.eval
    assert ev("get_db inst:inst_1 .ref_name") == "INV_D1"
    assert ev("get_db inst:inst_1 .lib_cell") == "lib_cell:INV_D1"
    assert ev("get_db inst:inst_1 .location") == "50 40"
    assert ev("get_db inst:inst_1 .orient") == "N"
    assert ev("get_db inst:inst_1 .bbox") == "50 40 50.6 40.254"
    assert ev("get_db inst:inst_1 .status") == "placed"
    assert ev("get_db inst:inst_1 .lib_cell.size_x") == "0.6"
    assert "Created inst:inst_1 (INV_D1) at {50 40} N, bbox {50 40 50.6 40.254}" in \
        lib.out.getvalue()


def test_name_orient_and_auto_names(lib):
    lib.eval("create_inst -ref_cell lib_cell:INV_D2 -location {10 10} -name drv -orient E")
    assert lib.eval("get_db inst:drv .bbox") == "10 10 10.508 11.2"     # 1.2 x 0.508 rotated
    lib.eval("create_inst -ref_cell INV_D1 -location {20 10}")
    lib.eval("create_inst -ref_cell INV_D1 -location {30 10}")
    assert lib.eval("get_db insts .name") == "drv inst_2 inst_3"


def test_warnings(lib):
    lib.eval("create_inst -ref_cell INV_D1 -location {50 40} -name a")
    lib.eval("create_inst -ref_cell INV_D1 -location {50.3 40} -name b")      # overlaps a
    lib.eval("create_inst -ref_cell INV_D1 -location {60 60} -name c")        # in the notch
    lib.eval("create_inst -ref_cell INV_D1 -location {1.00001 1} -name d")    # off grid
    out = lib.out.getvalue()
    assert "WARN: (HT4-123): b overlaps instance a" in out
    assert "WARN: (HT4-122): c bbox {60 60 60.6 60.254} is not inside the design boundary" in out
    assert "WARN: (HT4-124): location {1.00001 1} is not on the manufacturing grid" in out
    lib.eval("create_inst -ref_cell INV_D1 -location {49.4 40} -name e")      # touches a only
    assert "e overlaps" not in lib.out.getvalue()


@pytest.mark.parametrize("cmd, msg_id, text", [
    ("create_inst -location {1 1}", "HT4-001", "-ref_cell and -location are required"),
    ("create_inst -ref_cell INV_D1", "HT4-001", "-ref_cell and -location are required"),
    ("create_inst -ref_cell INV_D1 -location {1}", "HT4-001", "two numbers"),
    ("create_inst -ref_cell INV_D1 -location {a b}", "HT4-001", "two numbers"),
    ("create_inst -ref_cell INV_D1 -location {1 1} -orient R90", "HT4-001", "-orient must be"),
    ("create_inst -ref_cell NOPE -location {1 1}", "HT4-120", "'NOPE' is not in the library"),
    ("create_inst -ref_cell PAD1 -location {1 1}", "HT4-120", "has no SIZE"),
    ("create_inst -ref_cell INV_D1 -location {1 1} -name a/b", "HT4-001", "must not"),
])
def test_errors(lib, cmd, msg_id, text):
    msg = err(lib, cmd)
    assert msg_id in msg and text in msg
    assert lib.eval("get_db insts") == ""


def test_duplicate_name_and_no_library(lib, tech_session):
    lib.eval("create_inst -ref_cell INV_D1 -location {1 1} -name x")
    assert "HT4-121" in err(lib, "create_inst -ref_cell INV_D1 -location {5 5} -name x")
    bare = Session(out=io.StringIO())
    assert "HT4-026" in err(bare, "create_inst -ref_cell INV_D1 -location {1 1}")


def test_saved_by_write_db_and_selectable(lib, tmp_path):
    lib.eval("create_inst -ref_cell INV_D1 -location {50 40} -name u1")
    lib.eval("select_obj inst:u1")
    assert lib.eval("get_db selected .ref_name") == "INV_D1"
    lib.eval(f"write_db {tmp_path}/i.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path}/i.db")
    assert fresh.eval("get_db inst:u1 .bbox") == "50 40 50.6 40.254"


def test_read_db_file_option_continues_the_session(lib, tmp_path):
    lib.eval("create_inst -ref_cell INV_D1 -location {50 40}")
    lib.eval("create_route_rule -name r1 -layer H2 -width 0.1 -spacing 0.1")
    lib.eval(f"write_db -file {tmp_path}/c.db")
    fresh = Session(out=io.StringIO())
    fresh.db.selection.append("inst:stale")          # left over from before the read
    fresh.eval(f"read_db -file {tmp_path}/c.db")
    out = fresh.out.getvalue()
    for label in ("Tech", "Library", "Design", "Route rules", "Instances"):
        assert f"  {label}" in out, label
    assert fresh.db.selection == []
    # the next instance continues the numbering of the saved session
    assert fresh.eval("create_inst -ref_cell INV_D1 -location {60 40}") == "inst:inst_2"
    assert fresh.eval("get_db route_rule_layer:r1/H2 .spacing") == "0.1"


def test_read_db_file_errors(session, tmp_path):
    assert "HT4-001" in err(session, f"read_db -file {tmp_path}/a.db {tmp_path}/a.db")
    assert "HT4-040" in err(session, f"read_db -file {tmp_path}/none.db")
    assert "HT4-001" in err(session, f"write_db -file {tmp_path}/a.db {tmp_path}/b.db")
    session.eval(f"write_db -file {tmp_path}/empty.db")
    session.eval(f"read_db -file {tmp_path}/empty.db")
    assert "(the database is empty)" in session.out.getvalue()
