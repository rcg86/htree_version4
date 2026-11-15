"""route_final_stub on stubs that lie over a bend of their spine
(move_spine_to_boundary): a wire a straight piece, a crossing box a bend."""

import pytest

pytest.importorskip("scipy")

from test_move_spine import MOVES, build
from test_route_net import _floats, out_of

# The fixture of test_move_spine: signal tracks at 1.8 + 2.88 k on IA and IB,
# the stub line at x 78.64 (nearest signal track 79.56, then 76.68).
Z_MOVES = "{head bottom down 69.4 left 5.76 down 5.76}"


def bent(s, moves=MOVES, width=0.36):
    s.eval(f"move_spine_to_boundary -spine sp -moves {moves}")
    s.eval(f"create_route_rule -name r -layer {{IA IB}} -width {width} -spacing {width}")
    out_of(s)
    return s


def stub_wires(s, net, kind="stub"):
    """[(layer, [x1, y1, x2, y2])] of a net's route_final_stub rows of a kind."""
    return [(r["layer"], _floats(r["rect"])) for r in s.db.net_wire_rows(net)
            if r["kind"] == kind]


def same(found, want):
    assert [layer for layer, _ in found] == [layer for layer, _ in want], found
    for (_, rect), (_, box) in zip(found, want):
        assert rect == pytest.approx(box, abs=1e-6), found


def test_l_shaped_stub_is_a_wire_a_piece_and_a_box_at_the_bend(tech_session, write_lef):
    s = bent(build(tech_session, write_lef))
    assert _floats(s.eval("get_db stub:sp/stub2 .points")) == pytest.approx(
        [68.88, 30.6, 78.64, 30.6, 78.64, 39.84])
    done = s.split_list(s.eval("route_final_stub -rule r"))
    assert list(done) == ["stub:sp/stub1", "stub:sp/stub2"]
    text = out_of(s)
    assert "route_final_stub: 2 of 2 stubs routed" in text
    # the flat piece on IA at y 30.6, the upright one on IB at x 79.56 (0.92 off its centre
    # line): each runs to the other's track and half its width on
    same(stub_wires(s, "sp_L3_inv2_Y"), [("IA", [68.88, 30.42, 79.74, 30.78]),
                                         ("IB", [79.38, 30.42, 79.74, 39.84])])
    same(stub_wires(s, "sp_L3_inv2_Y", "stub_cross"), [("IA/IB", [79.38, 30.42, 79.74, 30.78])])
    assert ("stub sp/stub2 (sp_L3_inv2_Y): 2 pieces round 1 bend(s) (length 19.92, 0.92 more "
            "than the stub's 19)") in text
    assert "    IA y 30.6, 68.88 .. 79.56 (length 10.68)" in text
    assert "    IB x 79.56 (0.92 from its centre line), 30.6 .. 39.84 (length 9.24)" in text
    # stub1 lies flat now: one IA wire, reported on one line as a straight stub is
    same(stub_wires(s, "sp_L3_inv1_Y"), [("IA", [47.88, 30.42, 66.88, 30.78])])
    assert "stub sp/stub1 (sp_L3_inv1_Y): IA y 30.6, 47.88 .. 66.88 (length 19)" in text
    assert "HT4-192" in text and "route_net -net sp_L3_inv2_Y first" in text
    # the view draws every row: the wires filled, the box as an outline on its first layer
    from core.gui.layout_data import load_layout
    drawn = [w for w in load_layout(s.db).net_wires if w.net == "sp_L3_inv2_Y"]
    assert sorted((w.layer, w.outline) for w in drawn) == [("IA", False), ("IA", True),
                                                           ("IB", False)]


def test_z_shaped_stub_has_three_wires_and_two_boxes(tech_session, write_lef):
    s = bent(build(tech_session, write_lef), Z_MOVES)
    assert _floats(s.eval("get_db stub:sp/stub1 .points")) == pytest.approx(
        [73.8, 24.84, 73.8, 30.6, 78.64, 30.6, 78.64, 39])
    s.eval("route_final_stub -rule r -stub stub1")
    text = out_of(s)
    same(stub_wires(s, "sp_L3_inv1_Y"), [("IB", [73.62, 24.84, 73.98, 30.78]),
                                         ("IA", [73.62, 30.42, 79.74, 30.78]),
                                         ("IB", [79.38, 30.42, 79.74, 39])])
    same(stub_wires(s, "sp_L3_inv1_Y", "stub_cross"), [("IA/IB", [73.62, 30.42, 73.98, 30.78]),
                                                       ("IA/IB", [79.38, 30.42, 79.74, 30.78])])
    assert "3 pieces round 2 bend(s) (length 19.92, 0.92 more than the stub's 19)" in text
    assert "    IB x 73.8, 24.84 .. 30.6 (length 5.76)" in text
    assert "    IA y 30.6, 73.8 .. 79.56 (length 5.76)" in text
    assert "    IB x 79.56 (0.92 from its centre line), 30.6 .. 39 (length 8.4)" in text


def test_end_piece_inside_the_wire_it_joins_gets_no_wire(tech_session, write_lef):
    # no track assignment: every track (0.36 + 0.72 k) is a signal track
    s = bent(build(tech_session, write_lef, tracks=False), "{head bottom down 69.4 left 21.1}")
    assert _floats(s.eval("get_db stub:sp/stub2 .points")) == pytest.approx(
        [78.54, 30.6, 78.64, 30.6, 78.64, 49.5])
    s.eval("route_final_stub -rule r -stub stub2")
    text = out_of(s)
    same(stub_wires(s, "sp_L3_inv2_Y"), [("IB", [78.66, 30.6, 79.02, 49.5])])
    assert stub_wires(s, "sp_L3_inv2_Y", "stub_cross") == []
    assert "IB x 78.84 (0.2 from its centre line), 30.6 .. 49.5 (length 18.9)" in text
    assert "its first 0.1 um, past the bend, are inside the IB wire: no wire of their own" in text


def test_every_piece_gets_its_shields(tech_session, write_lef):
    s = bent(build(tech_session, write_lef), width=0.72)
    s.eval("set_db ignore_shield_less_than_routing_length 0")
    s.eval("route_final_stub -rule r -stub stub2 -shield")
    text = out_of(s)
    same(stub_wires(s, "sp_L3_inv2_Y"), [("IA", [68.88, 30.24, 79.92, 30.96]),
                                         ("IB", [79.2, 30.24, 79.92, 39.84])])
    shields = [(r["layer"], r["shield_net"], _floats(r["rect"]))
               for r in s.db.net_wire_rows("sp_L3_inv2_Y") if r["kind"] == "stub_shield"]
    # one each side of each piece, a track of its net 1.44 (width + spacing) away
    at = sorted((layer, net, round((r[1] + r[3]) / 2 if layer == "IA" else (r[0] + r[2]) / 2, 6))
                for layer, net, r in shields)
    assert at == [("IA", "VDD", 29.16), ("IA", "VSS", 32.04),
                  ("IB", "VDD", 81.0), ("IB", "VSS", 78.12)]
    for layer, _, r in shields:
        assert (r[3] - r[1] if layer == "IA" else r[2] - r[0]) == pytest.approx(0.72)
    assert "shield VDD: 2 wire(s)" in text and "shield VSS: 2 wire(s)" in text
    # routed again without -shield: the shields go with the old wires
    s.eval("route_final_stub -rule r -stub stub2")
    assert not [r for r in s.db.net_wire_rows("sp_L3_inv2_Y") if r["kind"] == "stub_shield"]
    assert len(stub_wires(s, "sp_L3_inv2_Y")) == 2


def test_blocked_track_moves_a_piece_and_the_end_of_the_one_it_meets(tech_session, write_lef):
    s = bent(build(tech_session, write_lef))
    # another net's IB wire on the upright piece's nearest track
    s.db.set_net_wires("sp_L1_inv1_Y", [("wire", "IB", "79.38 32 79.74 36")])
    s.eval("route_final_stub -rule r -stub stub2")
    text = out_of(s)
    same(stub_wires(s, "sp_L3_inv2_Y"), [("IA", [68.88, 30.42, 76.86, 30.78]),
                                         ("IB", [76.5, 30.42, 76.86, 39.84])])
    same(stub_wires(s, "sp_L3_inv2_Y", "stub_cross"), [("IA/IB", [76.5, 30.42, 76.86, 30.78])])
    assert "(length 17.04, 1.96 less than the stub's 19)" in text
    assert "    IA y 30.6, 68.88 .. 76.68 (length 7.8)" in text
    assert "    IB x 76.68 (1.96 from its centre line), 30.6 .. 39.84 (length 9.24)" in text
    # no free track for a piece: the stub is not routed, its old wires stay
    s.db.set_net_wires("sp_L1_inv1_Y", [("wire", "IA", "60 0 100 100")])
    assert s.eval("route_final_stub -rule r -stub stub2") == ""
    text = out_of(s)
    assert "HT4-191" in text and "IA spacing 0.36" in text and "0 of 1 stubs routed" in text
    assert len(stub_wires(s, "sp_L3_inv2_Y")) == 2


@pytest.mark.parametrize("moves", [MOVES, Z_MOVES])
@pytest.mark.parametrize("stubs_first", [False, True])
def test_leaf_routes_meet_the_bent_stubs(tech_session, write_lef, tmp_path, moves, stubs_first):
    s = bent(build(tech_session, write_lef), moves)
    leaves = ("sp_L3_inv1_Y", "sp_L3_inv2_Y")
    s.eval("route_pin -inst *sp_*")
    if stubs_first:              # the routes then end on the stub wires
        s.eval("route_final_stub -rule r")
        s.eval("route_net -net [get_db nets .name] -rule r")
    else:                        # a stub wire pushed off its centre line by the cells'
        s.eval("route_net -net [get_db nets .name] -rule r")     # straps: its leaf's route
        s.eval("route_final_stub -rule r")                       # ends on the track the stub
        text = out_of(s)                                         # gets, so the two meet
        assert "HT4-192" not in text and text.count("meets its leaf route") == 2
        s.eval(f"route_net -net {{{' '.join(leaves)}}} -rule r")
    text = out_of(s)
    assert text.count("(tap, on its wire): ends on the stub wire at") == 2
    before = {net: stub_wires(s, net) for net in leaves}
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    assert "2 of 2 stubs routed" in text and "HT4-192" not in text
    assert text.count("meets its leaf route") == 2
    after = {net: stub_wires(s, net) for net in leaves}
    for net in leaves:
        if not stubs_first:      # the stubs stay where they were. (Stubs first: the pin
            same(after[net], before[net])    # route extensions of route_net keep only the
        own = [_floats(r["rect"]) for r in s.db.net_wire_rows(net)   # tech spacing to a stub
               if r["kind"] in ("wire", "extension")]                # wire, which may move.)
        assert any(min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and      # a leaf wire overlaps one
                   min(a[3], b[3]) - max(a[1], b[1]) > 1e-6
                   for a in own for _, b in after[net])
    bends = sum(len(_floats(s.eval(f"get_db stub:sp/{n} .points"))) // 2 - 2
                for n in ("stub1", "stub2"))
    assert sum(len(after[net]) for net in leaves) == 2 + bends
    # write_def: every stub wire in its leaf net's block
    path = tmp_path / "s.def"
    s.eval(f"write_def -output {path}")
    for net in leaves:
        block = path.read_text().split(f"- {net} ")[1].split("\n  ;")[0]
        for layer, r in after[net]:
            x1, y1, x2, y2 = (round(v * 1000) for v in r)
            assert f"{layer} ( {x1} {y1} ) RECT ( 0 0 {x2 - x1} {y2 - y1} )" in block
    # delete_route of the stubs removes their wires and boxes, the leaf routes stay
    s.eval("delete_route -nets [get_db stubs]")
    for net in leaves:
        kinds = {r["kind"] for r in s.db.net_wire_rows(net)}
        assert not any(k.startswith("stub") for k in kinds) and kinds
