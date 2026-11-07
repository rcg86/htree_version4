import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import io
import tkinter

import pytest

pytest.importorskip("PySide6")

from conftest import ROOT, TECH_LEF
from core.gui import app
from core.gui.layout_data import (Track, clip_line_to_polygon, load_layout,
                                  visible_track_positions)
from core.htree_builder import Session

SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def loaded(tech_session):
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


@pytest.fixture(autouse=True)
def fresh_window():
    yield
    app.close()


# -- layout_data (no Qt) --------------------------------------------------------------

def test_load_layout_layers_and_counts(loaded):
    lay = load_layout(loaded.db)
    assert lay.design == "top"
    assert lay.bbox == (0, 0, 100, 80)
    names = [l.name for l in lay.layers]
    assert names[:6] == ["H1", "H2", "G1", "G2", "IA", "IB"]        # tech order first
    assert names[6:] == ["M1"]                                      # then others
    h1 = lay.layer("H1")
    # H1 is horizontal in tech; small.def has only TRACKS X for it: none drawn
    assert (h1.in_tech, h1.port_shapes, h1.track_patterns) == (True, 4, 0)
    m1 = lay.layer("M1")
    assert (m1.in_tech, m1.port_shapes, m1.track_patterns) == (False, 1, 1)
    assert len(lay.shapes) == 6 and len(lay.tracks) == 3
    assert lay.shapes[0].handle == "port_shape:top/a/1"


def test_load_layout_empty(session):
    lay = load_layout(session.db)
    assert (lay.design, lay.layers, lay.shapes, lay.bbox) == (None, [], [], None)


def test_visible_track_positions():
    t = Track("t", "x", start=1.0, num=10, step=2.0, layers=["M1"])   # 1 3 5 ... 19
    assert visible_track_positions(t, 4, 9) == [5, 7, 9]
    assert visible_track_positions(t, -100, 0) == []
    assert visible_track_positions(t, 18, 100) == [19]               # stops at num
    assert visible_track_positions(t, 0, 100, limit=5) is None        # too dense


def test_clip_line_to_comb_polygon():
    # comb: trunk on the right (x 8..10), two arms to the left
    comb = [10, 0, 10, 10, 0, 10, 0, 8, 8, 8, 8, 2, 0, 2, 0, 0]
    assert clip_line_to_polygon(comb, False, 1) == [(0, 10)]          # y=1: bottom arm
    assert clip_line_to_polygon(comb, False, 5) == [(8, 10)]          # y=5: trunk only
    assert clip_line_to_polygon(comb, True, 4) == [(0, 2), (8, 10)]   # x=4: both arms
    assert clip_line_to_polygon(comb, True, 11) == []


# -- gui_show -------------------------------------------------------------------------

def test_gui_show_opens_window(loaded):
    loaded.eval("gui_show")
    assert "GUI opened" in loaded.out.getvalue()
    w = app.window()
    assert w is not None and w.windowTitle() == "htree4 - top"
    assert {k for k, b in w.object_boxes.items() if b.isEnabled()} == \
        {"boundary", "ports", "tracks"}
    for key in ("nets", "cells", "spine"):
        assert not w.object_boxes[key].isChecked()
    assert w.layer_boxes["H1"].isChecked() and not w.layer_boxes["M1"].isChecked()
    loaded.eval("gui_show")                                           # again: same window
    assert app.window() is w


def test_refresh_after_command(tech_session):
    tech_session.eval("gui_show")
    w = app.window()
    assert w.layout.shapes == [] and not w.object_boxes["ports"].isEnabled()
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    assert len(w.layout.shapes) == 6 and w.object_boxes["ports"].isEnabled()
    calls = []
    w.refresh = lambda: calls.append(1)
    tech_session.eval("get_db ports")                                 # no change: no reload
    assert calls == []


def test_visibility_checkboxes(loaded):
    loaded.eval("gui_show")
    w = app.window()
    h1 = w.canvas.shape_items["H1"]
    m1 = w.canvas.shape_items["M1"]
    assert all(i.isVisible() for i in h1) and not any(i.isVisible() for i in m1)
    w.layer_boxes["H1"].setChecked(False)
    assert not any(i.isVisible() for i in h1)
    w.set_all_layers(True)
    assert all(i.isVisible() for i in m1 + h1)
    w.object_boxes["ports"].setChecked(False)
    assert not any(i.isVisible() for items in w.canvas.shape_items.values() for i in items)
    w.object_boxes["boundary"].setChecked(False)
    assert not w.canvas.boundary_item.isVisible()
    w.set_all_layers(None)                                            # tech only
    assert w.layer_boxes["H1"].isChecked() and not w.layer_boxes["M1"].isChecked()


def _point_of(w, shape_handle):
    item = next(i for its in w.canvas.shape_items.values() for i in its
                if i.data(0) == shape_handle)
    w.canvas.centerOn(item)
    return item, w.canvas.mapFromScene(item.sceneBoundingRect().center())


def test_click_selects_port_and_get_db_selected(loaded):
    loaded.eval("gui_show")
    w = app.window()
    item, point = _point_of(w, "port_shape:top/a/1")
    assert w.canvas.owner_at(point) == "port:top/a"
    w.on_select(["port:top/a"], "replace")
    assert loaded.eval("get_db selected") == "port:top/a"
    assert loaded.eval("get_db selected .direction") == "in"
    assert item in w.canvas.highlighted
    out = loaded.out.getvalue()
    assert "Selected port:top/a  layers H1  rect {9.95 0 10.05 0.4}  direction in  net a" in out
    assert "port:top/a" in w.sel_label.text()


def test_click_on_port_with_two_shapes_lights_both(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.layer_boxes["H2"].setChecked(True)
    w.on_select(["port:top/b"], "replace")
    lit = {i.data(0) for i in w.canvas.highlighted}
    assert lit == {"port_shape:top/b/1", "port_shape:top/b/2"}


def test_toggle_add_and_clear(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.on_select(["port:top/a"], "replace")
    w.on_select(["port:top/c"], "toggle")                    # Ctrl+click adds
    assert loaded.eval("get_db selected") == "port:top/a port:top/c"
    assert "Selected 2 objects (get_db selected)" in loaded.out.getvalue()
    w.on_select(["port:top/a"], "toggle")                    # Ctrl+click again removes
    assert loaded.eval("get_db selected") == "port:top/c"
    w.on_select(["port:top/d"], "add")
    assert loaded.eval("get_db selected .name") == "c d"
    w.on_select([], "replace")                               # click on empty space
    assert loaded.eval("get_db selected") == ""
    assert w.canvas.highlighted == {} and w.sel_label.text() == ""
    assert "Selection cleared" in loaded.out.getvalue()


def test_area_select(loaded):
    loaded.eval("gui_show")
    w = app.window()
    from PySide6.QtCore import QRectF
    from core.gui.canvas import scene
    # ports a (x 10) and b's first shape (x 20) are near y=0; c is at x=0, y=30
    owners = w.canvas.owners_in(QRectF(scene(5, 1), scene(25, -1)))
    assert sorted(owners) == ["port:top/a", "port:top/b"]
    w.layer_boxes["H1"].setChecked(False)                    # hidden shapes are not picked
    assert w.canvas.owners_in(QRectF(scene(5, 1), scene(25, -1))) == []


def test_terminal_selection_highlights_in_gui(loaded):
    loaded.eval("gui_show")
    w = app.window()
    loaded.eval("select_obj port:top/c")
    assert {i.data(0) for i in w.canvas.highlighted} == {"port_shape:top/c/1"}
    assert w.sel_label.text().startswith("port:top/c")
    loaded.eval("deselect_obj -all")
    assert w.canvas.highlighted == {}


def test_selection_survives_refresh_and_drops_stale(loaded, write_lef):
    loaded.eval("gui_show")
    w = app.window()
    w.on_select(["port:top/a"], "replace")
    loaded.eval(f"read_tech -file {{{TECH_LEF}}}")           # refresh: still selected
    assert loaded.eval("get_db selected") == "port:top/a"
    assert w.canvas.highlighted
    other = write_lef("DESIGN t2 ;\nUNITS DISTANCE MICRONS 100 ;\nEND DESIGN\n", "t2.def")
    loaded.eval(f"read_def -file {other}")                   # port:top/a no longer exists
    assert loaded.eval("get_db selected") == ""
    assert w.canvas.highlighted == {}


def test_new_session_gets_new_window(loaded):
    loaded.eval("gui_show")
    first = app.window()
    other = Session(out=io.StringIO())
    other.eval("gui_show")
    assert app.window() is not first and app.window().session is other
    assert not any(getattr(h, "gui_hook", False) for h in loaded.after_command)


def test_no_display(session, monkeypatch):
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert "HT4-101" in err(session, "gui_show") and "DISPLAY is not set" in \
        err(session, "gui_show")
    assert app.window() is None


# -- panning ---------------------------------------------------------------------------

def _content_in_viewport(w):
    from core.gui.canvas import scene
    x1, y1, x2, y2 = w.layout.bbox
    a = w.canvas.mapFromScene(scene(x1, y1))
    b = w.canvas.mapFromScene(scene(x2, y2))
    return min(a.x(), b.x()), max(a.x(), b.x()), min(a.y(), b.y()), max(a.y(), b.y())


@pytest.mark.parametrize("zoom_out_steps", [0, 8])
def test_pan_moves_design_past_every_edge(loaded, zoom_out_steps):
    """User report: dragging left stopped with the design at the right edge."""
    loaded.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    for _ in range(zoom_out_steps):
        w.canvas.zoom(1 / 1.15)
    vw, vh = w.canvas.viewport().width(), w.canvas.viewport().height()
    h, v = w.canvas.horizontalScrollBar(), w.canvas.verticalScrollBar()
    h.setValue(h.maximum())                      # drag far left: design leaves on the left
    assert _content_in_viewport(w)[1] < 0
    h.setValue(h.minimum())                      # drag far right
    assert _content_in_viewport(w)[0] > vw
    v.setValue(v.maximum())
    assert _content_in_viewport(w)[3] < 0
    v.setValue(v.minimum())
    assert _content_in_viewport(w)[2] > vh


def test_zoom_out_is_limited(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    for _ in range(200):
        w.canvas.zoom(1 / 1.15)
    x1, x2, y1, y2 = _content_in_viewport(w)
    assert x2 - x1 >= 2 or y2 - y1 >= 2          # still visible, not a speck
    test_scale = abs(w.canvas.transform().m11())
    w.canvas.zoom(1 / 1.15)
    assert abs(w.canvas.transform().m11()) == test_scale   # no further


# -- menu, toolbar, zoom selected, blink selected ---------------------------------------

def test_menu_and_toolbar(loaded):
    loaded.eval("gui_show")
    w = app.window()
    menus = {a.text().replace("&", ""): [x.text() for x in a.menu().actions() if x.text()]
             for a in w.menuBar().actions()}
    assert menus == {"File": ["Close Window"],
                     "View": ["Fit", "Zoom Selected", "Blink Selected", "Ruler", "Clear Rulers",
                              "Show View Panel"],
                     "Select": ["Clear Selection"]}
    assert [a.text() for a in w.toolbar.actions() if a.text()] == \
        ["Fit", "Zoom Selected", "Blink Selected"]
    assert w.ruler_button.text() == "Ruler"                   # next to Blink Selected
    assert w.toolBarArea(w.toolbar) == w.toolBarArea(w.toolbar).TopToolBarArea  # under the menu


def test_zoom_selected(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    w.zoom_selected()
    assert w.statusBar().currentMessage() == "Nothing selected"
    w.on_select(["port:top/a"], "replace")
    before = abs(w.canvas.transform().m11())
    w.act_zoom_sel.trigger()
    after = abs(w.canvas.transform().m11())
    assert after > before * 5                                 # zoomed in a lot
    # the pin is in the middle of the window
    item = next(iter(w.canvas.highlighted))
    c = w.canvas.mapFromScene(item.sceneBoundingRect().center())
    vp = w.canvas.viewport()
    assert abs(c.x() - vp.width() / 2) < 3 and abs(c.y() - vp.height() / 2) < 3
    # a 0.1 um pin is not blown up to fill the screen: about 5 um stay visible
    visible = w.canvas.mapToScene(vp.rect()).boundingRect()
    assert min(visible.width(), visible.height()) >= 5


def test_zoom_selected_not_drawn(loaded):
    loaded.eval("gui_show")
    w = app.window()
    loaded.eval("select_obj design:top")
    w.zoom_selected()
    assert w.statusBar().currentMessage() == "The selected objects are not drawn in the layout"


def test_blink_selected(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    w.on_select(["port:top/a"], "replace")
    item = next(iter(w.canvas.highlighted))
    w.canvas.blink(w.canvas.selection_rect(), times=2, ms=1)
    timer, marker, left = w.canvas._blink
    assert marker.scene() is w.canvas.scene() and left == 4
    # the marker is at least BLINK_MIN_PIXELS on screen although the pin is tiny
    from core.gui.canvas import BLINK_MIN_PIXELS
    box = w.canvas.mapFromScene(marker.rect()).boundingRect()
    assert box.width() >= BLINK_MIN_PIXELS - 2
    w.canvas._blink_step()
    assert not marker.isVisible() and item.opacity() < 1 and item.isVisible()
    w.canvas._blink_step()
    assert marker.isVisible() and item.opacity() == 1
    w.canvas._blink_step(); w.canvas._blink_step()            # last step cleans up
    assert w.canvas._blink is None and marker.scene() is None and item.opacity() == 1


def test_blink_keeps_hidden_layers_hidden(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.on_select(["port:top/a"], "replace")
    w.layer_boxes["H1"].setChecked(False)
    item = next(iter(w.canvas.highlighted))
    w.canvas.blink(w.canvas.selection_rect(), times=1, ms=1)
    w.canvas._blink_step(); w.canvas._blink_step()
    assert not item.isVisible()


def test_blink_stops_on_refresh(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.on_select(["port:top/a"], "replace")
    w.blink_selected()
    assert w.canvas._blink is not None
    loaded.eval(f"read_tech -file {{{TECH_LEF}}}")            # refresh rebuilds the scene
    assert w.canvas._blink is None


# -- mouse map with real events: drag zooms, Shift+drag selects, middle drag pans --------

def _send(w, kind, point, button, buttons, mods=None):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    t = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
         "release": QEvent.MouseButtonRelease}[kind]
    p = QPointF(point)
    QApplication.sendEvent(w.canvas.viewport(), QMouseEvent(
        t, p, p, button, buttons, mods if mods is not None else Qt.NoModifier))


def _drag(w, a, b, button=None, mods=None):
    from PySide6.QtCore import QPointF, Qt
    button = button or Qt.LeftButton
    a, b = QPointF(a), QPointF(b)
    _send(w, "press", a, button, button, mods)
    for i in range(1, 9):
        _send(w, "move", a + (b - a) * (i / 8), Qt.NoButton, button, mods)
    _send(w, "release", b, button, Qt.NoButton, mods)


def _view(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    return w


def test_left_drag_zooms_to_box(loaded):
    from core.gui.canvas import scene
    w = _view(loaded)
    before = abs(w.canvas.transform().m11())
    a = w.canvas.mapFromScene(scene(5, 5))
    b = w.canvas.mapFromScene(scene(25, -1))
    _drag(w, a, b)
    assert abs(w.canvas.transform().m11()) > before * 3
    visible = w.canvas.mapToScene(w.canvas.viewport().rect()).boundingRect()
    assert visible.contains(scene(15, 2)) and visible.width() < 40
    assert loaded.eval("get_db selected") == ""                # zooming does not select


def test_shift_drag_selects_all_ports_inside(loaded):
    from PySide6.QtCore import Qt
    from core.gui.canvas import scene
    w = _view(loaded)
    w.set_all_layers(True)
    # box around a (x 9.95..10.05) and b's rect (x 19.9..20), both near y = 0
    _drag(w, w.canvas.mapFromScene(scene(5, 1)), w.canvas.mapFromScene(scene(25, -1)),
          mods=Qt.ShiftModifier)
    assert sorted(loaded.split_list(loaded.eval("get_db selected"))) == \
        ["port:top/a", "port:top/b"]
    # Ctrl+Shift+drag adds; c is at x 0..0.2, y 29.9..30
    _drag(w, w.canvas.mapFromScene(scene(-1, 31)), w.canvas.mapFromScene(scene(1, 29)),
          mods=Qt.ShiftModifier | Qt.ControlModifier)
    assert len(loaded.split_list(loaded.eval("get_db selected"))) == 3


def test_shift_drag_needs_shape_inside_box(loaded):
    from PySide6.QtCore import Qt
    from core.gui.canvas import scene
    from PySide6.QtCore import QRectF
    w = _view(loaded)
    w.canvas.fitInView(QRectF(scene(9.5, 1), scene(10.5, -0.5)), Qt.KeepAspectRatio)
    # pin a is x 9.95..10.05, y 0..0.4; this box covers only its right half
    box = (scene(10.0, 0.5), scene(10.3, -0.2))
    assert w.canvas.owners_in(QRectF(*box).normalized()) == []
    _drag(w, w.canvas.mapFromScene(box[0]), w.canvas.mapFromScene(box[1]),
          mods=Qt.ShiftModifier)
    assert loaded.eval("get_db selected") == ""
    # the same box enlarged to hold the whole pin selects it
    _drag(w, w.canvas.mapFromScene(scene(9.9, 0.5)), w.canvas.mapFromScene(scene(10.3, -0.2)),
          mods=Qt.ShiftModifier)
    assert loaded.eval("get_db selected") == "port:top/a"


def test_middle_drag_pans(loaded):
    from PySide6.QtCore import QPoint, Qt
    from core.gui.canvas import scene
    w = _view(loaded)
    scale = abs(w.canvas.transform().m11())
    left_before = w.canvas.mapFromScene(scene(0, 0)).x()
    _drag(w, QPoint(500, 350), QPoint(300, 350), button=Qt.MiddleButton)
    assert w.canvas.mapFromScene(scene(0, 0)).x() == left_before - 200   # moved with the mouse
    assert abs(w.canvas.transform().m11()) == scale                       # no zoom


def test_click_still_selects(loaded):
    from core.gui.canvas import scene
    w = _view(loaded)
    _, point = _point_of(w, "port_shape:top/a/1")
    _send(w, "press", point, *_left())
    _send(w, "release", point, _left()[0], _nobutton())
    assert loaded.eval("get_db selected") == "port:top/a"


def test_arrow_keys_pan(loaded):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    w = _view(loaded)
    x0 = w.canvas.mapFromScene(scene(0, 0)).x()
    QApplication.sendEvent(w.canvas, QKeyEvent(QEvent.KeyPress, Qt.Key_Left, Qt.NoModifier))
    assert w.canvas.mapFromScene(scene(0, 0)).x() == x0 + w.canvas.viewport().width() // 4


def _left():
    from PySide6.QtCore import Qt
    return Qt.LeftButton, Qt.LeftButton


def _nobutton():
    from PySide6.QtCore import Qt
    return Qt.NoButton


# -- track assignments in the GUI ---------------------------------------------------------

ASSIGN_DEF = """DESIGN t ;
UNITS DISTANCE MICRONS 100 ;
DIEAREA ( 0 0 ) ( 1000 1000 ) ;
TRACKS Y 50 DO 10 STEP 100 LAYER H1 ;
TRACKS X 50 DO 10 STEP 100 LAYER H1 ;
PINS 1 ;
- VDD + NET VDD + SPECIAL + DIRECTION INOUT + USE POWER ;
END PINS
END DESIGN
"""


@pytest.fixture
def assigned(tech_session, write_lef):
    tech_session.eval(f"read_def -file {write_lef(ASSIGN_DEF, 'a.def')}")
    tech_session.eval("assign_track_for_route -net {VDD, -, VSS, -} -layer H1")
    return tech_session


def test_load_assignment(assigned):
    from core.gui.layout_data import SIGNAL_COLOR, visible_assigned_tracks
    lay = load_layout(assigned.db)
    a, = lay.assignments
    assert (a.layer, a.direction, a.pattern) == ("H1", "y", ["VDD", "-", "VSS", "-"])
    assert a.positions == [0.5 + i for i in range(10)]
    assert a.counts == [("VDD", 3), ("VSS", 2), ("-", 5)]
    assert a.colors["-"] == SIGNAL_COLOR and a.colors["VDD"] != a.colors["VSS"]
    assert visible_assigned_tracks(a, 1, 5, {"VDD", "VSS", "-"}) == \
        [(1.5, "-"), (2.5, "VSS"), (3.5, "-"), (4.5, "VDD")]
    assert visible_assigned_tracks(a, 0, 10, {"VSS"}) == [(2.5, "VSS"), (6.5, "VSS")]
    assert visible_assigned_tracks(a, 0, 10, {"VDD"}, limit=5) is None   # too dense


def test_tracks_dropdown_panel(assigned):
    assigned.eval("gui_show")
    w = app.window()
    assert not w.assign_panel.isVisibleTo(w)
    w.assign_toggle.setChecked(True)                           # open the dropdown
    assert w.assign_panel.isVisibleTo(w)
    assert {k: b.text() for k, b in w.assign_boxes.items()} == {
        ("H1", "VDD"): "VDD  (3)", ("H1", "VSS"): "VSS  (2)", ("H1", "-"): "signal (-)  (5)"}
    w.assign_boxes[("H1", "-")].setChecked(False)
    assert w.canvas.assign_hidden == {("H1", "-")}
    w.assign_toggle.setChecked(False)
    assert not w.assign_panel.isVisibleTo(w)


def test_dropdown_without_assignments(loaded):
    loaded.eval("gui_show")
    w = app.window()
    w.assign_toggle.setChecked(True)
    assert w.assign_boxes == {}
    labels = [w.assign_vbox.itemAt(i).widget().text() for i in range(w.assign_vbox.count())]
    assert any("No track assignments" in t for t in labels)


def test_assignment_after_gui_show_refreshes_and_keeps_choices(tech_session, write_lef):
    tech_session.eval(f"read_def -file {write_lef(ASSIGN_DEF, 'a.def')}")
    tech_session.eval("gui_show")
    w = app.window()
    assert w.assign_boxes == {}
    tech_session.eval("assign_track_for_route -net {VDD - VSS -} -layer H1")
    assert ("H1", "VSS") in w.assign_boxes
    w.assign_boxes[("H1", "VSS")].setChecked(False)
    tech_session.eval("assign_track_for_route -net {VDD - VSS -} -layer H1")   # refresh
    assert not w.assign_boxes[("H1", "VSS")].isChecked()
    assert ("H1", "VSS") in w.canvas.assign_hidden


def test_assigned_tracks_drawn_in_net_colors(assigned):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    assigned.eval("gui_show")
    w = app.window()
    w.resize(900, 700)
    w.object_boxes["tracks"].setChecked(True)
    w.object_boxes["boundary"].setChecked(False)
    w.canvas.fitInView(QRectF(scene(0, 10), scene(10, 0)), Qt.KeepAspectRatio)
    QApplication.processEvents()
    a = w.layout.assignments[0]

    def color_at_track(y):
        img = w.canvas.viewport().grab().toImage()
        p = w.canvas.mapFromScene(scene(3.0, y))          # between the vertical tracks
        return {img.pixelColor(p.x(), p.y() + d).name() for d in (-1, 0, 1)}

    assert QColor(a.colors["VDD"]).name() in color_at_track(0.5)
    assert QColor(a.colors["VSS"]).name() in color_at_track(2.5)
    w.assign_boxes[("H1", "VSS")].setChecked(False)
    QApplication.processEvents()
    assert QColor(a.colors["VSS"]).name() not in color_at_track(2.5)



# -- tracks only in the tech layer's preferred direction ------------------------------------

def test_drawn_layers_rule():
    from core.gui.layout_data import drawn_layers
    pref = {"IA": "y", "IB": "x"}
    assert drawn_layers(Track("t", "y", 0, 1, 1, ["IA"]), pref) == ["IA"]
    assert drawn_layers(Track("t", "x", 0, 1, 1, ["IA"]), pref) == []        # IA horizontal
    assert drawn_layers(Track("t", "x", 0, 1, 1, ["IA", "IB"]), pref) == ["IB"]
    assert drawn_layers(Track("t", "x", 0, 1, 1, ["M1"]), pref) == ["M1"]    # no tech direction
    assert drawn_layers(Track("t", "y", 0, 1, 1, ["M1"]), pref) == ["M1"]


def test_preferred_from_tech(loaded):
    lay = load_layout(loaded.db)
    assert lay.preferred == {"H1": "y", "H2": "x", "G1": "y", "G2": "x", "IA": "y", "IB": "x"}
    assert lay.layer("H2").track_patterns == 0     # H2 vertical, small.def has only TRACKS Y
    assert lay.layer("M1").track_patterns == 1     # not in tech: drawn as given


NONPREF_DEF = """DESIGN t ;
UNITS DISTANCE MICRONS 100 ;
DIEAREA ( 0 0 ) ( 1000 1000 ) ;
TRACKS Y 50 DO 10 STEP 100 LAYER H1 ;
TRACKS X 50 DO 10 STEP 100 LAYER H1 ;
END DESIGN
"""


def test_non_preferred_tracks_not_drawn(tech_session, write_lef):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    tech_session.eval(f"read_def -file {write_lef(NONPREF_DEF, 'n.def')}")
    tech_session.eval("gui_show")
    w = app.window()
    w.resize(900, 700)
    w.object_boxes["tracks"].setChecked(True)
    w.object_boxes["boundary"].setChecked(False)
    w.canvas.fitInView(QRectF(scene(0, 10), scene(10, 0)), Qt.KeepAspectRatio)
    QApplication.processEvents()
    img = w.canvas.viewport().grab().toImage()
    bg = img.pixelColor(2, 2).name()

    def hits(x, y):
        p = w.canvas.mapFromScene(scene(x, y))
        return {img.pixelColor(p.x() + dx, p.y() + dy).name()
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - {bg}

    assert hits(3.0, 0.5)          # horizontal H1 track at y 0.5 is drawn
    assert not hits(0.5, 3.0)      # vertical H1 track at x 0.5 is not (H1 is horizontal)



# -- ruler ------------------------------------------------------------------------------------

def test_ruler_geometry():
    from core.gui.layout_data import (constrain_orthogonal, nearest_on_segments,
                                      polygon_edges, ruler_text)
    square = polygon_edges([0, 0, 10, 0, 10, 10, 0, 10])
    assert nearest_on_segments((10.3, 5), square, 1) == (10, 5)          # onto an edge
    assert nearest_on_segments((10.2, 10.2), square, 1) == (10, 10)      # corner
    assert nearest_on_segments((5, 5), square, 1) is None                # nothing close
    assert constrain_orthogonal((0, 0), (5, 1)) == (5, 0)
    assert constrain_orthogonal((0, 0), (1, 5)) == (0, 5)
    assert ruler_text((0, 0), (3, 0), False) == "3 um"
    assert ruler_text((0, 0), (3, 4), True) == "5 um  (dx 3, dy 4)"
    assert ruler_text((0, 0), (0.12345, 0), False) == "0.12345 um"


def test_ruler_button_dropdown(loaded):
    loaded.eval("gui_show")
    w = app.window()
    from PySide6.QtWidgets import QToolButton
    assert w.ruler_button.popupMode() == QToolButton.MenuButtonPopup
    assert [a.text() for a in w.ruler_menu.actions() if a.text()] == \
        ["Orthogonal", "Diagonal", "Snap to nearest object edge", "Clear Rulers"]
    assert w.act_ortho.isChecked() and not w.act_diag.isChecked()      # orthogonal default
    w.act_diag.setChecked(True)
    assert not w.act_ortho.isChecked() and w.canvas.ruler["diagonal"]
    w.act_snap.setChecked(False)
    assert w.canvas.ruler["snap"] is False
    w.act_ruler.setChecked(True)
    assert w.canvas.ruler["on"]


def _ruler_view(loaded):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import scene
    w = _view(loaded)
    w.canvas.fitInView(QRectF(scene(0, 12), scene(32, -2)), Qt.KeepAspectRatio)
    w.act_ruler.setChecked(True)
    return w


def _ruler_click(w, x, y):
    from PySide6.QtCore import Qt
    from core.gui.canvas import scene
    p = w.canvas.mapFromScene(scene(x, y))
    _send(w, "move", p, Qt.NoButton, Qt.NoButton)
    _send(w, "press", p, Qt.LeftButton, Qt.LeftButton)
    _send(w, "release", p, Qt.LeftButton, Qt.NoButton)


def test_ruler_measures_with_clicks(loaded):
    w = _ruler_view(loaded)
    w.act_snap.setChecked(False)
    _ruler_click(w, 2, 5)
    assert w.canvas.ruler_in_progress()
    _ruler_click(w, 12, 5.3)                 # orthogonal: held horizontal
    assert not w.canvas.ruler_in_progress() and len(w.canvas.rulers) == 1
    out = loaded.out.getvalue()
    line = next(l for l in out.splitlines() if l.startswith("Ruler: "))
    length = float(line.split()[1])
    assert abs(length - 10) < 0.1 and "to (" in line
    assert loaded.eval("get_db selected") == ""          # ruler clicks do not select


def test_ruler_diagonal(loaded):
    w = _ruler_view(loaded)
    w.act_snap.setChecked(False)
    w.act_diag.setChecked(True)
    _ruler_click(w, 2, 2)
    _ruler_click(w, 5, 6)
    text = w.canvas.rulers[0][-1].text()
    assert text.startswith("5") and "dx 3" in text and "dy 4" in text


def test_ruler_snaps_to_visible_shape_edge(loaded):
    w = _ruler_view(loaded)
    # pin a: x 9.95..10.05, y 0..0.4 (H1, shown). A click just right of it snaps.
    from core.gui.canvas import scene
    p = w.canvas.ruler_point(scene(10.2, 0.2))
    assert abs(p[0] - 10.05) < 1e-9 and abs(p[1] - 0.2) < 1e-9


def test_ruler_does_not_snap_to_hidden_objects(loaded):
    from core.gui.canvas import scene
    w = _ruler_view(loaded)
    w.object_boxes["boundary"].setChecked(False)
    w.layer_boxes["H1"].setChecked(False)                  # pin a hidden
    p = w.canvas.ruler_point(scene(10.2, 0.2))
    assert abs(p[0] - 10.2) < 1e-6 and abs(p[1] - 0.2) < 1e-6   # stays where clicked
    w.layer_boxes["H1"].setChecked(True)
    w.act_snap.setChecked(False)                           # snapping off: no snap either
    p = w.canvas.ruler_point(scene(10.2, 0.2))
    assert abs(p[0] - 10.2) < 1e-6


def test_ruler_snaps_to_boundary_only_when_shown(loaded):
    from core.gui.canvas import scene
    w = _ruler_view(loaded)
    w.layer_boxes["H1"].setChecked(False)
    # boundary edge x = 40 between y 50 and 80; click at (40.3, 60)
    from PySide6.QtCore import QRectF, Qt
    w.canvas.fitInView(QRectF(scene(30, 70), scene(50, 50)), Qt.KeepAspectRatio)
    assert abs(w.canvas.ruler_point(scene(40.3, 60))[0] - 40) < 1e-9
    w.object_boxes["boundary"].setChecked(False)
    assert abs(w.canvas.ruler_point(scene(40.3, 60))[0] - 40.3) < 1e-6


def test_ruler_snaps_to_drawn_tracks_only(tech_session, write_lef):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import scene
    tech_session.eval(f"read_def -file {write_lef(NONPREF_DEF, 'n.def')}")
    tech_session.eval("gui_show")
    w = app.window()
    w.resize(900, 700)
    w.object_boxes["boundary"].setChecked(False)
    w.canvas.fitInView(QRectF(scene(0, 10), scene(10, 0)), Qt.KeepAspectRatio)
    w.act_ruler.setChecked(True)
    assert abs(w.canvas.ruler_point(scene(3, 0.6))[1] - 0.6) < 1e-6   # tracks off: no snap
    w.object_boxes["tracks"].setChecked(True)
    assert abs(w.canvas.ruler_point(scene(3, 0.6))[1] - 0.5) < 1e-9   # H1 track y 0.5
    # H1 vertical tracks (x 0.5, 1.5, ...) are not drawn, so no snap to x = 0.5
    assert abs(w.canvas.ruler_point(scene(0.6, 3.3))[0] - 0.6) < 1e-6


def test_ruler_cancel_and_clear(loaded):
    from PySide6.QtCore import Qt
    w = _ruler_view(loaded)
    _ruler_click(w, 2, 5)
    w.on_escape()                                          # Esc cancels a ruler in progress
    assert not w.canvas.ruler_in_progress() and w.canvas.rulers == []
    _ruler_click(w, 2, 5)
    _ruler_click(w, 6, 5)
    _ruler_click(w, 2, 8)
    _ruler_click(w, 2, 9)
    assert len(w.canvas.rulers) == 2
    w.act_clear_rulers.trigger()
    assert w.canvas.rulers == []
    _ruler_click(w, 2, 5)
    from core.gui.canvas import scene
    p = w.canvas.mapFromScene(scene(3, 5))
    _send(w, "press", p, Qt.RightButton, Qt.RightButton)   # right click cancels
    assert not w.canvas.ruler_in_progress()


def test_ruler_off_restores_click_select(loaded):
    w = _ruler_view(loaded)
    w.act_ruler.setChecked(False)
    _, point = _point_of(w, "port_shape:top/a/1")
    _send(w, "press", point, *_left())
    _send(w, "release", point, _left()[0], _nobutton())
    assert loaded.eval("get_db selected") == "port:top/a"
