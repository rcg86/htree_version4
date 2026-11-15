"""connect_pin and disconnect_pin: the netlist of the instance pins (the
spine nets, the connection table), and what reads it: get_db pin .net,
route_net, write_logical, write_def, write_db / read_db."""

import io
import sqlite3

import pytest

pytest.importorskip("scipy")

from core.htree_builder import Session
from test_route_net import DEF, SPEC
from test_route_pin import CELL_LEF, err, out_of

# Two input ports and an output port; the net of p2 has the name connect_pin
# would give the output net of an instance x.
PINS = """PINS 3 ;
- clk + NET clk + DIRECTION INPUT + USE CLOCK ;
- q + NET q + DIRECTION OUTPUT ;
- p2 + NET x_Y + DIRECTION INPUT ;
END PINS
"""


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def net(s, pin):
    return s.eval(f"get_db pin:{pin} .net.name")


def loads(s, name):
    return lst(s, f"get_db spine_net:sp/{name} .loads")


@pytest.fixture
def design(tech_session, write_lef):
    """The spine sp (L1 -> L2 -> two leaves with a stub each) in a design with
    ports, and three instances of no spine."""
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF.replace('END DESIGN', PINS + 'END DESIGN'), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    for name, at in (("buf1", "{10 -20}"), ("d1", "{12 20}"), ("d2", "{20 -20}")):
        s.eval(f"create_inst -name {name} -ref_cell INV_RP -location {at}")
    out_of(s)
    return s


def test_net_of_a_pin(design):
    s = design
    assert net(s, "sp_L1_inv1/A") == "net"                    # the spec's root_net
    assert net(s, "sp_L1_inv1/Y") == net(s, "sp_L2_inv1/A") == "sp_L1_inv1_Y"
    assert net(s, "sp_L3_inv1/A") == net(s, "sp_L3_inv2/A") == "sp_L2_inv1_Y"
    assert net(s, "sp_L3_inv1/Y") == "sp_L3_inv1_Y"           # a leaf's net
    assert net(s, "sp_L1_inv1/VDD") == net(s, "sp_L1_inv1/B") == ""
    assert net(s, "buf1/A") == net(s, "buf1/Y") == ""
    assert s.eval("get_db pin:sp_L2_inv1/A -if {.net.name == sp_L1_inv1_Y}") == "pin:sp_L2_inv1/A"
    assert s.eval("get_db inst:sp_L2_inv1 .pins -if {.net.name == sp_L1*}") == "pin:sp_L2_inv1/A"
    assert s.eval("get_db inst:sp_L2_inv1 .pins.name -if {.net.driver.name == sp_L2*}") == "Y"


def test_net_of_a_pin_is_an_object(design):
    """.net is the net object, so the chain goes on: a spine_net for a net of
    a spine, a net for one that is no spine's (a port's, connect_pin's)."""
    s = design
    assert s.eval("get_db pin:sp_L2_inv1/A .net") == "spine_net:sp/sp_L1_inv1_Y"
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == "net:net"
    assert s.eval("get_db pin:buf1/A .net") == s.eval("get_db pin:sp_L1_inv1/VDD .net") == ""
    assert s.eval("get_db [get_db inst:sp_L2_inv1 .pins -if {.name == A}] .net.name") == \
        "sp_L1_inv1_Y"
    assert lst(s, "get_db inst:sp_L2_inv1 .pins.net.name") == ["sp_L1_inv1_Y", "sp_L2_inv1_Y"]
    assert s.eval("get_db pin:sp_L2_inv1/A .net.driver") == "inst:sp_L1_inv1"
    assert lst(s, "get_db pin:sp_L2_inv1/A .net.pins") == ["pin:sp_L1_inv1/Y", "pin:sp_L2_inv1/A"]
    assert s.eval("get_db pin:sp_L2_inv1/A .net.length") == \
        s.eval("get_db spine_net:sp/sp_L1_inv1_Y .length")
    # the pins of a spine net: its driver's and its loads', a stub is none
    assert lst(s, "get_db spine_net:sp/sp_L2_inv1_Y .pins") == \
        ["pin:sp_L2_inv1/Y", "pin:sp_L3_inv1/A", "pin:sp_L3_inv2/A"]
    assert lst(s, "get_db spine_net:sp/sp_L3_inv1_Y .pins") == ["pin:sp_L3_inv1/Y"]
    assert s.eval("get_db pin:sp_L3_inv1/A .net.pins -if {.direction == out}") == \
        "pin:sp_L2_inv1/Y"

    # a net of no spine: the root net of the spec, then connect_pin's and a port's
    assert s.eval("get_db net:net .*") == ""
    assert (s.eval("get_db net:net .obj_type"), s.eval("get_db net:net .name")) == ("net", "net")
    assert s.eval("get_db net:net .pins") == "pin:sp_L1_inv1/A"
    assert s.eval("get_db net:net .driver") == s.eval("get_db net:net .ports") == ""
    s.eval("connect_pin -from buf1/Y -to {d1/A d2/A}")
    assert s.eval("get_db pin:d1/A .net") == "net:buf1_Y"
    assert s.eval("get_db net:buf1_Y .driver") == "pin:buf1/Y"
    assert sorted(lst(s, "get_db net:buf1_Y .pins")) == ["pin:buf1/Y", "pin:d1/A", "pin:d2/A"]
    assert sorted(lst(s, "get_db pin:d1/A .net.pins.inst.name")) == ["buf1", "d1", "d2"]
    s.eval("connect_pin -from clk -to buf1/A")
    assert s.eval("get_db pin:buf1/A .net") == "net:clk"
    assert s.eval("get_db net:clk .driver") == s.eval("get_db net:clk .ports") == "port:t/clk"
    assert s.eval("get_db net:clk .ports.direction") == "in"
    assert s.eval("get_db net:q .pins") == "" and s.eval("get_db net:q .ports.name") == "q"
    out_of(s)
    # no such net; a spine's net is a spine_net, not a net
    for handle in ("net:nothing", "net:sp_L1_inv1_Y"):
        assert "HT4-022" in err(s, f"get_db {handle}")
    assert "HT4-023" in err(s, "get_db net:clk .length")


def test_directions(design):
    s = design
    for script, said in (
            ("connect_pin -from buf1/A -to d1/A", "-from buf1/A is an input pin"),
            ("connect_pin -from q -to d1/A", "-from port q is an output port"),
            ("connect_pin -from port:t/q -to d1/A", "-from port q is an output port"),
            ("connect_pin -from buf1/VDD -to d1/A", "-from buf1/VDD is a pin without a direction"),
            ("connect_pin -from buf1/Y -to {d1/A d1/Y d2/A clk sp_L1_inv1/VSS}",
             "not one: d1/Y (an output pin), port clk (an input port), "
             "sp_L1_inv1/VSS (a pin without a direction)")):
        text = err(s, script)
        assert "HT4-251" in text and said in text
    # one wrong pin: nothing is connected
    assert net(s, "d1/A") == net(s, "d2/A") == net(s, "buf1/Y") == ""
    assert s.db.connection_rows() == []


def test_usage_and_unknown(design):
    s = design
    assert "HT4-001" in err(s, "connect_pin -from buf1/Y")
    assert "HT4-001" in err(s, "connect_pin -to d1/A")
    assert "HT4-001" in err(s, "connect_pin -from {buf1/Y d1/Y} -to d2/A")
    assert "HT4-001" in err(s, "connect_pin -from buf1/Y -to {}")
    assert "HT4-001" in err(s, "connect_pin -from buf1/Y -to d1/A -net n")
    assert "HT4-001" in err(s, "disconnect_pin")
    assert "HT4-022" in err(s, "connect_pin -from nosuch/Y -to d1/A")
    assert "HT4-022" in err(s, "connect_pin -from buf1/Y -to d1/NOPIN")
    assert "HT4-022" in err(s, "connect_pin -from nosuch -to d1/A")          # no such port
    assert "HT4-022" in err(s, "connect_pin -from port:t/nosuch -to d1/A")
    text = err(s, "disconnect_pin -pin inst:buf1")
    assert "HT4-022" in text and "'inst:buf1' is a inst" in text
    assert "HT4-022" in err(s, "disconnect_pin -pin {d1/A nosuch/A}")


def test_new_net_between_instances(design):
    s = design
    assert s.eval("connect_pin -from buf1/Y -to {d1/A pin:d2/A}") == "pin:d1/A pin:d2/A"
    text = out_of(s)
    assert "connect_pin: net buf1_Y (new): buf1/Y -> d1/A d2/A" in text
    assert "a net of no spine: route_net -net net:buf1_Y -rule <rule> routes it" in text
    assert "netlist only" not in text
    assert net(s, "buf1/Y") == net(s, "d1/A") == net(s, "d2/A") == "buf1_Y"
    # again: on the net already, and the net is not new
    s.eval("connect_pin -from pin:buf1/Y -to {d1/A d1/B}")
    text = out_of(s)
    assert "connect_pin: net buf1_Y: buf1/Y -> d1/B" in text
    assert "on the net already: d1/A" in text
    assert net(s, "d1/B") == "buf1_Y"
    # the load pin taken off: the others stay
    assert s.eval("disconnect_pin -pin d1/A") == "pin:d1/A"
    assert "disconnect_pin: net buf1_Y: d1/A taken off" in out_of(s)
    assert (net(s, "d1/A"), net(s, "d1/B"), net(s, "d2/A")) == ("", "buf1_Y", "buf1_Y")
    # the driver: every load goes, and the net with them
    assert set(lst(s, "disconnect_pin -pin buf1/Y")) == {"pin:d1/B", "pin:d2/A"}
    assert "buf1/Y drives it, 2 load(s) taken off" in out_of(s)
    assert net(s, "buf1/Y") == net(s, "d1/B") == net(s, "d2/A") == ""
    assert s.db.connection_rows() == []


def test_port_driver(design):
    s = design
    s.eval("connect_pin -from port:t/clk -to buf1/A")
    assert "connect_pin: net clk: port clk -> buf1/A" in out_of(s)
    s.eval("connect_pin -from clk -to {buf1/A d1/A}")                # the bare port name
    text = out_of(s)
    assert "port clk -> d1/A" in text and "on the net already: buf1/A" in text
    assert net(s, "buf1/A") == net(s, "d1/A") == "clk"
    assert set(lst(s, "disconnect_pin -pin clk")) == {"pin:buf1/A", "pin:d1/A"}
    assert "disconnect_pin: net clk: port clk drives it, 2 load(s) taken off" in out_of(s)
    assert net(s, "buf1/A") == ""
    # an output port drives nothing in the design: nothing to take off
    assert s.eval("disconnect_pin -pin port:t/q") == ""
    assert "HT4-255" in out_of(s)


def test_net_name_taken(design):
    s = design
    s.eval("create_inst -name x -ref_cell INV_RP -location {30 30}")
    text = err(s, "connect_pin -from x/Y -to d1/A")                  # x_Y: the net of port p2
    assert "HT4-252" in text and "'x_Y'" in text
    assert net(s, "d1/A") == ""


def test_already_connected_and_disconnect(design):
    s = design
    s.eval("connect_pin -from buf1/Y -to d1/A")
    out_of(s)
    text = err(s, "connect_pin -from sp_L2_inv1/Y -to {d2/A d1/A sp_L2_inv1/A}")
    assert "HT4-253" in text
    assert "already connected: d1/A (net buf1_Y), sp_L2_inv1/A (net sp_L1_inv1_Y)" in text
    assert net(s, "d2/A") == "" and loads(s, "sp_L2_inv1_Y") == ["sp_L3_inv1", "sp_L3_inv2"]
    s.eval("connect_pin -from sp_L2_inv1/Y -to {d2/A d1/A} -disconnect")
    text = out_of(s)
    assert "connect_pin: net sp_L2_inv1_Y: sp_L2_inv1/Y -> d2/A d1/A" in text
    assert "disconnected first: d1/A from net buf1_Y" in text
    assert net(s, "d1/A") == net(s, "d2/A") == "sp_L2_inv1_Y"
    assert net(s, "buf1/Y") == ""                                    # its last load went
    # -disconnect with nothing to disconnect is a plain connect
    s.eval("connect_pin -from buf1/Y -to d1/B -disconnect")
    assert "disconnected first" not in out_of(s)


def test_spine_net_loads(design):
    s = design
    # the first input pin onto the output of a spine cell: a load of the spine net
    s.eval("connect_pin -from sp_L2_inv1/Y -to {d1/A d2/B}")
    text = out_of(s)
    assert "netlist only, route_net does not route to it" in text and text.rstrip().endswith("d2/B")
    assert loads(s, "sp_L2_inv1_Y") == ["sp_L3_inv1", "sp_L3_inv2", "d1"]
    assert [(r["inst"], r["pin"], r["net"], r["driver"]) for r in s.db.connection_rows()] == \
        [("d2", "B", "sp_L2_inv1_Y", "sp_L2_inv1/Y")]
    assert net(s, "d1/A") == net(s, "d2/B") == "sp_L2_inv1_Y"
    # a spine load taken off and put back
    s.eval("disconnect_pin -pin sp_L3_inv1/A")
    assert loads(s, "sp_L2_inv1_Y") == ["sp_L3_inv2", "d1"] and net(s, "sp_L3_inv1/A") == ""
    assert s.eval("disconnect_pin -pin sp_L3_inv1/A") == ""
    text = out_of(s)
    assert "HT4-255" in text and "nothing to disconnect on sp_L3_inv1/A" in text
    s.eval("connect_pin -from sp_L2_inv1/Y -to sp_L3_inv1/A")
    assert loads(s, "sp_L2_inv1_Y") == ["sp_L3_inv2", "d1", "sp_L3_inv1"]
    # a spine cell moved to another spine net
    s.eval("connect_pin -from sp_L1_inv1/Y -to sp_L3_inv2/A -disconnect")
    assert loads(s, "sp_L1_inv1_Y") == ["sp_L2_inv1", "sp_L3_inv2"]
    assert loads(s, "sp_L2_inv1_Y") == ["d1", "sp_L3_inv1"]
    # the driver of a spine net: every load goes, table rows too; the net stays
    assert set(lst(s, "disconnect_pin -pin sp_L2_inv1/Y")) == \
        {"pin:d1/A", "pin:sp_L3_inv1/A", "pin:d2/B"}
    assert loads(s, "sp_L2_inv1_Y") == [] and s.db.connection_rows() == []
    assert net(s, "sp_L2_inv1/Y") == "sp_L2_inv1_Y"


def test_leaf_net_keeps_its_stub(design):
    s = design
    s.eval("connect_pin -from sp_L3_inv1/Y -to d1/A")
    assert "netlist only" in out_of(s)
    assert loads(s, "sp_L3_inv1_Y") == ["stub1"] and net(s, "d1/A") == "sp_L3_inv1_Y"
    assert s.eval("disconnect_pin -pin sp_L3_inv1/Y") == "pin:d1/A"
    assert loads(s, "sp_L3_inv1_Y") == ["stub1"] and net(s, "d1/A") == ""
    assert s.eval("disconnect_pin -pin sp_L3_inv1/Y") == ""           # a stub is no pin
    assert "HT4-255" in out_of(s)


def test_root_input(design):
    s = design
    assert "HT4-253" in err(s, "connect_pin -from buf1/Y -to sp_L1_inv1/A")
    s.eval("disconnect_pin -pin sp_L1_inv1/A")
    assert "disconnect_pin: net net: sp_L1_inv1/A taken off" in out_of(s)
    assert net(s, "sp_L1_inv1/A") == ""                               # root_net does not come back
    assert [(r["inst"], r["net"]) for r in s.db.connection_rows()] == [("sp_L1_inv1", None)]
    s.eval("connect_pin -from buf1/Y -to sp_L1_inv1/A")
    assert net(s, "sp_L1_inv1/A") == "buf1_Y"
    assert [(r["inst"], r["net"]) for r in s.db.connection_rows()] == [("sp_L1_inv1", "buf1_Y")]
    s.eval("connect_pin -from clk -to sp_L1_inv1/A -disconnect")
    assert net(s, "sp_L1_inv1/A") == "clk" and net(s, "buf1/Y") == ""


def test_route_net_routes_to_a_connected_load(design):
    s = design
    for inst in ("sp_L2_inv1", "sp_L3_inv1", "sp_L3_inv2", "d1"):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    s.eval("connect_pin -from sp_L2_inv1/Y -to d1/A")
    assert "HT4-254" not in out_of(s)                                 # not routed yet
    s.eval("route_net -net sp_L2_inv1_Y -rule r")
    text = out_of(s)
    assert "load d1/A (strap 5): connected across the strap" in text
    assert s.eval("get_db strap:d1/5 .net") == "sp_L2_inv1_Y"
    assert s.eval("check_drc -check_open_only -layer_range IA:IB") == "0"
    out_of(s)
    # a routed net: the netlist changes, the routing does not, and says so
    wires = lst(s, "get_db spine_net:sp/sp_L2_inv1_Y .net_wires")
    s.eval("disconnect_pin -pin d1/A")
    text = out_of(s)
    assert "HT4-254" in text and "net sp_L2_inv1_Y is routed" in text and "for d1/A" in text
    assert lst(s, "get_db spine_net:sp/sp_L2_inv1_Y .net_wires") == wires
    s.eval("connect_pin -from sp_L2_inv1/Y -to d1/A")
    assert "HT4-254" in out_of(s)
    # routed again without the load: its strap is no longer the net's
    s.eval("disconnect_pin -pin d1/A")
    s.eval("route_net -net sp_L2_inv1_Y -rule r")
    assert "d1/A" not in out_of(s).split("HT4-173")[1]
    assert s.eval("get_db strap:d1/5 .net") == "SIGNAL"


def test_write_logical(design, tmp_path):
    s = design
    path = tmp_path / "l.tcl"
    s.eval(f"write_logical -output {path}")
    plain = path.read_text()
    assert "Other instances (create_inst), not connected" in plain
    assert "connect_pin" not in plain and "connect buf1" not in plain
    assert "4 nets, 7 instances" in out_of(s)

    s.eval("connect_pin -from clk -to buf1/A")
    s.eval("connect_pin -from buf1/Y -to {sp_L1_inv1/A d2/B} -disconnect")
    s.eval("connect_pin -from sp_L2_inv1/Y -to d1/A")
    s.eval("disconnect_pin -pin sp_L3_inv2/A")
    out_of(s)
    s.eval(f"write_logical -output {path} -overwrite")
    assert "5 nets, 7 instances" in out_of(s)
    text = path.read_text()
    step1 = text.split("Step 2")[0]
    assert "# connect_pin: net clk of port clk must exist in the design" in step1
    assert step1.count("create_net -name buf1_Y\n") == 1
    assert "create_net -name clk" not in text
    assert step1.index("create_net -name sp_L3_inv2_Y") < step1.index("create_net -name buf1_Y")

    def block(inst):
        return text.split(f"# {inst} ")[1].split("\n\n")[0].splitlines()[3:]
    assert block("sp_L1_inv1") == ["connect sp_L1_inv1/A -net buf1_Y",
                                   "connect sp_L1_inv1/Y -net sp_L1_inv1_Y"]
    assert block("sp_L3_inv2") == ["connect sp_L3_inv2/Y -net sp_L3_inv2_Y"]
    assert block("buf1") == ["connect buf1/A -net clk", "connect buf1/Y -net buf1_Y"]
    assert block("d1") == ["connect d1/A -net sp_L2_inv1_Y"]
    assert block("d2") == ["connect d2/B -net buf1_Y"]
    assert "Other instances (create_inst)\n" in text and "not connected" not in text
    # step 1 is as before, with the connect_pin lines after the spine nets
    assert step1.replace("# connect_pin: net clk of port clk must exist in the design\n"
                         "create_net -name buf1_Y\n\n", "") == plain.split("Step 2")[0]


def test_write_def_nets(design, tmp_path):
    s = design
    s.eval("connect_pin -from sp_L2_inv1/Y -to {d1/A d2/B}")           # a load, a table row
    s.eval("connect_pin -from sp_L3_inv1/Y -to buf1/A")               # on a leaf's net
    s.eval("disconnect_pin -pin sp_L3_inv2/A")
    s.eval(f"write_def -output {tmp_path}/o.def")
    nets = (tmp_path / "o.def").read_text().split("\nNETS")[1]
    assert "- sp_L2_inv1_Y ( sp_L2_inv1 Y ) ( sp_L3_inv1 A ) ( d1 A ) ( d2 B ) + USE CLOCK" in nets
    assert "- sp_L3_inv1_Y ( sp_L3_inv1 Y ) ( buf1 A ) + USE CLOCK" in nets
    assert "sp_L3_inv2 A" not in nets


def test_write_db_read_db(design, tmp_path):
    s = design
    s.eval("connect_pin -from buf1/Y -to {d1/A sp_L1_inv1/A} -disconnect")
    s.eval("connect_pin -from sp_L2_inv1/Y -to d2/A")
    s.eval("disconnect_pin -pin sp_L3_inv1/A")
    path = tmp_path / "c.db"
    s.eval(f"write_db -file {path}")
    other = Session(out=io.StringIO())
    other.eval(f"read_db -file {path}")
    assert "Connections : 2 pin(s) set by connect_pin or disconnect_pin" in out_of(other)
    for pin in ("d1/A", "sp_L1_inv1/A", "buf1/Y", "d2/A", "sp_L3_inv1/A", "sp_L3_inv2/A"):
        assert net(other, pin) == net(s, pin)
    assert net(other, "sp_L1_inv1/A") == "buf1_Y" and net(other, "sp_L3_inv1/A") == ""
    # and it goes on from there
    other.eval("disconnect_pin -pin buf1/Y")
    assert net(other, "d1/A") == "" and net(s, "d1/A") == "buf1_Y"


def test_read_db_of_schema_21(design, tmp_path):
    s = design
    path = tmp_path / "old.db"
    s.eval(f"write_db -file {path}")
    con = sqlite3.connect(path)                       # as written before connect_pin
    with con:
        con.execute("DROP TABLE connection")
        con.execute("UPDATE meta SET value = '21' WHERE key = 'schema_version'")
    con.close()
    other = Session(out=io.StringIO())
    other.eval(f"read_db -file {path}")
    assert "Connections" not in out_of(other)
    assert net(other, "sp_L1_inv1/A") == "net" and net(other, "sp_L2_inv1/A") == "sp_L1_inv1_Y"
    other.eval("connect_pin -from buf1/Y -to d1/A")
    assert net(other, "d1/A") == "buf1_Y"
    other.eval(f"write_db -file {tmp_path}/new.db")
    con = sqlite3.connect(tmp_path / "new.db")
    assert con.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0] == "22"
    assert con.execute("SELECT inst, pin, net, driver FROM connection").fetchall() == \
        [("d1", "A", "buf1_Y", "buf1/Y")]
    con.close()
