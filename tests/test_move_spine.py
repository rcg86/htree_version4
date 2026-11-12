import random
import tkinter

import pytest

pytest.importorskip("scipy")

from core.spine_snake import Line, Snake, SnakeError, member_axes, stub_middle, stub_points
from test_route_net import SPEC, _floats, out_of
from test_route_pin import CELL_LEF

# An L-shaped die: a channel x 60 .. 100 up to y 200 and a band y 0 .. 40 from
# x 0. IA (horizontal) and IB (vertical) tracks every 0.72 from 0.36; rows of
# 0.2 sites, 1.778 tall, N and FS in turn.
DEF = """VERSION 5.8 ;
DESIGN t ;
UNITS DISTANCE MICRONS 1000 ;
DIEAREA ( 0 0 ) ( 100000 0 ) ( 100000 200000 ) ( 60000 200000 ) ( 60000 40000 ) ( 0 40000 ) ;
%s
TRACKS Y 360 DO 278 STEP 720 LAYER IA ;
TRACKS X 360 DO 139 STEP 720 LAYER IB ;
END DESIGN
"""
ROWS = "".join(f"ROW r{k} core 0 {k * 1778} {'N' if k % 2 == 0 else 'FS'} DO 500 BY 1 STEP 200 0 ;\n"
               for k in range(112))
LEF = CELL_LEF.replace("  SIZE 3.12", "  SITE core ;\n  SIZE 3.12")
PATTERN = "{VDD NA - NA VSS NA - NA}"      # signal tracks at 1.8 + 2.88 k


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


def build(s, write_lef, rows=True, mirror=False, tracks=True, location="70 100"):
    s.eval(f"read_lef -file {{{write_lef(LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF % (ROWS if rows else ''), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    if tracks:
        s.eval(f"assign_track_for_route -layer IA -net {PATTERN}")
        s.eval(f"assign_track_for_route -layer IB -net {PATTERN}")
    # the stub line is 3 columns of 2.88 right of -location: x 78.64, y 100 .. 140
    s.eval(f"create_spine -name sp -spec_name sp -location {{{location}}} -build "
           f"-ref_cell INV_RP" + (" -mirror" if mirror else ""))
    out_of(s)
    return s


@pytest.fixture
def spine(tech_session, write_lef):
    return build(tech_session, write_lef)


def near(pts, want):
    assert len(pts) == len(want), pts
    for p, q in zip(pts, want):
        assert p == pytest.approx(q, abs=1e-6), pts


def length(pts):
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def centres(s):
    """{inst: centre} from the database (INV_RP is 3.12 x 1.778)."""
    return {r["name"]: (r["x"] + 1.56, r["y"] + 0.889) for r in s.db.inst_rows()}


# -- the engine ------------------------------------------------------------------------

@pytest.mark.parametrize("mirror", [False, True])
def test_straight_spine_is_where_create_spine_put_it(tech_session, write_lef, mirror):
    s = build(tech_session, write_lef, mirror=mirror)
    sn = Snake(s.db, "sp")
    near(sn.body(), [(78.64, 60 if mirror else 100), (78.64, 140)])
    assert (sn.head, sn.end_name(), sn.heading()) == ("lo", "bottom", (0, -1))
    built = centres(s)
    for inst, x, y in sn.cells():                     # within the grid snap of the corner
        assert (x, y) == pytest.approx(built[inst], abs=1e-3)
    sid = s.db.spine_row("sp")["id"]
    stored = {r["name"]: sorted(stub_points(r["points"])) for r in s.db.spine_stub_rows(sid)}
    for _, name, pts in sn.stub_lines():
        near(sorted(pts), stored[name])
    segs = lambda text: [(tuple(v[:2]), tuple(v[2:]))
                         for v in (_floats(seg) for seg in text.split(";") if seg)]
    stored = {r["name"]: segs(r["route"]) for r in s.db.spine_net_rows(sid)}
    for _, name, lines in sn.net_lines():
        got = [(l[:2], l[2:]) for l in lines]
        assert sum(length(seg) for seg in got) == pytest.approx(
            sum(length(seg) for seg in stored[name]))
        assert all(any(_within(seg, st) for st in stored[name]) for seg in got)


def _within(seg, other):
    (a, b), (c, d) = seg, other
    return all(min(c[k], d[k]) - 1e-6 <= p[k] <= max(c[k], d[k]) + 1e-6
               for p in (a, b) for k in (0, 1))


def test_head_lands_on_signal_tracks_and_turns(spine):
    sn = Snake(spine.db, "sp")
    assert sn.track_layers == {"y": "IA", "x": "IB"} and sn.periods == {"y": 5.76, "x": 5.76}
    assert sn.round_step("down", 7) == 5.76 and sn.round_step("left", 1) == 5.76
    step = sn.move("down", 70)                        # y 30: the track at 30.6
    assert (step.moved, step.note) == (pytest.approx(69.4), "")
    near(sn.body(), [(78.64, 30.6), (78.64, 70.6)])
    step = sn.move("left", 30)                        # x 48.64: the track at 47.88
    assert step.moved == pytest.approx(30.76) and step.head == pytest.approx((47.88, 30.6))
    near(sn.body(), [(47.88, 30.6), (78.64, 30.6), (78.64, 39.84)])
    assert sn.heading() == (-1, 0)
    assert sn.moves_text() == "head bottom down 69.4 left 30.76"
    # the first stub lies on the new stretch, the second over the corner; both keep 19 um
    lines = {name: pts for _, name, pts in sn.stub_lines()}
    near(lines["stub1"], [(47.88, 30.6), (66.88, 30.6)])
    near(lines["stub2"], [(68.88, 30.6), (78.64, 30.6), (78.64, 39.84)])
    assert length(lines["stub2"]) == pytest.approx(19)
    # the root was 8.64 left of the stubs on the way up: now 8.64 above them
    cells = {n: (x, y) for n, x, y in sn.cells()}
    assert cells["sp_L1_inv1"] == pytest.approx((47.88, 39.24))
    assert sn.axis_of("sp_L1_inv1") == "x"


def test_round_step_whole_periods(spine):
    sn = Snake(spine.db, "sp")
    assert sn.round_step("up", 20) == pytest.approx(17.28)        # 3.47 periods -> 3
    assert sn.round_step("up", 21) == pytest.approx(23.04)        # 3.65 -> 4
    free = Snake(spine.db, "sp", limits=False)                    # no tracks: the grid
    assert free.round_step("up", 7) == pytest.approx(7)


def test_net_lines_follow_the_path(spine):
    sn = Snake(spine.db, "sp", limits=False)
    before = {name: sum(length([l[:2], l[2:]]) for l in lines)
              for _, name, lines in sn.net_lines()}
    sn.move("down", 70)
    sn.move("left", 12)
    sn.move("down", 20)
    after = {name: lines for _, name, lines in sn.net_lines()}
    for name, lines in after.items():
        assert all(l[0] == pytest.approx(l[2]) or l[1] == pytest.approx(l[3]) for l in lines)
        # a trunk beside the stubs is longer round the outside of a corner and
        # shorter round the inside, by twice its distance from the stub line a turn
        assert abs(sum(length([l[:2], l[2:]]) for l in lines) - before[name]) <= 4 * 8.64 + 1e-6
    for _, name, pts in sn.stub_lines():
        assert length(pts) == pytest.approx(19)


def test_clearance_is_a_hard_stop_for_the_head(spine):
    sn = Snake(spine.db, "sp", (0, 0, 0, 12.08))
    assert sn.move("down", 81).moved == pytest.approx(80.92)      # y 19.08, a track
    step = sn.move("down", 20)       # 7 um of room: the last track inside is 5.76 on
    assert step.moved == pytest.approx(5.76) and "bottom clearance 12.08" in step.note
    assert step.head == pytest.approx((78.64, 13.32))
    step = sn.move("down", 5.76)
    assert step.moved == 0 and step.note.startswith("stopped by the bottom clearance")
    assert sn.moves_text() == "head bottom down 86.68"
    assert sn.undo() and sn.head_point() == pytest.approx((78.64, 19.08))


def test_clearance_beside_the_move(spine):
    sn = Snake(spine.db, "sp", (0, 0, 5, 0))
    sn.move("down", 63.64)                            # y 36.36: 3.64 under the band's top
    step = sn.move("left", 50)       # beyond x 60 the top is 3.64 away: stop before it
    assert step.head == pytest.approx((62.28, 36.36)) and "top clearance 5" in step.note
    free = Snake(spine.db, "sp")                      # no clearance: on to the track asked
    free.move("down", 63.64)
    assert free.move("left", 50).head == pytest.approx((27.72, 36.36))
    edge = Snake(spine.db, "sp")                      # the boundary itself stops the head
    step = edge.move("down", 500)
    assert step.head == pytest.approx((78.64, 1.8)) and "bottom clearance 0" in step.note


def test_head_outside_the_die_lands_on_the_grid(tech_session, write_lef):
    s = build(tech_session, write_lef, location="70 170")
    sn = Snake(s.db, "sp", (5, 5, 5, 5))
    sn.set_head("top")
    assert sn.head_point() == pytest.approx((78.64, 210)) and "stub2" in sn.outside()
    assert sn.move("up", 5.0001).head == pytest.approx((78.64, 215))   # no track, no stop
    step = sn.move("down", 8)                         # still above the tracks: as asked
    assert step.head == pytest.approx((78.64, 207)) and step.note == ""
    step = sn.move("down", 12)                        # y 195: the track at 194.76
    assert step.head == pytest.approx((78.64, 194.76))
    assert sn.outside() == []
    step = sn.move("up", 20)                          # inside now: the top clearance holds
    assert step.moved == 0 and "top clearance 5" in step.note
    assert sn.moves_text() == "head top up 5 down 20.24"       # one way: one record


def test_back_up_along_its_own_path(spine):
    sn = Snake(spine.db, "sp")
    sn.move("down", 69.4)
    straight = sn.body()
    sn.move("down", 28.8)
    assert sn.move("up", 28.8).moved == pytest.approx(28.8)       # back: the tail goes up
    near(sn.body(), straight)
    sn.move("left", 30.76)
    step = sn.move("right", 100)                      # back, as far as the corner
    assert step.moved == pytest.approx(30.76) and "next corner" in step.note
    near(sn.body(), straight)
    assert sn.heading() == (0, -1)
    assert sn.move("up", 10).moved == pytest.approx(8.64)         # on round it: y 39.24
    near(sn.body(), [(78.64, 39.24), (78.64, 79.24)])
    assert sn.moves_text() == "head bottom down 98.2 up 28.8 left 30.76 right 30.76 up 8.64"


def test_refuses_to_run_into_its_own_body(spine):
    sn = Snake(spine.db, "sp", limits=False)
    assert sn.width == pytest.approx((-10.2, 0))      # the root column and half a cell
    sn.move("down", 70)
    sn.move("left", 5)
    before = (sn.body(), sn.moves_text())
    step = sn.move("up", 20)                          # 5 um beside itself: no room
    assert step.moved == 0 and step.note.startswith("refused: the spine would run into")
    assert (sn.body(), sn.moves_text()) == before
    sn.move("left", 20)                               # 25 um away: a U turn fits
    assert sn.move("up", 10).moved == pytest.approx(10)
    near(sn.body(), [(53.64, 40), (53.64, 30), (78.64, 30), (78.64, 35)])


def test_swap_head_keeps_the_path(spine):
    sn = Snake(spine.db, "sp")
    sn.move("down", 69.4)
    sn.move("left", 30.76)
    body = sn.body()
    sn.swap_head()
    assert (sn.end_name(), sn.heading(), sn.body()) == ("top", (0, 1), body)
    assert sn.head_point() == pytest.approx((78.64, 39.84))
    step = sn.move("down", 5)                         # back: the left end runs on left
    assert step.moved == pytest.approx(6.36)          # to the track at y 33.48
    near(sn.body(), [(41.52, 30.6), (78.64, 30.6), (78.64, 33.48)])
    assert sn.moves_text() == "head bottom down 69.4 left 30.76 head top down 6.36"
    assert sn.undo() and sn.undo() and sn.end_name() == "bottom" and sn.body() == body
    with pytest.raises(SnakeError):
        sn.set_head("left")
    with pytest.raises(SnakeError):
        sn.move("north", 1)


def test_outside_and_cell_overlaps(spine):
    sn = Snake(spine.db, "sp")
    # as built the columns are 2.88 apart and the cell 3.12 wide
    assert sn.outside() == [] and sn.cell_overlaps() == [("sp_L2_inv1", "sp_L3_inv1")]
    sn.move("down", 69.4)
    sn.move("left", 30.76)
    assert sn.outside() == [] and sn.cell_overlaps() == []       # above each other now
    sn.swap_head()
    sn.move("down", 9.24)                             # back to the corner: all of it flat
    near(sn.body(), [(38.64, 30.6), (78.64, 30.6)])
    assert sn.heading() == (1, 0) and sn.outside() == []
    step = sn.move("left", 60)       # on back: the left end runs out of the die
    assert step.head == pytest.approx((19.08, 30.6)) and step.note == ""
    assert sn.outside() == ["sp_L1_inv1", "sp_L2_inv1", "sp_L3_inv1", "stub1"]


def test_repeating_the_recorded_moves_gives_the_same_path(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True)
    rng = random.Random(7)
    for trial in range(8):
        sn = Snake(s.db, "sp", (2, 3, 4, 5))
        for _ in range(40):
            if rng.random() < 0.15:
                sn.swap_head()
            else:
                sn.move(rng.choice(["up", "down", "left", "right"]),
                        rng.choice([2.88, 5.76, 11.52, 7, 40]))
            if rng.random() < 0.05:
                sn.undo()
        again = Snake(s.db, "sp", (2, 3, 4, 5))
        words = sn.moves_text().split()
        for word, value in zip(words[0::2], words[1::2]):
            if word == "head":
                again.set_head(value)
            else:
                step = again.move(word, float(value))
                assert step.moved == pytest.approx(float(value)), (trial, sn.moves_text())
        assert again.body() == sn.body(), (trial, sn.moves_text())
        assert Line(sn.body()).total == pytest.approx(sn.length)


def test_stub_helpers():
    pts = stub_points("0 0 0 10 6 10")
    assert pts == [(0, 0), (0, 10), (6, 10)]
    assert stub_middle(pts) == pytest.approx((0, 8))
    assert stub_middle(stub_points("1 2 1 12")) == pytest.approx((1, 7))


# -- the command -----------------------------------------------------------------------

MOVES = "{head bottom down 69.4 left 30.76}"


def test_command_stores_the_bent_spine(spine):
    s = spine
    s.eval("route_pin -inst *sp_*")
    assert s.db.strap_rows() and s.db.pin_wire_rows()
    out_of(s)
    assert s.eval(f"move_spine_to_boundary -spine sp -moves {MOVES}") == "spine:sp"
    text = out_of(s)
    assert "down 69.4: head bottom at 78.64 30.6" in text
    assert "Moved spine:sp onto a path with 1 corner(s): 4 instances, 2 stubs, 4 nets" in text
    assert "legalize_placement:" in text and "HT4-234" not in text
    assert not s.db.strap_rows() and not s.db.pin_wire_rows()          # routing removed
    assert s.eval("get_db spine:sp .path") == "47.88 30.6 78.64 30.6 78.64 39.84"
    assert _floats(s.eval("get_db stub:sp/stub1 .points")) == pytest.approx(
        [47.88, 30.6, 66.88, 30.6])
    assert _floats(s.eval("get_db stub:sp/stub2 .points")) == pytest.approx(
        [68.88, 30.6, 78.64, 30.6, 78.64, 39.84])
    assert float(s.eval("get_db stub:sp/stub2 .length")) == pytest.approx(19)
    assert _floats(s.eval("get_db stub:sp/stub2 .tap")) == pytest.approx([78.38, 30.6])
    # -location is where the spine's (0, 0) went: 8.64 above the left end
    assert _floats(s.eval("get_db spine:sp .location")) == pytest.approx([47.88, 39.24])
    rows = {round(k * 1.778, 6): ("N" if k % 2 == 0 else "FS") for k in range(112)}
    want = {n: c for n, *c in Snake(s.db, "sp").cells()}
    for name, (x, y) in centres(s).items():           # on sites, a cell's reach from the path
        r = s.db.inst_row(name)
        assert rows.get(round(r["y"], 6)) == (r["orient"] or "N")
        assert abs(r["x"] / 0.2 - round(r["x"] / 0.2)) < 1e-6
        assert abs(x - want[name][0]) + abs(y - want[name][1]) <= 3.12 + 1.778
    from core import objects
    from core.commands.legalize_placement import _overlap
    boxes = [objects.inst_bbox(s.db, r) for r in s.db.inst_rows()]
    assert not any(_overlap(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


def test_member_axes_on_a_bent_spine(spine):
    s = spine
    assert set(member_axes(s.db).values()) == {"y"}
    s.eval("move_spine_to_boundary -spine sp -moves {down 69.4 left 12}")   # x 68.04
    assert s.eval("get_db spine:sp .path") == "68.04 30.6 78.64 30.6 78.64 60"
    # the legalizer's way for each cell: three on the flat stretch, one on the way up
    assert member_axes(s.db) == {"sp_L1_inv1": "x", "sp_L2_inv1": "x", "sp_L3_inv1": "x",
                                 "sp_L3_inv2": "y"}
    from core import objects
    from core.commands.legalize_placement import _overlap
    boxes = [objects.inst_bbox(s.db, r) for r in s.db.inst_rows()]
    assert not any(_overlap(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


def test_command_on_a_mirrored_spine(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True)
    names = s.eval("get_db spine:sp .stubs").split()
    assert len(names) == 4
    s.eval("move_spine_to_boundary -spine sp -moves {down 40.92 left 30.76 head top down 10}")
    path = _floats(s.eval("get_db spine:sp .path"))
    assert len(path) == 6 and Line(list(zip(path[0::2], path[1::2]))).total == pytest.approx(80)
    for name in names:                                # two flat, one bent, one upright
        assert float(s.eval(f"get_db {name} .length")) == pytest.approx(19)
    assert sorted(len(_floats(s.eval(f"get_db {n} .points"))) for n in names) == [4, 4, 4, 6]
    assert set(member_axes(s.db).values()) == {"x", "y"}


def test_command_again_starts_from_the_stored_path(spine, tmp_path):
    s = spine
    s.eval(f"move_spine_to_boundary -spine sp -moves {MOVES}")
    path = tmp_path / "bent.db"
    s.eval(f"write_db -file {{{path}}}")
    s.eval(f"read_db -file {{{path}}}")
    s.eval("move_spine_to_boundary -spine spine:sp -moves {left 5.76}")
    assert _floats(s.eval("get_db spine:sp .path")) == pytest.approx(
        [42.12, 30.6, 78.64, 30.6, 78.64, 34.08])
    assert float(s.eval("get_db stub:sp/stub2 .length")) == pytest.approx(19)
    s.eval("move_obj -direction up -distance 2 sp")   # a bent spine moves whole
    assert _floats(s.eval("get_db spine:sp .path")) == pytest.approx(
        [42.12, 32.6, 78.64, 32.6, 78.64, 36.08])
    assert _floats(s.eval("get_db stub:sp/stub1 .points")) == pytest.approx(
        [42.12, 32.6, 61.12, 32.6])
    # back to the corner with the top end: the spine lies flat, on two points
    s.eval("move_spine_to_boundary -spine sp -moves {head top down 20}")
    assert _floats(s.eval("get_db spine:sp .path")) == pytest.approx([38.64, 32.6, 78.64, 32.6])
    assert set(member_axes(s.db).values()) == {"x"}


def test_command_reports_stops_and_outside(spine):
    s = spine
    s.eval("move_spine_to_boundary -spine sp -clearance {0 0 0 12.08} -moves {down 81 down 20}")
    text = out_of(s)
    assert "down 81: moved 80.92 to the signal track; head bottom at 78.64 19.08" in text
    assert "HT4-232" in text and "moved 5.76, stopped by the bottom clearance 12.08" in text
    s.eval("move_spine_to_boundary -spine sp -moves {left 30.24 up 31.68}")
    text = out_of(s)
    # the band's top stops the head, on the last track under it
    assert "HT4-232" in text and "head bottom at 47.88 39.24" in text
    assert "HT4-234" not in text


def test_command_errors_change_nothing(spine):
    s = spine
    before = (s.eval("get_db spine:sp .path"), centres(s))
    assert "HT4-233" in err(s, "move_spine_to_boundary -spine sp -moves "
                               "{down 69.4 left 5.76 up 20}")
    assert "HT4-230" in err(s, "move_spine_to_boundary -spine nope -moves {down 5}")
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {down}")
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {north 5}")
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {down -5}")
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {head left down 5}")
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {head top}")
    assert "HT4-001" in err(s, "move_spine_to_boundary -spine sp")
    assert "HT4-001" in err(s, "move_spine_to_boundary -moves {down 5}")
    assert "HT4-001" in err(s, "move_spine_to_boundary -spine sp -moves {down 5} "
                               "-clearance {1 2 3}")
    assert "HT4-001" in err(s, "move_spine_to_boundary -spine sp -moves {down 5} "
                               "-clearance {1 2 3 -4}")
    assert (s.eval("get_db spine:sp .path"), centres(s)) == before


def test_command_without_rows_or_tracks(tech_session, write_lef):
    s = build(tech_session, write_lef, rows=False, tracks=False)
    s.eval("move_spine_to_boundary -spine sp -moves {down 70 left 30}")
    text = out_of(s)
    assert "HT4-235" in text and "legalize_placement" not in text
    assert s.eval("get_db spine:sp .path") == "48.64 30 78.64 30 78.64 40"   # as asked
    s.eval("move_spine_to_boundary -spine sp -moves {up 20}")
    assert "HT4-232" in out_of(s)                     # the boundary stops the head
    assert s.eval("get_db spine:sp .path") == "48.64 40 48.64 30 78.64 30"
    # the other end is not stopped: backing up pushes it out of the die
    s.eval("move_spine_to_boundary -spine sp -moves {head top left 30}")
    text = out_of(s)
    assert s.eval("get_db spine:sp .path") == "48.64 70 48.64 30"
    assert "HT4-234" in text and "outside the design boundary: sp_L1_inv1" in text


def test_horizontal_spine(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF % ROWS, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC.replace('vertical', 'horizontal'), 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {10 10} -build -ref_cell INV_RP")
    sn = Snake(s.db, "sp")
    near(sn.body(), [(10, 18.64), (50, 18.64)])       # the stubs 3 columns above -location
    assert sn.ends == ("left", "right") and sn.end_name() == "left"
    assert "HT4-231" in err(s, "move_spine_to_boundary -spine sp -moves {head bottom up 5}")
    s.eval("move_spine_to_boundary -spine sp -moves {head right right 30 up 20}")
    pts = _floats(s.eval("get_db spine:sp .path"))
    assert len(pts) == 6 and pts[2:4] == pts[4:6][:1] + pts[2:4][1:]         # one corner
    assert float(s.eval("get_db stub:sp/stub2 .length")) == pytest.approx(19)
    assert float(s.eval("get_db stub:sp/stub1 .length")) == pytest.approx(19)


# -- what reads a bent spine -----------------------------------------------------------

def test_bent_stubs_in_the_gui_data_and_the_routers(spine):
    s = spine
    s.eval(f"move_spine_to_boundary -spine sp -moves {MOVES}")
    from core.gui.layout_data import load_spines
    stubs = load_spines(s.db)[0].stubs
    assert [n for n, _ in stubs] == ["stub1", "stub2", "stub2"]               # a line a stretch
    assert stubs[1][1] == pytest.approx([68.88, 30.6, 78.64, 30.6])
    assert stubs[2][1] == pytest.approx([78.64, 30.6, 78.64, 39.84])
    from core.commands.route_net import _stub_terminal
    stub = s.db.spine_stub_rows(s.db.spine_row("sp")["id"])[1]
    assert _stub_terminal(stub).point == pytest.approx((78.38, 30.6))
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    s.eval("route_final_stub -rule r")
    text = out_of(s)
    assert "HT4-193" in text and "sp/stub2" in text   # over the bend: not routed yet
    wires = [r for r in s.db.net_wire_rows() if r["kind"] == "stub"]
    assert [r["layer"] for r in wires] == ["IA"]      # stub1 lies flat now: on IA
    x1, y1, x2, y2 = _floats(wires[0]["rect"])
    assert (x1, x2) == pytest.approx((47.88, 66.88)) and y2 - y1 == pytest.approx(0.36)
