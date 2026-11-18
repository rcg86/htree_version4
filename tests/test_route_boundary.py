"""The design boundary is a hard limit of route_net and route_final_stub: no
wire, crossing box, extension or shield is stored outside it."""

import random

import pytest

pytest.importorskip("scipy")

from core.commands.route_net import H, V, Fence, Inside, Layer, _lee
from core.messages import HtreeError
from core.placement import point_in_polygon
from test_move_spine import DEF, LEF, PATTERN, ROWS, SPEC, build
from test_route_net import _floats, out_of

# The die of test_move_spine (a channel x 60 .. 100 up to y 200, a band y 0 ..
# 40 from x 0) with a slot cut into the channel from the left: x 60 .. 81,
# y 119.4 .. 120.6, between the cells of sp_L2_inv1 (y 108.6) and sp_L3_inv2
# (y 129.6) and between the two stubs (100 .. 119 and 121 .. 140).
L_DIE = [0, 0, 100, 0, 100, 200, 60, 200, 60, 40, 0, 40]
SLOT_DIE = [0, 0, 100, 0, 100, 200, 60, 200, 60, 120.6, 81, 120.6, 81, 119.4, 60, 119.4,
            60, 40, 0, 40]
# Two arms x 0 .. 10 and 20 .. 30 up to y 30 on a base y 0 .. 10.
U_DIE = [0, 0, 30, 0, 30, 30, 20, 30, 20, 10, 10, 10, 10, 30, 0, 30]


def within(rect, polygon):
    """True when the rect is inside a rectilinear polygon: the centre of every
    cell the polygon's and the rect's coordinates cut it into is. (Not the
    router's own check.)"""
    x1, y1, x2, y2 = rect
    xs = sorted({x1, x2} | {x for x in polygon[0::2] if x1 < x < x2})
    ys = sorted({y1, y2} | {y for y in polygon[1::2] if y1 < y < y2})
    return all(point_in_polygon((a + b) / 2, (c + d) / 2, polygon)
               for a, b in zip(xs, xs[1:]) for c, d in zip(ys, ys[1:]))


def outside(s, polygon=None):
    """The stored routing shapes that are not inside the boundary."""
    polygon = polygon or _floats(s.db.design_row()["boundary"])
    return [(r["net"], r["kind"], r["layer"], r["rect"]) for r in s.db.net_wire_rows()
            if not within(_floats(r["rect"]), polygon)]


def wires(s, net, kind="wire"):
    return sorted((r["layer"], tuple(_floats(r["rect"])))        # its stub's rows too
                  for r in s.db.net_wire_rows(net) + s.db.stub_wire_rows(net)
                  if r["kind"] == kind)


def build_on(s, write_lef, die, width=0.36):
    """The spine of test_move_spine on another die (points in um), pins routed."""
    area = " ".join(f"( {round(x * 1000)} {round(y * 1000)} )"
                    for x, y in zip(die[0::2], die[1::2]))
    old = next(line for line in DEF.splitlines() if line.startswith("DIEAREA"))
    s.eval(f"read_lef -file {{{write_lef(LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF.replace(old, f'DIEAREA {area} ;') % ROWS, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval(f"assign_track_for_route -layer IA -net {PATTERN}")
    s.eval(f"assign_track_for_route -layer IB -net {PATTERN}")
    s.eval("create_spine -name sp -spec_name sp -location {70 100} -build -ref_cell INV_RP")
    return routable(s, width)


def routable(s, width=0.36):
    s.eval(f"create_route_rule -name r -layer {{IA IB}} -width {width} -spacing {width}")
    s.eval("route_pin -inst *sp_*")
    out_of(s)
    return s


def set_boundary(s, die):
    """Another boundary under a built spine (the cells stay where they are)."""
    with s.db.conn:
        s.db.conn.execute("UPDATE design SET boundary = ?", (" ".join(str(c) for c in die),))


# -- the fence -------------------------------------------------------------------------

def test_fence_gives_the_inside_stretches_of_a_band():
    fence = Fence(L_DIE)
    assert fence.row(10, 11) == [(0, 100)]
    assert fence.row(39, 41) == [(60, 100)]            # the band crosses the corner
    assert fence.col(10, 11) == [(0, 40)] and fence.col(59, 61) == [(0, 40)]
    assert fence.col(70, 71) == [(0, 200)]
    assert fence.holds((0, 0, 100, 40)) and fence.holds((60, 0, 100, 200))   # on it counts
    assert not fence.holds((59.9, 30, 60.1, 41)) and not fence.holds((10, 39, 70, 41))
    assert not fence.holds((100, 10, 100.1, 11)) and not fence.holds((-5, -5, -4, -4))
    assert fence.holds((70, 50, 70, 60)) and fence.holds((70, 50, 80, 50))   # no area
    arms = Fence(U_DIE)
    assert arms.row(15, 20) == [(0, 10), (20, 30)] and arms.row(5, 15) == [(0, 10), (20, 30)]
    assert arms.row(2, 8) == [(0, 30)] and arms.col(12, 18) == [(0, 10)]
    assert not arms.holds((5, 15, 25, 20))             # corners inside, across the gap
    assert arms.spans(2, 28, 15, 16, True) == [(2, 10), (20, 28)]
    assert arms.spans(0, 30, 12, 13, False) == [(0, 10)]
    assert arms.spans(12, 18, 15, 16, True) == []


@pytest.mark.parametrize("die", [L_DIE, SLOT_DIE, U_DIE])
def test_fence_agrees_with_a_point_by_point_check(die):
    fence, rng = Fence(die), random.Random(4)
    span = max(die) + 4
    found = 0
    for _ in range(3000):                               # on a 0.5 grid: many on an edge
        x1, y1 = (rng.randrange(-4, 2 * span) / 2 for _ in range(2))
        rect = (x1, y1, x1 + rng.randrange(1, 60) / 2, y1 + rng.randrange(1, 60) / 2)
        assert fence.holds(rect) == within(rect, die), rect
        found += fence.holds(rect)
    assert 100 < found < 2900


def test_slanted_boundary_is_refused():
    with pytest.raises(HtreeError) as exc:
        Fence([0, 0, 10, 0, 5, 10])
    assert exc.value.msg_id == 179 and "slanted edge (10 0) (5 10)" in exc.value.text


def test_lee_goes_round_a_gap_of_the_boundary():
    xs = ys = [1.0 * k for k in range(1, 30)]           # index k: coordinate k + 1
    lay = Layer("IA", 0.2, 0.2)
    inside = Inside(Fence(U_DIE), xs, ys, lay, Layer("IB", 0.2, 0.2))
    start, goal = (H, 4, 19), {1: {(H, 24, 19)}}        # (5, 20) to (25, 20): arm to arm
    _, path, cost = _lee({start}, goal, xs, ys, set(), 1.0)
    assert cost == pytest.approx(20) and {n[2] for n in path} == {19}     # straight across
    _, path, cost = _lee({start}, goal, xs, ys, set(), 1.0, inside)
    assert all(inside.node(i, j) for _, i, j in path)
    assert min(ys[j] for _, _, j in path) < 10          # through the base
    assert cost == pytest.approx(20 + 2 * 11 + 4 * 1.0)  # down to y 9, along, up; 4 changes
    # a crossing in the gap is no node; a step from arm to arm on one row is not taken
    assert not inside.node(14, 19) and inside.node(4, 19) and inside.node(24, 19)
    assert not inside.step((H, 8, 19), (H, 9, 19)) and inside.step((H, 7, 19), (H, 8, 19))
    assert not inside.step((V, 14, 8), (V, 14, 9)) and inside.step((V, 4, 8), (V, 4, 9))
    # no way round: the base too is cut (two separate dies would be the same)
    shut = Inside(Fence([0, 0, 10, 0, 10, 30, 0, 30]), xs, ys, lay, lay)
    assert _lee({start}, goal, xs, ys, set(), 1.0, shut) is None


# -- route_net -------------------------------------------------------------------------

def test_route_goes_round_a_slot_of_the_die(tech_session, write_lef):
    s = build_on(tech_session, write_lef, SLOT_DIE)
    done = s.split_list(s.eval("route_net -net [get_db nets .name] -rule r"))
    text = out_of(s)
    assert len(done) == 4 and "HT4-174" not in text and "HT4-178" not in text
    assert outside(s) == []
    # L2 to its upper leaf: up to the row under the slot (y 117), right to the first track
    # past its end (x 82.44), up, and back on the first row its strap is reached from
    assert wires(s, "sp_L2_inv1_Y") == [
        ("IA", pytest.approx((73.62, 116.82, 82.62, 117.18))),
        ("IA", pytest.approx((79.38, 128.34, 82.62, 128.7))),
        ("IB", pytest.approx((73.62, 107.7, 73.98, 117.18))),
        ("IB", pytest.approx((79.38, 128.34, 79.74, 129.42))),
        ("IB", pytest.approx((82.26, 116.82, 82.62, 128.7)))]
    assert "sp_L2_inv1_Y: 5 wires, track length 31.68 um" in text and "4 layer change(s)" in text
    # without the slot the same net is one straight wire, through where the slot is
    set_boundary(s, L_DIE)
    s.eval("route_net -net sp_L2_inv1_Y -rule r")
    assert wires(s, "sp_L2_inv1_Y") == [("IB", pytest.approx((73.62, 107.7, 73.98, 129.42)))]
    assert outside(s) == [] and len(outside(s, SLOT_DIE)) == 1


def test_shields_are_cut_at_the_boundary(tech_session, write_lef):
    s = build_on(tech_session, write_lef, SLOT_DIE, width=0.72)
    s.eval("set_db ignore_shield_less_than_routing_length 0")
    s.eval("route_net -net [get_db nets .name] -rule r -shield")
    s.eval("route_final_stub -rule r -shield")
    text = out_of(s)
    assert outside(s) == []
    # the wire round the slot's end (x 82.44) has its left shield on x 81, half over the
    # slot's end (x 81): it stops at the slot (y 119.4) and starts again above it (120.6)
    at_81 = [r for layer, r in wires(s, "sp_L2_inv1_Y", "shield")
             if layer == "IB" and r[0] == pytest.approx(80.64)]
    assert [r[1::2] for r in at_81] == [pytest.approx((116.64, 119.4)),
                                        pytest.approx((120.6, 129.42))]
    assert "shields cut over 1.2 um where they would leave the design boundary" in text
    assert text.count("leave the design boundary") == 1      # the other nets: nothing cut


def test_no_way_inside_the_boundary_is_no_route(tech_session, write_lef):
    # the slot nearly through the channel: a neck of 0.1 um, no track in it
    s = build_on(tech_session, write_lef, [c if c != 81 else 99.9 for c in SLOT_DIE])
    done = s.split_list(s.eval("route_net -net [get_db nets .name] -rule r"))
    text = out_of(s)
    assert len(done) == 4 and outside(s) == []
    assert ("HT4-174): sp_L2_inv1_Y: no path inside the design boundary to sp_L3_inv2/A "
            "(strap 5); they are not routed") in text
    assert "load sp_L3_inv2/A (strap 5): not routed" in text
    # its lower leaf, on the driver's side of the slot, is routed
    assert wires(s, "sp_L2_inv1_Y") == [("IB", pytest.approx((73.62, 107.7, 73.98, 111.42)))]


def test_pins_and_stubs_outside_the_boundary_are_not_routed(tech_session, write_lef):
    s = routable(build(tech_session, write_lef))
    set_boundary(s, [60, 0, 100, 0, 100, 125, 60, 125])        # the upper leaf is outside
    done = s.split_list(s.eval("route_net -net [get_db nets .name] -rule r"))
    text = out_of(s)
    assert list(done) == ["spine_net:sp/sp_L1_inv1_Y", "spine_net:sp/sp_L3_inv1_Y"]
    assert ("HT4-178): sp_L2_inv1_Y: sp_L3_inv2/A (strap 5) is outside the design boundary "
            "(no track crossing at it holds a wire inside it); not routed") in text
    assert "HT4-178): sp_L3_inv2_Y: sp_L3_inv2/Y (strap 3) is outside the design" in text
    # its pin routes are not extended either
    assert ("sp_L3_inv2/A strap 5: left: the signal track at x 73.8 is outside the design "
            "boundary, right: the signal track at x 79.56 is outside the design boundary") in text
    assert s.db.net_wire_rows("sp_L2_inv1_Y") == [] and s.db.net_wire_rows("sp_L3_inv2_Y") == []
    assert list(s.split_list(s.eval("route_final_stub -rule r"))) == ["stub:sp/stub1"]
    text = out_of(s)
    assert ("HT4-178): stub sp/stub2: its wire would not lie inside the design boundary on "
            "any signal track within 20 of its centre line; not routed") in text
    assert "1 of 2 stubs routed" in text and "HT4-191" not in text
    assert wires(s, "sp_L3_inv2_Y", "stub") == [] and outside(s) == []


def test_stub_takes_a_track_inside_the_boundary(tech_session, write_lef):
    s = routable(build(tech_session, write_lef))
    # a slot (x 60 .. 81, y 105.4 .. 106.6) across the line of stub1 (x 78.64, y 100 .. 119)
    set_boundary(s, [c if c not in (120.6, 119.4) else c - 14 for c in SLOT_DIE])
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    # stub1: not on x 79.56 or 76.68 (through the slot) but on the first track past its end
    assert wires(s, "sp_L3_inv1_Y", "stub") == [("IB", pytest.approx((82.26, 100, 82.62, 119)))]
    assert "stub sp/stub1 (sp_L3_inv1_Y): IB x 82.44 (3.8 from its centre line)" in text
    # stub2 is on the same centre line: it shares the track, though x 79.56 holds it
    assert wires(s, "sp_L3_inv2_Y", "stub") == [("IB", pytest.approx((82.26, 121, 82.62, 140)))]
    assert "spine sp: 2 of 2 stub(s) on 1 track(s)" in text
    assert outside(s) == []


def test_no_boundary_no_limit(tech_session, write_lef):
    s = routable(build(tech_session, write_lef))
    with s.db.conn:
        s.db.conn.execute("UPDATE design SET boundary = ''")
    assert len(s.split_list(s.eval("route_net -net [get_db nets .name] -rule r"))) == 4
    assert wires(s, "sp_L2_inv1_Y") == [("IB", pytest.approx((73.62, 107.7, 73.98, 129.42)))]
