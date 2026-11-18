"""A signal wire moved by move_wire (and the GUI's Tools > Move) has its
shields made again where it lies now, as route_net -shield makes them."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

pytest.importorskip("scipy")

from test_move_spine import build
from test_route_net import out_of

L2 = "sp_L2_inv1_Y"


@pytest.fixture
def shielded(tech_session, write_lef):
    """The mirrored spine routed with rule w (0.72 wide, 0.72 apart: the
    shields on the VDD and VSS tracks 1.44 either side). sp_L2_inv1_Y's IB
    wire is on x 73.8, its shields on 72.36 (VSS) and 75.24 (VDD)."""
    s = build(tech_session, write_lef, mirror=True, rows=False)
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name w -layer {IA IB} -width 0.72 -spacing 0.72")
    s.eval("route_net -net [get_db nets .name] -rule w -shield")
    out_of(s)
    return s


def wire(s, net=L2):
    r = next(r for r in s.db.net_wire_rows(net) if r["kind"] == "wire" and r["layer"] == "IB")
    return f"net_wire:{net}/{r['seq']}"


def shields(s, net=L2, layer="IB"):
    """{(x of the centre line, power net, y1, y2)} of the net's shields on layer."""
    found = set()
    for r in s.db.net_wire_rows(net):
        if r["kind"] == "shield" and r["layer"] == layer:
            x1, y1, x2, y2 = (float(c) for c in r["rect"].split())
            found.add((round((x1 + x2) / 2, 6), r["shield_net"], y1, y2))
    return found


def test_next_track_makes_the_shields_again(shielded):
    s = shielded
    h = wire(s)
    assert shields(s) == {(72.36, "VSS", 104.82, 135.18), (75.24, "VDD", 104.82, 135.18)}
    s.eval(f"move_wire -wires {h} -next_track right")
    text = out_of(s)
    assert f"  shields of {h} made again where it lies now: VDD IB x 75.24 (30.36 um); VSS IB " \
           f"x 78.12 (30.36 um); 2 old shield(s) removed" in text
    assert shields(s) == {(75.24, "VDD", 104.82, 135.18), (78.12, "VSS", 104.82, 135.18)}
    # shields: 2 went, 2 made; links: 2 crossing boxes went, 2 made, and the 2 power
    # straps they lengthen (to the new shield now)
    assert len(set(s.db.redrawn)) == 10
    assert sorted({h for h in s.db.redrawn if h.startswith("strap:")}) == \
        ["strap:sp_L3_inv2/1", "strap:sp_L3_inv2/4"]


def test_a_delta_move_and_back_gives_the_same_shields(shielded):
    s = shielded
    h, before = wire(s), shields(s)
    s.eval(f"move_wire -wires {h} -delta {{5.76 0}}")
    # 81.0 is past the reach of the cells' straps: that shield covers the wire only
    assert shields(s) == {(78.12, "VSS", 104.82, 135.18), (81.0, "VDD", 107.7, 129.42)}
    s.eval(f"move_wire -wires {h} -delta {{-5.76 0}}")
    assert shields(s) == before


def test_shields_given_with_their_wire_are_made_again_not_moved(shielded):
    s = shielded
    h = wire(s)
    group = [h] + [f"net_wire:{L2}/{r['seq']}" for r in s.db.net_wire_rows(L2)
                   if r["kind"] == "shield" and r["layer"] == "IB"]
    assert s.eval(f"move_wire -wires {{{' '.join(group)}}} -delta {{2.88 0}}") == h
    assert shields(s) == {(75.24, "VDD", 104.82, 135.18), (78.12, "VSS", 104.82, 135.18)}


def test_a_net_routed_without_shields_gets_none(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True, rows=False)
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name w -layer {IA IB} -width 0.72 -spacing 0.72")
    s.eval(f"route_net -net {L2} -rule w")
    out_of(s)
    s.eval(f"move_wire -wires {wire(s)} -next_track right")
    assert "made again" not in out_of(s) and not shields(s)


def test_the_gui_redraws_the_new_shields_and_undo_puts_them_back(shielded):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from core.gui import app
    s = shielded
    s.eval("gui_show")
    w = app.window()
    try:
        h, before = wire(s), shields(s)
        drawn = lambda: {(round((r[0] + r[2]) / 2, 6), round(r[1], 6), round(r[3], 6))
                         for k, items in w.canvas.owner_items.items()
                         if k.startswith(f"net_wire:{L2}/") and s.db.net_wire_row(
                             L2, int(k.rpartition("/")[2])) is not None
                         and s.db.net_wire_row(L2, int(k.rpartition("/")[2]))["kind"] == "shield"
                         for r in [w.canvas._rect_of(items[0])]}
        stored = lambda: {(x, y1, y2) for x, _, y1, y2 in shields(s)} | \
            {(x, y1, y2) for x, _, y1, y2 in shields(s, layer="IA")}
        assert drawn() == stored()
        w.on_select([h], "replace")
        w.act_tool_move.setChecked(True)
        QApplication.sendEvent(w.canvas, QKeyEvent(QEvent.KeyPress, Qt.Key_Right,
                                                   Qt.ShiftModifier))
        assert shields(s) == {(75.24, "VDD", 104.82, 135.18), (78.12, "VSS", 104.82, 135.18)}
        assert drawn() == stored()                    # the old ones gone, the new drawn
        w.undo_edit()
        assert shields(s) == before and drawn() == stored()
    finally:
        app.close()


def links(s, net=L2):
    """The net's power links: the power straps it lengthens to its shields
    (as the pieces they add, kind shield_ext) and their crossing boxes."""
    from core.db import _num
    pieces = [("shield_ext", s.db.strap_row(r["inst"], r["seq"])) + (r,)
              for r in s.db.stretch_rows(owner=net) if r["kind"] == "shield_ext"]
    return sorted([(r["kind"], r["layer"], r["rect"], r["shield_net"])
                   for r in s.db.net_wire_rows(net) if r["kind"] == "cross" and r["shield_net"]]
                  + [(kind, strap["layer"], " ".join(_num(v) for v in (
                      st["x1"], float(strap["rect"].split()[1]), st["x2"],
                      float(strap["rect"].split()[3]))), strap["net"])
                     for kind, strap, st in pieces])


def power_opens(s):
    """{(box, net)} of check_drc's power opens (by place: a shield made again
    has another number)."""
    s.eval("check_drc")
    return {(l.split("}")[0].strip() + "}", l.split("net ")[1].split(":")[0])
            for l in out_of(s).splitlines() if "no path to a" in l
            and l.split("net ")[1].split(":")[0] in ("VSS", "VDD")}


def test_the_power_links_follow_the_new_shields(shielded):
    """sp_L3_inv2's VSS straps joined the VSS shield at x 72.36; on x 76.68
    the wire's VSS shield is on 78.12, and the straps reach it (1.16 right)."""
    s = shielded
    before, opens = links(s), power_opens(s)
    assert before == [("cross", "IB/IA", "72 130.14 72.72 130.86", "VSS"),
                      ("cross", "IB/IA", "72 134.46 72.72 135.18", "VSS"),
                      ("shield_ext", "IA", "72 130.14 74.2 130.86", "VSS"),
                      ("shield_ext", "IA", "72 134.46 74.2 135.18", "VSS")]
    s.eval(f"move_wire -wires {wire(s)} -next_track right")
    text = out_of(s)
    assert "power straps to shields: strap:sp_L3_inv2/1 VSS, extended 1.16 right to the " \
           "shield at x 78.12; strap:sp_L3_inv2/4 VSS, extended 1.16 right to the shield at " \
           "x 78.12" in text
    assert "    power links made again: 4 (power straps lengthened to the shields, and their " \
           "crossing boxes); 4 old one(s) removed" in text
    assert links(s) == [("cross", "IB/IA", "77.76 130.14 78.48 130.86", "VSS"),
                        ("cross", "IB/IA", "77.76 134.46 78.48 135.18", "VSS"),
                        ("shield_ext", "IA", "77.32 130.14 78.48 130.86", "VSS"),
                        ("shield_ext", "IA", "77.32 134.46 78.48 135.18", "VSS")]
    assert power_opens(s) <= opens          # none new: the straps are still joined (and
    #                                         the new VSS shield joins two L3 shields)
    s.eval(f"move_wire -wires {wire(s)} -delta {{-2.88 0}}")
    assert links(s) == before and power_opens(s) == opens


def test_links_are_made_again_as_route_net_makes_them(shielded):
    """After a move and its way back the net is as route_net -shield left it;
    and route_net run again makes the same links as the move did."""
    s = shielded
    s.eval(f"move_wire -wires {wire(s)} -next_track right")
    moved = links(s)
    s.eval(f"set_db {wire(s)} .route_status fixed")
    s.eval(f"route_net -net {L2} -rule w -shield")
    assert links(s) == moved
