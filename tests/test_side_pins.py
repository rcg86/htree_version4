"""route_pin: a signal pin whose net comes from the left or the right gets no
strap; its H2 pin wire is extended to a free IA signal track, and route_net
brings its IA wire along that track onto the pin wire (an H2/IA crossing box
for the via). A pin whose net comes from above or below keeps its strap."""

import pytest

pytest.importorskip("scipy")

from test_copy_obj import ALL
from test_move_spine import build
from test_pin_access import chain  # noqa: F401  (a fixture)
from test_route_pin import out_of

pytestmark = pytest.mark.side_pins


def floats(text):
    return tuple(float(c) for c in text.split())


def spine(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True, rows=False)
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def test_a_pin_reached_from_the_side_gets_no_strap(tech_session, write_lef):
    s = spine(tech_session, write_lef)
    s.eval("route_pin -inst sp_L2_inv1")
    text = out_of(s)
    assert "pins reached from the side, on IA directly: Y (net sp_L2_inv1_Y from the right): " \
           "no strap, its pin wire on to IA y " in text
    y = float(text.split("its pin wire on to IA y ")[1].split()[0].rstrip(";"))
    wire = s.db.pin_wire_row("sp_L2_inv1", "Y")
    assert wire["strap"] is None
    x1, y1, x2, y2 = floats(wire["rect"])
    assert y1 <= y - 0.18 + 1e-6 and y + 0.18 <= y2 + 1e-6      # it reaches the track
    nets = int(text.split("Straps over inst:sp_L2_inv1 (INV_RP) on IA: ")[1].split()[0])
    assert len(s.db.strap_rows("sp_L2_inv1")) == nets - 1        # one strap fewer
    assert s.db.pin_wire_row("sp_L2_inv1", "A")["strap"] is not None   # A: from below
    # the track is clear of the cell's straps by the rule
    for r in s.db.strap_rows("sp_L2_inv1"):
        _, sy1, _, sy2 = floats(r["rect"])
        assert sy2 + 0.36 <= y - 0.18 + 1e-6 or y + 0.18 + 0.36 <= sy1 + 1e-6


def test_a_net_from_below_keeps_its_straps(chain):
    s = chain                            # c1 -> c2 -> c3 up one column
    s.eval("route_pin -inst {c1 c2 c3}")
    assert "reached from the side" not in out_of(s)
    assert all(w["strap"] is not None for w in s.db.pin_wire_rows("c2"))


def test_the_spine_routes_clean_with_side_pins(tech_session, write_lef):
    s = spine(tech_session, write_lef)
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    out_of(s)
    side = [w for w in s.db.pin_wire_rows() if w["strap"] is None]
    assert side
    s.eval(f"route_net -net {ALL} -rule r -shield")
    text = out_of(s)
    assert "HT4-174" not in text
    assert text.count("connected on its pin wire, along the track") == len(side)
    s.eval("route_final_stub -rule r -shield")
    assert "HT4-192" not in out_of(s)
    for w in side:                       # on the net now, an H2/IA box on the pin wire
        w = s.db.pin_wire_row(w["inst"], w["pin"])
        x1, _, x2, _ = floats(w["rect"])
        boxes = [floats(r["rect"]) for r in s.db.net_wire_rows(w["net"])
                 if r["kind"] == "cross" and r["layer"] == "H2/IA"]
        assert any(abs(b[0] - x1) < 1e-6 and abs(b[2] - x2) < 1e-6 for b in boxes), w["pin"]
    s.eval("check_drc")
    drc = out_of(s)
    assert "  open      signal  -       0" in drc and "  open      power   -       0" in drc
    # the only shorts: the two roots this test spine puts on one another
    shorts = [l for l in drc.splitlines() if l.startswith(("  IA {", "  H2 {"))]
    assert shorts and all("sp_L1_inv1" in l and "sp_mirror_L1_inv1" in l for l in shorts)


def test_no_way_out_keeps_the_strap(tech_session, write_lef):
    s = spine(tech_session, write_lef)
    s.eval("route_pin -inst sp_L3_inv1")
    out_of(s)
    # another net's wire all along the right of the cells: no way out to the right
    s.db.set_net_wires("wall", [("wire", "IA", "77.5 90 90 130")])
    s.eval("route_pin -inst sp_L2_inv1")
    text = out_of(s)
    assert "Y (net sp_L2_inv1_Y from the right): no IA signal track free from it out past " \
           "the cell's right edge, keeps its strap" in text
    assert s.db.pin_wire_row("sp_L2_inv1", "Y")["strap"] is not None


def test_a_stub_that_runs_past_the_leaf_keeps_its_strap(tech_session, write_lef):
    # the stub of a leaf runs up a vertical track just left of the leaf's Y pin: the
    # route comes along it from above or below, so Y keeps its strap (it is nearest
    # to the left only because the line is 1 um from the pin)
    from core import objects
    from core.commands.route_pin import _other_end
    s = spine(tech_session, write_lef)
    row = next(r for r in s.db.spine_stub_rows(s.db.spine_row("sp")["id"])
               if r["driver"] == "sp_L3_inv1")
    x1, _, _, _ = objects.inst_bbox(s.db, s.db.inst_row("sp_L3_inv1"))
    _, y = objects.pin_centre(s.db, "sp_L3_inv1", "Y")
    with s.db.conn:
        s.db.conn.execute("UPDATE spine_stub SET points = ? WHERE id = ?",
                          (f"{x1} {y - 300} {x1} {y + 300}", row["id"]))
    assert _other_end(s.db, "sp_L3_inv1", "Y") == (x1, y, "v")
    s.eval("route_pin -inst sp_L3_inv1")
    assert "Y (net sp_L3_inv1_Y" not in out_of(s)               # A: its driver is left
    assert s.db.pin_wire_row("sp_L3_inv1", "Y")["strap"] is not None
    # a stub that leaves along x, level with the pin: from the side
    with s.db.conn:
        s.db.conn.execute("UPDATE spine_stub SET points = ? WHERE id = ?",
                          (f"{x1 - 1} {y} {x1 - 300} {y}", row["id"]))
    s.eval("route_pin -inst sp_L3_inv1")
    assert "Y (net sp_L3_inv1_Y from the left)" in out_of(s)
