"""connect_pin with output ports in -to: each driven through a buffer of
-ref_cell, its output pin -distance um (default 10) from the port towards
the driver; its input on the driver's net, its output on the port's."""

import pytest

pytest.importorskip("scipy")

from core import objects
from test_connect_spine import lst, ported  # noqa: F401  (a fixture)
from test_route_pin import err, out_of


def from_port(s, inst, pin, port):
    px, py = objects.pin_centre(s.db, inst, pin)
    ax, ay = objects.port_centre(s.db, port)
    return abs(px - ax) + abs(py - ay)


def test_port_to_port_gets_a_buffer(ported):
    s = ported
    made = lst(s, "connect_pin -from [get_db ports clk] -to [get_db ports q] -ref_cell INV_RP")
    text = out_of(s)
    assert made == ["inst:buf_q"]
    assert "connect_pin: net clk: port clk -> buf_q/A" in text
    assert "port q: buf_q (INV_RP) at {" in text and "buf_q/Y -> net q_net" in text
    assert "route_net -net {clk q_net}" in text
    # the input on the port's net, the output drives the other port
    assert s.eval("get_db pin:buf_q/A .net") == "net:clk"
    assert s.eval("get_db net:q_net .driver") == "pin:buf_q/Y"
    # 10 um from the port q, on the way to clk (to the left of q)
    assert from_port(s, "buf_q", "Y", "q") == pytest.approx(10, abs=0.01)
    assert objects.pin_centre(s.db, "buf_q", "Y")[0] < objects.port_centre(s.db, "q")[0]
    got = s.split_list(s.eval("all_fanout -from clk -to [get_db ports q]"))
    assert [list(s.split_list(p)) for p in got] == [["port q", "0", "1"]]


def test_ports_and_pins_with_distance_and_name(ported):
    s = ported
    s.eval("create_inst -name d1 -ref_cell INV_RP -location {-50 10}")
    out_of(s)
    made = lst(s, "connect_pin -from clk -to {d1/A top near} -ref_cell INV_RP -distance 25 "
                  "-name fd")
    assert made == ["pin:d1/A", "inst:fd_top", "inst:fd_near"]
    for b, port in (("fd_top", "top"), ("fd_near", "near")):
        assert from_port(s, b, "Y", port) == pytest.approx(25, abs=0.01)
        assert s.eval(f"get_db pin:{b}/A .net") == "net:clk"
    # a pin as -from: the same
    s.eval("create_inst -name d2 -ref_cell INV_RP -location {50 -20}")
    out_of(s)
    assert lst(s, "connect_pin -from d2/Y -to {d[3]} -ref_cell INV_RP") == ["inst:buf_d_3"]
    assert s.eval("get_db pin:buf_d_3/A .net") == "net:d2_Y"


def test_a_driven_port_and_errors(ported):
    s = ported
    s.eval("connect_pin -from clk -to q -ref_cell INV_RP")
    out_of(s)
    insts = lst(s, "get_db insts")
    assert "-ref_cell <lib_cell>" in err(s, "connect_pin -from clk -to top")
    assert "HT4-308" in err(s, "connect_pin -from clk -to q -ref_cell INV_RP")   # driven
    assert "HT4-308" in err(s, "connect_pin -from clk -to nowhere -ref_cell INV_RP")
    assert "HT4-257" in err(s, "connect_pin -from clk -to top -ref_cell NOPE")
    assert "connect_pin: lib cell" in err(s, "connect_pin -from clk -to top -ref_cell NOPE")
    assert "-distance must be" in err(s, "connect_pin -from clk -to top -ref_cell INV_RP "
                                         "-distance 0")
    assert "-name" in err(s, "connect_pin -from clk -to top -ref_cell INV_RP -name a/b")
    assert "HT4-251" in err(s, "connect_pin -from clk -to clk -ref_cell INV_RP")  # an input
    assert lst(s, "get_db insts") == insts                         # nothing made
    # -disconnect: the port's driver taken off, a new buffer drives it
    assert lst(s, "connect_pin -from clk -to q -ref_cell INV_RP -disconnect") == \
        ["inst:buf_q_2"]
    assert "buf_q_2/Y -> net q_net (taken off buf_q/Y)" in out_of(s)
    assert s.eval("get_db net:q_net .driver") == "pin:buf_q_2/Y"


def test_one_driver_to_many_ports_by_a_list(ported):
    # get_db ports {a b c}: a Tcl list of names or patterns, each matched in turn
    s = ported
    assert s.eval("get_db ports {top q}") == "port:t/top port:t/q"
    assert s.eval("get_db ports {q to* q}") == "port:t/q port:t/top"    # each once
    assert s.eval("get_db ports q") == "port:t/q"                       # one, as before
    made = lst(s, "connect_pin -from [get_db ports {clk}] -to [get_db ports {q top near}] "
                  "-ref_cell INV_RP")
    assert made == ["inst:buf_q", "inst:buf_top", "inst:buf_near"]
    for port, buf in (("q_net", "buf_q"), ("top", "buf_top"), ("near", "buf_near")):
        assert s.eval(f"get_db net:{port} .driver") == f"pin:{buf}/Y"
        assert s.eval(f"get_db pin:{buf}/A .net") == "net:clk"
    # a get_db that matched nothing: said so
    assert "-to is empty" in err(s, "connect_pin -from clk -to [get_db ports {nothing}] "
                                    "-ref_cell INV_RP")
