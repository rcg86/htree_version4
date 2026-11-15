"""route_final_stub: the stubs of a spine on one centre line share one track,
so a straight spine has one stub track and a spine with two bends three."""

import pytest

pytest.importorskip("scipy")

import core.commands.route_final_stub as route_final_stub
from test_move_spine import build
from test_route_bent_stub import Z_MOVES, bent, same, stub_wires
from test_route_net import out_of

# The fixture of test_move_spine: the stub line at x 78.64, signal tracks at
# 1.8 + 2.88 k (79.56 the nearest, then 76.68). Mirrored: stub1 (y 100 .. 119)
# and stub1_mirror (y 81 .. 100) meet at the middle of the spine.
NETS = {"stub1": "sp_L3_inv1_Y", "stub2": "sp_L3_inv2_Y",
        "stub1_mirror": "sp_mirror_L3_inv1_Y", "stub2_mirror": "sp_mirror_L3_inv2_Y"}


def ruled(s):
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def tracks(s, layer="IB"):
    """{stub: the track (wire centre) of its wires on layer}, of the routed ones."""
    found = {}
    for stub, net in NETS.items():
        at = {round((r[0] + r[2]) / 2 if layer == "IB" else (r[1] + r[3]) / 2, 6)
              for lay, r in stub_wires(s, net) if lay == layer}
        if at:
            found[stub] = at
    return found


def test_mirrored_stubs_share_a_track_and_keep_apart_at_the_middle(tech_session, write_lef):
    s = ruled(build(tech_session, write_lef, mirror=True))
    done = s.split_list(s.eval("route_final_stub -rule r"))
    assert len(done) == 4
    text = out_of(s)
    assert tracks(s) == {stub: {79.56} for stub in NETS}
    assert ("  spine sp: 4 of 4 stub(s) on 1 track(s), the stubs on one centre line on one "
            "track: IB x 79.56 (4 stub(s), 0.92 from their centre line)") in text
    # the two that meet at y 100: each ends 0.18 short, so their wires keep the IB spacing
    same(stub_wires(s, NETS["stub1"]), [("IB", [79.38, 100.18, 79.74, 119])])
    same(stub_wires(s, NETS["stub1_mirror"]), [("IB", [79.38, 81, 79.74, 99.82])])
    assert "stub sp/stub1 (sp_L3_inv1_Y): IB x 79.56 (0.92 from its centre line), 100.18 .. 119" \
        in text
    assert ("    its first 0.18 um are left off: stub stub1_mirror is on the same track there "
            "(IB spacing 0.36)") in text
    # the others, 2 apart (the gap of the spec), keep their whole length
    same(stub_wires(s, NETS["stub2"]), [("IB", [79.38, 121, 79.74, 140])])
    same(stub_wires(s, NETS["stub2_mirror"]), [("IB", [79.38, 60, 79.74, 79])])
    assert "HT4-191" not in text and "HT4-193" not in text


def test_a_track_blocked_at_one_stub_moves_all_of_its_line(tech_session, write_lef):
    s = ruled(build(tech_session, write_lef, mirror=True))
    # another net's wire on the nearest track, beside stub2 only
    s.db.set_net_wires("other", [("wire", "IB", "79.38 125 79.74 130")])
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    assert tracks(s) == {stub: {76.68} for stub in NETS}
    assert "on 1 track(s)" in text and "IB x 76.68 (4 stub(s), 1.96 from their centre line)" in text


def test_a_few_stubs_take_the_tracks_of_the_whole_spine(tech_session, write_lef):
    s = ruled(build(tech_session, write_lef, mirror=True))
    s.db.set_net_wires("other", [("wire", "IB", "79.38 125 79.74 130")])
    # stub1 alone: not on its own nearest track but on the one all four can share
    assert s.eval("route_final_stub -rule r -stub stub1") == "stub:sp/stub1"
    text = out_of(s)
    assert tracks(s) == {"stub1": {76.68}}
    assert "1 of 1 stubs routed" in text and "HT4-193" not in text
    s.eval("route_final_stub -rule r")
    assert tracks(s) == {stub: {76.68} for stub in NETS}
    # the wire gone, stub1 again: it moves, and the three left behind are named
    s.db.set_net_wires("other", [])
    out_of(s)
    s.eval("route_final_stub -rule r -stub stub1")
    text = out_of(s)
    assert tracks(s) == {"stub1": {79.56}, **{stub: {76.68} for stub in list(NETS)[1:]}}
    assert ("HT4-193): spine sp: the wires of stub(s) stub2 stub1_mirror stub2_mirror, of an "
            "earlier route_final_stub, are not on the tracks its stubs share now: route them "
            "again (route_final_stub -stub {stub2 stub1_mirror stub2_mirror})") in text
    s.eval("route_final_stub -rule r -stub {stub2 stub1_mirror stub2_mirror}")
    assert tracks(s) == {stub: {79.56} for stub in NETS} and "HT4-193" not in out_of(s)


def test_a_spine_with_two_bends_has_three_tracks(tech_session, write_lef):
    s = bent(build(tech_session, write_lef, mirror=True), Z_MOVES)
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    assert ("  spine sp: 4 of 4 stub(s) on 3 track(s), the stubs on one centre line on one "
            "track: IB x 79.56 (4 stub(s), 0.92 from their centre line); IB x 73.8 (1 stub(s)); "
            "IA y 1.8 (1 stub(s))") in text
    # the last upright piece of the bent stub is on the track of the three straight ones
    assert tracks(s) == {"stub1": {79.56}, "stub2": {79.56}, "stub1_mirror": {79.56},
                         "stub2_mirror": {73.8, 79.56}}
    assert tracks(s, "IA") == {"stub2_mirror": {1.8}}
    s.db.set_net_wires("other", [("wire", "IB", "79.38 60 79.74 70")])       # beside stub2
    s.eval("route_final_stub -rule r")
    out_of(s)
    assert tracks(s) == {"stub1": {76.68}, "stub2": {76.68}, "stub1_mirror": {76.68},
                         "stub2_mirror": {73.8, 76.68}}
    # the flat piece of the bent stub ends on the track the upright one moved to
    assert ("IA", pytest.approx([73.62, 1.62, 76.86, 1.98])) in stub_wires(s, NETS["stub2_mirror"])


def test_a_stub_that_cannot_share_the_track_is_left_out(tech_session, write_lef):
    s = ruled(build(tech_session, write_lef))
    # beside stub1 only x 79.56 is free, beside stub2 only x 76.68
    s.db.set_net_wires("other", [("wire", "IB", "0 105 79 110"),
                                 ("wire", "IB", "80.12 105 200 110"),
                                 ("wire", "IB", "0 125 76.1 130"),
                                 ("wire", "IB", "77.3 125 200 130")])
    assert s.eval("route_final_stub -rule r") == "stub:sp/stub1"
    text = out_of(s)
    assert tracks(s) == {"stub1": {79.56}}
    assert "spine sp: 1 of 2 stub(s) on 1 track(s)" in text and "1 of 2 stubs routed" in text
    assert ("HT4-191): stub sp/stub2: no signal track within 20 of its centre line that it can "
            "share with the other stubs of spine sp on that line") in text
    # on its own it has a track, and with it stub1 has none: the first of the spine stays
    assert s.eval("route_final_stub -rule r -stub stub2") == ""
    assert tracks(s) == {"stub1": {79.56}}


def test_stubs_closer_than_the_spacing_on_a_track(tech_session, write_lef, monkeypatch):
    s = ruled(build(tech_session, write_lef, mirror=True))
    monkeypatch.setattr(route_final_stub, "_keep_apart", lambda *args: None)   # ends as given
    assert len(s.split_list(s.eval("route_final_stub -rule r"))) == 3
    text = out_of(s)
    assert ("HT4-191): stub sp/stub1_mirror: on the track it shares with stub stub1 its wire "
            "would come closer than the spacing to that stub's; not routed") in text
    assert sorted(tracks(s)) == ["stub1", "stub2", "stub2_mirror"]


@pytest.mark.parametrize("stubs_first", [False, True])
def test_leaf_routes_end_on_the_shared_track(tech_session, write_lef, stubs_first):
    s = ruled(build(tech_session, write_lef, mirror=True))
    s.eval("route_pin -inst *sp_*")
    s.db.set_net_wires("other", [("wire", "IB", "79.38 125 79.74 130")])
    out_of(s)
    if stubs_first:
        s.eval("route_final_stub -rule r")
    s.eval("route_net -net [get_db nets .name] -rule r")
    text = out_of(s)
    # stub1's own nearest track is x 79.56: its leaf's route ends on the shared x 76.68
    assert ("load stub stub1 (tap, on its wire): ends on the stub wire at {76.68 " if stubs_first
            else "load stub stub1 (tap): ends at the stub (the stub is not routed) at {76.68 ") \
        in text
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    assert tracks(s) == {stub: {76.68} for stub in NETS}
    assert text.count("meets its leaf route") == 4 and "HT4-192" not in text
