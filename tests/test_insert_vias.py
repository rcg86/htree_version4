"""insert_vias: vias where two wires of one net cross on two layers."""

import io
import sqlite3
from collections import Counter

import pytest

pytest.importorskip("scipy")

from core import vias
from core.gui.layout_data import load_layout
from core.htree_builder import Session
from test_check_drc import check, wires
from test_route_pin import CELL_LEF, err, out_of
from test_route_pin import DEF as PIN_DEF
from test_vias import lst, routed, via_session  # noqa: F401  (fixtures)
from via_tech import tech_text

EVERYWHERE = "{-100 -100 100 100}"
# A wire along x on IA and one along y on IB: they cross at CROSS.
ACROSS = ("wire", "IA", "0 0 10 0.4")
UP = ("wire", "IB", "5 -5 5.4 5")
CROSS = "5 0 5.4 0.4"
SOURCE = "net_wire:auto_via:net_wire:n/2/1"          # the via of n, under its IB wire


def insert(s, bottom="IA", top="IB", more="", area=EVERYWHERE):
    """(the via handles returned, the report) of an insert_vias; area None: no -area."""
    where = f"-area {area}" if area is not None else ""
    found = lst(s, f"insert_vias -bottom_layer {bottom} -top_layer {top} {where} {more}")
    return found, out_of(s)


def table(s, net):
    """(kind, via_def, bottom, cut, top, rect) of the vias of a net."""
    return [(r["kind"], r["via_def"], r["bottom"], r["cut"], r["top"], r["rect"])
            for r in vias.rows(s.db, net)]


def inserted(s):
    """(net, layer, rect, shield net, via definitions) of the insert_via rows."""
    return [(r["net"], r["layer"], r["rect"], r["shield_net"], r["via_def"])
            for r in s.db.net_wire_rows() if r["kind"] == "insert_via"]


@pytest.fixture
def crossed(via_session):
    """Net n: a wire on IA and one on IB that cross, and no via."""
    wires(via_session, "n", ACROSS, UP)
    out_of(via_session)
    return via_session


# -- the crossings -----------------------------------------------------------------

def test_a_crossing_of_one_net_gets_a_via(crossed):
    s = crossed
    assert table(s, "n") == []
    found, text = insert(s)
    assert found == ["via:n/1"]
    assert table(s, "n") == [("insert", None, "IA", "C6", "IB", CROSS)]
    assert s.eval("get_db via:n/1 .source") == SOURCE
    # kept under the wire on the top layer, on the net of the two wires
    assert inserted(s) == [("auto_via:net_wire:n/2", "IA/IB", CROSS, "n", None)]
    assert "insert_vias: IA to IB in {-100 -100 100 100}: 1 crossing(s)" in text
    assert "Inserted      : 1 via(s) at 1 crossing(s) (cut layers C6)" in text
    assert "Nets          : n(1)" in text
    assert "Definitions   : none; 1 via(s) have none" in text


def test_again_inserts_nothing(crossed):
    s = crossed
    insert(s)
    found, text = insert(s)
    assert found == [] and len(inserted(s)) == 1 and len(table(s, "n")) == 1
    assert "Inserted      : 0 via(s) at 0 crossing(s)" in text
    assert "Already there : 1 crossing(s)" in text


def test_wires_of_two_nets_get_no_via(via_session):
    s = via_session
    wires(s, "a", ACROSS)
    wires(s, "b", UP)
    found, text = insert(s)
    assert found == [] and inserted(s) == []
    assert "0 crossing(s)" in text
    assert "No wire or pin on IA crosses a wire of its own net on IB inside the area" in text


def test_a_crossing_box_of_the_router_is_already_a_via(routed):
    s = routed
    before = [tuple(r) for r in vias.rows(s.db)]
    found, text = insert(s)
    assert found == [] and inserted(s) == []
    assert "Already there : 11 crossing(s)" in text
    assert [tuple(r) for r in vias.rows(s.db)] == before


def test_shields_and_straps_are_on_their_power_net(routed):
    s = routed
    # A VSS shield on IB over the L2 cell's VSS strap 4 (1.32 9.14 4.44 9.86), its
    # VDD_SOC straps 6 and 7 and its sp_L1_inv1_Y strap 5: a via to the VSS strap only.
    wires(s, "extra", ("shield", "IB", "1.98 4.5 2.34 9.86", "VSS"))
    opens = len(check(s, "-check_open_only")[1]["Opens, power nets"])
    found, _ = insert(s, more="-nets VSS")
    assert [(r["net"], r["kind"], r["rect"]) for r in vias.rows(s.db) if r["kind"] == "insert"] \
        == [("VSS", "insert", "1.98 9.14 2.34 9.86")]
    assert found == [vias.handle(r) for r in vias.rows(s.db) if r["kind"] == "insert"]
    assert inserted(s) == [("auto_via:net_wire:extra/1", "IA/IB", "1.98 9.14 2.34 9.86",
                            "VSS", None)]
    # the shield now hangs on that strap: its open is gone (tests/test_check_drc.py)
    power = check(s, "-check_open_only")[1]["Opens, power nets"]
    assert len(power) < opens and not any("net_wire:extra/1" in v for v in power)


def test_straps_of_unrouted_pins_get_no_via(routed):
    s = routed
    found, text = insert(s, bottom="H2", top="IA")
    kinds = Counter(r["net"] for r in vias.rows(s.db) if r["kind"] == "insert")
    # the pin wires on H2 under the other straps of their power net; 3 vias each
    assert kinds == {"VSS": 12, "VDD_SOC": 30} and len(found) == 42
    assert "Nets          : VSS(4) VDD_SOC(10)" in text


# -- instance pins -----------------------------------------------------------------

Y1, Y2, A = "1 0.2 1.4 0.7", "1 1.1 1.4 1.6", "8.523 0.348 8.933 1.444"   # D12, placed


@pytest.fixture
def pinned(via_session, write_lef):
    """Net u1_Y from u1/Y (two D12 rectangles) to u2/A (one), no pin wires: an H2
    wire over each pin and an IA wire that joins the two."""
    s = via_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(PIN_DEF, 'd.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.eval("create_inst -ref_cell INV_RP -location {6 0} -name u2")
    s.eval("connect_pin -from u1/Y -to u2/A")
    wires(s, "u1_Y", ("wire", "H2", "1 -1 1.4 3"), ("wire", "IA", "1 2.6 8.933 3"),
          ("wire", "H2", "8.523 0 8.933 3"))
    out_of(s)
    return s


def test_every_rectangle_of_a_pin_gets_a_via(pinned):
    s = pinned
    opens = check(s, "-check_open_only")[0]
    assert opens == 4                                 # the three wires and the load
    found, text = insert(s, bottom="D12", top="H2")
    # Y is two rectangles: a stack on each. A is one.
    stack = lambda box: [("insert", None, "D12", "C1", "H1", box),      # noqa: E731
                         ("insert", None, "H1", "C2", "H2", box)]
    assert table(s, "u1_Y") == stack(Y1) + stack(Y2) + stack(A)
    assert found == [f"via:u1_Y/{k}" for k in range(1, 7)]
    # kept under the wire that lies over the pin
    assert inserted(s) == [("auto_via:net_wire:u1_Y/1", "D12/H2", Y1, "u1_Y", None),
                           ("auto_via:net_wire:u1_Y/1", "D12/H2", Y2, "u1_Y", None),
                           ("auto_via:net_wire:u1_Y/3", "D12/H2", A, "u1_Y", None)]
    assert "3 crossing(s)" in text
    assert "On pins       : 3 of them a wire over a pin rectangle on D12" in text
    assert "Inserted      : 6 via(s) at 3 crossing(s) (cut layers C1 C2)" in text
    insert(s, bottom="H2", top="IA")                  # the wires to each other
    assert check(s, "-check_open_only")[0] == 0       # the net is whole, pins and all
    found, text = insert(s, bottom="D12", top="H2")
    assert found == [] and "Already there : 3 crossing(s)" in text


def test_pin_rectangles_follow_area_nets_and_the_net_of_the_pin(pinned):
    s = pinned
    # the area holds the lower rectangle of Y only
    found, text = insert(s, bottom="D12", top="H2", area="{0 0 2 1}")
    assert [r[-1] for r in table(s, "u1_Y")] == [Y1, Y1] and len(found) == 2
    assert "Not in -area" not in text
    # a wire of another net over a pin, and a pin on no net (u2/Y): no via
    wires(s, "other", ("wire", "H2", "8.523 0 8.933 3"), ("wire", "H2", "7 -1 7.4 3"))
    found, text = insert(s, bottom="D12", top="H2", more="-nets other")
    assert found == [] and "0 crossing(s)" in text
    assert "No wire or pin on D12 crosses a wire of its own net on H2 inside the area, " \
           "of the nets given" in text
    found, _ = insert(s, bottom="D12", top="H2", more="-nets u1_*")
    assert [r[-1] for r in table(s, "u1_Y")] == [Y1, Y1, Y2, Y2, A, A] and len(found) == 4


def test_a_pin_under_its_pin_wire_is_already_connected(routed):
    s = routed
    before = [tuple(r) for r in vias.rows(s.db)]
    found, text = insert(s, bottom="D12", top="H2")
    # 4 instances, 6 rectangles each (Y and VDD have two), power pins on the net of
    # their pin wire: route_pin's vias are there. The pin wire of the root's input is
    # on no net yet (SIGNAL): not a crossing.
    assert found == [] and inserted(s) == []
    assert "23 crossing(s)" in text and "On pins       : 23 of them" in text
    assert "Already there : 23 crossing(s)" in text
    assert s.db.pin_wire_row("sp_L1_inv1", "A")["net"] in (None, "SIGNAL")
    assert [tuple(r) for r in vias.rows(s.db)] == before


# -- stacks and -via_ref -----------------------------------------------------------

@pytest.fixture
def stacked(via_session):
    """Net n: a wire on H2 under one on IA, three cut layers apart."""
    wires(via_session, "n", ("wire", "H2", "0 0 10 0.4"), ("wire", "IA", "5 -5 5.4 5"))
    out_of(via_session)
    return via_session


def test_a_stack_through_the_cut_layers_between(stacked):
    s = stacked
    found, text = insert(s, bottom="H2", top="IA")
    assert found == ["via:n/1", "via:n/2", "via:n/3"]
    assert table(s, "n") == [("insert", None, "H2", "C3", "G1", CROSS),
                             ("insert", None, "G1", "C4", "G2", CROSS),
                             ("insert", None, "G2", "C5", "IA", CROSS)]
    assert inserted(s) == [("auto_via:net_wire:n/2", "H2/IA", CROSS, "n", None)]
    assert "Inserted      : 3 via(s) at 1 crossing(s) (cut layers C3 C4 C5)" in text


def test_via_ref_names_the_definitions(stacked):
    s = stacked
    s.eval("assign_via_for_route -via {V_G1_G2 V_G2_IA}")
    found, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_H2_G1 via_def:V_G2_IA}")
    assert [r[1] for r in table(s, "n")] == ["V_H2_G1", "V_G1_G2", "V_G2_IA"]
    assert inserted(s)[0][4] == "V_H2_G1 V_G2_IA"          # the assigned one is not kept
    assert "Definitions   : V_H2_G1(1) V_G1_G2(1) V_G2_IA(1)" in text
    assert "have none" not in text
    s.eval("assign_via_for_route -reset")
    assert [r[1] for r in table(s, "n")] == ["V_H2_G1", None, "V_G2_IA"]


def test_via_ref_comes_before_the_assignment(crossed):
    s = crossed
    s.eval("assign_via_for_route -via V_IA_IB")
    wires(s, "m", ("wire", "IA", "0 2 10 2.4"), ("wire", "IB", "5 1 5.4 3"))
    insert(s, more="-nets n -via_ref V_IA_IB_2")
    insert(s, more="-nets m")
    assert [r[1] for r in table(s, "n")] == ["V_IA_IB_2"]
    assert [r[1] for r in table(s, "m")] == ["V_IA_IB"]


def test_again_with_another_via_ref_changes_the_definition(stacked):
    s = stacked
    insert(s, bottom="H2", top="IA", more="-via_ref V_H2_G1")
    found, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_G1_G2 V_G2_IA}")
    assert found == [] and len(inserted(s)) == 1
    assert [r[1] for r in table(s, "n")] == ["V_H2_G1", "V_G1_G2", "V_G2_IA"]
    assert "Already there : 1 crossing(s); the definitions of 1 inserted before changed" in text
    _, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_G1_G2 V_G2_IA}")
    assert "changed" not in text
    insert(s, bottom="H2", top="IA")                       # without -via_ref: as they are
    assert [r[1] for r in table(s, "n")] == ["V_H2_G1", "V_G1_G2", "V_G2_IA"]


def test_via_ref_errors(stacked):
    s = stacked
    cmd = "insert_vias -bottom_layer H2 -top_layer IA -area {-9 -9 9 9} -via_ref "
    assert "HT4-273" in err(s, cmd + "NOPE")
    text = err(s, cmd + "V_IA_IB")
    assert "HT4-274" in text and "joins IA and IB through C6" in text
    assert "the vias from H2 to IA are H2/G1 G1/G2 G2/IA" in text
    assert "HT4-001" in err(s, cmd + "{}")
    # XM is a routing layer no via definition reaches
    text = err(s, "insert_vias -bottom_layer IA -top_layer XM -area {-9 -9 9 9} "
                  "-via_ref V_IA_IB")
    assert "HT4-274" in text and "no via definitions join IA and XM" in text
    text = err(s, "insert_vias -bottom_layer IA -top_layer IB -area {-9 -9 9 9} "
                  "-via_ref {V_IA_IB V_IA_IB_2}")
    assert "HT4-275" in text and "'V_IA_IB' and 'V_IA_IB_2' both join IA and IB" in text
    assert inserted(s) == []


def test_the_hops_a_net_has_are_not_made_again(stacked):
    s = stacked
    # the net is on G1 there already, by a crossing box of the router
    wires(s, "n", ("wire", "H2", "0 0 10 0.4"), ("wire", "IA", "5 -5 5.4 5"),
          ("cross", "H2/G1", CROSS))
    found, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_H2_G1 V_G1_G2}")
    assert inserted(s) == [("auto_via:net_wire:n/2", "G1/IA", CROSS, "n", "V_G1_G2")]
    assert table(s, "n") == [("cross", None, "H2", "C3", "G1", CROSS),
                             ("insert", "V_G1_G2", "G1", "C4", "G2", CROSS),
                             ("insert", None, "G2", "C5", "IA", CROSS)]
    assert found == ["via:n/2", "via:n/3"]


def test_without_via_definitions_one_via_and_no_cut_layer(session, write_lef):
    s = session
    s.eval(f"read_tech -file {{{write_lef(tech_text(vias=False), 'nv.lef')}}}")
    wires(s, "n", ("wire", "H2", "0 0 10 0.4"), ("wire", "IA", "5 -5 5.4 5"),
          ("wire", "H2", "0 2 10 2.4"), ("wire", "IA", "5 1.5 5.4 3"))
    wires(s, "other", ("wire", "G2", "4 2 6 2.4"))         # between the second pair
    cmd = "insert_vias -bottom_layer H2 -top_layer IA -area {-9 -9 9 9}"
    found, text = lst(s, cmd), out_of(s)
    assert found == ["via:n/1"]
    assert table(s, "n") == [("insert", None, "H2", None, "IA", CROSS)]
    assert "HT4-277" in text and "Blocked       : 1 crossing(s)" in text


# -- blocked -----------------------------------------------------------------------

def test_a_wire_of_another_net_in_between_blocks(stacked):
    s = stacked
    wires(s, "other", ("wire", "G1", "4 0.1 6 0.3"), ("wire", "G2", "4 3 6 3.3"),
          ("wire", "IB", "4 0.1 6 0.3"))
    wires(s, "more", ("wire", "G2", "0 0.1 9 0.3", "n"))   # the net's own: not in the way
    found, text = insert(s, bottom="H2", top="IA")
    assert found == [] and inserted(s) == [] and table(s, "n") == []
    assert "Blocked       : 1 crossing(s)" in text
    assert "**WARN: (HT4-277): insert_vias: net n at {5 0 5.4 0.4}: no via, " \
           "net_wire:other/1 (net other) lies on G1 between H2 and IA there" in text
    wires(s, "other", ("wire", "G1", "4 1 6 1.3"))         # moved off the crossing
    found, text = insert(s, bottom="H2", top="IA")
    assert len(found) == 3 and "Blocked" not in text


# -- -area and -nets ---------------------------------------------------------------

def test_the_crossing_box_must_lie_in_the_area(crossed):
    s = crossed
    found, text = insert(s, area="{0 0 5.2 5}")            # half of the box
    assert found == [] and inserted(s) == []
    assert "0 crossing(s)" in text
    assert "Not in -area  : 1 crossing(s) partly inside, not inserted" in text
    found, text = insert(s, area="{6 0 9 5}")              # beside it
    assert found == [] and "Not in -area" not in text
    found, _ = insert(s, area="{5.4 0.4 5 0}")             # the box itself, corners swapped
    assert found == ["via:n/1"]


def test_no_area_is_the_whole_design(via_session):
    s = via_session
    # three nets, far apart: one inside EVERYWHERE, two outside it
    for net, x in (("near", 0), ("far", 500), ("off", -900)):
        wires(s, net, ("wire", "IA", f"{x} 0 {x + 10} 0.4"),
              ("wire", "IB", f"{x + 5} -5 {x + 5.4} 5"))
    found, text = insert(s, area=None, more="-nets {near far}")
    assert found == ["via:near/1", "via:far/1"]
    assert "insert_vias: IA to IB in the design: 2 crossing(s)" in text
    assert "Not in -area" not in text
    found, text = insert(s, area=None)                     # every net: the one left
    assert found == ["via:off/1"]
    assert "in the design: 3 crossing(s)" in text and "Already there : 2 crossing(s)" in text
    found, text = insert(s, bottom="H2", top="IA", area=None)
    assert found == []
    assert "No wire or pin on H2 crosses a wire of its own net on IA in the design" in text


def test_nets_names_patterns_and_handles(via_session):
    s = via_session
    for k, net in enumerate(("clk_a", "clk_b", "rst", "bus[3]")):
        wires(s, net, ("wire", "IA", f"0 {2 * k} 10 {2 * k + 0.4}"),
              ("wire", "IB", f"5 {2 * k - 0.5} 5.4 {2 * k + 1}"))
    found, text = insert(s, more="-nets {bus[3]}")
    assert found == ["via:bus[3]/1"]
    found, text = insert(s, more="-nets {clk_* net:rst}")
    assert found == ["via:clk_a/1", "via:clk_b/1", "via:rst/1"]
    assert "Nets          : clk_a(1) clk_b(1) rst(1)" in text
    text = err(s, f"insert_vias -bottom_layer IA -top_layer IB -area {EVERYWHERE} "
                  f"-nets {{clk_a nope}}")
    assert "HT4-276" in text and "no net 'nope' with route wires" in text
    assert "HT4-001" in err(s, f"insert_vias -bottom_layer IA -top_layer IB "
                               f"-area {EVERYWHERE} -nets {{}}")


def test_nets_of_a_spine(routed):
    s = routed
    found, text = insert(s, bottom="H2", top="IA",
                         more="-nets {spine_net:sp/sp_L1_inv1_Y stub:sp/stub1}")
    assert found == []                 # the pin wires of these nets are on their straps
    assert "3 crossing(s)" in text and "Already there : 3 crossing(s)" in text
    found, _ = insert(s, bottom="H2", top="IA", more="-nets VSS")
    assert len(found) == 12 and all(h.startswith("via:VSS/") for h in found)


# -- errors ------------------------------------------------------------------------

def test_layer_and_usage_errors(crossed):
    s = crossed
    cmd = "insert_vias -area {0 0 9 9} "
    assert "HT4-001" in err(s, cmd + "-top_layer IB")
    text = err(s, "insert_vias -bottom_layer IA")           # -area is not required
    assert "HT4-001" in text and "-top_layer required" in text and "[-area" in text
    text = err(s, cmd + "-bottom_layer NOPE -top_layer IB")
    assert "HT4-272" in text and "-bottom_layer 'NOPE' is not a routing layer" in text
    assert "HT4-272" in err(s, cmd + "-bottom_layer IA -top_layer C6")      # a cut layer
    text = err(s, cmd + "-bottom_layer IB -top_layer IA")
    assert "HT4-272" in text and "-bottom_layer IB is not below -top_layer IA" in text
    assert "HT4-272" in err(s, cmd + "-bottom_layer IA -top_layer IA")
    text = err(s, "insert_vias -bottom_layer IA -top_layer IB -area {0 0 9}")
    assert "HT4-245" in text and "insert_vias: -area needs four numbers" in text
    assert inserted(s) == []


# -- the via lives with its wire ---------------------------------------------------

def test_the_via_goes_with_the_wire_it_is_under(crossed):
    s = crossed
    insert(s, more="-via_ref V_IA_IB_2")
    s.eval("stretch_wire -wire net_wire:n/2 -edge top -to 8")          # still over it
    assert table(s, "n") == [("insert", "V_IA_IB_2", "IA", "C6", "IB", CROSS)]
    s.eval("stretch_wire -wire net_wire:n/2 -edge bottom -to 3")       # off the crossing
    assert table(s, "n") == [] and inserted(s) == []
    s.eval("stretch_wire -wire net_wire:n/2 -edge bottom -to -5")
    insert(s)
    s.eval("move_wire -wires net_wire:n/2 -delta {1 0}")               # moved: stale
    assert table(s, "n") == [] and inserted(s) == []
    assert insert(s)[0] == ["via:n/1"] and table(s, "n")[0][5] == "6 0 6.4 0.4"
    gone = lst(s, "delete_wire -wires net_wire:n/2")
    assert gone == ["net_wire:n/2", SOURCE] and table(s, "n") == []


def test_delete_wire_removes_an_inserted_via(stacked):
    s = stacked
    found, _ = insert(s, bottom="H2", top="IA", more="-via_ref V_G1_G2")
    assert lst(s, f"delete_wire -wires [get_db {{{' '.join(found)}}} .source]") == [SOURCE]
    assert table(s, "n") == [] and len(s.db.net_wire_rows("n")) == 2
    s.eval("delete_wire -undo")
    assert [r[1] for r in table(s, "n")] == [None, "V_G1_G2", None]


# -- write_db, read_db, the GUI ----------------------------------------------------

def test_inserted_vias_in_a_written_database(stacked, tmp_path):
    s = stacked
    insert(s, bottom="H2", top="IA", more="-via_ref {V_H2_G1 V_G2_IA}")
    want, path = table(s, "n"), tmp_path / "v.db"
    s.eval(f"write_db {path}")
    other = Session(out=io.StringIO())
    other.eval(f"read_db {path}")
    assert table(other, "n") == want and inserted(other) == inserted(s)
    assert insert(other, bottom="H2", top="IA")[0] == []


def test_read_db_of_schema_22(stacked, tmp_path):
    s = stacked
    path = tmp_path / "old.db"
    s.eval(f"write_db {path}")
    con = sqlite3.connect(path)                       # as written before insert_vias
    con.executescript(
        "ALTER TABLE net_wire RENAME TO new;"
        "CREATE TABLE net_wire (id INTEGER PRIMARY KEY, net TEXT NOT NULL, seq INTEGER, "
        "kind TEXT, layer TEXT, rect TEXT, shield_net TEXT);"
        "INSERT INTO net_wire SELECT id, net, seq, kind, layer, rect, shield_net FROM new;"
        "DROP TABLE new;"
        "DROP TABLE net_route_status;"
        "UPDATE meta SET value = '22' WHERE key = 'schema_version';")
    con.close()
    other = Session(out=io.StringIO())
    other.eval(f"read_db {path}")
    assert len(other.db.net_wire_rows("n")) == 2
    found, _ = insert(other, bottom="H2", top="IA", more="-via_ref V_H2_G1")
    assert len(found) == 3 and [r[1] for r in table(other, "n")] == ["V_H2_G1", None, None]
    other.eval(f"write_db {tmp_path}/new.db")
    con = sqlite3.connect(tmp_path / "new.db")
    assert con.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0] == "26"
    assert con.execute("SELECT via_def FROM net_wire WHERE kind = 'insert_via'").fetchall() == \
        [("V_H2_G1",)]


def test_the_gui_draws_an_inserted_via(stacked):
    s = stacked
    insert(s, bottom="H2", top="IA", more="-via_ref V_H2_G1")
    lay = load_layout(s.db)
    box = next(w for w in lay.net_wires if w.handle == SOURCE)
    assert box.outline and box.layer == "H2" and box.label == "n"
    assert Counter(v.handle for v in lay.vias if v.handle.startswith("via:n/")) \
        == {"via:n/1": 3, "via:n/2": 1, "via:n/3": 1}      # a definition's shapes, two boxes
