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
# tests/via_tech.py's VIARULE GEN_IA_IB (cut 0.1, pitch 0.2) on the 0.4 x 0.4 crossing: 2 x 2
# cuts, the IA pad 0.05 past them along x, 0.02 along y; the IB pad the other way round
GEN = "GEN_IA_IB_2x2_50_20_20_50"


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
    assert table(s, "n") == [("insert", GEN, "IA", "C6", "IB", CROSS)]
    assert s.eval("get_db via:n/1 .source") == SOURCE
    # kept under the wire on the top layer, on the net of the two wires
    assert inserted(s) == [("auto_via:net_wire:n/2", "IA/IB", CROSS, "n", GEN)]
    assert "insert_vias: IA to IB in {-100 -100 100 100}: 1 crossing(s)" in text
    assert "Inserted      : 1 via(s) at 1 crossing(s) (cut layers C6)" in text
    assert "Nets          : n(1)" in text
    assert f"Definitions   : {GEN}(1)" in text


def test_the_generated_via_fills_the_crossing(crossed):
    s = crossed
    insert(s)
    row = s.db.via_def_row(GEN)
    assert (row["source"], row["via_rule"]) == ("gen", "GEN_IA_IB")
    assert row["extra"].split("\n") == ["CUTSIZE 0.1 0.1", "LAYERS IA C6 IB",
                                        "CUTSPACING 0.1 0.1", "ENCLOSURE 0.05 0.02 0.02 0.05",
                                        "ROWCOL 2 2"]
    placed = vias.placed_shapes(s.db, vias.row(s.db, "n", 1))
    box = [float(c) for c in CROSS.split()]
    cuts = [p for layer, _, p in placed if layer == "C6"]
    assert len(cuts) == 4
    for layer, _, p in placed:                  # pads and cuts inside the crossing
        assert box[0] - 1e-9 <= p[0] and p[2] <= box[2] + 1e-9
        assert box[1] - 1e-9 <= p[1] and p[3] <= box[3] + 1e-9
    # its middle on the crossing's
    assert vias.bbox([("C6", "rect", p) for p in cuts]) == (5.05, 0.05, 5.35, 0.35)
    # a wider crossing: more cuts (IB wire 0.8 wide: 4 columns)
    wires(s, "w", ("wire", "IA", "0 2 10 2.4"), ("wire", "IB", "5 1 5.8 3"))
    insert(s, more="-nets w")
    assert [r[1] for r in table(s, "w")] == ["GEN_IA_IB_2x4_50_20_20_50"]


def test_write_def_writes_the_generated_vias(crossed, tmp_path):
    s = crossed
    insert(s)
    s.eval(f"write_def -output {tmp_path / 'g.def'}")
    assert "VIAS 1" in out_of(s)
    text = (tmp_path / "g.def").read_text()
    assert ("VIAS 1 ;\n"
            f"- {GEN}\n"
            " + VIARULE GEN_IA_IB\n"
            " + CUTSIZE 100 100\n"
            " + LAYERS IA C6 IB\n"
            " + CUTSPACING 100 100\n"
            " + ENCLOSURE 50 20 20 50\n"
            " + ROWCOL 2 2 ;\n"
            "END VIAS\n") in text
    assert text.index("END VIAS") < text.index("SPECIALNETS")
    assert f"( 5200 200 ) {GEN}" in text                    # the via, by that name
    # read back (DEF VIAS from a VIARULE): the same shapes
    from core.def_parser import parse_def
    via = next(v for v in parse_def(str(tmp_path / "g.def")).vias if v.name == GEN)
    assert sorted((sh.layer, sh.points) for sh in via.shapes) == \
        sorted((layer, pts) for layer, _, pts in vias.definition_shapes(s.db, GEN))


def test_again_removes_them_and_makes_them_again(crossed):
    s = crossed
    insert(s)
    found, text = insert(s)
    assert found == ["via:n/1"] and len(inserted(s)) == 1 and len(table(s, "n")) == 1
    assert "Removed       : the vias insert_vias made before at 1 crossing(s) here, made again" in text
    assert "Inserted      : 1 via(s) at 1 crossing(s)" in text


def test_only_the_nets_and_layers_given_are_made_again(via_session):
    s = via_session
    wires(s, "n", ACROSS, UP, ("wire", "H2", "1 -1 1.4 1"))      # H2 under the IA wire
    wires(s, "m", ("wire", "IA", "0 2 10 2.4"), ("wire", "IB", "5 1 5.4 3"))
    insert(s)                                              # IA/IB of n and m
    insert(s, bottom="H2", top="IA")                       # H2/IA of n
    ids = lambda net, layer: [r["id"] for r in s.db.net_wire_rows()      # noqa: E731
                              if r["kind"] == "insert_via" and r["shield_net"] == net
                              and r["layer"] == layer]
    m_via, n_low = ids("m", "IA/IB"), ids("n", "H2/IA")
    assert len(m_via) == 1 and len(n_low) == 1
    found, text = insert(s, more="-nets n")
    assert found == [h for h in found if h.startswith("via:n/")] and len(found) == 1
    assert "Removed       : the vias insert_vias made before at 1 crossing(s)" in text
    assert ids("m", "IA/IB") == m_via                      # another net: kept
    assert ids("n", "H2/IA") == n_low                      # other layers: kept
    assert ids("n", "IA/IB") != []
    # the layers from H2 to IB take in both of n's
    _, text = insert(s, bottom="H2", top="IB", more="-nets n")
    assert "made before at 2 crossing(s)" in text


def test_wires_of_two_nets_get_no_via(via_session):
    s = via_session
    wires(s, "a", ACROSS)
    wires(s, "b", UP)
    found, text = insert(s)
    assert found == [] and inserted(s) == []
    assert "0 crossing(s)" in text
    assert "No wire or pin on IA crosses a wire of its own net on IB inside the area" in text


def test_an_inserted_via_takes_the_place_of_the_router_one(routed):
    s = routed
    at = lambda: sorted((r["net"], r["x"], r["y"]) for r in vias.rows(s.db)   # noqa: E731
                        if (r["bottom"], r["top"]) == ("IA", "IB"))
    before = at()
    assert {r["kind"] for r in vias.rows(s.db) if r["bottom"] == "IA"} >= {"cross"}
    found, text = insert(s)
    assert len(found) == 11 and len(inserted(s)) == 11
    assert "11 crossing(s)" in text and "Inserted      : 11 via(s) at 11 crossing(s)" in text
    # one via at each crossing, as before: the inserted one, none of the router's there
    assert at() == before
    assert {r["kind"] for r in vias.rows(s.db) if (r["bottom"], r["top"]) == ("IA", "IB")} \
        == {"insert"}


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
                            "VSS", "GEN_IA_IB_3x2_50_20_20_50")]
    # the shield now hangs on that strap: its open is gone (tests/test_check_drc.py)
    power = check(s, "-check_open_only")[1]["Opens, power nets"]
    assert len(power) < opens and not any("net_wire:extra/1" in v for v in power)


def test_pin_wires_on_the_straps_of_their_net_get_a_stack(routed):
    s = routed
    found, text = insert(s, bottom="H2", top="IA")
    kinds = Counter(r["net"] for r in vias.rows(s.db) if r["kind"] == "insert")
    # every pin wire on H2 over a strap of its net, power and signal (route_pin named the
    # signal straps), the ones route_pin's vias joined too; a stack of 3 vias each
    assert kinds == {"VSS": 24, "VDD_SOC": 27, "sp_primary_input": 3, "sp_L1_inv1_Y": 6,
                     "sp_L2_inv1_Y": 9, "sp_L3_inv1_Y": 3, "sp_L3_inv2_Y": 3}
    assert len(found) == 75 and "Inserted      : 75 via(s) at 25 crossing(s)" in text
    # sp_L3_inv1's VDD pin wire (x 4.387 .. 4.797) overlaps the end of sp_L2_inv1's
    # VDD straps (to x 4.44) by 0.053: an H2 pad 0.4 wide would stick out of it (the
    # third: the strap route_pin's own via was on)
    assert "(HT4-311): insert_vias: 3 crossing(s) with no via: no via definition of the " \
           "layers fits on the two wires there (a pad would stick out of the metal, towards " \
           "other nets): VDD_SOC {4.387 12.02 4.44 12.74}, VDD_SOC {4.387 6.26 4.44 6.98}, " \
           "VDD_SOC {4.387 4.82 4.44 5.54}" in text


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
    found, text = insert(s, bottom="D12", top="H2")         # again: removed, made again
    pins = [r for r in table(s, "u1_Y") if r[2] in ("D12", "H1")]
    assert len(found) == 6 and pins == stack(Y1) + stack(Y2) + stack(A)
    assert "Removed       : the vias insert_vias made before at 3 crossing(s) here" in text


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
    # the one of Y1 made again with the others
    assert [r[-1] for r in table(s, "u1_Y")] == [Y1, Y1, Y2, Y2, A, A] and len(found) == 6


def test_an_inserted_stack_takes_the_place_of_the_pin_vias(routed):
    s = routed
    at = lambda: sorted((r["net"], r["bottom"], r["x"], r["y"]) for r in vias.rows(s.db)  # noqa
                        if r["bottom"] in ("D12", "H1") and r["top"] in ("H1", "H2"))
    before = at()
    found, text = insert(s, bottom="D12", top="H2")
    # 4 instances, 6 rectangles each (Y and VDD have two), every pin on the net of its
    # pin wire (route_pin names them, the root's input on the root net too)
    assert "24 crossing(s)" in text and "On pins       : 24 of them" in text
    assert len(found) == 48 and len(inserted(s)) == 24
    assert s.db.pin_wire_row("sp_L1_inv1", "A")["net"] == "sp_primary_input"
    # the same stacks at the same places, now the inserted ones: no pin via left beside them
    assert at() == before
    assert {r["kind"] for r in vias.rows(s.db) if r["bottom"] == "D12"} == {"insert"}


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


def test_via_ref_comes_before_the_generated_via_and_that_before_the_assignment(crossed):
    s = crossed
    s.eval("assign_via_for_route -via V_IA_IB")
    wires(s, "m", ("wire", "IA", "0 2 10 2.4"), ("wire", "IB", "5 1 5.4 3"))
    insert(s, more="-nets n -via_ref V_IA_IB_2")
    insert(s, more="-nets m")
    assert [r[1] for r in table(s, "n")] == ["V_IA_IB_2"]
    assert [r[1] for r in table(s, "m")] == [GEN]


def test_again_with_another_via_ref_makes_them_with_it(stacked):
    s = stacked
    insert(s, bottom="H2", top="IA", more="-via_ref V_H2_G1")
    assert [r[1] for r in table(s, "n")] == ["V_H2_G1", None, None]
    found, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_G1_G2 V_G2_IA}")
    assert len(found) == 3 and len(inserted(s)) == 1
    assert "Removed       : the vias insert_vias made before at 1 crossing(s) here, made again" in text
    # made again: the definitions of this -via_ref only
    assert [r[1] for r in table(s, "n")] == [None, "V_G1_G2", "V_G2_IA"]
    insert(s, bottom="H2", top="IA")                       # without -via_ref: none named
    assert [r[1] for r in table(s, "n")] == [None, None, None]


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


def test_the_stack_takes_the_place_of_the_hops_the_net_has(stacked):
    s = stacked
    # the net is on G1 there already, by a crossing box of the router
    wires(s, "n", ("wire", "H2", "0 0 10 0.4"), ("wire", "IA", "5 -5 5.4 5"),
          ("cross", "H2/G1", CROSS))
    assert table(s, "n") == [("cross", None, "H2", "C3", "G1", CROSS)]
    found, text = insert(s, bottom="H2", top="IA", more="-via_ref {V_H2_G1 V_G1_G2}")
    # the whole stack inserted; the router's H2/G1 via gives way to it
    assert inserted(s) == [("auto_via:net_wire:n/2", "H2/IA", CROSS, "n", "V_H2_G1 V_G1_G2")]
    assert table(s, "n") == [("insert", "V_H2_G1", "H2", "C3", "G1", CROSS),
                             ("insert", "V_G1_G2", "G1", "C4", "G2", CROSS),
                             ("insert", None, "G2", "C5", "IA", CROSS)]
    assert found == ["via:n/1", "via:n/2", "via:n/3"]


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
    found, text = insert(s, area=None)                     # every net: all three
    assert sorted(found) == ["via:far/1", "via:near/1", "via:off/1"]
    assert "in the design: 3 crossing(s)" in text
    assert "Removed       : the vias insert_vias made before at 2 crossing(s)" in text
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
    # the pin wires of these nets on their straps: a stack of 3 each
    mine = {"sp_L1_inv1_Y", s.eval("get_db stub:sp/stub1 .net").split(":")[-1].split("/")[-1]}
    assert len(found) == 9 and {h[4:].rsplit("/", 1)[0] for h in found} <= mine
    assert "3 crossing(s)" in text
    found, text = insert(s, bottom="H2", top="IA", more="-nets VSS")
    assert len(found) == 24 and all(h.startswith("via:VSS/") for h in found)
    assert "Removed" not in text                       # the other nets' vias stay
    assert sum(r["shield_net"] in mine for r in s.db.net_wire_rows()
               if r["kind"] == "insert_via") == 3


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
    assert len(insert(other, bottom="H2", top="IA")[0]) == 3      # removed, made again


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
    assert con.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0] == "27"
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


def test_a_crossing_too_narrow_for_any_via_gets_none(crossed):
    # IA wire n ends 0.1 over the IB wire: a via there would stick out of it on IA
    s = crossed
    s.db.delete_wires([("net_wire", r["id"]) for r in s.db.net_wire_rows("n")
                       if r["layer"] == "IA"])
    up = [tuple(float(c) for c in r["rect"].split()) for r in s.db.net_wire_rows("n")
          if r["layer"] == "IB"][0]
    s.db.add_net_wires([("n", "wire", "IA", f"{up[0] - 5} {up[1] + 1} {up[0] + 0.1} "
                         f"{up[1] + 1.36}", None, None)])
    found, text = insert(s, area=None)
    assert found == [] and "(HT4-311)" in text and "1 crossing(s) with no via" in text
