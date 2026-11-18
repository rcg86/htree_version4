"""The spine spec's tracks: track: {input: k, output: k} per cell. Track k is
the k-th signal track past the spine's location, in its build direction;
legalize_placement moves the cells across the spine so their straps reach
them, route_net keeps each net on its tracks, route_final_stub puts the stubs
on the leaves' output track."""

import pytest

pytest.importorskip("scipy")

import test_move_spine
from core import spine_tracks
from test_route_net import SPEC, err, out_of

# The test spine: location x 70, built toward +x (the stub line at x 78.64);
# signal tracks at 1.8 + 2.88 k, so track 1 = 70.92, 2 = 73.8, 3 = 76.68,
# 4 = 79.56. L1 comes in on 1 and leaves on 3, L2 stays on 3, the leaves come
# in on 3 and leave on 4, where their stubs go.
TSPEC = SPEC.replace("inv1: {input: net}", "inv1: {input: net, track: {input: 1, output: 3}}") \
    .replace("inv1: {input: L1/inv1/Y}", "inv1: {input: L1/inv1/Y, track: {input: 3, output: 3}}") \
    .replace("output: stub1}", "output: stub1, track: {input: 3, output: 4}}") \
    .replace("output: stub2}", "output: stub2, track: {input: 3, output: 4}}")


# Routable: no two inputs on one track at one height (L2 and the upper leaf sit
# side by side). L1 stays on track 2, L2 goes 2 -> 3, the leaves 3 -> 4.
RSPEC = TSPEC.replace("track: {input: 1, output: 3}", "track: {input: 2, output: 2}") \
    .replace("track: {input: 3, output: 3}", "track: {input: 2, output: 3}")


@pytest.fixture
def tracked(tech_session, write_lef, monkeypatch):
    return _build(tech_session, write_lef, monkeypatch, TSPEC)


@pytest.fixture
def routable(tech_session, write_lef, monkeypatch):
    # not mirrored: this spine's two roots lie on one another (origin 0)
    return _build(tech_session, write_lef, monkeypatch, RSPEC, mirror=False)


def _build(tech_session, write_lef, monkeypatch, spec, mirror=True):
    monkeypatch.setattr(test_move_spine, "SPEC", spec)
    s = test_move_spine.build(tech_session, write_lef, mirror=mirror)
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def ib_tracks(s, net, kinds=("wire",)):
    """The x of the net's long IB wires (more than 2 um) of the kinds."""
    return sorted({round((float(r["rect"].split()[0]) + float(r["rect"].split()[2])) / 2, 6)
                   for r in s.db.net_wire_rows(net) + s.db.stub_wire_rows(net)
                   if r["layer"] == "IB" and r["kind"] in kinds
                   and float(r["rect"].split()[3]) - float(r["rect"].split()[1]) > 2})


def test_the_spec_takes_tracks(tracked, write_lef):
    s = tracked
    assert s.eval("get_db spine_cell:sp/L1/inv1 .track_input") == "1"
    assert s.eval("get_db spine_cell:sp/L3/inv2 .track_output") == "4"
    bad = TSPEC.replace("track: {input: 1, output: 3}", "track: {input: 0, output: 3}")
    assert "L1/inv1 track input must be a whole number from 1" in \
        err(s, f"read_spine_spec -file {{{write_lef(bad, 'b.yaml')}}}")
    bad = TSPEC.replace("track: {input: 1, output: 3}", "track: 2")
    assert "L1/inv1 track must be a mapping like {input: 2, output: 3}" in \
        err(s, f"read_spine_spec -file {{{write_lef(bad, 'c.yaml')}}}")


def test_the_tracks_are_counted_from_the_location(tracked):
    places = {inst: (cin, cout) for inst, (_, cin, cout, _, _) in
              spine_tracks.placed(tracked.db, "sp").items()}
    assert places == {"sp_L1_inv1": (70.92, 76.68), "sp_L2_inv1": (76.68, 76.68),
                      "sp_L3_inv1": (76.68, 79.56), "sp_L3_inv2": (76.68, 79.56),
                      "sp_mirror_L1_inv1": (70.92, 76.68), "sp_mirror_L2_inv1": (76.68, 76.68),
                      "sp_mirror_L3_inv1": (76.68, 79.56), "sp_mirror_L3_inv2": (76.68, 79.56)}


def test_legalize_moves_a_cell_to_reach_its_tracks(tracked):
    s = tracked
    s.eval("legalize_placement -inst [get_db insts]")
    text = out_of(s)
    # L1 (x 68.4 on its site) reaches x 65.4 .. 74.52: not track 3 (76.68). It moves right.
    assert "  2 instance(s) moved across their spine so their straps reach the tracks of the " \
           "spine spec (track: input / output): sp_L1_inv1 2.4, sp_mirror_L1_inv1 2.4" in text
    assert "pin access: every signal pin of the 8 instance(s) has a track" in text
    s.eval("legalize_placement -inst [get_db insts]")      # done: nothing moves again
    assert "moved across" not in out_of(s)


def test_every_net_and_stub_on_its_tracks(routable):
    s = routable
    s.eval("legalize_placement -inst [get_db insts]")
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    out_of(s)
    s.eval("route_net -net [get_db nets .name] -rule r")
    assert "HT4-174" not in out_of(s)
    s.eval("route_final_stub -rule r")
    assert "HT4-17" not in out_of(s)
    assert ib_tracks(s, "sp_L1_inv1_Y") == [73.8]                      # 2 to 2
    assert ib_tracks(s, "sp_L2_inv1_Y") == [76.68]                     # 3 to the leaves' 3
    for leaf in ("sp_L3_inv1_Y", "sp_L3_inv2_Y"):
        assert ib_tracks(s, leaf, ("wire", "stub")) in ([79.56], [])
        assert ib_tracks(s, leaf, ("stub",)) == [79.56]                # the stubs on 4
    s.eval("check_drc")
    assert not [l for l in out_of(s).splitlines() if "no path" in l and "sp_" in l
                and "net net" not in l]


def test_a_cell_on_one_track_keeps_its_way_out(routable):
    """L1 comes in and goes out on track 2: the piece of it past L1's input
    strap, to the crossing past its output strap, is its output net's."""
    from core.commands import route_net
    s = routable
    s.eval("legalize_placement -inst [get_db insts]")
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    out_of(s)
    spine = s.db.spine_row("sp")
    cells = spine_tracks.placed(s.db, "sp")
    grid = route_net.Grid(s.db, route_net._rule_layers(s.db, "r"))
    exits = {net: (x, y1, y2) for x, y1, y2, net in route_net._exits(s.db, grid, spine, cells)}
    assert set(exits) == {"sp_L1_inv1_Y"}
    x, y1, y2 = exits["sp_L1_inv1_Y"]
    a = [float(c) for c in s.db.strap_row("sp_L1_inv1", s.db.pin_wire_row(
        "sp_L1_inv1", "A")["strap"])["rect"].split()]
    assert x == 73.8 and min(y1, y2) <= (a[1] + a[3]) / 2 <= max(y1, y2)
    # another net may not lie there: its nodes are blocked for it
    row = next(r for r in s.db.spine_net_rows(spine["id"]) if r["name"] == "sp_L2_inv1_Y")
    lanes = route_net._spec_lanes(s.db, grid, spine, row, {})
    assert ("sp_L1_inv1_Y" in [e[3] for e in lanes.exits])
