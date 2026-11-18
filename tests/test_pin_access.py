"""Pin access for a signal that runs straight through a cell: legalize_placement
turns the cell (N or FS) so its input pin faces the incoming net, route_pin
gives the higher pin the higher strap, and route_net takes each signal strap
from its outer side and keeps the track the cell is crossed on, so the net
coming in and the net going out pass the cell on one track."""

from types import SimpleNamespace

import pytest

pytest.importorskip("scipy")

from core.commands.route_net import H, KEEP, Terminal, V, _flow_order
from test_move_spine import build
from test_route_net import err, out_of


@pytest.fixture
def chain(tech_session, write_lef):
    """Three INV_RP cells up one column at x 88, built FS, c1 -> c2 -> c3.
    In INV_RP the Y pin is a little higher than A in N (0.004 um), lower in
    FS: an upward signal wants N."""
    s = build(tech_session, write_lef, mirror=True)
    for k, y in ((1, 140), (2, 160), (3, 180)):
        s.eval(f"create_inst -name c{k} -ref_cell INV_RP -location {{88 {y}}} -orient FS")
    s.eval("connect_pin -from c1/Y -to c2/A")
    s.eval("connect_pin -from c2/Y -to c3/A")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def ib(s, net):
    return [w["rect"] for w in s.db.net_wire_rows(net) if w["kind"] == "wire"
            and w["layer"] == "IB"]


def test_legalize_turns_the_cell_to_face_its_input(chain):
    s = chain
    s.eval("route_pin -inst c2")
    assert s.db.strap_rows("c2")
    s.eval("legalize_placement -inst {c1 c2 c3}")
    text = out_of(s)
    assert "  2 instance(s) turned so the input pin faces the incoming net (their pin routes " \
           "removed): c2 FS -> N, c3 FS -> N; route_pin -inst {c2 c3}" in text
    assert [s.db.inst_row(n)["orient"] for n in ("c1", "c2", "c3")] == ["FS", "N", "N"]
    assert not s.db.strap_rows("c2")          # upside down: made again by route_pin
    # c1 has no driver: the way its signal comes cannot be told; the others face it now
    s.eval("legalize_placement -inst {c1 c2 c3}")
    assert "turned" not in out_of(s)


def test_keep_orientation(chain):
    s = chain
    s.eval("legalize_placement -inst {c1 c2 c3} -keep_orientation")
    assert "turned" not in out_of(s)
    assert s.db.inst_row("c2")["orient"] == "FS"


def test_route_pin_gives_the_higher_pin_the_higher_strap(chain):
    s = chain
    s.eval("route_pin -inst {c1 c2}")       # c1 FS, then c2 turned to N
    s.db.set_inst_orient("c2", "N")
    s.eval("route_pin -inst c2")
    out_of(s)
    straps = lambda inst: {p: s.db.pin_wire_row(inst, p)["strap"] for p in ("A", "Y")}
    assert straps("c2") == {"A": 5, "Y": 3}       # N: Y higher, the higher strap (3)
    assert straps("c1") == {"A": 3, "Y": 5}       # FS: A higher


def test_both_nets_pass_the_cell_on_one_track(chain):
    s = chain
    s.eval("legalize_placement -inst {c1 c2 c3}")
    s.eval("route_pin -inst {c1 c2 c3}")
    out_of(s)
    for order in ("{c2_Y c1_Y}", "{c1_Y c2_Y}"):
        s.eval(f"route_net -net {order} -rule r")
        text = out_of(s)
        assert "load c2/A (strap 5): connected across the strap (its pin route, extended 2.86 " \
               "left and 0.14 right) at {85.32 157.32}" in text
        assert "driver c2/Y (strap 3): connected across the strap (its pin route, extended " \
               "2.86 left and 0.14 right) at {85.32 163.08}" in text
        # c1_Y stops under c2's A strap, c2_Y starts over its Y strap: 2.16 apart
        assert ib(s, "c1_Y") == ["85.14 139.551 85.5 159.829"]
        assert ib(s, "c2_Y") == ["85.14 161.989 85.5 181.165"]   # c3 faces it too
    s.eval("check_drc")
    assert not [l for l in out_of(s).splitlines() if ("c1_Y" in l or "c2_Y" in l) and "{" in l]


def test_a_strap_is_reached_from_its_outer_side_too():
    """The nearest track, and the one on the outer side (away from the cell's
    other signal strap) dearer by its longer drop; off the track the cell is
    crossed on, KEEP pitches dearer."""
    lay = SimpleNamespace(width=0.36, spacing=0.36)
    xs, ys = [0.0, 2.88, 5.76], [0.0, 2.88, 5.76]
    t = Terminal("strap", "a", (0, 3.4, 6, 3.8), strap=(0, 3.4, 6, 3.8), strap_layer="IA")
    t.outer = 1                                  # the other strap is below: outer is up
    nodes = t.nodes(xs, ys, lay, lay, [])
    assert nodes[(V, 1, 1)] == 0.0                         # 2.88: 0.72 under the centre
    assert nodes[(V, 1, 2)] == pytest.approx(2.16 - 0.72)  # 5.76: 2.16 over it
    t.outer = -1                                 # outer is down: the nearest only
    # (x 0 is the strap's end: no room for half a wire on it)
    assert set(t.nodes(xs, ys, lay, lay, [])) == {(V, 1, 1), (V, 2, 1)}
    t.outer, t.keep_x = 1, 2.88
    nodes = t.nodes(xs, ys, lay, lay, [])
    assert nodes[(V, 1, 1)] == 0.0 and nodes[(V, 2, 1)] == pytest.approx(KEEP * 2.88)


def test_nets_are_routed_the_way_the_signal_runs():
    spine = {"id": 1}
    row = lambda name, driver, loads: {"name": name, "driver": driver, "loads": loads}
    nets = [(spine, row("n3", "c3", "c4")), (spine, row("n1", "c1", "c2")),
            (spine, row("n2", "c2", "c3")), (None, {"name": "p", "driver": "x", "loads": ""})]
    assert [r["name"] for _, r in _flow_order(nets)] == ["n1", "n2", "n3", "p"]


def test_legalize_reports_pins_that_cannot_be_reached(chain):
    s = chain
    s.eval("route_pin -inst {c1 c2 c3}")
    s.eval("legalize_placement -inst {c1 c2 c3} -keep_orientation")
    assert "legalize_placement: pin access: every signal pin of the 3 instance(s) has a " \
           "track to be reached on" in out_of(s)
    # another net's wires over every signal track c2's straps reach (x 82.44 .. 91.08)
    s.db.set_net_wires("blk", [("wire", "IB", f"{x - 0.18:.2f} 150 {x + 0.18:.2f} 170")
                               for x in (82.44, 85.32, 88.2, 91.08)])
    s.eval("legalize_placement -inst {c1 c2 c3} -keep_orientation")
    text = out_of(s)
    assert "**WARN: (HT4-288): legalize_placement: 2 signal pin(s) with no track route_net " \
           "can reach them on" in text
    for pin in ("c2/A", "c2/Y"):
        line = next(l for l in text.splitlines() if l.startswith(f"    {pin} (strap"))
        assert "x 85.32 taken by blk" in line and "x 88.2 taken by blk" in line
    # the nets of cells legalize moved are routed again: their wires are not in the way
    from core import pin_access
    assert pin_access.check(s.db, ["c2"], ignore={"blk"}) == []


def test_a_track_outside_the_design_is_named(chain):
    """Above y 40 the die starts at x 60: e1 at x 60.2 reaches x 57.2 .. 66.32
    with its straps, the track 59.4 is outside it; 62.28 and 65.16 taken."""
    s = chain
    s.eval("create_inst -name e1 -ref_cell INV_RP -location {60.2 150}")
    s.eval("connect_pin -from c1/Y -to e1/A")
    s.eval("route_pin -inst e1")
    out_of(s)
    from core import pin_access
    assert pin_access.check(s.db, ["e1"]) == []
    s.db.set_net_wires("blk", [("wire", "IB", f"{x - 0.18:.2f} 140 {x + 0.18:.2f} 160")
                               for x in (62.28, 65.16)])
    rows = {(i, p): why for i, p, _, why in pin_access.check(s.db, ["e1"])}
    assert rows[("e1", "A")] == [(59.4, "outside the design"), (62.28, "taken by blk"),
                                 (65.16, "taken by blk")]
