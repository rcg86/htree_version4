"""move_wire, stretch_wire, delete_wire, and the GUI's Tools > Move / Stretch /
Delete that run them."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

from test_route_net import spine  # noqa: F401  (a fixture)
from test_route_pin import err, out_of, placed  # noqa: F401  (placed is a fixture)


def rect(s, handle):
    return tuple(float(v) for v in s.eval(f"get_db {handle} .rect").split())


# -- the commands ------------------------------------------------------------------------

def test_move_wire(placed):
    placed.eval("route_pin -inst u1")
    a, b = rect(placed, "strap:u1/1"), rect(placed, "pin_wire:u1/A")
    out_of(placed)
    assert placed.eval("move_wire -wires {strap:u1/1 pin_wire:u1/A} -delta {1.5 -0.72}") == \
        "strap:u1/1 pin_wire:u1/A"
    assert "move_wire: moved 2 wire(s) by 1.5 -0.72" in out_of(placed)
    assert rect(placed, "strap:u1/1") == pytest.approx((a[0] + 1.5, a[1] - 0.72,
                                                        a[2] + 1.5, a[3] - 0.72))
    assert rect(placed, "pin_wire:u1/A") == pytest.approx((b[0] + 1.5, b[1] - 0.72,
                                                           b[2] + 1.5, b[3] - 0.72))
    assert placed.eval("get_db strap:u1/1 .net") == "VSS"   # net and layer stay
    # the strap's centre is off the IA tracks (-9.36 + k 0.72): reported
    placed.eval("move_wire -wires strap:u1/1 -delta {0 0.1}")
    assert "HT4-222" in out_of(placed)
    c = (rect(placed, "strap:u1/1")[1] + rect(placed, "strap:u1/1")[3]) / 2
    placed.eval(f"move_wire -wires strap:u1/1 -delta {{0 {round(5.04 - c, 6)}}}")
    assert "HT4-222" not in out_of(placed)                  # on the 5.04 track


def test_stretch_wire(placed):
    placed.eval("route_pin -inst u1")
    x1, y1, x2, y2 = rect(placed, "strap:u1/2")
    out_of(placed)
    assert placed.eval(f"stretch_wire -wire strap:u1/2 -edge right -to {x2 + 2}") == "strap:u1/2"
    assert "right edge" in out_of(placed) and rect(placed, "strap:u1/2") == \
        pytest.approx((x1, y1, x2 + 2, y2))
    placed.eval(f"stretch_wire -wire strap:u1/2 -edge left -to {x1 + 1}")
    assert "shorter by 1" in out_of(placed)
    assert rect(placed, "strap:u1/2") == pytest.approx((x1 + 1, y1, x2 + 2, y2))
    assert "HT4-221" in err(placed, f"stretch_wire -wire strap:u1/2 -edge left -to {x2 + 2}")
    assert rect(placed, "strap:u1/2") == pytest.approx((x1 + 1, y1, x2 + 2, y2))   # unchanged


def test_edit_errors(placed):
    placed.eval("route_pin -inst u1")
    assert "HT4-220" in err(placed, "move_wire -wires inst:u1 -delta {1 0}")
    assert "HT4-220" in err(placed, "move_wire -wires {strap:u1/1 strap:u1/99} -delta {1 0}")
    assert "HT4-001" in err(placed, "move_wire -wires strap:u1/1 -delta 1")
    assert "HT4-001" in err(placed, "stretch_wire -wire strap:u1/1 -edge middle -to 1")
    assert "HT4-001" in err(placed, "stretch_wire -wire {strap:u1/1 strap:u1/2} -edge top -to 9")
    a = rect(placed, "strap:u1/1")
    assert rect(placed, "strap:u1/1") == a                  # nothing moved by a failed call


# -- move_wire -next_track ------------------------------------------------------------------

def centre(s, handle):
    x1, y1, x2, y2 = rect(s, handle)
    return pytest.approx(((x1 + x2) / 2, (y1 + y2) / 2))


def test_next_track_without_a_track_assignment(placed):
    """IA tracks: y -9.36 + 0.72 k. The straps sit 0.169 above them."""
    placed.eval("route_pin -inst u1")
    a = rect(placed, "strap:u1/3")                            # centre y 2.329
    out_of(placed)
    assert placed.eval("move_wire -wires strap:u1/3 -next_track down") == "strap:u1/3"
    text = out_of(placed)
    assert "move_wire: moved 1 wire(s) to the next track down" in text
    assert "strap:u1/3 (signal): IA y 2.329 -> 2.16" in text and "HT4-" not in text
    n = rect(placed, "strap:u1/3")
    assert centre(placed, "strap:u1/3") == (1.56, 2.16)       # off the tracks: onto the next
    assert (n[0], n[2]) == (a[0], a[2]) and n[3] - n[1] == pytest.approx(0.72)   # size, x kept
    placed.eval("move_wire -wires strap:u1/3 -next_track down")   # twice: two tracks
    assert centre(placed, "strap:u1/3") == (1.56, 1.44)
    placed.eval("move_wire -wires {strap:u1/3 strap:u1/1} -next_track up")   # any net: any track
    assert centre(placed, "strap:u1/3") == (1.56, 2.16)
    assert centre(placed, "strap:u1/1") == (1.56, 5.76)       # 5.209 -> 5.76


def test_next_track_keeps_each_net_on_its_tracks(placed):
    """Pattern over the IA tracks: VDD_SOC y -9.36 -3.6 2.16 7.92, signal
    -7.92 -5.04 -2.16 0.72 3.6 6.48 9.36, VSS -6.48 -0.72 5.04 10.8."""
    placed.eval("route_pin -inst u1")                         # 1 VSS, 2 VDD_SOC, 3 SIGNAL
    placed.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    placed.db.set_net_wires("n1", [("extension", "IA", "0 8 6 8.36"),
                                   ("shield", "IA", "0 9 6 9.36", "VSS"),
                                   ("shield", "IA", "0 7 6 7.36", "VDD_SOC")])
    out_of(placed)
    wires = "strap:u1/1 strap:u1/2 strap:u1/3 net_wire:n1/1 net_wire:n1/2 net_wire:n1/3"
    assert placed.eval(f"move_wire -wires {{{wires}}} -next_track down") == wires
    text = out_of(placed)
    assert "strap:u1/1 (VSS): IA y 5.209 -> 5.04" in text
    assert "strap:u1/2 (VDD_SOC): IA y 3.769 -> 2.16" in text
    assert "strap:u1/3 (signal): IA y 2.329 -> 0.72" in text
    assert "net_wire:n1/1 (signal): IA y 8.18 -> 6.48" in text
    assert "net_wire:n1/2 (VSS): IA y 9.18 -> 5.04" in text   # a shield alone: its net's track
    assert "net_wire:n1/3 (VDD_SOC): IA y 7.18 -> 2.16" in text
    placed.eval("move_wire -wires {strap:u1/1 strap:u1/3} -next_track down")   # twice: two tracks
    assert centre(placed, "strap:u1/1") == (1.56, -0.72)      # the next VSS track
    assert centre(placed, "strap:u1/3") == (1.56, -2.16)      # the next signal track
    placed.eval("move_wire -wires {strap:u1/1 strap:u1/3} -next_track up")
    assert centre(placed, "strap:u1/1") == (1.56, 5.04) and centre(placed, "strap:u1/3") == (1.56, 0.72)
    # a strap route_net shorted to its net is a signal
    placed.db.conn.execute("UPDATE strap SET net = 'n1' WHERE inst = 'u1' AND seq = 3")
    placed.eval("move_wire -wires strap:u1/3 -next_track up")
    assert centre(placed, "strap:u1/3") == (1.56, 3.6)


def lines(s, *handles):
    """The centre line (y of a horizontal wire, x of a vertical one) of each."""
    found = []
    for h in handles:
        x1, y1, x2, y2 = rect(s, h)
        found.append(round((y1 + y2) / 2 if x2 - x1 >= y2 - y1 else (x1 + x2) / 2, 6))
    return found


def wire_at(c, lo=0, hi=6, w=0.36):
    return f"{lo} {round(c - w / 2, 6)} {hi} {round(c + w / 2, 6)}"


GROUP = "net_wire:n1/1", "net_wire:n1/2", "net_wire:n1/3"     # signal, VDD_SOC and VSS shield


def test_next_track_moves_a_signal_with_its_shields(placed):
    """Signal on y 6.48 between its VDD_SOC shield (7.92) and VSS shield
    (5.04). One signal track down, 3.6, the power tracks beside it are the
    other way round: VSS 5.04 above, VDD_SOC 2.16 below."""
    placed.eval("route_pin -inst u1")
    placed.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    placed.db.set_net_wires("n1", [("wire", "IA", wire_at(6.48)),
                                   ("shield", "IA", wire_at(7.92, -1, 7), "VDD_SOC"),
                                   ("shield", "IA", wire_at(5.04, -1, 3), "VSS"),
                                   ("shield", "IA", wire_at(5.04, 4, 7), "VSS"),   # cut in two
                                   ("cross", "IA/IB", "1 6.3 1.36 6.66")])
    spans = [(r[0], r[2]) for r in (rect(placed, f"net_wire:n1/{k}") for k in (1, 2, 3, 4))]
    out_of(placed)
    # the signal alone is given: its shields go with it
    moved = placed.eval("move_wire -wires net_wire:n1/1 -next_track down")
    assert set(placed.split_list(moved)) == {"net_wire:n1/1", "net_wire:n1/2"}
    text = out_of(placed)
    assert "moved 2 wire(s) to the next track down" in text
    assert "net_wire:n1/1 (signal): IA y 6.48 -> 3.6; net_wire:n1/3 (VSS shield) stays on y 5.04; " \
           "net_wire:n1/4 (VSS shield) stays on y 5.04" in text
    assert "net_wire:n1/2 (VDD_SOC shield of net_wire:n1/1): IA y 7.92 -> 2.16" in text
    assert lines(placed, *GROUP, "net_wire:n1/4") == [3.6, 2.16, 5.04, 5.04]
    assert [(r[0], r[2]) for r in (rect(placed, f"net_wire:n1/{k}") for k in (1, 2, 3, 4))] == spans
    # again, with the shields and a crossing box selected too: the same group move
    placed.eval(f"move_wire -wires {{{' '.join(GROUP)} net_wire:n1/4 net_wire:n1/5}} -next_track down")
    assert lines(placed, *GROUP, "net_wire:n1/4") == [0.72, 2.16, -0.72, -0.72]
    # the box goes the signal's distance; it was not given the first time, so it stayed then
    assert rect(placed, "net_wire:n1/5") == pytest.approx((1, 3.42, 1.36, 3.78))
    placed.eval("move_wire -wires net_wire:n1/1 -next_track up")
    placed.eval("move_wire -wires net_wire:n1/1 -next_track up")
    assert lines(placed, *GROUP, "net_wire:n1/4") == [6.48, 7.92, 5.04, 5.04]   # back where it was
    # a shield given without its signal steps alone, to the next track of its net
    placed.eval("move_wire -wires net_wire:n1/2 -next_track down")
    assert lines(placed, *GROUP) == [6.48, 2.16, 5.04]
    # the last signal track up, 9.36, has VSS 10.8 above but no VDD_SOC track below at 1.44
    placed.eval("move_wire -wires net_wire:n1/2 -next_track up")
    out_of(placed)
    assert placed.eval("move_wire -wires net_wire:n1/1 -next_track up") != ""
    assert lines(placed, *GROUP, "net_wire:n1/4") == [9.36, 7.92, 10.8, 10.8]
    assert placed.eval("move_wire -wires net_wire:n1/1 -next_track up") == ""
    assert "net_wire:n1/1 (no signal track of IA up of y 9.36)" in out_of(placed)


def test_next_track_group_rules(placed):
    placed.eval("route_pin -inst u1")
    db = placed.db
    # no track assignment: the shields keep their side, the group moves a track
    db.set_net_wires("n1", [("wire", "IA", wire_at(0.72)), ("shield", "IA", wire_at(2.16), "VDD_SOC"),
                            ("shield", "IA", wire_at(-0.72), "VSS")])
    placed.eval("move_wire -wires net_wire:n1/1 -next_track up")
    assert lines(placed, *GROUP) == [1.44, 2.88, 0]
    # a stub and its stub shields; a net's second wire keeps its own shields
    db.set_net_wires("n1", [("stub", "IA", wire_at(0.72)), ("stub_shield", "IA", wire_at(2.16), "VDD_SOC"),
                            ("stub_shield", "IA", wire_at(-0.72), "VSS")], stub=True)
    db.set_net_wires("n1", [("wire", "IA", wire_at(6.48)), ("shield", "IA", wire_at(7.92), "VDD_SOC"),
                            ("shield", "IA", wire_at(5.04), "VSS"),
                            ("wire", "IA", wire_at(-5.04)), ("shield", "IA", wire_at(-3.6), "VDD_SOC"),
                            ("shield", "IA", wire_at(-6.48), "VSS"),
                            ("wire", "IA", wire_at(3.6, 20, 30)),      # not beside any shield
                            ("extension", "IA", wire_at(9.36))])       # not a wire with shields
    names = [f"net_wire:{r['net']}/{r['seq']}"                 # the stub's under n1_stub
             for r in db.stub_wire_rows("n1") + db.net_wire_rows("n1")]
    stub, stub_shields, first, second = names[0], names[1:3], names[3:6], names[6:9]
    placed.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    before = lines(placed, *names)
    out_of(placed)
    assert set(placed.split_list(placed.eval(f"move_wire -wires {stub} -next_track up"))) == \
        {stub, stub_shields[1]}
    assert lines(placed, stub, *stub_shields) == [3.6, 2.16, 5.04]
    assert lines(placed, *names[3:]) == before[3:]            # the net's other wires stay
    placed.eval(f"move_wire -wires {second[0]} -next_track down")
    assert lines(placed, *second) == [-7.92, -9.36, -6.48]
    assert lines(placed, *first) == before[3:6]
    for alone in names[9:]:                                   # no shields: a plain step
        assert placed.eval(f"move_wire -wires {alone} -next_track down") == alone
    assert lines(placed, *names[9:]) == [0.72, 6.48]
    assert lines(placed, *first) == before[3:6]
    # shields that are not on tracks beside the signal: the group stays
    db.set_net_wires("n2", [("wire", "IA", wire_at(6.48)), ("shield", "IA", wire_at(7.5), "VDD_SOC")])
    out_of(placed)
    assert placed.eval("move_wire -wires net_wire:n2/1 -next_track down") == ""
    assert "with a track of each of its shields' nets beside it" in out_of(placed)
    assert lines(placed, "net_wire:n2/1", "net_wire:n2/2") == [6.48, 7.5]
    # a pattern where the next signal track has no VDD_SOC track beside it: the one after
    placed.eval("assign_track_for_route -net {VDD_SOC - VSS - -} -layer IA")
    # tracks y -9.36 + 0.72 k: k % 5 = 0 VDD_SOC, 2 VSS, else signal
    db.set_net_wires("n3", [("wire", "IA", wire_at(-8.64)), ("shield", "IA", wire_at(-9.36), "VDD_SOC"),
                            ("shield", "IA", wire_at(-7.92), "VSS")])
    placed.eval("move_wire -wires net_wire:n3/1 -next_track up")
    assert lines(placed, "net_wire:n3/1", "net_wire:n3/2", "net_wire:n3/3") == [-5.04, -5.76, -4.32]


def test_next_track_wires_that_stay(placed):
    placed.eval("route_pin -inst u1")
    placed.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    placed.db.set_net_wires("n1", [("wire", "IB", "5 0 5.36 6"), ("cross", "IA/IB", "1 2 1.36 2.72"),
                                   ("shield", "IA", "0 9 6 9.36", "VDDX")])
    before = {h: rect(placed, h) for h in ("strap:u1/2", "net_wire:n1/1", "net_wire:n1/2")}
    out_of(placed)
    # the last VDD_SOC track is y 7.92: one step up, then none
    assert placed.eval("move_wire -wires strap:u1/2 -next_track up") == "strap:u1/2"
    assert centre(placed, "strap:u1/2") == (1.56, 7.92)
    out_of(placed)
    assert placed.eval("move_wire -wires {strap:u1/2 strap:u1/3} -next_track up") == "strap:u1/3"
    text = out_of(placed)
    assert "moved 1 wire(s) to the next track up" in text and "HT4-226" in text
    assert "strap:u1/2 (no VDD_SOC track of IA up of y 7.92)" in text
    assert centre(placed, "strap:u1/2") == (1.56, 7.92)
    # along its length, a layer without tracks, a net without a track, a box alone
    assert placed.eval("move_wire -wires {strap:u1/1 net_wire:n1/1 net_wire:n1/2 net_wire:n1/3} "
                       "-next_track left") == ""
    text = out_of(placed)
    assert "moved 0 wire(s)" in text
    assert "strap:u1/1 (runs left to right: up or down moves it a track)" in text
    assert "net_wire:n1/1 (IB has no DEF TRACKS X)" in text
    assert "net_wire:n1/2 (a crossing box has no track: select it with its wire)" in text
    assert placed.eval("move_wire -wires {net_wire:n1/1 net_wire:n1/3} -next_track down") == ""
    text = out_of(placed)
    assert "net_wire:n1/1 (runs up and down: left or right moves it a track)" in text
    assert "net_wire:n1/3 (IA has no VDDX track)" in text
    assert rect(placed, "net_wire:n1/1") == before["net_wire:n1/1"]
    # a crossing box goes with its wire; not when the wires move different distances
    placed.eval("move_wire -wires {strap:u1/3 net_wire:n1/2} -next_track down")
    step = centre(placed, "strap:u1/3").expected[1] - 3.6     # it was on y 3.6
    assert rect(placed, "net_wire:n1/2") == pytest.approx((1, 2 + step, 1.36, 2.72 + step))
    box = rect(placed, "net_wire:n1/2")
    assert placed.eval("move_wire -wires {strap:u1/3 strap:u1/1 net_wire:n1/2} -next_track down") \
        == "strap:u1/3 strap:u1/1"
    assert "they all move the same distance" in out_of(placed)
    assert rect(placed, "net_wire:n1/2") == box


def test_move_wire_each_by_its_own_delta(placed):
    placed.eval("route_pin -inst u1")
    a, b = rect(placed, "strap:u1/1"), rect(placed, "strap:u1/2")
    out_of(placed)
    placed.eval("move_wire -wires {strap:u1/1 strap:u1/2} -delta {{0 0.72} {1 -1.44}}")
    assert "moved 2 wire(s) strap:u1/1 by 0 0.72, strap:u1/2 by 1 -1.44" in out_of(placed)
    assert rect(placed, "strap:u1/1") == pytest.approx((a[0], a[1] + 0.72, a[2], a[3] + 0.72))
    assert rect(placed, "strap:u1/2") == pytest.approx((b[0] + 1, b[1] - 1.44, b[2] + 1, b[3] - 1.44))
    placed.eval("move_wire -wires strap:u1/1 -delta {{0 -0.72}}")
    assert rect(placed, "strap:u1/1") == pytest.approx(a)
    for bad in ("-delta {{0 1}}", "-delta {{0 1} {0 2} {0 3}}", "-delta {{0 1} {0 x}}",
                "-delta {0 1} -next_track up", "-next_track sideways", ""):
        assert "HT4-001" in err(placed, f"move_wire -wires {{strap:u1/1 strap:u1/2}} {bad}")
    assert rect(placed, "strap:u1/1") == pytest.approx(a)     # nothing moved by a failed call


# -- delete_wire ----------------------------------------------------------------------------

def table(s, name):
    return [dict(r) for r in s.db.conn.execute(f"SELECT * FROM {name} ORDER BY id")]


def test_delete_wire_and_undo(placed):
    placed.eval("route_pin -inst u1")
    placed.db.set_net_wires("manual", [("wire", "IB", "5 0 5.36 6"), ("wire", "IA", "0 3 6 3.36")])
    before = {t: table(placed, t) for t in ("strap", "pin_wire", "net_wire")}
    out_of(placed)
    assert placed.eval("delete_wire -wires {net_wire:manual/1 pin_wire:u1/Y}") == \
        "net_wire:manual/1 pin_wire:u1/Y"
    text = out_of(placed)
    assert "delete_wire: deleted 2 wire(s)" in text and "cannot stay" not in text
    assert placed.eval("get_db net_wires") == "net_wire:manual/2"     # the other keeps its handle
    assert "pin_wire:u1/Y" not in placed.eval("get_db pin_wires")
    assert len(table(placed, "strap")) == 7                   # the strap it ended on stays
    assert "HT4-022" in err(placed, "get_db net_wire:manual/1 .rect")     # it is gone
    assert "HT4-220" in err(placed, "delete_wire -wires net_wire:manual/1")
    placed.eval("delete_wire -wires net_wire:manual/2")
    out_of(placed)
    # -undo: the last delete first, each wire back as it was (row, handle, order)
    assert placed.eval("delete_wire -undo") == "net_wire:manual/2"
    assert "delete_wire: put back 1 wire(s): net_wire:manual/2" in out_of(placed)
    assert placed.eval("delete_wire -undo") == "pin_wire:u1/Y net_wire:manual/1"
    assert {t: table(placed, t) for t in before} == before
    assert "HT4-223" in err(placed, "delete_wire -undo")      # nothing left to put back


def test_delete_strap_takes_its_pin_wires_and_auto_vias(placed):
    placed.eval("route_pin -inst u1")
    seq = placed.db.pin_wire_row("u1", "A")["strap"]
    placed.db.set_net_wires(f"auto_via:strap:u1/{seq}", [("via", "IA/IB", "1 1 1.36 1.36", "x")])
    before = {t: table(placed, t) for t in ("strap", "pin_wire", "net_wire")}
    out_of(placed)
    gone = list(placed.split_list(placed.eval(f"delete_wire -wires strap:u1/{seq}")))
    assert gone == [f"strap:u1/{seq}", "pin_wire:u1/A", f"net_wire:auto_via:strap:u1/{seq}/1"]
    text = out_of(placed)
    assert "deleted 1 wire(s)" in text and "and 2 that cannot stay without them" in text
    assert "pin_wire:u1/A" in text
    straps = placed.split_list(placed.eval("get_db straps"))
    assert len(straps) == 6 and f"strap:u1/{seq}" not in straps    # numbers not closed up
    assert placed.db.pin_wire_row("u1", "A") is None and table(placed, "net_wire") == []
    assert len(table(placed, "pin_wire")) == 3                # the other pin wires stay
    assert list(placed.split_list(placed.eval("delete_wire -undo"))) == gone
    assert {t: table(placed, t) for t in before} == before


def test_delete_wire_errors_and_undo_refused(placed, tmp_path):
    placed.eval("route_pin -inst u1")
    assert "HT4-001" in err(placed, "delete_wire")
    assert "HT4-001" in err(placed, "delete_wire -wires strap:u1/1 -undo")
    assert "HT4-220" in err(placed, "delete_wire -wires {strap:u1/1 inst:u1}")
    assert "HT4-220" in err(placed, "delete_wire -wires {}")
    assert len(table(placed, "strap")) == 7                   # nothing deleted by a failed call
    assert "HT4-223" in err(placed, "delete_wire -undo")
    # route_pin again makes the strap anew: the deleted one has no place to go back to
    placed.eval("delete_wire -wires strap:u1/1")
    placed.eval("route_pin -inst u1")
    out_of(placed)
    assert placed.eval("delete_wire -undo") == ""
    text = out_of(placed)
    assert "put back 0 wire(s)" in text and "HT4-224" in text and "strap:u1/1" in text
    assert len(table(placed, "strap")) == 7
    # a net wire whose number a new wire took
    placed.db.set_net_wires("manual", [("wire", "IB", "5 0 5.36 6")])
    placed.eval("delete_wire -wires net_wire:manual/1")
    placed.db.set_net_wires("manual", [("wire", "IA", "0 3 6 3.36")])
    placed.eval("delete_wire -undo")
    assert "HT4-224" in out_of(placed)
    assert [r["layer"] for r in table(placed, "net_wire")] == ["IA"]
    # the deleted wires are session state: not in a saved database, gone after read_db
    placed.eval("delete_wire -wires strap:u1/2")
    placed.eval(f"write_db {tmp_path}/s.db")
    placed.eval(f"read_db {tmp_path}/s.db")
    assert len(table(placed, "strap")) == 6
    assert "HT4-223" in err(placed, "delete_wire -undo")


def test_route_net_after_a_deleted_strap(spine):
    spine.eval("route_pin -inst *sp_*")
    seq = spine.db.pin_wire_row("sp_L2_inv1", "A")["strap"]
    power = next(r for r in spine.db.strap_rows("sp_L2_inv1") if r["net"] == "VSS")
    spine.eval(f"delete_wire -wires {{strap:sp_L2_inv1/{seq} strap:sp_L2_inv1/{power['seq']}}}")
    out_of(spine)
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield")  # the pin is as before route_pin
    text = out_of(spine)
    assert "route_pin is not done on sp_L2_inv1 (pin A)" in text
    assert "load sp_L2_inv1/A: ends near the pin, not connected" in text
    assert "driver sp_L1_inv1/Y (strap 3): connected" in text


# -- the GUI toolbox ------------------------------------------------------------------------

@pytest.fixture
def window(placed):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QRectF, Qt
    from core.gui import app
    from core.gui.canvas import scene
    placed.eval("route_pin -inst u1")
    placed.eval("gui_show")
    w = app.window()
    w.resize(1000, 800)
    w.canvas.fitInView(QRectF(scene(-2, 7), scene(6, -4)), Qt.KeepAspectRatio)
    out_of(placed)
    yield placed, w
    app.close()


def _at(w, x, y):
    from core.gui.canvas import scene
    return w.canvas.mapFromScene(scene(x, y))


def _drag(w, a, b, mods=None):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    a, b = QPointF(a), QPointF(b)
    vp = w.canvas.viewport()
    send = lambda t, p, btn, btns: QApplication.sendEvent(
        vp, QMouseEvent(t, p, p, btn, btns, mods if mods is not None else Qt.NoModifier))
    send(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton)
    for i in range(1, 9):
        send(QEvent.MouseMove, a + (b - a) * (i / 8), Qt.NoButton, Qt.LeftButton)
    send(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)


def test_tools_move_drags_a_wire_onto_a_track(window):
    s, w = window
    w.act_tool_move.setChecked(True)
    assert w.tools_button.text() == "Tools: Move" and w.canvas.edit["mode"] == "move"
    x1, y1, x2, y2 = rect(s, "strap:u1/1")
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    transform = w.canvas.transform()
    _drag(w, _at(w, cx, cy), _at(w, cx + 1.0, cy - 1.5))
    assert w.canvas.transform() == transform                  # the view stays
    n = rect(s, "strap:u1/1")
    assert n[0] - x1 == pytest.approx(1.0, abs=0.02)          # along: as dragged (grid)
    c = (n[1] + n[3]) / 2
    k = (c + 9.36) / 0.72
    assert k == pytest.approx(round(k), abs=1e-6)             # across: onto an IA track
    assert abs(c - (cy - 1.5)) <= 0.36 + 1e-6
    assert n[2] - n[0] == pytest.approx(x2 - x1) and n[3] - n[1] == pytest.approx(y2 - y1)
    text = s.out.getvalue()
    assert "move_wire -wires {strap:u1/1} -delta {0.99" in text   # echoed with its output
    assert "move_wire: moved 1 wire(s)" in text
    w.act_undo_edit.trigger()                                 # Undo Edit: back again
    assert rect(s, "strap:u1/1") == pytest.approx((x1, y1, x2, y2))
    assert not w.act_undo_edit.isEnabled()


def test_ctrl_drag_in_a_tool_only_prints_the_box(window):
    from PySide6.QtCore import Qt
    s, w = window
    x1, y1, x2, y2 = rect(s, "strap:u1/1")
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    for act in (w.act_tool_move, w.act_tool_stretch):
        act.setChecked(True)
        s.out.seek(0)
        s.out.truncate()
        # from the middle of the wire (Move) and from its right edge (Stretch)
        start = (cx, cy) if act is w.act_tool_move else (x2, cy)
        _drag(w, _at(w, *start), _at(w, start[0] + 1.0, cy - 1.5), mods=Qt.ControlModifier)
        assert rect(s, "strap:u1/1") == pytest.approx((x1, y1, x2, y2))     # not edited
        assert not w.canvas.editing() and not w.undo_edits
        lines = s.out.getvalue().splitlines()
        assert len(lines) == 1
        box = [float(v) for v in lines[0][1:-1].split()]
        assert box == pytest.approx([start[0], cy - 1.5, start[0] + 1.0, cy], abs=0.05)
        assert s.eval("get_db selected") == ""
    # a Ctrl+click on the wire picks it, as the tool does
    _drag(w, _at(w, cx, cy), _at(w, cx, cy), mods=Qt.ControlModifier)
    assert s.eval("get_db selected") == "strap:u1/1"


def test_tools_move_takes_the_selection(window):
    s, w = window
    w.act_edit_snap.setChecked(False)
    w.on_select(["strap:u1/1", "strap:u1/2", "inst:u1"], "replace")
    a, b = rect(s, "strap:u1/1"), rect(s, "strap:u1/2")
    w.act_tool_move.setChecked(True)
    cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    _drag(w, _at(w, cx, cy), _at(w, cx, cy + 2))
    dy = rect(s, "strap:u1/1")[1] - a[1]
    assert dy == pytest.approx(2, abs=0.05)                   # no snap: as dragged
    assert rect(s, "strap:u1/2")[1] - b[1] == pytest.approx(dy)   # both selected wires
    assert s.eval("get_db inst:u1 .location") == "0 0"       # the instance is not a wire


def _shift(w, key):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    keys = {"up": Qt.Key_Up, "down": Qt.Key_Down, "left": Qt.Key_Left, "right": Qt.Key_Right}
    QApplication.sendEvent(w.canvas, QKeyEvent(QEvent.KeyPress, keys[key], Qt.ShiftModifier))


def test_tools_move_shift_arrow_moves_the_selection_a_track(window):
    s, w = window
    s.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    out_of(s)
    a, b = rect(s, "strap:u1/3"), rect(s, "strap:u1/1")       # SIGNAL y 2.329, VSS y 5.209
    w.on_select(["strap:u1/3", "strap:u1/1", "inst:u1"], "replace")
    h0 = w.canvas.horizontalScrollBar().value(), w.canvas.verticalScrollBar().value()
    _shift(w, "down")                                         # not the Move tool: pans
    assert "move_wire" not in s.out.getvalue() and rect(s, "strap:u1/3") == a
    w.canvas.horizontalScrollBar().setValue(h0[0])
    w.canvas.verticalScrollBar().setValue(h0[1])
    w.act_tool_move.setChecked(True)
    transform = w.canvas.transform()
    _shift(w, "down")
    text = s.out.getvalue()
    assert "move_wire -wires {strap:u1/3 strap:u1/1} -next_track down" in text
    assert centre(s, "strap:u1/3") == (1.56, 0.72)            # the next signal track
    assert centre(s, "strap:u1/1") == (1.56, 5.04)            # the next VSS track
    item = w.canvas.owner_items["strap:u1/3"][0]
    assert w.canvas._rect_of(item) == pytest.approx(rect(s, "strap:u1/3"))   # redrawn there
    assert w.canvas.transform() == transform                  # the view stays, no pan
    assert (w.canvas.horizontalScrollBar().value(), w.canvas.verticalScrollBar().value()) == h0
    assert s.eval("get_db selected") == "strap:u1/3 strap:u1/1 inst:u1"
    assert s.eval("get_db inst:u1 .location") == "0 0"
    _shift(w, "down")                                         # twice: two tracks
    assert centre(s, "strap:u1/3") == (1.56, -2.16) and centre(s, "strap:u1/1") == (1.56, -0.72)
    _shift(w, "left")                                         # along the wires: nothing runs
    assert "Move: not moved: strap:u1/3 (runs left to right" in w.statusBar().currentMessage()
    assert s.out.getvalue().count("move_wire -wires") == 2 and len(w.undo_edits) == 2
    w.undo_edit()                                             # one key press an undo
    assert centre(s, "strap:u1/3") == (1.56, 0.72) and centre(s, "strap:u1/1") == (1.56, 5.04)
    assert "move_wire -wires {strap:u1/3 strap:u1/1} -delta {{0 2.88} {0 5.76}}" in s.out.getvalue()
    w.undo_edit()                                             # back off the tracks, as it was
    assert rect(s, "strap:u1/3") == pytest.approx(a) and rect(s, "strap:u1/1") == pytest.approx(b)
    assert w.canvas._rect_of(item) == pytest.approx(a)
    assert not w.act_undo_edit.isEnabled()


def test_tools_move_shift_arrow_takes_the_shields_of_a_signal(window):
    s, w = window
    s.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    s.db.set_net_wires("n1", [("wire", "IA", wire_at(6.48)), ("shield", "IA", wire_at(7.92), "VDD_SOC"),
                              ("shield", "IA", wire_at(5.04), "VSS")])
    w.refresh()
    out_of(s)
    before = [rect(s, h) for h in GROUP]
    w.on_select(["net_wire:n1/1"], "replace")                 # the signal only
    w.act_tool_move.setChecked(True)
    _shift(w, "down")
    assert "move_wire -wires {net_wire:n1/1} -next_track down" in s.out.getvalue()
    assert lines(s, *GROUP) == [3.6, 2.16, 5.04]
    for h in GROUP:                                           # the shield is redrawn too
        assert w.canvas._rect_of(w.canvas.owner_items[h][0]) == pytest.approx(rect(s, h))
    assert s.eval("get_db selected") == "net_wire:n1/1"
    _shift(w, "down")
    assert lines(s, *GROUP) == [0.72, 2.16, -0.72]
    w.undo_edit()                                             # the group back, a key press an undo
    assert lines(s, *GROUP) == [3.6, 2.16, 5.04]
    w.undo_edit()
    assert [rect(s, h) for h in GROUP] == [pytest.approx(r) for r in before]
    for h in GROUP:
        assert w.canvas._rect_of(w.canvas.owner_items[h][0]) == pytest.approx(rect(s, h))
    assert not w.undo_edits


def test_tools_move_shift_arrow_needs_a_selected_wire(window):
    s, w = window
    w.act_tool_move.setChecked(True)
    for sel in ([], ["inst:u1"]):
        w.on_select(sel, "replace")
        _shift(w, "up")
        assert "Move: select a wire or a via first" in w.statusBar().currentMessage()
    assert "move_wire" not in s.out.getvalue() and not w.undo_edits
    # the last signal track up is y 9.36... with no assignment the last track is 11.52
    w.on_select(["strap:u1/1"], "replace")
    for _ in range(12):
        _shift(w, "up")
    assert centre(s, "strap:u1/1") == (1.56, 11.52) and len(w.undo_edits) == 9
    assert "no signal track of IA up of y 11.52" in w.statusBar().currentMessage()


def test_tools_stretch_drags_an_edge(window):
    s, w = window
    w.act_tool_stretch.setChecked(True)
    x1, y1, x2, y2 = rect(s, "strap:u1/3")
    cy = (y1 + y2) / 2
    assert w.canvas.edge_at(_at(w, x2, cy))[1] == "right"
    _drag(w, _at(w, x2, cy), _at(w, x2 + 1.234, cy))
    n = rect(s, "strap:u1/3")
    assert (n[0], n[1], n[3]) == pytest.approx((x1, y1, y2))
    assert n[2] - x2 == pytest.approx(1.234, abs=0.03)
    assert "stretch_wire -wire strap:u1/3 -edge right -to" in s.out.getvalue()
    w.undo_edit()
    assert rect(s, "strap:u1/3") == pytest.approx((x1, y1, x2, y2))


def test_tools_stretch_snaps_to_another_edge(window):
    s, w = window
    w.act_tool_stretch.setChecked(True)
    x1, y1, x2, y2 = rect(s, "strap:u1/3")
    target = rect(s, "pin_wire:u1/A")                         # a vertical pin wire's left edge
    cy = (y1 + y2) / 2
    _drag(w, _at(w, x2, cy), _at(w, target[0] + 0.02, cy))
    assert rect(s, "strap:u1/3")[2] == pytest.approx(target[0])


def test_tools_click_selects_and_select_mode(window):
    s, w = window
    w.act_tool_move.setChecked(True)
    a = rect(s, "strap:u1/1")
    p = _at(w, (a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    _drag(w, p, p)                                            # a click, no drag: selects
    assert s.eval("get_db selected") == "strap:u1/1"
    assert rect(s, "strap:u1/1") == a
    w.act_ruler.setChecked(True)                              # the ruler ends the edit mode
    assert w.act_tool_select.isChecked() and w.canvas.edit["mode"] is None
    w.act_tool_stretch.setChecked(True)                       # and an edit mode the ruler
    assert not w.act_ruler.isChecked()


def test_tools_delete_deletes_the_selected_wires(window):
    s, w = window
    seq = s.db.pin_wire_row("u1", "A")["strap"]
    strap = f"strap:u1/{seq}"
    w.act_delete.trigger()                                    # nothing selected: nothing run
    assert "select a wire, strap or pin wire first" in w.statusBar().currentMessage()
    assert "delete_wire" not in s.out.getvalue()
    w.on_select(["inst:u1"], "replace")                       # an instance is not deleted
    w.act_delete.trigger()
    assert "instances, pins, ports and stubs are not deleted" in w.statusBar().currentMessage()
    assert "delete_wire" not in s.out.getvalue() and s.db.inst_row("u1") is not None
    w.on_select([strap, "pin_wire:u1/Y", "inst:u1"], "replace")
    transform = w.canvas.transform()
    drawn = set(w.canvas.owner_items)
    w.act_delete.trigger()
    text = s.out.getvalue()
    assert f"delete_wire -wires {{{strap} pin_wire:u1/Y}}" in text    # echoed with its output
    assert "delete_wire: deleted 2 wire(s)" in text
    assert s.db.strap_row("u1", seq) is None and s.db.pin_wire_row("u1", "Y") is None
    assert s.db.pin_wire_row("u1", "A") is None               # it ended on the strap
    # ... and the vias of the two pin wires (pin to wire, wire to strap) with them:
    # 2 of A, 3 of Y, whose pin is two rectangles
    assert drawn - set(w.canvas.owner_items) == {strap, "pin_wire:u1/Y", "pin_wire:u1/A"} | \
        {f"via:SIGNAL/{k}" for k in range(1, 6)}
    assert w.canvas.transform() == transform                  # the view stays
    assert s.eval("get_db selected") == "inst:u1" and s.db.inst_row("u1") is not None
    assert w.act_undo_edit.isEnabled()
    w.act_undo_edit.trigger()                                 # Undo Edit: delete_wire -undo
    assert "delete_wire -undo" in s.out.getvalue()
    assert s.db.strap_row("u1", seq) is not None and len(s.db.pin_wire_rows("u1")) == 4
    assert set(w.canvas.owner_items) == drawn and w.canvas.transform() == transform
    assert all(item.isVisible() for h in (strap, "pin_wire:u1/A") for item in w.canvas.owner_items[h])
    assert not w.act_undo_edit.isEnabled()


def test_tools_delete_then_undo_in_order(window):
    s, w = window
    a = rect(s, "strap:u1/1")
    w.act_edit_snap.setChecked(False)
    w.act_tool_move.setChecked(True)
    cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    _drag(w, _at(w, cx, cy), _at(w, cx, cy + 2))              # move it, then delete it
    moved = rect(s, "strap:u1/1")
    w.on_select(["strap:u1/1"], "replace")
    w.act_delete.trigger()
    assert s.db.strap_row("u1", 1) is None
    w.undo_edit()                                             # back where it was moved to
    assert rect(s, "strap:u1/1") == moved
    item = w.canvas.owner_items["strap:u1/1"][0]
    assert w.canvas._rect_of(item) == pytest.approx(moved)
    w.undo_edit()                                             # then the move
    assert rect(s, "strap:u1/1") == pytest.approx(a)
    assert w.canvas._rect_of(w.canvas.owner_items["strap:u1/1"][0]) == pytest.approx(a)


# -- auto vias while stretching ------------------------------------------------------------

def vias(s, handle):
    return sorted((r["layer"], r["rect"], r["shield_net"])
                  for r in s.db.net_wire_rows(f"auto_via:{handle}"))


def test_stretch_auto_via_depth(placed):
    # the VSS pin wire on H2 crosses the VSS straps on IA: 3 layers up (H2 G1 G2 IA)
    placed.eval("route_pin -inst u1")
    attr = "route_auto_via_insertion_during_stretch"
    assert placed.eval(f"get_db {attr}") == "1"
    placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 0.4")    # off both straps
    for depth in ("1", "2"):                                  # IA is too far: no via
        placed.eval(f"set_db {attr} {depth}")
        placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 5.569")
        assert vias(placed, "pin_wire:u1/VSS") == []
        placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 0.4")
    placed.eval(f"set_db {attr} 3")
    out_of(placed)
    placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 5.569")
    text = out_of(placed)
    assert vias(placed, "pin_wire:u1/VSS") == [("H2/IA", "1.8 0.529 2.2 1.249", "VSS"),
                                               ("H2/IA", "1.8 4.849 2.2 5.569", "VSS")]
    assert "auto via H2/IA {1.8 4.849 2.2 5.569} to strap:u1/1" in text
    # the signal pin wires cross straps too, but SIGNAL connects to nothing
    placed.eval("stretch_wire -wire pin_wire:u1/A -edge top -to 0.4")
    placed.eval("stretch_wire -wire pin_wire:u1/A -edge top -to 5.569")
    assert vias(placed, "pin_wire:u1/A") == []
    # shortened again: the via it left goes, the one it still covers stays
    placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 3")
    assert "no longer on the wire removed" in out_of(placed)
    assert vias(placed, "pin_wire:u1/VSS") == [("H2/IA", "1.8 0.529 2.2 1.249", "VSS")]
    placed.eval(f"set_db {attr} 0")                           # 0: none at all
    placed.eval("stretch_wire -wire pin_wire:u1/VSS -edge top -to 5.569")
    assert vias(placed, "pin_wire:u1/VSS") == [("H2/IA", "1.8 0.529 2.2 1.249", "VSS")]
    assert "HT4-141" in err(placed, f"set_db {attr} 1.5")


def test_stretch_auto_via_next_layer_same_net_only(placed):
    placed.eval("route_pin -inst u1")
    placed.db.set_net_wires("manual", [("shield", "IB", "5 0 5.36 6", "VSS"),
                                       ("shield", "IB", "6 0 6.36 6", "VDD_SOC")])
    out_of(placed)
    placed.eval("stretch_wire -wire strap:u1/1 -edge right -to 7")   # VSS strap over both
    assert vias(placed, "strap:u1/1") == [("IA/IB", "5 4.849 5.36 5.569", "VSS")]
    assert "auto via IA/IB {5 4.849 5.36 5.569} to net_wire:manual/1" in out_of(placed)
    placed.eval("stretch_wire -wire strap:u1/1 -edge right -to 7.5")   # nothing new crossed
    assert len(vias(placed, "strap:u1/1")) == 1
    placed.eval("move_wire -wires strap:u1/1 -delta {0 0.72}")          # moved: stale, gone
    assert "removed the auto vias of strap:u1/1" in out_of(placed)
    assert vias(placed, "strap:u1/1") == []
    placed.eval("move_wire -wires strap:u1/1 -delta {0 -0.72}")
    placed.eval("stretch_wire -wire strap:u1/1 -edge right -to 3.12")
    placed.eval("stretch_wire -wire strap:u1/1 -edge right -to 7")
    assert len(vias(placed, "strap:u1/1")) == 1
    placed.eval("route_pin -inst u1")                         # the straps are rebuilt
    assert vias(placed, "strap:u1/1") == []
    from core.gui.layout_data import load_layout             # drawn as a crossing box
    placed.eval("stretch_wire -wire strap:u1/1 -edge right -to 7")
    (via,) = [w for w in load_layout(placed.db).net_wires
              if w.handle.startswith("net_wire:auto_via:")]
    assert via.outline and via.label == "VSS" and via.cls == "ground" and via.layer == "IA"


def test_gui_stretch_draws_the_auto_via(window):
    s, w = window
    s.db.set_net_wires("manual", [("shield", "IB", "5 0 5.36 6", "VSS")])
    w.refresh()
    w.act_tool_stretch.setChecked(True)
    x1, y1, x2, y2 = rect(s, "strap:u1/1")
    cy = (y1 + y2) / 2
    transform = w.canvas.transform()
    _drag(w, _at(w, x2, cy), _at(w, 6.0, cy))
    assert vias(s, "strap:u1/1")
    handles = [h for h in w.canvas.owner_items if h.startswith("net_wire:auto_via:strap:u1/1/")]
    assert len(handles) == 1 and w.canvas.transform() == transform
    w.undo_edit()                                             # stretched back: via gone
    assert vias(s, "strap:u1/1") == []
    assert not [h for h in w.canvas.owner_items if h.startswith("net_wire:auto_via:")]


# -- status bar: the selected object's name in the centre -----------------------------------

def test_status_bar_object_name(window):
    s, w = window
    s.db.set_net_wires("clk_n", [("wire", "IB", "5 0 5.36 6"),
                                 ("shield", "IB", "6 0 6.36 6", "VSS")])
    w.refresh()
    bar = w.statusBar()
    assert w.name_label.parent() is bar and w.name_label.text() == ""
    cases = {"net_wire:clk_n/1": "clk_n",                   # a wire: its net
             "net_wire:clk_n/2": "VSS",                     # a shield: its power net
             "inst:u1": "u1",
             "pin:u1/A": "u1/A",
             "strap:u1/1": "VSS",                           # a power strap
             "strap:u1/3": "u1/Y",                          # unrouted signal strap: inst/pin
             "strap:u1/5": "u1/A",
             "pin_wire:u1/Y": "u1/Y"}
    for handle, name in cases.items():
        w.on_select([handle], "replace")
        assert w.name_label.text() == name, handle
        assert handle in w.sel_label.text()                 # the right side keeps the details
    w.on_select(["inst:u1", "pin:u1/A", "strap:u1/1", "strap:u1/2"], "replace")
    assert w.name_label.text() == "u1, u1/A, VSS  +1 more"
    assert w.name_label.toolTip() == "u1\nu1/A\nVSS\nVDD_SOC"
    w.on_select(["strap:u1/1", "strap:u1/4"], "replace")     # same net: once
    assert w.name_label.text() == "VSS"
    w.on_select([], "replace")
    assert w.name_label.text() == ""


def test_tools_move_shift_arrow_moves_a_selected_via_a_track(window):
    """A via selected alone steps as its crossing box (its .source): up or
    down onto the next signal track of IA (the horizontal one of its two
    layers); IB has no tracks here, so left or right leaves it."""
    from core import vias
    s, w = window
    s.eval("assign_track_for_route -net {VDD_SOC NA - NA VSS NA - NA} -layer IA")
    s.db.set_net_wires("n1", [("wire", "IA", wire_at(6.48)),
                              ("cross", "IA/IB", "2.82 6.3 3.18 6.66")])
    w.refresh()
    out_of(s)
    via = vias.handle(next(r for r in vias.rows(s.db, "n1")))
    assert s.eval(f"get_db {via} .source") == "net_wire:n1/2"
    w.on_select([via], "replace")
    w.act_tool_move.setChecked(True)
    _shift(w, "down")
    text = s.out.getvalue()
    assert f"move_wire -wires {{{via}}} -next_track down" in text
    assert "net_wire:n1/2 (crossing box, IA signal track): y 6.48 -> 3.6" in text
    assert rect(s, "net_wire:n1/2") == pytest.approx((2.82, 3.42, 3.18, 3.78))
    assert lines(s, "net_wire:n1/1") == [6.48]                # its wire stays
    assert [(r["x"], r["y"]) for r in vias.rows(s.db, "n1")] == [(3.0, 3.6)]
    _shift(w, "left")
    assert "IB has no DEF TRACKS X" in w.statusBar().currentMessage()
    w.undo_edit()
    assert rect(s, "net_wire:n1/2") == pytest.approx((2.82, 6.3, 3.18, 6.66))



def test_tools_delete_deletes_a_fixed_wire(window):
    # Delete on the selection deletes it even when it is fixed (set_db .route_status
    # fixed); Undo Edit puts it back, still fixed
    s, w = window
    (net, seq), = s.db.add_net_wires([("n1", "wire", "IA", "0 20 10 20.36", None, None)])
    row = s.db.net_wire_row(net, seq)
    s.db.set_wire_fixed(row["id"], True)
    handle = f"net_wire:{net}/{seq}"
    w.on_select([handle], "replace")
    w.act_delete.trigger()
    text = s.out.getvalue()
    assert "HT4-286" not in text
    assert f"delete_wire: deleted 1 wire(s), 1 of them of fixed nets (they stay fixed): " \
           f"{handle}" in text
    assert s.db.net_wire_row(net, seq) is None
    w.act_undo_edit.trigger()
    assert s.db.net_wire_row(net, seq)["status"] == "fixed"
