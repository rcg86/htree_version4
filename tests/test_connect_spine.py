"""connect_spine: the inputs of spines and input pins onto the net of the
nearest stub of a spine (the netlist only), an output port through a buffer
placed -distance from it, and what reads it: get_db pin .net, write_logical,
write_def, write_db / read_db."""

import io

import pytest

pytest.importorskip("scipy")

from core import objects
from core.commands.connect_spine import _distance, _ways
from core.htree_builder import Session
from test_move_spine import DEF as L_DEF, LEF as SITE_LEF, ROWS
from test_route_net import DEF, SPEC
from test_route_pin import CELL_LEF, err, out_of

PINS = """PINS 2 ;
- clk + NET clk + DIRECTION INPUT + USE CLOCK ;
- q + NET q + DIRECTION OUTPUT ;
END PINS
"""
# Ports with a place: the stubs of sp are at x 8.64, stub1 at y 10, stub2 at
# y 30 .. 40 (see test_ports_get_a_buffer).
PORTS = """PINS 6 ;
- clk + NET clk + DIRECTION INPUT + USE CLOCK
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( -90000 10000 ) N ;
- q + NET q_net + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 100000 10000 ) N ;
- top + NET top + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 20000 100000 ) N ;
- near + NET near + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 12000 30000 ) N ;
- nowhere + NET nowhere + DIRECTION OUTPUT ;
- d[3] + NET d[3] + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 12000 -30000 ) N ;
END PINS
"""
BUF = "-ref_name INV_RP -distance 10 -name out"
# The pins connect_spine -from sp -to {sp2 sp3 buf1/A} connects, by stub.
ON_STUB1 = ["sp2_L1_inv1/A", "buf1/A"]
ON_STUB2 = ["sp3_L1_inv1/A", "sp3_mirror_L1_inv1/A"]


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def net(s, pin):
    return s.eval(f"get_db pin:{pin} .net.name")


def to_stub(s, pin, stub):
    """The Manhattan distance from the centre of pin to a straight stub of sp,
    worked out here from its two ends."""
    x, y = objects.pin_centre(s.db, *pin.split("/"))
    x1, y1, x2, y2 = (float(c) for c in s.eval(f"get_db stub:sp/{stub} .points").split())
    assert x1 == x2 and y1 < y2                       # the stubs of sp run along y
    return abs(x - x1) + max(y1 - y, 0, y - y2)


@pytest.fixture
def design(tech_session, write_lef):
    """Three spines of two stubs each (sp, sp2 and the mirrored sp3) and an
    instance of no spine, in a design with ports."""
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF.replace('END DESIGN', PINS + 'END DESIGN'), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_spine -name sp2 -spec_name sp -location {30 -10} -build -ref_cell INV_RP")
    s.eval("create_spine -name sp3 -spec_name sp -location {-40 30} -build -ref_cell INV_RP "
           "-mirror")
    s.eval("create_inst -name buf1 -ref_cell INV_RP -location {10 -20}")
    out_of(s)
    return s


def test_each_takes_its_nearest_stub(design):
    s = design
    assert lst(s, "get_db spine:sp .stubs.name") == ["stub1", "stub2"]
    made = lst(s, "connect_spine -from sp -to {sp2 spine:sp3 buf1/A}")
    text = out_of(s)
    assert made == [f"pin:{p}" for p in ("sp2_L1_inv1/A", *ON_STUB2, "buf1/A")]
    assert "spine sp (2 stub(s)) -> 3 of -to, 4 pin(s) connected" in text
    # two of -to on one stub, the roots of the mirrored spine both on the other
    for pin in ON_STUB1:
        assert net(s, pin) == "sp_L3_inv1_Y"
        assert s.eval(f"get_db pin:{pin} .net") == "spine_net:sp/sp_L3_inv1_Y"
        assert s.eval(f"get_db pin:{pin} .net.driver") == "inst:sp_L3_inv1"
    for pin in ON_STUB2:
        assert net(s, pin) == "sp_L3_inv2_Y"
        assert s.eval(f"get_db pin:{pin} .net.driver") == "inst:sp_L3_inv2"
    # the stub taken is the nearer one, and the distance reported is to it
    rows = {line.split()[1]: line.split() for line in text.splitlines()
            if line.startswith(("  spine ", "  pin "))}
    for pin, stub, other in (("sp2_L1_inv1/A", "stub1", "stub2"),
                             ("buf1/A", "stub1", "stub2")):
        near = to_stub(s, pin, stub)
        assert near < to_stub(s, pin, other)
        row = rows[pin.split("_L1")[0]]
        assert row[2] == stub and float(row[4]) == pytest.approx(near, abs=1e-3)
    # the mirrored spine: from the middle of its two root pins
    (ax, ay), (bx, by) = (objects.pin_centre(s.db, *p.split("/")) for p in ON_STUB2)
    middle = (ax + bx) / 2, (ay + by) / 2
    x1, y1, _, y2 = (float(c) for c in s.eval("get_db stub:sp/stub2 .points").split())
    near = abs(middle[0] - x1) + max(y1 - middle[1], 0, middle[1] - y2)
    assert rows["sp3"][2] == "stub2" and float(rows["sp3"][4]) == pytest.approx(near, abs=1e-3)
    assert rows["sp3"][5:] == ON_STUB2
    # the roots were on the spec's root_net: taken off it, and said so
    assert "disconnected first: sp2_L1_inv1/A from net sp2_primary_input, sp3_L1_inv1/A from " \
        "net sp3_primary_input" in text
    assert "buf1/A from" not in text
    assert "netlist only: no wire is made" in text and "HT4-254" not in text
    # a leaf's net keeps its stub as its only load for route_net
    assert lst(s, "get_db spine_net:sp/sp_L3_inv1_Y .loads") == ["stub1"]
    assert net(s, "sp_L1_inv1/A") == "sp_primary_input"       # the -from spine's own root


def test_again_and_from_another_spine(design):
    s = design
    s.eval("connect_spine -from sp -to {sp2 buf1/A}")
    out_of(s)
    made = lst(s, "connect_spine -from sp -to {sp2 buf1/A sp2}")       # sp2 given twice
    text = out_of(s)
    assert made == ["pin:sp2_L1_inv1/A", "pin:buf1/A"]
    assert "-> 2 of -to, 0 pin(s) connected" in text
    assert "on the net already: sp2_L1_inv1/A buf1/A" in text
    assert "disconnected first" not in text and "netlist only" not in text
    # a pin on a stub of one spine moves to the stub of another
    s.eval("connect_spine -from spine:sp3 -to buf1/A")
    text = out_of(s)
    assert "disconnected first: buf1/A from net sp_L3_inv1_Y" in text
    assert net(s, "buf1/A").startswith("sp3_") and net(s, "buf1/A").endswith("_Y")
    assert s.eval("get_db pin:buf1/A .net").startswith("spine_net:sp3/")
    assert net(s, "sp2_L1_inv1/A") == "sp_L3_inv1_Y"


def test_loops(design):
    s = design
    assert "HT4-268" in err(s, "connect_spine -from sp -to sp")
    assert "HT4-268" in err(s, "connect_spine -from sp -to {sp2 spine:sp}")
    text = err(s, "connect_spine -from sp -to sp_L2_inv1/A")           # a pin of its own
    assert "HT4-268" in text and "sp_L2_inv1" in text
    assert net(s, "sp2_L1_inv1/A") == "sp2_primary_input"     # nothing connected
    s.eval("connect_spine -from sp -to sp2")
    s.eval("connect_spine -from sp2 -to sp3")
    out_of(s)
    # sp drives sp2 drives sp3: none of them may drive one before it
    for script in ("connect_spine -from sp2 -to sp", "connect_spine -from sp3 -to sp2",
                   "connect_spine -from sp3 -to sp", "connect_spine -from sp3 -to sp_L1_inv1/A"):
        assert "HT4-268" in err(s, script)
    assert net(s, "sp_L1_inv1/A") == "sp_primary_input"
    s.eval("connect_spine -from sp3 -to buf1/A")              # not in a loop


def test_errors(design):
    s = design
    for script in ("connect_spine -from sp", "connect_spine -to sp2",
                   "connect_spine -from {sp sp2} -to sp3", "connect_spine -from sp -to {}"):
        assert "HT4-001" in err(s, script)
    assert "HT4-022" in err(s, "connect_spine -from nosuch -to sp2")
    assert "HT4-022" in err(s, "connect_spine -from sp -to nosuch")
    assert "HT4-022" in err(s, "connect_spine -from sp -to nosuch/A")
    assert "HT4-251" in err(s, "connect_spine -from sp -to buf1/Y")    # an output pin
    assert "HT4-251" in err(s, "connect_spine -from sp -to buf1/VDD")
    assert "HT4-251" in err(s, "connect_spine -from sp -to clk")       # an input port
    for port in ("q", "port:t/q"):                            # a port that is nowhere
        assert "HT4-269" in err(s, f"connect_spine -from sp -to {port} {BUF}")
    # checked before anything is changed
    assert "HT4-251" in err(s, "connect_spine -from sp -to {sp2 buf1/Y}")
    assert net(s, "sp2_L1_inv1/A") == "sp2_primary_input" and net(s, "buf1/A") == ""


def test_spine_without_stubs(design):
    s = design
    with s.db.conn:
        s.db.conn.execute("DELETE FROM spine_stub WHERE spine_id = ?",
                          (s.db.spine_row("sp")["id"],))
    assert "HT4-267" in err(s, "connect_spine -from sp -to sp2")
    s.eval("connect_spine -from sp2 -to sp")                  # as a -to it needs none


def test_distance_to_a_bent_stub():
    bent = [(0, 0), (0, 10), (6, 10)]
    assert _distance((0, 4), bent) == 0
    assert _distance((-3, 5), bent) == 3
    assert _distance((3, 8), bent) == 2                       # the second piece is nearer
    assert _distance((8, 12), bent) == 4
    assert _distance((2, -5), bent) == 7


def test_routed_nets(design):
    s = design
    for inst in ("sp_L3_inv1", "sp2_L1_inv1", "buf1"):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    s.eval("connect_pin -from buf1/Y -to sp2_L1_inv1/A -disconnect")
    s.eval("route_net -net {sp_L3_inv1_Y buf1_Y} -rule r")
    stub, plain = (lst(s, f"get_db {n} .net_wires")
                   for n in ("spine_net:sp/sp_L3_inv1_Y", "net:buf1_Y"))
    assert stub and plain
    out_of(s)
    s.eval("connect_spine -from sp -to {sp2 sp3}")
    text = out_of(s)
    # the net sp2's root was taken off is routed to it; a stub's net is routed
    # to its stub only, and "netlist only" says so
    assert text.count("HT4-254") == 1 and "net buf1_Y is routed" in text
    assert "for sp2_L1_inv1/A" in text and "netlist only" in text
    assert lst(s, "get_db spine_net:sp/sp_L3_inv1_Y .net_wires") == stub
    assert net(s, "sp2_L1_inv1/A") == "sp_L3_inv1_Y"
    # moved from one routed stub net to another: no wire went to the pin
    s.eval("connect_spine -from sp3 -to sp2")
    assert "HT4-254" not in out_of(s)


def test_write_logical_and_def(design, tmp_path):
    s = design
    s.eval("connect_spine -from sp -to {sp2 sp3 buf1/A}")
    s.eval(f"write_logical -output {tmp_path}/l.tcl")
    text = (tmp_path / "l.tcl").read_text()
    for pin in ON_STUB1:
        assert f"connect {pin} -net sp_L3_inv1_Y\n" in text
    for pin in ON_STUB2:
        assert f"connect {pin} -net sp_L3_inv2_Y\n" in text
    assert "connect sp_L1_inv1/A -net sp_primary_input\n" in text
    assert "connect sp2_L1_inv1/A -net sp2_primary_input\n" not in text
    s.eval(f"write_def -output {tmp_path}/o.def -sections nets")
    nets = (tmp_path / "o.def").read_text().split("\nNETS")[1]
    assert "- sp_L3_inv1_Y ( sp_L3_inv1 Y ) ( sp2_L1_inv1 A ) ( buf1 A ) + USE CLOCK" in nets
    assert ("- sp_L3_inv2_Y ( sp_L3_inv2 Y ) ( sp3_L1_inv1 A ) ( sp3_mirror_L1_inv1 A ) "
            "+ USE CLOCK") in nets


def test_write_db_read_db(design, tmp_path):
    s = design
    s.eval("connect_spine -from sp -to {sp2 sp3 buf1/A}")
    path = tmp_path / "c.db"
    s.eval(f"write_db -file {path}")
    other = Session(out=io.StringIO())
    other.eval(f"read_db -file {path}")
    for pin in ON_STUB1 + ON_STUB2 + ["sp_L1_inv1/A"]:
        assert net(other, pin) == net(s, pin)
    assert net(other, "sp3_mirror_L1_inv1/A") == "sp_L3_inv2_Y"
    # and it goes on from there
    assert "HT4-268" in err(other, "connect_spine -from sp2 -to sp")
    other.eval("connect_spine -from sp2 -to buf1/A")
    assert net(other, "buf1/A").startswith("sp2_") and net(s, "buf1/A") == "sp_L3_inv1_Y"


# -- ports: driven through a buffer ----------------------------------------------

@pytest.fixture
def ported(tech_session, write_lef):
    """sp and sp2 in a design with ports that have a place."""
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF.replace('END DESIGN', PORTS + 'END DESIGN'), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_spine -name sp2 -spec_name sp -location {30 -10} -build -ref_cell INV_RP")
    out_of(s)
    return s


def from_port(s, inst, port):
    """(dx, dy) from the centre of a port to the output pin of its buffer."""
    px, py = objects.pin_centre(s.db, inst, "Y")
    ax, ay = objects.port_centre(s.db, port)
    return px - ax, py - ay


def test_ways_to_a_stub():
    # dist from the port in x + y: the longer leg first, then the other way
    assert _ways((0, 0), (30, -20), 10) == ((10, 0), (0, -10))
    assert _ways((0, 0), (-5, 20), 10) == ((0, 10), (-5, 5))
    assert _ways((0, 0), (-5, 20), 22) == ((-2, 20), (-5, 17))
    assert _ways((0, 0), (3, 4), 10) == ((3, 4), (3, 4))      # the stub is nearer


def test_ports_get_a_buffer(ported):
    s = ported
    insts = lst(s, "get_db insts")
    made = lst(s, f"connect_spine -from sp -to {{sp2 q port:t/top near q}} {BUF}")
    text = out_of(s)
    assert made == [f"pin:{p}" for p in ("sp2_L1_inv1/A", "out_q/A", "out_top/A", "out_near/A")]
    assert "-> 4 of -to, 4 pin(s) connected, 3 buffer(s) made" in text
    assert lst(s, "get_db insts") == insts + ["inst:out_q", "inst:out_top", "inst:out_near"]
    # each port on its nearest stub: the input of its buffer on the stub's net
    rows = {line.split()[1]: line.split() for line in text.splitlines()
            if line.startswith("  port ")}
    assert [rows[p][2] for p in ("q", "top", "near")] == ["stub1", "stub2", "stub2"]
    assert float(rows["q"][4]) == pytest.approx(91.36) and rows["q"][5:] == ["out_q/A"]
    assert float(rows["top"][4]) == pytest.approx(71.36)
    for buf, stub_net, leaf in (("out_q", "sp_L3_inv1_Y", "sp_L3_inv1"),
                                ("out_top", "sp_L3_inv2_Y", "sp_L3_inv2")):
        assert s.eval(f"get_db pin:{buf}/A .net") == f"spine_net:sp/{stub_net}"
        assert s.eval(f"get_db pin:{buf}/A .net.driver") == f"inst:{leaf}"
        assert s.eval(f"get_db inst:{buf} .orient") == s.eval(f"get_db inst:{leaf} .orient")
        assert s.eval(f"get_db inst:{buf} .ref_name") == "INV_RP"
    # the output of the buffer drives the port: on the net of the port
    assert s.eval("get_db pin:out_q/Y .net") == "net:q_net"
    assert s.eval("get_db net:q_net .driver") == "pin:out_q/Y"
    assert s.eval("get_db net:q_net .ports") == "port:t/q"
    assert s.eval("get_db net:top .pins") == "pin:out_top/Y"
    # the output pin is 10 um from the port, on the way to the stub: along
    # the longer leg (q: along x, top: along y); within the manufacturing grid
    assert from_port(s, "out_q", "q") == pytest.approx((-10, 0), abs=0.01)
    assert from_port(s, "out_top", "top") == pytest.approx((0, -10), abs=0.01)
    # near is 3.36 um from its stub: the buffer is at the stub
    assert from_port(s, "out_near", "near") == pytest.approx((-3.36, 0), abs=0.01)
    assert "(its stub is 3.36 um from the port: at the stub)" in text
    # plain instances, of no spine; the stub is still the load route_net takes
    assert "inst:out_q" not in lst(s, "get_db spine:sp .insts")
    assert lst(s, "get_db spine_net:sp/sp_L3_inv1_Y .loads") == ["stub1"]
    # this DEF has no ROW: not on sites
    assert "HT4-264" in text and "no placement rows" in text
    assert "Next: legalize_placement, route_pin -inst {out_q out_top out_near}" in text
    assert "nor the net of an output port" in text
    assert "HT4-261" not in text and "HT4-262" not in text


def test_a_port_again_and_one_driven_already(ported):
    s = ported
    s.eval(f"connect_spine -from sp -to {{q top}} {BUF}")
    insts = lst(s, "get_db insts")
    out_of(s)
    # again: the buffers are there, on their stubs
    made = lst(s, "connect_spine -from sp -to {q top} -ref_cell INV_RP -distance 10")
    text = out_of(s)
    assert made == ["pin:out_q/A", "pin:out_top/A"]
    assert "0 pin(s) connected" in text and "buffer(s) made" not in text
    assert "on the net already: out_q/A out_top/A" in text
    assert lst(s, "get_db insts") == insts
    # from another spine: the port has its driver
    text = err(s, f"connect_spine -from sp2 -to q {BUF}")
    assert "HT4-269" in text and "driven already, by out_q/Y" in text
    assert "disconnect_pin -pin out_q/Y" in text
    assert lst(s, "get_db insts") == insts
    # disconnect_pin takes the buffer off the port; the instance stays
    assert s.eval("disconnect_pin -pin out_q/Y") == "pin:out_q/Y"
    assert "net q_net: out_q/Y taken off, it drove port q" in out_of(s)
    assert s.eval("get_db pin:out_q/Y .net") == "" and s.eval("get_db net:top .pins")
    s.eval("disconnect_pin -pin out_q/Y")
    assert "HT4-255" in out_of(s)
    # now sp2 drives it, through a second buffer; default prefix buf, and a
    # -distance beyond the stub puts it at the stub
    made = lst(s, "connect_spine -from sp2 -to q -ref_name INV_RP -distance 300")
    text = out_of(s)
    assert made == ["pin:buf_q/A"] and "1 buffer(s) made" in text and "at the stub" in text
    assert s.eval("get_db net:q_net .driver") == "pin:buf_q/Y"
    assert s.eval("get_db pin:buf_q/A .net").startswith("spine_net:sp2/")
    assert net(s, "out_q/A") == "sp_L3_inv1_Y"                # the old one, as it was


def test_buffer_names_that_are_taken(ported):
    s = ported
    s.eval("create_inst -name out_q -ref_cell INV_RP -location {50 50}")
    s.eval("create_inst -name out_q_2 -ref_cell INV_RP -location {60 50}")
    assert lst(s, f"connect_spine -from sp -to q {BUF}") == ["pin:out_q_3/A"]
    assert s.eval("get_db net:q_net .driver") == "pin:out_q_3/Y"


def test_a_bit_of_a_bus_port(ported, tmp_path):
    s = ported
    # d[3]: the buffer gets a name without the brackets
    assert lst(s, f"connect_spine -from sp -to {{{{d[3]}}}} {BUF}") == ["pin:out_d_3/A"]
    assert "buffer(s) made" in out_of(s)
    assert s.eval("get_db {net:d[3]} .driver") == "pin:out_d_3/Y"
    assert s.eval("get_db {net:d[3]} .ports") == "{port:t/d[3]}"
    assert lst(s, f"connect_spine -from sp -to {{{{port:t/d[3]}}}} {BUF}") == ["pin:out_d_3/A"]
    assert "on the net already: out_d_3/A" in out_of(s)
    # the script is Tcl: the net name is one word there
    s.eval(f"write_logical -output {tmp_path}/l.tcl")
    text = (tmp_path / "l.tcl").read_text()
    assert "connect out_d_3/Y -net {d[3]}\n" in text
    s.eval(f"write_def -output {tmp_path}/o.def -sections nets")
    assert "- d[3] ( out_d_3 Y ) ( PIN d[3] )" in (tmp_path / "o.def").read_text()


def test_loads_on_the_net_of_a_driven_port(ported):
    s = ported
    s.eval(f"connect_spine -from sp -to q {BUF}")
    s.eval("create_inst -name buf1 -ref_cell INV_RP -location {10 -20}")
    s.eval("connect_pin -from out_q/Y -to buf1/A")
    assert lst(s, "get_db net:q_net .pins") == ["pin:out_q/Y", "pin:buf1/A"]
    out_of(s)
    assert lst(s, "disconnect_pin -pin out_q/Y") == ["pin:out_q/Y", "pin:buf1/A"]
    assert "it drove port q and 1 load(s), taken off as well: buf1/A" in out_of(s)
    assert s.eval("get_db net:q_net .pins") == "" and net(s, "buf1/A") == ""


def test_port_errors_change_nothing(ported):
    s = ported
    insts = lst(s, "get_db insts")
    for options in ("", "-ref_name INV_RP", "-distance 10",
                    "-ref_name INV_RP -ref_cell INV_RP -distance 10",
                    "-ref_name INV_RP -distance 0", "-ref_name INV_RP -distance -5",
                    "-ref_name INV_RP -distance far", "-ref_name INV_RP -distance 10 -name a/b",
                    "-ref_name INV_RP -distance 10 -name {}"):
        assert "HT4-001" in err(s, f"connect_spine -from sp -to {{sp2 q}} {options}"), options
    assert "HT4-251" in err(s, f"connect_spine -from sp -to {{sp2 clk}} {BUF}")
    assert "HT4-269" in err(s, f"connect_spine -from sp -to {{sp2 nowhere}} {BUF}")
    text = err(s, "connect_spine -from sp -to {sp2 q} -ref_name NOPE -distance 10")
    assert "HT4-257" in text and "INV_RP" in text
    assert "HT4-022" in err(s, f"connect_spine -from sp -to {{q port:t/nosuch}} {BUF}")
    assert lst(s, "get_db insts") == insts and net(s, "sp2_L1_inv1/A") == "sp2_primary_input"
    assert s.eval("get_db net:q_net .pins") == ""
    # the buffer options are for ports: without one in -to they are not used
    s.eval("connect_spine -from sp -to sp2 -ref_name NOPE")
    assert lst(s, "get_db insts") == insts


def test_ports_in_write_logical_and_def(ported, tmp_path):
    s = ported
    s.eval(f"connect_spine -from sp -to {{q top}} {BUF}")
    s.eval(f"write_logical -output {tmp_path}/l.tcl")
    text = (tmp_path / "l.tcl").read_text()
    assert "connect out_q/A -net sp_L3_inv1_Y\n" in text
    assert "connect out_q/Y -net q_net\n" in text and "connect out_top/Y -net top\n" in text
    # the nets of the ports are the design's: not made
    assert "net q_net of port q must exist in the design" in text
    made = [line.split()[-1] for line in text.splitlines() if line.startswith("create_net ")]
    assert "q_net" not in made and "top" not in made
    s.eval(f"write_def -output {tmp_path}/o.def -sections {{components nets}}")
    text = (tmp_path / "o.def").read_text()
    assert "- out_q INV_RP " in text.split("\nCOMPONENTS")[1]
    nets = text.split("\nNETS")[1]
    assert "- q_net ( out_q Y ) ( PIN q )" in nets and "- top ( out_top Y ) ( PIN top )" in nets
    assert "- sp_L3_inv1_Y ( sp_L3_inv1 Y ) ( out_q A ) + USE CLOCK" in nets


def test_ports_in_write_db_read_db(ported, tmp_path):
    s = ported
    s.eval(f"connect_spine -from sp -to {{q top}} {BUF}")
    path = tmp_path / "c.db"
    s.eval(f"write_db -file {path}")
    other = Session(out=io.StringIO())
    other.eval(f"read_db -file {path}")
    assert other.eval("get_db net:q_net .driver") == "pin:out_q/Y"
    assert net(other, "out_top/A") == "sp_L3_inv2_Y"
    assert other.eval("get_db inst:out_q .location") == s.eval("get_db inst:out_q .location")
    other.eval(f"connect_spine -from sp -to {{q top}} {BUF}")
    assert "on the net already: out_q/A out_top/A" in out_of(other)
    assert "HT4-269" in err(other, f"connect_spine -from sp2 -to q {BUF}")


# An L-shaped die with placement rows (test_move_spine): a band y 0 .. 40 from
# x 0 and a channel x 60 .. 100 up to y 200. The stubs of sp are in the
# channel, at x 78.64 from y 100 up; port o is in the band, port n in the
# notch, outside the die, port e on the upper edge of the band.
L_PORTS = """PINS 3 ;
- o + NET o + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 10000 20000 ) N ;
- n + NET n + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 30000 100000 ) N ;
- e + NET e + DIRECTION OUTPUT
  + LAYER IA ( -100 -100 ) ( 100 0 ) + FIXED ( 20000 40000 ) N ;
END PINS
"""


def l_die(s, write_lef, rows):
    s.eval(f"read_lef -file {{{write_lef(SITE_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(L_DEF % ((ROWS if rows else '') + L_PORTS), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {70 100} -build -ref_cell INV_RP")
    out_of(s)
    return s


def test_port_buffers_are_put_on_sites_inside_the_boundary(tech_session, write_lef):
    s = l_die(tech_session, write_lef, rows=True)
    assert lst(s, "connect_spine -from sp -to o -ref_name INV_RP -distance 30") == ["pin:buf_o/A"]
    text = out_of(s)
    assert "legalize_placement: 1 instance(s)" in text
    assert "HT4-264" not in text and "HT4-261" not in text and "HT4-262" not in text
    assert "Next: route_pin -inst {buf_o}" in text
    # the stub is 68.64 right of the port and 80 above it: 30 up, the longer
    # leg, is outside the die, so the buffer is 30 to the right, in the band;
    # on a site, a site step and a row (N and FS in turn) from there at most
    dx, dy = from_port(s, "buf_o", "o")
    assert dx == pytest.approx(30, abs=0.2) and dy == pytest.approx(0, abs=1.778)
    x, y = (float(c) for c in s.eval("get_db inst:buf_o .location").split())
    assert x / 0.2 == pytest.approx(round(x / 0.2), abs=1e-6)
    assert y / 1.778 == pytest.approx(round(y / 1.778), abs=1e-6)


def inside(s, inst):
    from core.placement import rect_in_polygon
    boundary = [float(v) for v in s.db.design_row()["boundary"].split()]
    return rect_in_polygon(objects.inst_bbox(s.db, s.db.inst_row(inst)), boundary)


def test_a_port_on_the_edge_of_the_die(tech_session, write_lef):
    s = l_die(tech_session, write_lef, rows=True)
    # e is on the upper edge of the band, its stub 58.64 right and 60.05 up:
    # 30 up is outside the die, 30 to the right the pin is on the edge and
    # the cell across it. That way is taken, and the cell put on a site inside
    s.eval("connect_spine -from sp -to e -ref_name INV_RP -distance 30")
    text = out_of(s)
    assert "HT4-262" not in text and "HT4-264" not in text
    assert inside(s, "buf_e")
    dx, dy = from_port(s, "buf_e", "e")
    assert dx == pytest.approx(30, abs=0.2) and -4 < dy < 0


def test_legalize_placement_keeps_a_cell_inside_the_boundary(tech_session, write_lef):
    s = l_die(tech_session, write_lef, rows=True)
    # the N row at y 39.116 is nearest, and reaches across the edge of the
    # band at y 40: the next N row down is taken
    s.eval("create_inst -name u1 -ref_cell INV_RP -location {20.03 39.2}")
    s.eval("create_inst -name u2 -ref_cell INV_RP -location {80.03 39.2}")      # in the channel
    out_of(s)
    s.eval("legalize_placement -inst {u1 u2}")
    assert s.eval("get_db inst:u1 .location") == "20 35.56" and inside(s, "u1")
    assert s.eval("get_db inst:u2 .location") == "80 39.116" and inside(s, "u2")
    # no free site inside near enough: the nearest, as before
    s.eval("create_inst -name u3 -ref_cell INV_RP -location {20.03 60}")
    s.eval("legalize_placement -inst u3")
    assert s.eval("get_db inst:u3 .location") == "20 60.452" and not inside(s, "u3")


def test_a_port_buffer_outside_the_boundary_is_named(tech_session, write_lef):
    s = l_die(tech_session, write_lef, rows=False)
    # port n is outside the die, 48.64 left of its stub: 30 from it, on the
    # way to the stub, the cell is across the boundary
    s.eval("connect_spine -from sp -to n -ref_name INV_RP -distance 30")
    text = out_of(s)
    assert "HT4-264" in text
    assert "HT4-262" in text and "connect_spine:" in text.split("HT4-262")[1].splitlines()[0]
    assert "buf_n" in text.split("HT4-262")[1].splitlines()[0]
    assert from_port(s, "buf_n", "n") == pytest.approx((30, 0), abs=0.01)


def test_an_instance_name_with_brackets_is_no_pattern(ported, tmp_path):
    from core.commands.route_pin import inst_names
    s = ported
    s.eval("create_inst -name x1 -ref_cell INV_RP -location {50 50}")
    s.eval("create_inst -name {x[1]} -ref_cell INV_RP -location {60 50}")
    assert inst_names(s, "{x[1]}") == ["x[1]"]                # as a pattern: x1
    assert inst_names(s, "{inst:x[1]} x*") == ["x[1]", "x1"]
    s.eval(f"write_logical -output {tmp_path}/l.tcl")
    text = (tmp_path / "l.tcl").read_text()
    assert "create_inst -cell INV_RP -name {x[1]}\n" in text and "place_inst {x[1]} " in text
    assert "create_inst -cell INV_RP -name x1\n" in text
