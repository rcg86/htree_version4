"""route_track: route_net's router with a table of the signal tracks used,
and -compact, which packs the nets on the tracks next to the stubs."""

import pytest

pytest.importorskip("scipy")

from core.commands.route_net import H, OUT_WEIGHT, TIE, V, _lee, _out_weights
from test_move_spine import build
from test_route_net import err, out_of

# The fixture of test_move_spine, mirrored: signal tracks at 1.8 + 2.88 k. The
# cells are in three columns 2.88 apart and their straps reach the IB tracks
# 70.92, 73.8 and 76.68 (L1 and L2), 73.8, 76.68 and 79.56 (L3); the stub line
# is at x 78.64, so the stubs' track is 79.56.
ALL = "[get_db nets .name]"


@pytest.fixture
def spine(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True)
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def wires(s, net=None):
    """The stored wires, without their row ids."""
    return sorted((r["net"], r["kind"], r["layer"], r["rect"], r["shield_net"] or "")
                  for r in s.db.net_wire_rows(net))


def tracks(s, net, layer="IB"):
    """{track: um of wire} of a net's wires on layer (IB: x, IA: y)."""
    found = {}
    for n, kind, lay, rect, _ in wires(s, net):
        if kind == "wire" and lay == layer:
            x1, y1, x2, y2 = (float(c) for c in rect.split())
            at, length = ((x1 + x2) / 2, y2 - y1) if layer == "IB" else ((y1 + y2) / 2, x2 - x1)
            found[round(at, 6)] = round(found.get(round(at, 6), 0) + length, 6)
    return found


def test_without_compact_the_wires_are_route_nets(spine):
    spine.eval(f"route_net -net {ALL} -rule r -shield")
    plain = wires(spine)
    out_of(spine)
    handles = spine.eval(f"route_track -net {ALL} -rule r -shield")
    assert wires(spine) == plain
    assert handles.split()[0] == "spine_net:sp/sp_L1_inv1_Y" and len(handles.split()) == 8
    text = out_of(spine)
    assert "route_track: rule r: IA horizontal" in text and "route_net:" not in text
    assert "compact" not in text
    # the table: L1 on 70.92, L2 on 73.8, the leaf routes on the stubs' track,
    # and 76.68 between them empty
    assert "route_track: signal tracks of the 8 net(s)" in text
    assert "  IB x 70.92 .. 79.56 (y 67.7 .. 132.3): 4 signal track(s), 1 empty" in text
    rows = [l.split() for l in text.splitlines() if l.startswith("    7")]
    # (L1 reaches its load's strap from the outer side of the cell: 14.68 um)
    assert [r[:3] for r in rows] == [["70.92", "14.68", "23%"], ["73.8", "43.44", "67%"],
                                    ["76.68", "0", "0%"], ["79.56", "10.96", "17%"]]
    assert rows[2][3] == "(empty)" and set(rows[1][3:]) == {"sp_L2_inv1_Y",
                                                           "sp_mirror_L2_inv1_Y"}


def test_compact_packs_the_nets_against_the_stub_track(spine):
    spine.eval(f"route_track -net {ALL} -rule r -compact")
    text = out_of(spine)
    assert "  compact: every net on the tracks nearest its pins" in text
    assert "  compact: tracks kept free for the stubs (route_final_stub): IB x 79.56 " \
        "(4 stub(s))" in text
    # no empty track left between the nets and the stubs; 70.92 is free
    assert "  IB x 73.8 .. 79.56 (y 60 .. 140): 3 signal track(s), 0 empty" in text
    assert "(empty)" not in text
    assert list(tracks(spine, "sp_L1_inv1_Y")) == [73.8]
    assert list(tracks(spine, "sp_L2_inv1_Y")) == [76.68]
    assert list(tracks(spine, "sp_mirror_L2_inv1_Y")) == [76.68]
    assert "sp_L3_inv1_Y (stub, kept free)" in text
    assert "HT4-174" not in text and "HT4-279" not in text
    # no more wire or layer changes than route_net needs here
    assert text.count(" 0 layer change(s)") == 8
    # the stubs then take the track kept for them, and meet their leaf routes
    spine.eval("route_final_stub -rule r")
    text = out_of(spine)
    assert "IB x 79.56 (4 stub(s), 0.92 from their centre line)" in text
    assert "HT4-192" not in text


def test_compact_keeps_the_stub_track_free(spine):
    # other nets' wires on the three tracks the L2 net can use, between its
    # driver and its upper load: route_net goes round them on the stubs' track
    spine.db.set_net_wires("other", [("wire", "IB", f"{x - 0.18} 115 {x + 0.18} 120")
                                     for x in (70.92, 73.8, 76.68)])
    spine.eval("route_net -net sp_L2_inv1_Y -rule r")
    assert 79.56 in tracks(spine, "sp_L2_inv1_Y")
    # -compact: that track is the stubs', the net passes on the next one out
    # and comes back to its own
    spine.eval("route_track -net sp_L2_inv1_Y -rule r -compact")
    used = tracks(spine, "sp_L2_inv1_Y")
    assert set(used) == {76.68, 82.44}
    assert used[82.44] == pytest.approx(20.52) and used[76.68] == pytest.approx(15.84)
    text = out_of(spine)
    assert "  IB x 76.68 .. 82.44 (y 60 .. 140): 3 signal track(s), 0 empty" in text


def test_compact_leaves_the_driver_strap_on_both_sides(spine):
    # 73.8 is blocked above the driver and 76.68 at the lower load
    spine.db.set_net_wires("other", [("wire", "IB", "73.62 113 73.98 120"),
                                     ("wire", "IB", "76.5 107 76.86 110")])
    spine.eval("route_net -net sp_L2_inv1_Y -rule r")
    assert "sp_L2_inv1_Y: 3 wires" in out_of(spine)          # a jog to the other track
    spine.eval("route_track -net sp_L2_inv1_Y -rule r -compact")
    text = out_of(spine)
    assert "sp_L2_inv1_Y: 2 wires, track length 20.16 um" in text
    assert "0 layer change(s), 4 crossing box(es)" in text
    assert "driver sp_L2_inv1/Y (strap 3): connected across the strap (its pin route, " \
        "extended 0.58 left and 2.42 right) at {73.8 111.24} and {76.68 111.24}" in text
    assert tracks(spine, "sp_L2_inv1_Y") == {73.8: pytest.approx(3.72),
                                            76.68: pytest.approx(18.84)}
    # a second place costs a layer change: not taken where one wire does
    spine.db.set_net_wires("other", [])
    spine.eval("route_track -net sp_mirror_L2_inv1_Y -rule r -compact")
    assert "sp_mirror_L2_inv1_Y: 1 wires" in out_of(spine)


def test_compact_removes_stubs_routed_on_another_track(spine):
    # the stubs routed while their track was blocked: on 76.68
    spine.db.set_net_wires("other", [("wire", "IB", "79.38 125 79.74 130")])
    spine.eval("route_final_stub -rule r")
    assert "IB x 76.68 (4 stub(s)" in out_of(spine)
    spine.db.set_net_wires("other", [])
    spine.eval(f"route_track -net {ALL} -rule r -compact")
    text = out_of(spine)
    # each stub's wire and its crossing box on the leaf's strap (on its net from route_pin)
    assert "(HT4-279): route_track: removed the 8 wires, crossing boxes and shields of 4 " \
        "stub(s) routed before on another track than the one kept free for them; " \
        "route_final_stub routes them again: stub:sp/stub1 stub:sp/stub2 " \
        "stub:sp/stub1_mirror stub:sp/stub2_mirror" in text
    assert not [w for w in wires(spine) if w[1].startswith("stub")]
    assert "HT4-174" not in text and list(tracks(spine, "sp_L2_inv1_Y")) == [76.68]
    # routed where they belong, they stay, and are in the table as stubs
    spine.eval("route_final_stub -rule r")
    stubs = [w for w in wires(spine) if w[1].startswith("stub")]
    out_of(spine)
    spine.eval(f"route_track -net {ALL} -rule r -compact")
    text = out_of(spine)
    assert "HT4-279" not in text and "sp_L3_inv1_Y (stub)" in text
    assert [w for w in wires(spine) if w[1].startswith("stub")] == stubs


def test_track_weights():
    tracks_ = [1.8 + 2.88 * k for k in range(6)]
    # the pins on tracks 2 and 3: 1 there, OUT_WEIGHT more per track further out
    assert _out_weights(tracks_, [3, 2, 2]) == pytest.approx(
        [1 + 2 * OUT_WEIGHT, 1 + OUT_WEIGHT, 1, 1, 1 + OUT_WEIGHT, 1 + 2 * OUT_WEIGHT])
    # and TIE more per track away from the nearest stub track
    near = _out_weights(tracks_, [1, 4], [tracks_[5]])
    assert near == pytest.approx([1 + OUT_WEIGHT + 5 * TIE, 1 + 4 * TIE, 1 + 3 * TIE,
                                  1 + 2 * TIE, 1 + TIE, 1 + OUT_WEIGHT])
    assert _out_weights(tracks_, [0, 5], [tracks_[0], tracks_[5]])[2:4] == pytest.approx(
        [1 + 2 * TIE, 1 + 2 * TIE])


def test_a_weighted_path_comes_back_to_its_track():
    xs = [float(k) for k in range(41)]
    ys = [float(k) for k in range(4)]
    blocked = {(H, 20, 0), (V, 20, 0)}               # track 0 is blocked half way
    ends = ({(H, 0, 0)}, {1: {(H, 40, 0)}})

    def on(path, j):
        return sum(1 for a, b in zip(path, path[1:]) if a[0] == b[0] == H and a[2] == j)

    # weights: the path leaves track 0 only for the two steps round the block
    weights = (_out_weights(ys, [0, 0]), _out_weights(xs, [0, 40]))
    _, path, cost = _lee(*ends, xs, ys, blocked, 1.0, None, weights)
    assert on(path, 0) == 38 and on(path, 1) == 2
    assert cost == pytest.approx(38 + 2 * (1 + OUT_WEIGHT) + 2 + 4 * 1.0)
    # track 1 blocked there as well: round both on track 2, then back
    _, path, cost = _lee(*ends, xs, ys, blocked | {(H, 20, 1)}, 1.0, None, weights)
    assert (on(path, 0), on(path, 1), on(path, 2)) == (38, 0, 2)
    assert cost == pytest.approx(38 + 2 * (1 + 2 * OUT_WEIGHT) + 4 + 4 * 1.0)
    # without weights the cost is the plain length and layer changes
    _, path, cost = _lee(*ends, xs, ys, blocked, 1.0)
    assert cost == pytest.approx(40 + 2 + 4 * 1.0)


def test_errors_and_help_say_route_track(spine):
    assert "(HT4-001): route_track: -net and -rule are required. Usage: route_track -net " \
        "<nets> -rule <route_rule> [-via_weight <um>] [-compact]" in err(spine, "route_track -rule r")
    assert "(HT4-170): route_track: no net 'nosuch'" in err(
        spine, "route_track -net nosuch -rule r -compact")
    assert "(HT4-171): route_track: there is no route rule 'nosuch'" in err(
        spine, "route_track -net sp_L1_inv1_Y -rule nosuch")
    # route_net keeps its name, and has no -compact
    assert "route_net: -net and -rule are required" in err(spine, "route_net -rule r")
    assert "-compact" in err(spine, "route_net -net sp_L1_inv1_Y -rule r -compact")
    assert not wires(spine)
