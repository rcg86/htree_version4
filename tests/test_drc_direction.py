"""check_drc: the routing direction of the cells. A cell whose signal pins
are reached both vertically and horizontally (heterogeneous routing
direction), and a pin reached against the routing_direction of its cell's
pin spec."""

import pytest

pytest.importorskip("scipy")

from core import drc
from test_route_pin import out_of
from test_vias import routed, via_session  # noqa: F401  (fixtures)


JOG = 5       # the test spine is small: its nets are 7 .. 22 um long


def lines(s, title, jog=JOG):
    s.eval(f"check_drc -direction_jog {jog}")
    text = out_of(s).splitlines()
    k = next((i for i, l in enumerate(text) if l.startswith(title)), None)
    if k is None:
        return [], text
    n = int(text[k].rsplit(":", 1)[1])
    return text[k + 1:k + 1 + n], text


def test_a_cell_routed_one_way_is_clean(routed):
    # the test spine: every net comes onto the straps from above or below
    s = routed
    assert {h for pins in drc.pin_directions(s.db, JOG).values() for h, _, _ in pins.values()} == \
        {"vertical"}
    found, text = lines(s, "Routing direction")
    assert found == []
    assert "  direction mixed   -       0" in text and "  direction spec    -       0" in text


def test_a_cell_reached_both_ways_is_reported(routed):
    # sp_L2_inv1's Y net made to drop onto its strap from within the strap stack and leave
    # along IA to the right: Y horizontal, its A still from below: both ways
    s = routed
    net = "sp_L2_inv1_Y"
    seq = s.db.pin_wire_row("sp_L2_inv1", "Y")["strap"]
    x1, y1, x2, y2 = map(float, s.db.strap_row("sp_L2_inv1", seq)["rect"].split())
    tap = [float(c) for c in next(r["rect"] for r in s.db.net_wire_rows(net)
                                  if r["kind"] == "wire" and r["layer"] == "IB").split()]
    s.db.set_net_wires(net, [("wire", "IB", f"{tap[0]} {y1} {tap[2]} {y2}", None),
                             ("wire", "IA", f"{tap[0]} {y1} {tap[2] + 30} {y2}", None)])
    pins = drc.pin_directions(s.db, JOG)["sp_L2_inv1"]
    assert (pins["A"][0], pins["Y"][0]) == ("vertical", "horizontal")
    found, text = lines(s, "Routing direction, heterogeneous")
    assert len(found) == 1 and "cell sp_L2_inv1: its pins are reached both ways " \
        "(heterogeneous routing direction; one needs vertical routing, one horizontal): " \
        "A vertical, Y horizontal" in found[0]
    assert "  direction mixed   -       1" in text


def test_a_pin_reached_against_its_spec(routed):
    s = routed
    from core.commands.route_pin import DEFAULTS
    s.db.set_pin_spec("sp_L2_inv1", dict(DEFAULTS, routing_direction="horizontal"), "h_spec")
    found, _ = lines(s, "Routing direction, against")
    box = drc.box_text(_box(s, "sp_L2_inv1"))
    assert found == [f"  {box}  cell sp_L2_inv1 (pin spec h_spec, routing_direction "
                     f"horizontal): A reached vertical, Y reached vertical"]


def _box(s, inst):
    from core import objects
    return objects.inst_bbox(s.db, s.db.inst_row(inst))


def test_a_jog_shorter_than_direction_jog_is_passed_over(routed):
    # the same Y made horizontal by a 30 um IA run: with -direction_jog 40 that run is a
    # jog too, so Y has no way of its own and the cell is not reported
    s = routed
    net = "sp_L2_inv1_Y"
    seq = s.db.pin_wire_row("sp_L2_inv1", "Y")["strap"]
    x1, y1, x2, y2 = map(float, s.db.strap_row("sp_L2_inv1", seq)["rect"].split())
    tap = [float(c) for c in next(r["rect"] for r in s.db.net_wire_rows(net)
                                  if r["kind"] == "wire" and r["layer"] == "IB").split()]
    s.db.set_net_wires(net, [("wire", "IB", f"{tap[0]} {y1} {tap[2]} {y2}", None),
                             ("wire", "IA", f"{tap[0]} {y1} {tap[2] + 30} {y2}", None)])
    assert drc.pin_directions(s.db, 5)["sp_L2_inv1"]["Y"][0] == "horizontal"
    assert "Y" not in drc.pin_directions(s.db, 40).get("sp_L2_inv1", {})
    found, _ = lines(s, "Routing direction, heterogeneous", jog=40)
    assert found == []
    assert "-direction_jog must be" in _err(s, "check_drc -direction_jog -1")


def _err(s, script):
    import tkinter
    with pytest.raises(tkinter.TclError) as exc:
        s.eval(script)
    return str(exc.value)
