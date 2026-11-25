"""route_pin inserts the vias of its pin routes: insert_vias from the pin
wire layer to the strap layer (H2 to IA) over the instances it routed, so a
pin wire is joined to every strap of its net it crosses (a power pin wire to
both straps of its net)."""

import pytest

pytest.importorskip("scipy")

from core import vias
from test_route_net import DEF, SPEC, def_block, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import CELL_LEF, out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import via_session  # noqa: F401  (a fixture: the tech with via definitions)

pytestmark = pytest.mark.pin_vias


def build(s, write_lef):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def inserted(s, inst=None):
    """The insert_vias vias (kind insert) on the pin wires and straps of inst."""
    return [r for r in vias.rows(s.db) if r["kind"] == "insert"
            and (inst is None or f":{inst}/" in (r["source"] or ""))]


def test_route_pin_inserts_the_vias_of_its_pin_routes(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_L1_inv1")
    text = out_of(s)
    assert "route_pin: insert_vias -bottom_layer H2 -top_layer IA over the instance(s): " in text
    made = int(text.split("over the instance(s): ")[1].split()[0])
    assert made > 0
    got = inserted(s)
    assert got and {(r["bottom"], r["top"]) for r in got} <= {("H2", "G1"), ("G1", "G2"),
                                                            ("G2", "IA")}
    # only over the instance routed: the others have none
    s.eval("route_pin -inst sp_L2_inv1")
    out_of(s)
    assert not [r for r in inserted(s) if "sp_L3_" in (r["source"] or "")]
    # each a crossing of a pin wire and a strap of its net (a power pin wire: both straps)
    for r in got:
        assert r["net"] in ("VDD_SOC", "VSS", "SIGNAL") or r["net"].startswith("sp_")
    # again: nothing more
    before = len(inserted(s))
    s.eval("route_pin -inst sp_L1_inv1")
    text = out_of(s)
    assert len(inserted(s)) == before


def test_routed_vias_get_definitions_and_are_written(via_session, write_lef, tmp_path):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    power = [r for r in inserted(s) if r["net"] in ("VDD_SOC", "VSS")]
    assert power and all(r["via_def"] for r in power)       # route_pin / route_net gave them
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    text = (tmp_path / "o.def").read_text()
    for net in ("VSS", "VDD_SOC"):
        mine = [r for r in vias.rows(s.db, net) if r["via_def"]]
        assert sum(1 for line in def_block(text, net) if " 0 ( " in line) == len(mine)


def test_power_straps_joined_and_deleting_a_strap_takes_its_vias(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_L1_inv1")
    out_of(s)
    mine = inserted(s, "sp_L1_inv1")
    assert mine
    strap = next(r["source"] for r in mine if r["source"].startswith("net_wire:auto_via:"))
    owner = strap.split("auto_via:", 1)[1].rsplit("/", 1)[0]        # e.g. strap:sp_L1_inv1/1
    s.eval(f"delete_wire -wires {owner}")
    out_of(s)
    assert not [r for r in inserted(s) if owner in (r["source"] or "")]
