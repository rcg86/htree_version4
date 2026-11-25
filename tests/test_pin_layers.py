"""route_pin: an H1 piece under each pin wire, the cell's height, so the vias
from the D12 pin up to the H2 pin wire land on H1 metal."""

import pytest

pytest.importorskip("scipy")

from core import vias
from test_pin_spec_names import HORIZONTAL
from test_route_pin import CELL_LEF, out_of
from test_route_pin import DEF as PIN_DEF
from test_vias import routed, via_session  # noqa: F401  (fixtures: the via tech, D12 too)

HEIGHT = 1.778                           # INV_RP: SIZE 3.12 BY 1.778, u1 at {0 0}


@pytest.fixture
def placed(via_session, write_lef):
    s = via_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(PIN_DEF, 'd.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    out_of(s)
    return s


def pieces(s, inst="u1"):
    """{pin: (layer, rect, net)} of route_pin's pieces under the pin wires of inst."""
    wires = {tuple(float(c) for c in w["rect"].split())[::2]: w["pin"]
             for w in s.db.pin_wire_rows(inst)}
    out = {}
    for r in s.db.net_wire_rows(f"pg:{inst}"):
        if r["kind"] == "pin_layer":
            rect = tuple(float(c) for c in r["rect"].split())
            out[wires[rect[::2]]] = (r["layer"], rect, r["shield_net"])
    return out


def test_an_h1_piece_under_each_pin_wire_the_cell_height(placed):
    s = placed
    s.eval("route_pin -inst u1")
    text = out_of(s)
    assert "H1 under each of the 4 pin wire(s), the cell's height (y 0 .. 1.778): H1 between " \
           "D12 and H2" in text
    got = pieces(s)
    assert set(got) == {"VDD", "VSS", "A", "Y"}
    for w in s.db.pin_wire_rows("u1"):
        x1, _, x2, _ = (float(c) for c in w["rect"].split())
        # as wide as the pin wire, from the bottom of the cell to its top, on the pin's net
        assert got[w["pin"]] == ("H1", (x1, 0.0, x2, HEIGHT), w["net"])
    # the pin stack's H1 pads lie on it (H1 is metal of the net there now)
    metal = vias.net_shapes(s.db)
    for v in vias.rows(s.db):
        if v["source"].startswith("pin_wire:u1/") and v["via_def"] and \
                "H1" in (v["bottom"], v["top"]) and v["net"] != "SIGNAL":
            assert vias.fits(vias.definition_shapes(s.db, v["via_def"]), metal[v["net"]],
                             v["bottom"], v["cut"], v["top"], v["x"], v["y"])


def test_routed_again_they_are_made_again(placed):
    s = placed
    s.eval("route_pin -inst u1")
    first = pieces(s)
    s.eval("route_pin -inst u1")
    # one each, not two: the old ones went with the old pin wires
    assert len([r for r in s.db.net_wire_rows("pg:u1") if r["kind"] == "pin_layer"]) == 4
    assert pieces(s) == first


def test_without_straps_too(placed, write_lef):
    s = placed
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("route_pin -inst u1 -spec_name horizontal_routing")
    assert s.db.strap_rows("u1") == []
    got = pieces(s)
    assert set(got) == {w["pin"] for w in s.db.pin_wire_rows("u1")} and got
    assert all(rect[1:4:2] == (0.0, HEIGHT) for _, rect, _ in got.values())


def test_optimize_pg_connection_keeps_them(routed):
    s = routed                                  # tests/test_vias.py: a spine on the via tech
    s.eval("route_net -net [get_db nets .name] -rule r -shield")
    out_of(s)
    insts = list(s.split_list(s.eval("get_db insts .name")))
    before = {i: pieces(s, i) for i in insts}
    assert all(len(p) == 4 for p in before.values())
    s.eval("optimize_pg_connection -inst [get_db insts] -extend 3")
    assert "new power connection(s)" in out_of(s)
    assert [r for i in insts for r in s.db.net_wire_rows(f"pg:{i}")
            if r["kind"] != "pin_layer"]                         # its own pieces are there
    assert {i: pieces(s, i) for i in insts} == before
    s.eval("optimize_pg_connection -inst [get_db insts] -extend 3")       # again
    assert {i: pieces(s, i) for i in insts} == before


def test_write_def_writes_them_on_the_pins_nets(placed, tmp_path):
    s = placed
    s.eval("route_pin -inst u1")
    got = pieces(s)
    s.eval(f"write_def -output {tmp_path / 'p.def'}")
    text = (tmp_path / "p.def").read_text()
    units = int(text.split("UNITS DISTANCE MICRONS ")[1].split()[0])
    dbu = lambda v: int(round(v * units))                         # noqa: E731
    for pin in ("VDD", "VSS"):                       # power: + ROUTED on the power net
        _, (x1, y1, x2, y2), net = got[pin]
        block = text[text.index(f"- {net}"):]
        block = block[:block.index("\n- ")] if "\n- " in block else block
        assert f"+ RECT H1 ( {dbu(x1)} {dbu(y1)} ) ( {dbu(x2)} {dbu(y2)} )" in block


def test_a_copied_spine_s_pieces_are_on_the_copy_s_nets(routed):
    s = routed
    s.eval("copy_obj -from sp -name cp -x_shift 40")
    out_of(s)
    nets = {r["shield_net"] for i in s.split_list(s.eval("get_db [get_db insts cp_*] .name"))
            for r in s.db.net_wire_rows(f"pg:{i}") if r["kind"] == "pin_layer"}
    # the copy's root input on the copy's root net, as its pin wire (no sp_ net on it)
    assert "cp_primary_input" in nets and not [n for n in nets if n.startswith("sp_")]
    for i in s.split_list(s.eval("get_db [get_db insts cp_*] .name")):
        got = pieces(s, i)
        assert {p: net for p, (_, _, net) in got.items()} == \
            {w["pin"]: w["net"] for w in s.db.pin_wire_rows(i)}
    s.eval("check_drc -check_shorts_only")
    text = out_of(s)
    assert not [l for l in text.splitlines() if "sp_" in l and "cp_" in l]


def test_a_pin_moved_to_another_net_takes_its_pieces_along(routed):
    # the root input sp_L1_inv1/A, routed on sp_primary_input, put on the net of a new
    # driver u1 (connect_pin): once route_net names its pin wire, its H1 piece and the
    # vias inserted on its pin wire are on that net too: no short with them
    s = routed
    s.eval("create_inst -ref_cell INV_RP -location {-20 0} -name u1")
    s.eval("route_pin -inst u1")
    s.eval("insert_vias -bottom_layer D12 -top_layer H2 -nets sp_primary_input")
    out_of(s)
    a = pieces(s, "sp_L1_inv1")["A"]
    assert a[2] == "sp_primary_input"
    s.eval("connect_pin -from u1/Y -to sp_L1_inv1/A -disconnect")
    net = s.eval("get_db pin:sp_L1_inv1/A .net.name")
    s.eval(f"route_net -net {net} -rule r")
    out_of(s)
    assert s.db.pin_wire_row("sp_L1_inv1", "A")["net"] == net
    assert pieces(s, "sp_L1_inv1")["A"][2] == net
    inserted = [r["shield_net"] for r in s.db.net_wire_rows()
                if r["net"] == "auto_via:pin_wire:sp_L1_inv1/A"]
    assert inserted and set(inserted) == {net}
    s.eval("check_drc -check_shorts_only")
    assert not [l for l in out_of(s).splitlines() if "sp_primary_input" in l and net in l]
