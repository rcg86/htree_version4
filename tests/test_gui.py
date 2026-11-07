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
    assert (h1.in_tech, h1.port_shapes, h1.track_patterns) == (True, 4, 1)
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
                     "View": ["Fit", "Zoom Selected", "Blink Selected", "Show View Panel"],
                     "Select": ["Clear Selection"]}
    assert [a.text() for a in w.toolbar.actions()] == ["Fit", "Zoom Selected", "Blink Selected"]
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
