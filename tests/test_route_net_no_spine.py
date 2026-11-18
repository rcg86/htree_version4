"""route_net on the nets of no spine (net:<name>): the net of a port, and the
nets connect_pin makes. And what reads their routing: get_db, set_db,
delete_route, write_def, check_drc, get_obj_in_area, legalize_placement."""
import pytest

pytest.importorskip("scipy")

from core.commands import legalize_placement
from test_route_net import DEF, SPEC, def_block, def_rect, err, out_of
from test_route_pin import CELL_LEF

# clk is on a layer below the rule's; clk2 on IB, over a track crossing; edge
# on the die edge, beyond the tracks; the net of idle has no pin on it.
PINS = """PINS 4 ;
- clk + NET clk_in + DIRECTION INPUT + USE CLOCK
  + LAYER H2 ( -100 -100 ) ( 100 100 ) + FIXED ( -30000 30000 ) N ;
- clk2 + NET clk2_in + DIRECTION INPUT + USE CLOCK
  + LAYER IB ( -400 -400 ) ( 400 400 ) + FIXED ( 20160 30240 ) N ;
- edge + NET edge_in + DIRECTION INPUT
  + LAYER H2 ( -100 -100 ) ( 0 100 ) + FIXED ( 100000 -20000 ) N ;
- idle + NET idle + DIRECTION INPUT ;
END PINS
"""
# The die with a notch from the left edge to x (%d, DEF units), y 18 .. 24:
# between the port clk and b1.
NOTCH = "DIEAREA ( -100000 -100000 ) ( 100000 -100000 ) ( 100000 100000 ) ( -100000 100000 ) " \
        "( -100000 24000 ) ( %d 24000 ) ( %d 18000 ) ( -100000 18000 ) ;"
PLAIN = ["clk_in", "b1_Y", "clk2_in", "edge_in"]


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def rects(s, net, kind, layer=None):
    found = []
    for h in lst(s, f"get_db net:{net} .net_wires"):
        if s.eval(f"get_db {h} .kind") == kind and layer in (None, s.eval(f"get_db {h} .layer")):
            found.append(tuple(float(v) for v in s.eval(f"get_db {h} .rect").split()))
    return found


def make(s, write_lef, design=DEF):
    """The spine of test_route_net in a design with ports. The port clk drives
    b1, which drives the root of the spine and d3 (by its second input pin);
    clk2 drives d2, edge drives d4."""
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(design.replace('END DESIGN', PINS + 'END DESIGN'), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    for name, at in (("b1", "-31 10"), ("d2", "19 10"), ("d3", "30 -20"), ("d4", "40 -30")):
        s.eval(f"create_inst -name {name} -ref_cell INV_RP -location {{{at}}}")
    s.eval("connect_pin -from clk -to b1/A")
    s.eval("connect_pin -from b1/Y -to {sp_L1_inv1/A d3/B} -disconnect")
    s.eval("connect_pin -from clk2 -to d2/A")
    s.eval("connect_pin -from edge -to d4/A")
    s.eval("route_pin -inst {b1 d2 d3 d4 sp_L1_inv1 sp_L2_inv1}")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    return s


@pytest.fixture
def ported(tech_session, write_lef):
    return make(tech_session, write_lef)


@pytest.fixture
def routed(ported):
    ported.eval(f"route_net -net {{{' '.join(PLAIN)}}} -rule r")
    out_of(ported)
    return ported


def test_routes_the_nets_of_no_spine(ported):
    s = ported
    assert lst(s, "route_net -net {clk_in net:b1_Y} -rule r") == ["net:clk_in", "net:b1_Y"]
    text = out_of(s)
    # an instance net: from the output pin to the pins on it, spine cells as any other
    assert "driver b1/Y (strap 3): connected across the strap" in text
    assert "load sp_L1_inv1/A (strap 5): connected across the strap" in text
    assert "now net b1_Y: strap:b1/3 pin_wire:b1/Y  strap:sp_L1_inv1/5 pin_wire:sp_L1_inv1/A" in text
    assert s.eval("get_db strap:sp_L1_inv1/5 .net") == "b1_Y"
    assert s.eval("get_db strap:b1/5 .net") == "clk_in"
    # a load by another pin than the first input of its cell: that pin (no pin route here)
    assert "HT4-172" in text and "route_pin is not done on d3 (pin B)" in text
    assert "load d3/B: ends near the pin, not connected" in text
    # one vertical wire from the crossing at the port down to the strap of b1/A
    (x1, y1, x2, y2), = rects(s, "clk_in", "wire", "IB")
    assert (x1 + x2) / 2 == pytest.approx(-30.24) and y2 == pytest.approx(30.24 + 0.18)
    assert s.eval("get_db net:clk_in .route_rule") == "route_rule:r"


def test_port_ends(ported):
    s = ported
    s.eval("route_net -net {clk_in clk2_in edge_in} -rule r")
    text = out_of(s)
    # a port on a layer below the rule's: the route ends at the crossing, not connected
    assert "HT4-266" in text and "clk_in: the route ends at the track crossing nearest port " \
        "clk, {-30.24 30.24} on IA and IB, 0.48 um from the centre of the port (shapes on H2); " \
        "it is not connected to the port" in text
    assert "driver port clk: ends near the port, not connected at {-30.24 30.24}" in text
    # a port on a rule layer under a wire of the route on that layer: connected
    assert "driver port clk2: connected on IB at {20.16 30.24}" in text
    assert "clk2_in: the route ends" not in text
    # a port beyond the tracks: from the last track
    assert "HT4-176" in text and "edge_in: port edge is beyond the signal tracks" in text
    assert "driver port edge: ends near the port, not connected at {50.4 -20.16}" in text


def test_nets_that_are_not_routed(ported):
    s = ported
    # the net of a port with no pin on it
    for word in ("idle", "net:idle"):
        assert s.eval(f"route_net -net {word} -rule r") == ""
        text = out_of(s)
        assert "HT4-265" in text and "net idle is not routed: no input pin of an instance" in text
    # every word must match a net; a pattern sees the nets with a pin on them
    for word in ("net:nosuch", "nosuch", "id*"):
        assert "HT4-170" in err(s, f"route_net -net {word} -rule r")
    # a net that lost its pins is no net any more
    s.eval("disconnect_pin -pin {sp_L1_inv1/A d3/B}")
    assert "HT4-170" in err(s, "route_net -net b1_Y -rule r")


def test_no_driver(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    # the root net of the spine: the input of the root is on it, nothing drives it
    assert s.eval("route_net -net sp_primary_input -rule r") == ""
    text = out_of(s)
    assert "HT4-265" in text and "net sp_primary_input is not routed: it has no driver" in text
    # by a pattern the spine nets are routed and this one is left, as before
    assert all(h.startswith("spine_net:sp/") for h in lst(s, "route_net -net * -rule r"))
    assert "HT4-265" not in out_of(s)


def test_a_pattern_takes_them(ported):
    s = ported
    done = lst(s, "route_net -net * -rule r")
    assert done == [f"spine_net:sp/sp_L{k}_Y" for k in ("1_inv1", "2_inv1", "3_inv1", "3_inv2")] \
        + ["net:b1_Y", "net:clk_in", "net:clk2_in", "net:edge_in"]
    # again: replaced, the same wires
    wires = {n: rects(s, n, "wire") for n in PLAIN}
    out_of(s)
    assert lst(s, "route_net -net net:clk_in -rule r") == ["net:clk_in"]
    assert "HT4-173" in out_of(s) and rects(s, "clk_in", "wire") == wires["clk_in"]


def test_inside_the_boundary(tech_session, write_lef):
    """The hard limit holds for a net of no spine: round the notch, not across."""
    old = next(line for line in DEF.splitlines() if line.startswith("DIEAREA"))
    s = make(tech_session, write_lef, DEF.replace(old, NOTCH % (-26000, -26000)))
    assert lst(s, "route_net -net clk_in -rule r") == ["net:clk_in"]
    text = out_of(s)
    assert "load b1/A (strap 5): connected across the strap" in text and "HT4-174" not in text
    wires = rects(s, "clk_in", "wire") + rects(s, "clk_in", "extension") + rects(s, "clk_in", "cross")
    assert len(rects(s, "clk_in", "wire")) >= 3                       # there, along and back
    for x1, y1, x2, y2 in wires:
        assert not (x1 < -26 - 1e-6 and y2 > 18 + 1e-6 and y1 < 24 - 1e-6), (x1, y1, x2, y2)


def test_no_way_round_is_not_routed(tech_session, write_lef):
    """A notch wider than the room of the grid: the net is left, not routed across."""
    old = next(line for line in DEF.splitlines() if line.startswith("DIEAREA"))
    s = make(tech_session, write_lef, DEF.replace(old, NOTCH % (-10000, -10000)))
    assert s.eval("route_net -net clk_in -rule r") == ""
    text = out_of(s)
    assert "HT4-174" in text and "clk_in: no path inside the design boundary to b1/A" in text
    assert rects(s, "clk_in", "wire") == []


def test_shields(ported):
    """-shield on the nets of no spine: a power wire each side, as on a spine net."""
    s = ported
    assert lst(s, "route_net -net {clk_in b1_Y} -rule r -shield") == ["net:clk_in", "net:b1_Y"]
    text = out_of(s)
    for net in ("clk_in", "b1_Y"):
        got = [s.eval(f"get_db {h} .shield_net") for h in lst(s, f"get_db net:{net} .net_wires")
               if s.eval(f"get_db {h} .kind") == "shield"]
        assert "VDD_SOC" in got and "VSS" in got
    # the power pins of the cells on the nets: b1 and the root of the spine reach the
    # shields; d3 has no pin routes
    assert "strap:b1/1 VSS (shield x -29.52 over it)" in text
    assert "power pins connected to shields: 4 of 6" in text
    assert "HT4-177" in text and "d3/VDD (strap 6) d3/VSS (strap 4)" in text
    # routed again without -shield: the shields go
    s.eval("route_net -net {clk_in b1_Y} -rule r")
    assert all(s.eval(f"get_db {h} .kind") != "shield"
               for net in ("clk_in", "b1_Y") for h in lst(s, f"get_db net:{net} .net_wires"))


def test_get_db_and_set_db(routed):
    s = routed
    wires = lst(s, "get_db net:clk_in .net_wires")
    assert wires and all(w.startswith("net_wire:clk_in/") for w in wires)
    assert s.eval(f"get_db {wires[0]} .net") == "net:clk_in"
    assert s.eval(f"get_db {wires[0]} .net.driver") == "port:t/clk"
    vias = lst(s, "get_db net:b1_Y .vias")
    assert vias and all(v.startswith("via:b1_Y/") for v in vias)
    assert s.eval("get_db net:clk_in .route_rule.name") == "r"
    assert s.eval("set_db net:clk_in .route_rule default") == "net:clk_in"
    assert s.eval("get_db net:clk_in .route_rule") == "route_rule:default"
    # a net with no routing
    assert s.eval("get_db net:idle .net_wires") == "" and s.eval("get_db net:idle .vias") == ""
    assert s.eval("get_db net:idle .route_rule") == "route_rule:default"


def test_delete_route(routed):
    s = routed
    assert lst(s, "delete_route -nets {net:clk_in b1*}") == ["net:clk_in", "net:b1_Y"]
    text = out_of(s)
    assert "clk_in: 4 wire(s), extension(s), crossing box(es) and shield(s) removed; 2 strap(s) " \
        "and pin wire(s) back on SIGNAL" in text
    assert s.eval("get_db net:clk_in .net_wires") == "" and s.eval("get_db net:b1_Y .vias") == ""
    assert s.eval("get_db strap:b1/5 .net") == s.eval("get_db strap:sp_L1_inv1/5 .net") == "SIGNAL"
    # the nets stay, and the others keep their routing
    assert s.eval("get_db net:clk_in .pins") == "pin:b1/A"
    assert s.eval("get_db net:clk2_in .net_wires") != ""
    assert "HT4-195" in err(s, "delete_route -nets net:nosuch")
    s.eval("delete_route -nets clk_in")
    assert "HT4-196" in out_of(s)


def test_write_def(routed, tmp_path):
    s = routed
    s.eval(f"write_def -output {{{tmp_path / 'o.def'}}}")
    text = (tmp_path / "o.def").read_text()
    special = text.split("SPECIALNETS")[1]
    # the straps route_net named after these nets are theirs, not a power net's: the
    # routed signal nets first (FIXED), then the power nets (ROUTED, + USE)
    names = [line.split()[1] for line in special.splitlines() if line.startswith("- ")]
    assert names[-2:] == ["VSS", "VDD_SOC"] and "clk_in" in names and "b1_Y" in names
    assert "\nNETS " not in text
    clk = def_block(text, "clk_in")
    assert clk[0] == "- clk_in" and clk[1].startswith("  + FIXED + RECT IB ")
    # the strap of b1/A, once: under its net
    strap = def_rect("FIXED", "IA", s.eval("get_db strap:b1/5 .rect"))
    assert text.count(strap.split("RECT")[1]) == 1 and strap in clk
    # the connections, when asked for
    s.eval(f"write_def -output {{{tmp_path / 'n.def'}}} -sections nets")
    nets = (tmp_path / "n.def").read_text()
    assert "NETS 8 ;" in nets                                    # 4 of the spine, 4 of none
    assert "- clk_in ( b1 A ) ( PIN clk ) + USE CLOCK ;" in nets
    b1_y = next(line for line in nets.splitlines() if line.startswith("- b1_Y "))
    assert all(f"( {pin} )" in b1_y for pin in ("b1 Y", "sp_L1_inv1 A", "d3 B")) and "PIN" not in b1_y


def test_check_drc(routed):
    s = routed
    s.eval("check_drc")
    text = out_of(s)
    assert "  Nets  : 8 signal nets, 2 power nets" in text
    assert "Opens, power nets" not in text and "short     -       -       0" in text
    # the nets of no spine are checked as signal nets: the pin with no pin route is open
    assert "net b1_Y: no path to the driver b1/Y from pin d3/B" in text
    assert "net clk_in" not in text and "net clk2_in" not in text    # one piece each
    # not routed: its pins are apart
    s.eval("delete_route -nets clk2_in")
    s.eval("connect_pin -from clk2 -to d4/B")
    s.eval("check_drc")
    assert "net clk2_in: no path to the rest of the net from pin d" in out_of(s)


def test_get_obj_in_area(routed):
    s = routed
    assert lst(s, "get_obj_in_area -area {20 20 20.3 21} -type net -touching") == ["net:clk2_in"]
    assert "net:clk2_in" in lst(s, "get_obj_in_area -area {15 0 25 35} -type net")
    assert lst(s, "get_obj_in_area -area {20 20 20.3 21} -type net") == []


def test_legalize_names_them(routed):
    db = routed.db
    assert legalize_placement._nets_of(db, ["b1"]) == ["b1_Y", "clk_in"]
    assert legalize_placement._nets_of(db, ["sp_L1_inv1"]) == ["b1_Y"]
    assert legalize_placement._nets_of(db, ["sp_L3_inv1"]) == []
