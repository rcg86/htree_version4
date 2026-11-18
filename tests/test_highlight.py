"""highlight: colour objects in the GUI from Tcl (session state, db.highlights),
the same colours Edit > Highlight gives."""

import pytest

pytest.importorskip("scipy")

from core import highlight
from test_route_net import DEF, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import err, out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import _route, routed, via_session  # noqa: F401  (fixtures)

NET = "spine_net:sp/sp_L1_inv1_Y"


def test_colour_names_and_hex():
    assert highlight.color_of("Red") == "#ff1744"
    assert highlight.color_of("gray") == highlight.COLORS["grey"]
    assert highlight.color_of("#0F0") == "#00ff00"
    assert highlight.color_of("#12ab34") == "#12ab34"
    assert highlight.color_of("bluish") is None and highlight.color_of("#12ab3") is None


def test_colour_and_clear(routed):
    s = routed
    assert s.eval("highlight -object sp_L1_inv1_Y -color red") == NET
    assert "highlight: 1 object(s) coloured #ff1744: spine_net:sp/sp_L1_inv1_Y" in out_of(s)
    wire = s.split_list(s.eval("get_db net_wires sp_L1_inv1_Y/*"))[0]
    s.eval(f"highlight -object {{{wire} inst:sp_L1_inv1}} -color #00f")
    assert highlight.coloured(s.db) == [(NET, "#ff1744"), (wire, "#0000ff"),
                                        ("inst:sp_L1_inv1", "#0000ff")]
    s.eval(f"highlight -object {NET} -color green")          # again: the new colour, last
    assert s.db.highlights[-1] == (NET, "#00e676") and len(s.db.highlights) == 3
    s.eval(f"highlight -clear -object {wire}")
    assert "colour taken off 1 object(s)" in out_of(s)
    assert s.db.highlights[-1] == (wire, None)                # off the net's colour too
    assert (wire, "#0000ff") not in s.db.highlights
    s.eval("highlight -clear")
    assert s.db.highlights == []
    assert "highlight: colour taken off every object (2)" in out_of(s)
    s.eval("highlight -clear")
    assert "highlight: nothing was coloured" in out_of(s)


def test_patterns_and_the_whole_spine(routed):
    s = routed
    got = s.split_list(s.eval("highlight -object sp_L3* -color yellow"))
    assert "inst:sp_L3_inv1" in got and "spine_net:sp/sp_L3_inv1_Y" in got
    assert s.eval("highlight -object spine:sp -color cyan") == "spine:sp"


def test_errors(routed):
    s = routed
    assert "HT4-290" in err(s, "highlight -object sp_L1_inv1_Y -color bluish")
    assert "HT4-291" in err(s, "highlight -object nothing_here -color red")
    assert "HT4-291" in err(s, "highlight -object net:nothing_here -color red")
    assert "HT4-022" in err(s, "highlight -object inst:nope -color red")
    assert "give -object and -color" in err(s, "highlight -object sp_L1_inv1_Y")
    assert "-clear takes no -color" in err(s, "highlight -clear -color red")
    assert s.db.highlights == []


def test_read_db_drops_the_colours(routed, tmp_path):
    s = routed
    s.eval(f"write_db -file {tmp_path / 'h.db'}")
    s.eval("highlight -object sp_L1_inv1_Y -color red")
    s.eval(f"read_db -file {tmp_path / 'h.db'}")
    assert s.db.highlights == []


def test_tab_completes_the_colour_names(routed):
    from core.complete import Completer
    c = Completer(routed)
    line = "highlight -object x -color b"
    assert c.candidates(line, len(line) - 1, "b") == ["blue ", "brown ", "black "]
    assert "-color " in c.candidates("highlight -", 10, "-")
