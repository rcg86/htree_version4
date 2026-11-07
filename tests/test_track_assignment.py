import io
import tkinter

import pytest

from core.commands.assign_track_for_route import parse_pattern
from core.htree_builder import Session

# Test tech: H1 horizontal, H2 vertical, G1 horizontal. Units 100/um.
DEF = """DESIGN t ;
UNITS DISTANCE MICRONS 100 ;
DIEAREA ( 0 0 ) ( 1000 1000 ) ;
TRACKS Y 50 DO 10 STEP 100 LAYER H1 ;
TRACKS X 25 DO 3 STEP 100 MASK 1 LAYER H2 ;
TRACKS X 75 DO 3 STEP 100 MASK 2 LAYER H2 ;
TRACKS X 50 DO 10 STEP 100 LAYER G1 ;
PINS 2 ;
- VDD + NET VDD + SPECIAL + DIRECTION INOUT + USE POWER ;
- VSS + NET VSS + SPECIAL + DIRECTION INOUT + USE GROUND ;
END PINS
END DESIGN
"""


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def design(tech_session, write_lef):
    tech_session.eval(f"read_def -file {write_lef(DEF, 't.def')}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


@pytest.mark.parametrize("text", ["VDD, - , VSS, -", "VDD - VSS -", "VDD,-,VSS,-"])
def test_parse_pattern(text):
    assert parse_pattern(text) == ["VDD", "-", "VSS", "-"]


def test_user_pattern_numbering(design):
    design.eval("assign_track_for_route -net {VDD, - , VSS, -} -layer H1")
    tracks = design.split_list(design.eval("get_db track_assignment:H1 .tracks"))
    # H1 is horizontal: TRACKS Y at y = 0.5 + n
    assert tracks == ("0.5 VDD", "1.5 -", "2.5 VSS", "3.5 -", "4.5 VDD", "5.5 -",
                      "6.5 VSS", "7.5 -", "8.5 VDD", "9.5 -")
    out = design.out.getvalue()
    assert "Track assignment for H1 (horizontal, DEF TRACKS Y): 10 tracks, y 0.5 .. 9.5" in out
    assert "  VDD         : 3 tracks, first at y 0.5" in out
    assert "  VSS         : 2 tracks, first at y 2.5" in out
    assert "  signal      : 5 tracks, first at y 1.5" in out


def test_attrs(design):
    design.eval("assign_track_for_route -net {VDD - VSS -} -layer H1")
    ev = design.eval
    assert ev("get_db track_assignments") == "track_assignment:H1"
    assert ev("get_db track_assignment:H1 .direction") == "y"
    assert ev("get_db track_assignment:H1 .pattern") == "VDD - VSS -"
    assert ev("get_db track_assignment:H1 .period") == "4"
    assert ev("get_db track_assignment:H1 .num_tracks") == "10"
    assert ev("get_db track_assignment:H1 .counts") == "VDD 3 VSS 2 - 5"


def test_vertical_layer_merges_mask_patterns(design):
    design.eval("assign_track_for_route -net {VSS -} -layer H2")
    tracks = design.split_list(design.eval("get_db track_assignment:H2 .tracks"))
    # two X patterns (masks) merged in coordinate order: 0.25 0.75 1.25 1.75 2.25 2.75
    assert tracks == ("0.25 VSS", "0.75 -", "1.25 VSS", "1.75 -", "2.25 VSS", "2.75 -")


def test_replace_and_unknown_net_warn(design):
    design.eval("assign_track_for_route -net {VDD -} -layer H1")
    design.eval("assign_track_for_route -net {VDDX -} -layer H1")
    out = design.out.getvalue()
    assert "WARN: (HT4-113): replacing the previous track assignment of H1" in out
    assert "WARN: (HT4-112): net 'VDDX' is not the net of any port in design t" in out
    assert design.eval("get_db track_assignment:H1 .pattern") == "VDDX -"


@pytest.mark.parametrize("cmd, msg_id, text", [
    ("assign_track_for_route -layer H1", "HT4-001", "-net and -layer are required"),
    ("assign_track_for_route -net {VDD -}", "HT4-001", "-net and -layer are required"),
    ("assign_track_for_route -net {} -layer H1", "HT4-001", "-net is empty"),
    ("assign_track_for_route -net {- -} -layer H1", "HT4-001", "names no net"),
    ("assign_track_for_route -net {VDD -} -layer M1", "HT4-110", "'M1' is not in tech"),
    ("assign_track_for_route -net {VDD -} -layer IA", "HT4-111", "no tracks on IA"),
])
def test_errors(design, cmd, msg_id, text):
    msg = err(design, cmd)
    assert msg_id in msg and text in msg


def test_wrong_direction_tracks(design):
    # G1 is horizontal in tech but the DEF only has TRACKS X for it
    msg = err(design, "assign_track_for_route -net {VDD -} -layer G1")
    assert "HT4-111" in msg and "needs DEF 'TRACKS Y'" in msg and "only TRACKS X for G1" in msg


def test_needs_tech_and_design(tech_session):
    bare = Session(out=io.StringIO())                       # nothing loaded
    assert "run read_tech first" in err(bare, "assign_track_for_route -net {VDD -} -layer H1")
    assert "run read_def first" in err(tech_session,
                                       "assign_track_for_route -net {VDD -} -layer H1")


def test_saved_by_write_db(design, tmp_path):
    design.eval("assign_track_for_route -net {VDD - VSS -} -layer H1")
    design.eval(f"write_db {tmp_path}/t.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path}/t.db")
    assert fresh.eval("get_db track_assignment:H1 .counts") == "VDD 3 VSS 2 - 5"


def test_missing_object(design):
    assert "HT4-022" in err(design, "get_db track_assignment:H1 .pattern")
