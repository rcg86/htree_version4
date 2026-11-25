"""Via definitions (tech LEF VIA, DEF VIAS), the via objects derived from the
routing, assign_via_for_route and get_obj_in_area."""

import io
import sqlite3
from collections import Counter

import pytest

pytest.importorskip("scipy")

from core import vias
from core.htree_builder import Session
from core.lef import generated_via_shapes
from test_route_net import DEF, SPEC, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import CELL_LEF, err, out_of
from test_route_pin import DEF as PIN_DEF
from via_tech import fixed, tech_text

VIA_NAMES = ["V_D12_H1", "V_H1_H2", "V_H2_G1", "V_G1_G2", "V_G2_IA", "V_IA_IB", "V_IA_IB_2"]

# Four ways to write a via: rectangles, with masks, with a polygon, and from
# a VIARULE's parameters (in database units).
DEF_VIAS = """VIAS 4 ;
- DV_RECT
  + RECT IA ( -200 -70 ) ( 200 70 )
  + RECT C6 ( 50 50 ) ( -50 -50 )
  + RECT IB ( -70 -200 ) ( 70 200 ) ;
- DV_MASK
  + RECT IA + MASK 2 ( -200 -70 ) ( 200 70 )
  + RECT C6 + MASK 1 ( -50 -50 ) ( 50 50 )
  + RECT IB ( -70 -200 ) ( 70 200 ) ;
- DV_POLY
  + POLYGON IA ( -200 -70 ) ( 200 -70 ) ( 200 70 ) ( 0 140 ) ( -200 70 )
  + RECT C6 ( -50 -50 ) ( 50 50 )
  + RECT IB ( -70 -200 ) ( 70 200 ) ;
- DV_GEN
  + VIARULE GEN_IA_IB
  + CUTSIZE 100 100
  + LAYERS IA C6 IB
  + CUTSPACING 100 100
  + ENCLOSURE 50 20 20 50
  + ROWCOL 2 2 ;
END VIAS
"""


def def_text(vias_section, base=DEF):
    return base.replace("END DESIGN", vias_section + "END DESIGN")


def lst(s, script):
    return list(s.split_list(s.eval(script)))


@pytest.fixture
def via_session(session, write_lef):
    session.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    return session


def _route(s, write_lef):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("route_pin -inst sp_*")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    s.eval("route_net -net [get_db nets .name] -rule r")
    s.eval("route_final_stub -rule r")
    # the routing commands gave every net its definitions (vias.auto_assign); these
    # tests start from vias with none, assigned by hand (test_auto_assign has those)
    s.eval("assign_via_for_route -reset")
    out_of(s)
    return s


@pytest.fixture
def routed(via_session, write_lef):
    """The spine of test_route_net, routed, on the tech with via definitions."""
    return _route(via_session, write_lef)


# -- via definitions of the tech LEF ---------------------------------------------

def test_tech_lef_vias(via_session):
    s = via_session
    assert "  Vias        : 7 (6 DEFAULT)" in out_of(s)
    assert lst(s, "get_db via_defs") == [f"via_def:{n}" for n in VIA_NAMES]
    assert lst(s, "get_db via_defs .name") == VIA_NAMES
    one = "via_def:V_IA_IB"
    assert [s.eval(f"get_db {one} .{a}") for a in
            ("obj_type", "source", "default", "via_rule", "bottom_layer", "cut_layer",
             "top_layer", "cuts", "rect")] == \
        ["via_def", "lef", "true", "", "IA", "C6", "IB", "1", "-0.2 -0.2 0.2 0.2"]
    assert lst(s, f"get_db {one} .layers") == ["IA", "C6", "IB"]
    assert lst(s, f"get_db {one} .shapes") == [
        "IA -0.2 -0.15 0.2 0.15", "C6 -0.1 -0.1 0.1 0.1", "IB -0.15 -0.2 0.15 0.2"]
    assert s.eval(f"get_db {one} .text").startswith("VIA V_IA_IB DEFAULT")
    # the generated one: a row of two cuts, the pads from the enclosures
    two = "via_def:V_IA_IB_2"
    assert [s.eval(f"get_db {two} .{a}") for a in ("default", "via_rule", "cuts")] == \
        ["false", "GEN_IA_IB", "2"]
    assert lst(s, f"get_db {two} .shapes") == [
        "IA -0.2 -0.07 0.2 0.07", "C6 -0.15 -0.05 -0.05 0.05", "C6 0.05 -0.05 0.15 0.05",
        "IB -0.17 -0.1 0.17 0.1"]
    assert lst(s, "get_db via_defs -if {.bottom_layer == IA} .name") == ["V_IA_IB", "V_IA_IB_2"]
    assert "HT4-022" in err(s, "get_db via_def:NONE .name")


def test_generated_via_shapes():
    made = generated_via_shapes(["A", "C", "B"], [0.1, 0.2], [0.1, 0.3], [0.05, 0.02, 0.02, 0.05],
                                rowcol=[2, 3], origin=[1, 2], offset=[0.01, 0, 0, -0.01])
    boxes = [(sh.layer, [round(v, 6) for v in sh.points]) for sh in made]
    # 3 columns of 0.1 with 0.1 between: 0.5 wide; 2 rows of 0.2 with 0.3: 0.7 tall
    assert boxes[0] == ("A", [0.71, 1.63, 1.31, 2.37])
    assert [layer for layer, _ in boxes] == ["A"] + ["C"] * 6 + ["B"]
    assert boxes[1] == ("C", [0.75, 1.65, 0.85, 1.85])
    assert boxes[6] == ("C", [1.15, 2.15, 1.25, 2.35])
    assert boxes[7] == ("B", [0.73, 1.59, 1.27, 2.39])


# -- via definitions of the DEF --------------------------------------------------

def test_def_vias(via_session, write_lef):
    s = via_session
    out_of(s)
    s.eval(f"read_def -file {{{write_lef(def_text(DEF_VIAS), 'v.def')}}}")
    text = out_of(s)
    assert "  Vias        : 4 (DV_RECT DV_MASK DV_POLY DV_GEN)" in text
    assert "HT4-096" not in text and "HT4-097" not in text
    assert lst(s, "get_db via_defs -if {.source == def} .name") == \
        ["DV_RECT", "DV_MASK", "DV_POLY", "DV_GEN"]
    assert lst(s, "get_db via_def:DV_RECT .shapes") == [
        "IA -0.2 -0.07 0.2 0.07", "C6 -0.05 -0.05 0.05 0.05", "IB -0.07 -0.2 0.07 0.2"]
    assert [r["mask"] for r in s.db.via_def_shapes(s.db.via_def_row("DV_MASK")["id"])] == \
        [2, 1, None]
    assert lst(s, "get_db via_def:DV_POLY .shapes")[0] == \
        "IA -0.2 -0.07 0.2 -0.07 0.2 0.07 0 0.14 -0.2 0.07"
    assert s.eval("get_db via_def:DV_POLY .rect") == "-0.2 -0.2 0.2 0.2"
    assert [s.eval(f"get_db via_def:DV_GEN .{a}") for a in
            ("via_rule", "cuts", "rect", "bottom_layer", "cut_layer", "top_layer")] == \
        ["GEN_IA_IB", "4", "-0.2 -0.2 0.2 0.2", "IA", "C6", "IB"]
    assert lst(s, "get_db via_def:DV_GEN .shapes")[:2] == [
        "IA -0.2 -0.17 0.2 0.17", "C6 -0.15 -0.15 -0.05 -0.05"]
    # read again without VIAS: the DEF's definitions go, the LEF's stay
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    assert lst(s, "get_db via_defs .name") == VIA_NAMES


def test_def_via_pattern_is_not_applied(via_session, write_lef):
    s = via_session
    body = DEF_VIAS.replace("+ ROWCOL 2 2 ;", "+ ROWCOL 2 2\n  + PATTERN 2_F ;")
    out_of(s)
    s.eval(f"read_def -file {{{write_lef(def_text(body), 'v.def')}}}")
    text = out_of(s)
    assert "HT4-097" in text and "1 generated via(s)" in text and "DV_GEN" in text
    assert s.eval("get_db via_def:DV_GEN .cuts") == "4"
    assert lst(s, "get_db via_def:DV_GEN .extra") == ["+ PATTERN 2_F"]


@pytest.mark.parametrize("body, message", [
    ("- A + RECT IA ( 0 0 ) ( 1 1 ) ;\n- A + RECT IA ( 0 0 ) ( 1 1 ) ;\n", "defined twice"),
    ("- A ;\n", "no shapes"),
    ("- A + RECT IA ;\n", "no points"),
    ("- A + RECT IA ( 0 0 ) ;\n", "needs 2 points"),
    ("- A + POLYGON IA ( 0 0 ) ( 1 1 ) ;\n", "needs 3 or more points"),
    ("- A + VIARULE R + CUTSIZE 100 100 + LAYERS IA C6 IB ;\n", "CUTSPACING ENCLOSURE"),
    ("A + RECT IA ( 0 0 ) ( 1 1 ) ;\n", "expected '- <via name>'"),
])
def test_def_via_errors(via_session, write_lef, body, message):
    text = err(via_session, "read_def -file {%s}" % write_lef(
        def_text(f"VIAS 1 ;\n{body}END VIAS\n"), "bad.def"))
    assert "HT4-091" in text and message in text
    assert lst(via_session, "get_db via_defs .name") == VIA_NAMES      # nothing loaded


def test_def_via_replaces_the_lef_via_of_its_name(via_session, write_lef):
    s = via_session
    out_of(s)
    body = "VIAS 1 ;\n- V_IA_IB + RECT IA ( -300 -300 ) ( 300 300 ) + RECT C6 ( -50 -50 ) " \
           "( 50 50 ) + RECT IB ( -300 -300 ) ( 300 300 ) ;\nEND VIAS\n"
    s.eval(f"read_def -file {{{write_lef(def_text(body), 'v.def')}}}")
    assert "HT4-096" in out_of(s)
    assert s.eval("get_db via_def:V_IA_IB .source") == "def"
    assert s.eval("get_db via_def:V_IA_IB .rect") == "-0.3 -0.3 0.3 0.3"
    assert len(lst(s, "get_db via_defs")) == 7
    # the tech read again: the DEF's definition is kept
    s.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    text = out_of(s)
    assert "HT4-014" in text and "V_IA_IB" in text
    assert s.eval("get_db via_def:V_IA_IB .source") == "def"
    assert len(lst(s, "get_db via_defs")) == 7


# -- via objects -----------------------------------------------------------------

def stack(s, handles):
    return [tuple(s.eval(f"get_db {h} .{a}") for a in
                  ("kind", "bottom_layer", "cut_layer", "top_layer")) for h in handles]


def test_vias_of_a_routed_net(routed):
    s = routed
    found = lst(s, "get_db [get_db nets sp_L1*] .vias")
    assert found == [f"via:sp_L1_inv1_Y/{k}" for k in range(1, 15)]
    assert lst(s, "get_db spine_net:sp/sp_L1_inv1_Y .vias") == found
    pin = [("pin", "D12", "C1", "H1"), ("pin", "H1", "C2", "H2")]
    strap = [("strap", "H2", "C3", "G1"), ("strap", "G1", "C4", "G2"),
             ("strap", "G2", "C5", "IA")]
    # the two crossings of the route, then the driver's and the load's stacks: pin Y
    # is two D12 rectangles and has a stack on each, pin A is one
    assert stack(s, found) == [("cross", "IA", "C6", "IB")] * 2 + pin * 2 + strap + pin + strap
    assert lst(s, "get_db [get_db vias -if {.source == pin_wire:sp_L1_inv1/Y && "
                  ".bottom_layer == D12}] .box") == \
        ["-0.56 -0.689 -0.16 -0.189", "-0.56 0.211 -0.16 0.711"]
    one = "via:sp_L1_inv1_Y/1"
    assert [s.eval(f"get_db {one} .{a}") for a in
            ("obj_type", "name", "net", "via_def", "location", "box", "rect", "shapes")] == \
        ["via", "1", "sp_L1_inv1_Y", "", "1.44 1.44", "1.26 1.08 1.62 1.8",
         "1.26 1.08 1.62 1.8", ""]
    # .source is the crossing box, or the pin wire, the via stands for
    source = s.eval(f"get_db {one} .source")
    assert source.startswith("net_wire:sp_L1_inv1_Y/")
    assert s.eval(f"get_db {source} .layer") == "IB/IA"
    assert s.eval(f"get_db {source} .rect") == s.eval(f"get_db {one} .box")
    assert s.eval("get_db via:sp_L1_inv1_Y/3 .source") == "pin_wire:sp_L1_inv1/Y"
    # a stack: its vias are at one point
    assert len({s.eval(f"get_db via:sp_L1_inv1_Y/{k} .location") for k in (7, 8, 9)}) == 1
    assert s.eval("get_db [get_db vias] .net -if {.kind == cross}") != ""
    assert lst(s, "get_db via:sp_L1_inv1_Y/1 .via_def") == []
    assert "HT4-022" in err(s, "get_db via:sp_L1_inv1_Y/15 .kind")
    assert "HT4-022" in err(s, "get_db via:none/1 .kind")


def test_every_net_and_stub_has_its_vias(routed):
    s = routed
    kinds = Counter((r["net"], r["kind"]) for r in vias.rows(s.db))
    assert len(lst(s, "get_db vias")) == sum(kinds.values()) == 107
    # 4 instances: each power pin wire has a stack to each rectangle of its pin (VSS
    # one, VDD two) and to its straps
    assert kinds["VSS", "pin"] == 8 and kinds["VDD_SOC", "pin"] == 16
    assert kinds["sp_L2_inv1_Y", "cross"] == 3
    assert not any(kind in ("stub_cross", "auto") for _, kind in kinds)
    # a stub joins its leaf net at a crossing the route already has: one via
    for stub in ("stub1", "stub2"):
        net = s.eval(f"get_db [get_db stub:sp/{stub} .net] .name")
        found = lst(s, f"get_db stub:sp/{stub} .vias")
        assert len(found) == 1 and found[0].startswith(f"via:{net}/")
        assert found[0] in lst(s, f"get_db spine_net:sp/{net} .vias")
        assert stack(s, found) == [("cross", "IA", "C6", "IB")]
    # via handles follow the routing. A net that loses its route loses its
    # crossings; its pin wires and straps stay on it (their pin's net): their vias too
    signal = len(vias.rows(s.db, "SIGNAL"))
    assert len(lst(s, "get_db spine_net:sp/sp_L2_inv1_Y .vias")) == 20
    s.eval("delete_route -nets sp_L2_inv1_Y")
    assert len(lst(s, "get_db spine_net:sp/sp_L2_inv1_Y .vias")) == 17     # the pins'
    assert len(vias.rows(s.db, "SIGNAL")) == signal
    assert len(lst(s, "get_db vias")) == 107 - 3


def test_vias_without_definitions_have_no_cut_layer(spine):
    # the tech of the other tests: no cut layers, no vias, no D12
    s = spine
    s.eval("route_net -net sp_L1_inv1_Y -rule r")
    found = lst(s, "get_db spine_net:sp/sp_L1_inv1_Y .vias")
    assert stack(s, found) == [("cross", "IA", "", "IB")] * 2 + \
        [("pin", "D12", "", "H2")] * 2 + [("strap", "H2", "", "IA")] + \
        [("pin", "D12", "", "H2"), ("strap", "H2", "", "IA")]    # Y: two rectangles, A: one
    assert lst(s, "get_db via_defs") == []


def test_pin_stacks_start_from_the_highest_pin_shapes_below_the_wire(via_session):
    tech = vias.tech_layers(via_session.db)
    wire = (0, 0, 0.4, 5)                               # a pin wire on H2
    d12, h1, m1 = ("D12", (0, 0, 0.4, 1)), ("H1", (0.1, 2, 0.3, 2.5)), ("M1", (0, 0, 3, 3))
    second = ("D12", (0, 1.5, 0.4, 4))
    over = lambda shapes: vias._pin_overlaps(shapes, "H2", wire, tech)  # noqa: E731
    assert over([d12]) == [d12]
    assert over([d12, second]) == [d12, second]         # every rectangle of the pin
    assert over([d12, second, ("D12", (1, 0, 2, 1))]) == [d12, second]  # ... under the wire
    assert over([d12, second, h1]) == [h1]              # of the highest layer only
    assert over([d12, m1]) == [d12]                     # M1 is not a layer of the tech
    assert over([d12, ("H2", (0, 3, 0.4, 4))]) == []    # a shape on the wire's layer: no via
    assert over([("IA", (0, 0, 0.4, 1))]) == []         # only above the wire
    assert over([("D12", (1, 0, 2, 1))]) == []          # not under the wire
    # no layer of the pin in the tech: the layer of the largest overlap, all its shapes
    none = {"H2": tech["H2"]}
    assert vias._pin_overlaps([d12, second, ("M1", (0, 0, 0.4, 2))], "H2", wire, none) == \
        [d12, second]
    assert vias._pin_overlaps([d12, ("M1", (0, 0, 0.4, 5))], "H2", wire, none) == \
        [("M1", (0, 0, 0.4, 5))]


# -- assign_via_for_route --------------------------------------------------------

def defs(s, net):
    return Counter(r["via_def"] for r in vias.rows(s.db, net))


def test_assign_via_for_route(routed):
    s = routed
    assert s.eval("assign_via_for_route") == ""
    assert "No via assignments" in out_of(s)
    s.eval("assign_via_for_route -via {V_IA_IB via_def:V_G2_IA}")
    text = out_of(s)
    assert "IA/IB" in text and "(every net)" in text and "V_G2_IA  16" in text
    assert "Vias: 107, with a definition 27, without: D12/H1(24) H1/H2(24) H2/G1(16) " \
           "G1/G2(16)" in text
    assert defs(s, "sp_L1_inv1_Y") == {"V_IA_IB": 2, "V_G2_IA": 2, None: 10}
    one = "via:sp_L1_inv1_Y/1"
    assert s.eval(f"get_db {one} .via_def") == "via_def:V_IA_IB"
    assert s.eval(f"get_db [get_db {one} .via_def] .cuts") == "1"
    # the via is its definition's shapes at its point; the box stays
    assert s.eval(f"get_db {one} .rect") == "1.24 1.24 1.64 1.64"
    assert s.eval(f"get_db {one} .box") == "1.26 1.08 1.62 1.8"
    assert lst(s, f"get_db {one} .shapes") == [
        "IA 1.24 1.29 1.64 1.59", "C6 1.34 1.34 1.54 1.54", "IB 1.29 1.24 1.59 1.64"]
    # one net with its own: the others keep theirs
    s.eval("assign_via_for_route -via V_IA_IB_2 -nets spine_net:sp/sp_L1_inv1_Y")
    text = out_of(s)
    assert "HT4-243" not in text and "sp_L1_inv1_Y" in text
    assert defs(s, "sp_L1_inv1_Y") == {"V_IA_IB_2": 2, "V_G2_IA": 2, None: 10}
    assert defs(s, "sp_L2_inv1_Y")["V_IA_IB"] == 3
    assert s.eval(f"get_db {one} .rect") == "1.24 1.34 1.64 1.54"
    # another for every net: a warning, and the net with its own keeps it
    s.eval("assign_via_for_route -via V_IA_IB_2")
    assert "HT4-243" in out_of(s)
    s.eval("assign_via_for_route -via V_IA_IB")
    assert "HT4-243" in out_of(s)
    assert defs(s, "sp_L1_inv1_Y")["V_IA_IB_2"] == 2
    # a net by its stub, and a net that has no via yet
    s.eval("assign_via_for_route -via V_IA_IB_2 -nets {stub:sp/stub1 later}")
    text = out_of(s)
    assert "HT4-244" in text and "'later'" in text
    assert defs(s, s.eval("get_db [get_db stub:sp/stub1 .net] .name"))["V_IA_IB_2"] == 3
    # -reset: of some nets, then all
    s.eval("assign_via_for_route -reset -nets sp_L1_inv1_Y")
    assert "Removed 1 via assignment(s) of sp_L1_inv1_Y" in out_of(s)
    assert defs(s, "sp_L1_inv1_Y") == {"V_IA_IB": 2, "V_G2_IA": 2, None: 10}
    s.eval("assign_via_for_route -reset")
    text = out_of(s)
    assert "Removed 4 via assignment(s)" in text and "No via assignments" in text
    assert set(defs(s, "sp_L1_inv1_Y")) == {None}


def test_assign_via_for_route_errors(routed, write_lef):
    s = routed
    assert "HT4-240" in err(s, "assign_via_for_route -via NONE")
    assert "HT4-242" in err(s, "assign_via_for_route -via {V_IA_IB V_IA_IB_2}")
    assert "HT4-001" in err(s, "assign_via_for_route -via V_IA_IB -reset")
    assert "HT4-001" in err(s, "assign_via_for_route -nets sp_L1_inv1_Y")
    assert "HT4-001" in err(s, "assign_via_for_route -via {}")
    assert "HT4-001" in err(s, "assign_via_for_route -via V_IA_IB -nets {}")
    assert "HT4-022" in err(s, "assign_via_for_route -via V_IA_IB -nets spine_net:sp/none")
    assert s.db.via_assignment_rows() == []
    # a definition whose layers are not one cut between two tech layers
    body = "VIAS 1 ;\n- ODD + RECT IA ( 0 0 ) ( 100 100 ) + RECT IB ( 0 0 ) ( 100 100 ) ;\n" \
           "END VIAS\n"
    s.eval(f"read_def -file {{{write_lef(def_text(body), 'v.def')}}}")
    assert [s.eval(f"get_db via_def:ODD .{a}") for a in
            ("bottom_layer", "cut_layer", "top_layer", "cuts")] == [""] * 4
    assert "HT4-241" in err(s, "assign_via_for_route -via ODD")


def test_assignment_of_a_definition_that_is_gone(routed, write_lef):
    s = routed
    s.eval("assign_via_for_route -via V_IA_IB")
    assert defs(s, "sp_L1_inv1_Y")["V_IA_IB"] == 2
    # the tech read again with another via of that name on other layers
    text = tech_text().replace(fixed("V_IA_IB", "IA", "C6", "IB"),
                               fixed("V_IA_IB", "G2", "C5", "IA"))
    s.eval(f"read_tech -file {{{write_lef(text, 'vt2.lef')}}}")
    assert "V_IA_IB" not in defs(s, "sp_L1_inv1_Y")
    out_of(s)
    s.eval("assign_via_for_route")
    assert "(no such definition now: not used)" in out_of(s)
    s.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    assert defs(s, "sp_L1_inv1_Y")["V_IA_IB"] == 2


# -- auto vias (stretch_wire) ----------------------------------------------------

def test_hop_distance(via_session, session, write_lef):
    distance = vias.hop_distance(via_session.db)
    assert distance("H2", "IA") == distance("IA", "H2") == 3
    assert distance("IA", "IB") == 1          # XM lies between them, no via reaches it
    assert distance("IA", "XM") == 1          # no via: routing layers in tech order
    assert distance("D12", "IB") == 6
    assert distance("IA", "NONE") is None
    other = Session(out=io.StringIO())
    other.eval(f"read_tech -file {{{write_lef(tech_text(vias=False), 'nv.lef')}}}")
    assert vias.hop_distance(other.db)("IA", "IB") == 2


def test_auto_via_is_a_via_of_kind_auto(via_session, write_lef):
    s = via_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(PIN_DEF, 'd.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.eval("route_pin -inst u1")
    kinds = lambda: Counter(r["kind"] for r in vias.rows(s.db, "VSS"))      # noqa: E731
    assert kinds() == {"pin": 2, "strap": 3}
    s.eval("set_db route_auto_via_insertion_during_stretch 3")
    s.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 0.4")
    assert kinds() == {"pin": 2}                      # off its strap
    s.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 5.569")
    # one auto via is on the pin wire's own strap: that is its strap via
    assert kinds() == {"pin": 2, "strap": 3, "auto": 3}
    auto = [r for r in vias.rows(s.db, "VSS") if r["kind"] == "auto"]
    assert [(r["bottom"], r["cut"], r["top"]) for r in auto] == \
        [("H2", "C3", "G1"), ("G1", "C4", "G2"), ("G2", "C5", "IA")]
    assert {r["rect"] for r in auto} == {"1.8 4.849 2.2 5.569"}
    assert auto[0]["source"].startswith("net_wire:auto_via:pin_wire:u1/VSS/")


# -- write_db, read_db -----------------------------------------------------------

def table(s):
    return [tuple(r)[1:] for r in vias.rows(s.db)]


def test_vias_in_a_written_database(routed, tmp_path):
    s = routed
    s.eval("assign_via_for_route -via V_IA_IB")
    s.eval("assign_via_for_route -via V_IA_IB_2 -nets sp_L1_inv1_Y")
    want, path = table(s), tmp_path / "v.db"
    s.eval(f"write_db {path}")
    con = sqlite3.connect(path)                       # the file has the via table
    assert con.execute("SELECT count(*) FROM via").fetchone()[0] == 107
    con.close()
    other = Session(out=io.StringIO())
    other.eval(f"read_db {path}")
    text = out_of(other)
    assert "Via definitions" in text and "schema version 20" not in text
    assert table(other) == want
    assert lst(other, "get_db via_defs .name") == VIA_NAMES
    assert defs(other, "sp_L1_inv1_Y")["V_IA_IB_2"] == 2


def test_read_db_of_schema_20(routed, tmp_path, write_lef):
    s = routed
    path = tmp_path / "old.db"
    s.eval(f"write_db {path}")
    con = sqlite3.connect(path)                       # as written before the via tables
    with con:
        for name in ("via", "via_assignment", "via_def_shape", "via_def", "connection"):
            con.execute(f"DROP TABLE {name}")
        con.execute("UPDATE meta SET value = '20' WHERE key = 'schema_version'")
    con.close()
    other = Session(out=io.StringIO())
    other.eval(f"read_db {path}")
    assert "schema version 20 and has no via definitions" in out_of(other)
    assert lst(other, "get_db via_defs") == []
    # the routing is there, so the vias are; the tech's cut layers are known,
    # its via definitions are not
    found = lst(other, "get_db spine_net:sp/sp_L1_inv1_Y .vias")
    assert stack(other, found)[0] == ("cross", "IA", "", "IB")
    other.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    assert table(other) == table(s)
    con = sqlite3.connect(path)
    with con:
        con.execute("UPDATE meta SET value = '19' WHERE key = 'schema_version'")
    con.close()
    assert "HT4-041" in err(other, f"read_db {path}")


# -- get_obj_in_area -------------------------------------------------------------

def test_get_obj_in_area(routed):
    s = routed
    # the L1 inverter is 3.12 x 1.778 about {0 0}; its stack is 9.36 tall
    inside = lst(s, "get_obj_in_area -area {-2 -5 2 5}")
    kinds = Counter(h.partition(":")[0] for h in inside)
    # 4 pin wires with a strap stack of 3 each and a pin stack of 2 on each pin
    # rectangle (6: Y and VDD have two), and the first crossing of the L1 route; the
    # route lengthens the strap there, so no wire of it lies inside. The root net: its
    # input's pin route (route_pin puts it on that net) lies inside. The H1 piece route_pin
    # put under each pin wire (net_wire pg:sp_L1_inv1/<n>, the cell's height)
    assert kinds == {"inst": 1, "pin": 6, "strap": 7, "pin_wire": 4, "via": 25, "net": 1,
                     "net_wire": 4}
    assert inside[0] == "inst:sp_L1_inv1" and inside[1].startswith("pin:sp_L1_inv1/")
    assert lst(s, "get_obj_in_area -area {-2 -5 2 5} -enclosed") == inside
    assert lst(s, "get_obj_in_area -area {2 5 -2 -5}") == inside          # corners either way
    # -type picks the objects and their order
    assert lst(s, "get_obj_in_area -area {-2 -5 2 5} -type inst") == ["inst:sp_L1_inv1"]
    both = lst(s, "get_obj_in_area -area {-2 -5 2 5} -type {vias inst}")
    assert both[-1] == "inst:sp_L1_inv1" and len(both) == 26
    assert lst(s, "get_obj_in_area -area {-2 -5 2 5} -type {via pins}")[0].startswith("via:")
    # a net is inside when all its wires and vias are: none is here
    # inside: the root net (its input's pin route); touching: the L1 route too
    assert lst(s, "get_obj_in_area -area {-2 -5 2 5} -type nets") == ["net:sp_primary_input"]
    touching = lst(s, "get_obj_in_area -area {-2 -5 2 5} -type nets -touching")
    assert set(touching) == {"spine_net:sp/sp_L1_inv1_Y", "net:sp_primary_input"}
    everything = lst(s, "get_obj_in_area -area {-100 -100 100 100} -type nets")
    assert set(everything) == set(lst(s, "get_db nets -if {.route_status != unrouted}")) | \
        {"net:sp_primary_input"}


def test_get_obj_in_area_touching_and_enclosed(routed):
    s = routed
    one = "strap:sp_L1_inv1/3"                  # -1.56 .. 1.56, lengthened by its route
    assert s.eval(f"get_db {one} .rect") == "-1.62 1.08 1.62 1.8"

    def got(area, flag="", kind="wires"):
        return lst(s, f"get_obj_in_area -area {{{area}}} -type {kind} {flag}")
    assert one in got("-1.62 1.08 1.62 1.8")            # its own rect encloses it
    assert one not in got("-1.5 1.08 1.62 1.8")
    assert one in got("-1.5 1.08 1.62 1.8", "-touching")
    assert one in got("1.62 1.8 3 1.9", "-touching")    # a shared corner touches
    assert one not in got("1.63 1.8 3 1.9", "-touching")
    assert got("0 1.4 0 1.4") == []                     # a point encloses nothing
    assert one in got("0 1.4 0 1.4", "-touching")
    # instances by their outline, pins by their shapes
    assert got("-1 -0.5 1 0.5", kind="inst") == []
    assert got("-1 -0.5 1 0.5", "-touching", "inst") == ["inst:sp_L1_inv1"]
    assert got("-0.7 -0.8 -0.1 0.8", kind="pins") == ["pin:sp_L1_inv1/Y"]
    assert "pin:sp_L1_inv1/Y" in got("-0.5 0.3 -0.4 0.4", "-touching", "pins")
    assert got("-0.5 0.3 -0.4 0.4", kind="pins") == []
    # a via by its definition's shapes once it has one, else by its box
    via = "via:sp_L1_inv1_Y/1"                          # box 1.26 1.08 1.62 1.8
    assert via in got("1.26 1.08 1.62 1.8", kind="vias")
    s.eval("assign_via_for_route -via V_IA_IB")         # now 1.24 1.24 1.64 1.64
    assert via not in got("1.26 1.08 1.62 1.8", kind="vias")
    assert via in got("1.24 1.24 1.64 1.64", kind="vias")
    assert via in got("1.26 1.08 1.62 1.8", "-touching", "vias")
    # a crossing box is not a wire: the via stands for it
    source = s.eval(f"get_db {via} .source")
    assert source not in got("-100 -100 100 100")
    # a stub is its own wire
    # nets with shapes: the routed ones, and the root net (its input's pin route)
    assert set(got("-100 -100 100 100", kind="nets")) == \
        set(lst(s, "get_db nets -if {.route_status != unrouted}")) | {"net:sp_primary_input"}
    area = s.eval(f"get_db {lst(s, 'get_db stub:sp/stub1 .net_wires')[0]} .rect")
    assert got(area, kind="nets") == ["stub:sp/stub1"]
    x, y = area.split()[:2]
    assert "stub:sp/stub1" in got(f"{x} {y} {x} {y}", "-touching", "nets")


def test_get_obj_in_area_errors(routed):
    s = routed
    assert "HT4-001" in err(s, "get_obj_in_area")
    assert "HT4-001" in err(s, "get_obj_in_area -area {0 0 1 1} -touching -enclosed")
    assert "HT4-245" in err(s, "get_obj_in_area -area {0 0 1}")
    assert "HT4-245" in err(s, "get_obj_in_area -area {0 0 1 x}")
    assert "HT4-246" in err(s, "get_obj_in_area -area {0 0 1 1} -type ports")
    assert "HT4-246" in err(s, "get_obj_in_area -area {0 0 1 1} -type {}")
    assert s.eval("get_obj_in_area -area {50 50 60 60}") == ""
