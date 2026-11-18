"""The routing commands give the vias their definitions: route_pin, route_net,
route_track and route_final_stub assign each net, per layer pair it has a via
on and no assignment for, the definition that fits the most of its vias
(vias.auto_assign), so write_def writes every via."""

import pytest

pytest.importorskip("scipy")

from core import vias
from test_route_net import DEF, SPEC, def_block, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import CELL_LEF, out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import via_session  # noqa: F401  (a fixture: the tech with via definitions)


def build(s, write_lef):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    return s


def assigned(s):
    return {(r["bottom"], r["top"], r["net"]): r["via_def"] for r in s.db.via_assignment_rows()}


def test_each_command_assigns_its_vias(via_session, write_lef, tmp_path):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    text = out_of(s)
    assert "route_pin: via definitions given to" in text
    assert ("D12", "H1", "VSS") in assigned(s)                   # the power pins' vias
    s.eval("route_net -net [get_db nets .name] -rule r")
    assert "route_net: via definitions given to" in out_of(s)
    assert assigned(s)[("IA", "IB", "sp_L1_inv1_Y")] in ("V_IA_IB", "V_IA_IB_2")
    s.eval("route_final_stub -rule r")
    out_of(s)
    rows = [r for r in vias.rows(s.db) if r["net"] != "SIGNAL"]
    assert rows and all(r["via_def"] for r in rows)          # every via has its definition
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    assert "HT4-183" not in out_of(s)
    text = (tmp_path / "o.def").read_text()
    for net in {r["net"] for r in rows}:                       # all of them written
        block = def_block(text, net)
        mine = [r for r in rows if r["net"] == net]
        assert sum(1 for line in block if " 0 ( " in line) == len(mine)
    # routed again: nothing more to assign, nothing printed
    s.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert "via definitions given" not in out_of(s)


def test_route_track_assigns_too(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("assign_via_for_route -reset")
    s.eval("route_track -net [get_db nets .name] -rule r")
    assert "route_track: via definitions given to" in out_of(s)
    assert ("IA", "IB", "sp_L1_inv1_Y") in assigned(s)


def test_the_choice_fits_and_an_assignment_by_hand_stays(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("assign_via_for_route -via V_IA_IB_2")               # for every net, by hand
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    a = assigned(s)
    assert a[("IA", "IB", "")] == "V_IA_IB_2"
    assert not [k for k in a if k[:2] == ("IA", "IB") and k[2]]     # no net's own over it
    # each net's choice fits the most of its vias of the pair
    metal = vias.net_shapes(s.db)
    for (bottom, top, net), name in a.items():
        if not net:
            continue
        mine = [r for r in vias.rows(s.db, net) if (r["bottom"], r["top"]) == (bottom, top)]
        fit = lambda n: sum(vias.fits(vias.definition_shapes(s.db, n), metal.get(net, {}),
                                      r["bottom"], r["cut"], r["top"], r["x"], r["y"])
                            for r in mine)
        others = [n for n, st in vias.definition_layers(s.db).items()
                  if st[0] == bottom and st[2] == top]
        assert fit(name) == max(fit(n) for n in others) == len(mine)


def test_fits():
    # an IA wire (horizontal) across an IB wire (vertical), 0.36 wide, crossing at 0..0.36
    metal = {"IA": [(-5, 0, 5, 0.36)], "IB": [(0, -5, 0.36, 5)]}
    on = lambda shapes: vias.fits(shapes, metal, "IA", "C6", "IB", 0.18, 0.18)
    small = [("IA", "RECT", [-0.25, -0.15, 0.25, 0.15]), ("C6", "RECT", [-0.1, -0.1, 0.1, 0.1]),
             ("IB", "RECT", [-0.15, -0.25, 0.15, 0.25])]
    assert on(small)                             # each pad runs on along its wire
    assert not on([("IA", "RECT", [-0.15, -0.25, 0.15, 0.25])] + small[1:])  # off the IA wire
    assert not on([small[0], ("C6", "RECT", [-0.3, -0.1, 0.3, 0.1]), small[2]])  # cut past IB
    # a pin: a short shape; a pad longer than it does not fit, on two shapes it does
    pin = {"IA": [(0, 0, 0.4, 0.36)], "IB": [(0, -5, 0.36, 5)]}
    long_pad = [("IA", "RECT", [-0.15, -0.15, 0.3, 0.15])] + small[1:]   # x 0.03 .. 0.48
    assert not vias.fits(long_pad, pin, "IA", "C6", "IB", 0.18, 0.18)
    pin["IA"].append((0.35, 0, 0.6, 0.36))
    assert vias.fits(long_pad, pin, "IA", "C6", "IB", 0.18, 0.18)
    # the inside of a stack: no metal of the net on the layer, not looked at
    assert vias.fits([("G2", "RECT", [-1, -1, 1, 1])] + small, metal, "IA", "C6", "IB", 0.18,
                     0.18)
    assert vias.fits([("G2", "RECT", [-1, -1, 1, 1])], {}, "G1", "T1", "G2", 0, 0)
