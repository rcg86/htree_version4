"""move_wire, stretch_wire, and the GUI's Tools > Move / Stretch that run them."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

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


def _drag(w, a, b):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    a, b = QPointF(a), QPointF(b)
    vp = w.canvas.viewport()
    send = lambda t, p, btn, btns: QApplication.sendEvent(
        vp, QMouseEvent(t, p, p, btn, btns, Qt.NoModifier))
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
