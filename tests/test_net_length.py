"""net .length: x + y from the driver of a net to its loads, a way two loads
share counted once; net / spine_net .route_length: the lengths of the net's
signal wires added up."""

import pytest

pytest.importorskip("scipy")

from core import objects
from test_add_buffer_on_net import ported, routed_port  # noqa: F401  (fixtures)
from test_route_pin import out_of


def far(s, a, b):
    (ax, ay), (bx, by) = (objects.pin_centre(s.db, *p.split("/")) for p in (a, b))
    return abs(ax - bx) + abs(ay - by)


def test_length_of_one_load_is_x_plus_y(ported):
    s = ported
    s.eval("create_inst -name b1 -ref_cell INV_RP -location {100 20}")
    s.eval("create_inst -name e1 -ref_cell INV_RP -location {300 120}")
    s.eval("connect_pin -from b1/Y -to e1/A")
    out_of(s)
    assert float(s.eval("get_db net:b1_Y .length")) == pytest.approx(far(s, "b1/Y", "e1/A"))
    assert float(s.eval("get_db net:b1_Y .route_length")) == 0      # not routed


def test_length_counts_a_shared_way_once(ported):
    # two loads side by side far away: one trunk out to them, then a short branch each
    s = ported
    s.eval("create_inst -name b1 -ref_cell INV_RP -location {100 20}")
    s.eval("create_inst -name e1 -ref_cell INV_RP -location {300 120}")
    s.eval("create_inst -name e2 -ref_cell INV_RP -location {300 140}")
    s.eval("connect_pin -from b1/Y -to {e1/A e2/A}")
    out_of(s)
    length = float(s.eval("get_db net:b1_Y .length"))
    one, two = far(s, "b1/Y", "e1/A"), far(s, "b1/Y", "e2/A")
    assert length == pytest.approx(max(one, two))         # e1 is on the way to e2
    assert length < one + two


def test_route_length_adds_up_the_wires(routed_port):
    s = routed_port
    wires = [float(v) for v in s.split_list(
        s.eval("get_db [get_db net:clk_in .net_wires -if {.kind == wire}] .length"))]
    assert wires
    assert float(s.eval("get_db net:clk_in .route_length")) == pytest.approx(sum(wires))
    assert s.eval("get_db net:clk_in .length") != ""
    # a spine net: its wires and its stub's
    net = "spine_net:sp/sp_L1_inv1_Y"
    assert float(s.eval(f"get_db {net} .route_length")) == 0
    s.eval("route_net -net sp_L1_inv1_Y -rule r")
    out_of(s)
    wires = [float(v) for v in s.split_list(
        s.eval(f"get_db [get_db {net} .net_wires -if {{.kind == wire}}] .length"))]
    assert sum(wires) > 0
    assert float(s.eval(f"get_db {net} .route_length")) == pytest.approx(sum(wires))
    # an input port with no load on its net: no length
    assert s.eval("get_db net:idle .length") == ""
