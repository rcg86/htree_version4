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
def fresh_window(tmp_path, monkeypatch):
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))  # not ~/.config
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
        {"boundary", "ports", "tracks", "rows", "labels"}         # no instances: no Pins
    assert not w.object_boxes["nets"].isChecked()
    assert not w.object_boxes["spine"].isEnabled()             # no spine built
    assert not w.object_boxes["cells"].isEnabled()             # no instances yet
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
                     "Edit": ["Select", "Stretch", "Move", "Snap (tracks, edges, grid)", "Undo Edit",
                              "Shortcuts..."],
                     "View": ["Fit", "Zoom In", "Zoom Out", "Zoom Selected", "Blink Selected",
                              "Ruler", "Clear Rulers", "Show View Panel"],
                     "Select": ["Clear Selection"]}
    assert [a.text() for a in w.toolbar.actions() if a.text()] == \
        ["Fit", "Zoom Selected", "Blink Selected", "Zoom In", "Zoom Out"]
    assert w.ruler_button.text() == "Ruler"                   # next to Blink Selected
    tools = w.toolbar.actions()                               # Zoom In, Zoom Out after Ruler
    ruler = next(i for i, a in enumerate(tools) if w.toolbar.widgetForAction(a) is w.ruler_button)
    assert [a.text() for a in tools[ruler + 1:ruler + 3]] == ["Zoom In", "Zoom Out"]
    assert w.toolbar.widgetForAction(tools[ruler + 3]) is w.tools_button   # then Tools
    assert w.tools_button.text() == "Tools"
    assert [a.text() for a in w.tools_menu.actions() if a.text()] == \
        ["Select", "Stretch", "Move", "Snap (tracks, edges, grid)", "Undo Edit"]
    assert w.toolBarArea(w.toolbar) == w.toolBarArea(w.toolbar).TopToolBarArea  # under the menu


def test_zoom_in_out_buttons(loaded):
    loaded.eval("gui_show")
    w = app.window()
    scale = w.canvas.transform().m11()
    w.act_zoom_in.trigger()
    assert w.canvas.transform().m11() == pytest.approx(scale * 1.5)
    w.act_zoom_out.trigger()
    assert w.canvas.transform().m11() == pytest.approx(scale)


def test_shortcuts_list_and_create(loaded, tmp_path, monkeypatch):
    import json
    from core.gui import shortcuts
    warned = []
    monkeypatch.setattr(shortcuts.QMessageBox, "warning", lambda *a: warned.append(a[2]))
    from PySide6.QtGui import QKeySequence
    from core.gui.shortcuts import NewShortcutDialog, ShortcutsDialog
    loaded.eval("gui_show")
    w = app.window()
    rows = ShortcutsDialog(w).rows()
    assert ("Fit", "F", "built in", "fit") in rows and ("Pan", "Arrow keys", "built in", None) in rows
    assert not [r for r in rows if r[0] in ("Zoom In", "Zoom Out")]   # none until created
    new = NewShortcutDialog(w)
    assert [new.action_box.itemText(i) for i in range(new.action_box.count())] == \
        ["Fit", "Zoom In", "Zoom Out", "Zoom Selected", "Blink Selected", "Ruler",
         "Clear Rulers", "Select", "Stretch", "Move", "Snap (tracks, edges, grid)",
         "Undo Edit", "Clear Selection", "Shortcuts..."]       # all but Close Window
    assert w.set_user_shortcut("zoom_in", "Ctrl+Z") is None
    assert w.set_user_shortcut("zoom_out", "Ctrl+Shift+Z") is None
    assert w.act_zoom_in.shortcut() == QKeySequence("Ctrl+Z")
    assert w.act_zoom_out.shortcut() == QKeySequence("Ctrl+Shift+Z")
    rows = ShortcutsDialog(w).rows()
    assert ("Zoom In", QKeySequence("Ctrl+Z").toString(QKeySequence.NativeText), "user",
            "zoom_in") in rows
    # taken keys are refused; the old shortcut stays
    assert "already the shortcut of Close Window" in w.set_user_shortcut("zoom_in", "Ctrl+W")
    assert "already the shortcut of Zoom Out" in w.set_user_shortcut("zoom_in", "Ctrl+Shift+Z")
    assert w.act_zoom_in.shortcut() == QKeySequence("Ctrl+Z")
    new.accept()                                              # no keys pressed: refused
    assert warned == ["Press the keys for the shortcut first."]
    assert w.act_zoom_in.shortcut() == QKeySequence("Ctrl+Z")
    saved = json.loads((tmp_path / "shortcuts.json").read_text())
    assert saved == {"zoom_in": "Ctrl+Z", "zoom_out": "Ctrl+Shift+Z"}
    # a new window gets them back; removing one saves too
    app.close()
    loaded.eval("gui_show")
    w = app.window()
    assert w.act_zoom_out.shortcut() == QKeySequence("Ctrl+Shift+Z")
    assert w.set_user_shortcut("zoom_out", None) is None
    assert w.act_zoom_out.shortcut().isEmpty()
    assert json.loads((tmp_path / "shortcuts.json").read_text()) == {"zoom_in": "Ctrl+Z"}


def test_tool_and_ruler_shortcuts(loaded, tmp_path):
    import json
    from PySide6.QtGui import QKeySequence
    from core.gui.shortcuts import ShortcutsDialog
    loaded.eval("gui_show")
    w = app.window()
    assert w.act_ruler.shortcut() == QKeySequence("K")       # built in
    assert w.act_clear_rulers.shortcut() == QKeySequence("Shift+K")
    assert w.act_tool_stretch.shortcut() == QKeySequence("S")
    assert w.act_tool_move.shortcut() == QKeySequence("M")
    rows = ShortcutsDialog(w).rows()
    assert ("Ruler", "K", "built in", "ruler") in rows and ("Move", "M", "built in", "tool_move") in rows
    # S turns Stretch on; S again goes back to Select
    w.act_tool_stretch.trigger()
    assert w.canvas.edit["mode"] == "stretch" and w.tools_button.text() == "Tools: Stretch"
    w.act_tool_stretch.trigger()
    assert w.act_tool_select.isChecked() and w.canvas.edit["mode"] is None
    w.act_tool_move.trigger()
    w.act_tool_stretch.trigger()                              # M then S: Stretch
    assert w.canvas.edit["mode"] == "stretch"
    w.act_ruler.trigger()                                     # K: the ruler, edit mode off
    assert w.canvas.ruler["on"] and w.canvas.edit["mode"] is None
    # user shortcuts replace the built in one; removing them brings it back
    assert w.set_user_shortcut("tool_stretch", "Ctrl+E") is None
    assert w.act_tool_stretch.shortcut() == QKeySequence("Ctrl+E")
    assert w.set_user_shortcut("ruler", "R") is None
    assert w.set_user_shortcut("tool_select", "Q") is None    # no built in one
    assert "already the shortcut of Move" in w.set_user_shortcut("ruler", "M")
    assert json.loads((tmp_path / "shortcuts.json").read_text()) == \
        {"tool_stretch": "Ctrl+E", "ruler": "R", "tool_select": "Q"}
    app.close()                                               # kept for the next window
    loaded.eval("gui_show")
    w = app.window()
    assert w.act_tool_stretch.shortcut() == QKeySequence("Ctrl+E")
    assert w.act_tool_select.shortcut() == QKeySequence("Q")
    assert w.set_user_shortcut("tool_stretch", None) is None
    assert w.act_tool_stretch.shortcut() == QKeySequence("S")
    assert w.set_user_shortcut("tool_select", None) is None
    assert w.act_tool_select.shortcut().isEmpty()


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


def test_segment_touches_rect():
    from core.gui.layout_data import segment_touches_rect
    box = (0, 0, 10, 10)
    assert segment_touches_rect((5, -5), (5, 20), box)          # crosses
    assert segment_touches_rect((2, 2), (3, 3), box)            # inside
    assert segment_touches_rect((-5, 10), (20, 10), box)        # along an edge
    assert not segment_touches_rect((11, -5), (11, 20), box)    # parallel, outside
    assert not segment_touches_rect((-5, 12), (12, -5 + 22), box)
    assert not segment_touches_rect((12, 0), (20, 5), box)
    assert segment_touches_rect((5, 5), (5, 5), box)            # a point
    assert not segment_touches_rect((15, 5), (15, 5), box)


def test_right_drag_selects_touching(loaded):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import scene
    w = _view(loaded)
    w.set_all_layers(True)
    w.canvas.fitInView(QRectF(scene(9.5, 1), scene(10.5, -0.5)), Qt.KeepAspectRatio)
    before = abs(w.canvas.transform().m11())
    # pin a is x 9.95..10.05, y 0..0.4; the box covers only its right half
    _drag(w, w.canvas.mapFromScene(scene(10.0, 0.5)), w.canvas.mapFromScene(scene(10.3, -0.2)),
          button=Qt.RightButton)
    assert loaded.eval("get_db selected") == "port:top/a"
    assert abs(w.canvas.transform().m11()) == before            # no zoom
    assert not w.canvas._rband.isVisible()
    # a right click alone keeps the selection
    p = w.canvas.mapFromScene(scene(10.4, -0.4))
    _drag(w, p, p, button=Qt.RightButton)
    assert loaded.eval("get_db selected") == "port:top/a"
    # Ctrl+right drag adds; a box touching nothing with plain right drag clears
    w.canvas.fit()
    _drag(w, w.canvas.mapFromScene(scene(19.95, 0.1)), w.canvas.mapFromScene(scene(25, -1)),
          button=Qt.RightButton, mods=Qt.ControlModifier)
    assert sorted(loaded.split_list(loaded.eval("get_db selected"))) == \
        ["port:top/a", "port:top/b"]
    _drag(w, w.canvas.mapFromScene(scene(60, 10)), w.canvas.mapFromScene(scene(70, 20)),
          button=Qt.RightButton)
    assert loaded.eval("get_db selected") == ""


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


def test_blank_tracks_start_hidden_and_draw_dashed(tech_session, write_lef):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    from core.gui.layout_data import BLANK_COLOR
    tech_session.eval(f"read_def -file {write_lef(ASSIGN_DEF, 'a.def')}")
    tech_session.eval("assign_track_for_route -layer H1 -net {VDD, -, NA, VSS, -, NA}")
    tech_session.eval("gui_show")
    w = app.window()
    box = w.assign_boxes[("H1", "NA")]
    assert box.text() == "blank (NA)  (3)" and not box.isChecked()
    assert ("H1", "NA") in w.canvas.assign_hidden
    w.resize(900, 700)
    w.object_boxes["tracks"].setChecked(True)
    w.object_boxes["boundary"].setChecked(False)
    w.canvas.fitInView(QRectF(scene(0, 10), scene(10, 0)), Qt.KeepAspectRatio)
    QApplication.processEvents()
    styles = {(round(a[1], 3)): style for _, style, a, b in
              w.canvas.track_segments(w.canvas.sceneRect()) if a[1] == b[1]}
    assert 2.5 not in styles                                   # blank track hidden
    box.setChecked(True)
    styles = {(round(a[1], 3)): style for _, style, a, b in
              w.canvas.track_segments(w.canvas.sceneRect()) if a[1] == b[1]}
    assert styles[2.5] == "dash" and styles[0.5] == "solid" and styles[1.5] == "dot"
    assert w.layout.assignments[0].colors["NA"] == BLANK_COLOR



# -- instances in the GUI ---------------------------------------------------------------------

CELLS_LEF_PATH = ROOT / "tests" / "data" / "cells.lef"


@pytest.fixture
def with_inst(loaded):
    loaded.eval(f"read_lef -file {{{CELLS_LEF_PATH}}}")
    loaded.eval("create_inst -ref_cell INV_D1 -location {50 40} -name u1")
    loaded.out.seek(0)
    loaded.out.truncate()
    return loaded


def test_load_insts_places_pins(with_inst):
    lay = load_layout(with_inst.db)
    inst, = lay.insts
    assert (inst.handle, inst.ref, inst.bbox) == ("inst:u1", "INV_D1", (50, 40, 50.6, 40.254))
    # INV_D1 pin A: M1 rect (0.1 0.2 0 0) -> placed and normalized at (50, 40)
    assert ("A", "M1", "rect", [50, 40, 50.1, 40.2]) in inst.pins
    assert lay.layer("M1").port_shapes == 1 + 2                # port y[0] + INV_D1 A and Y on M1


def test_insts_drawn_and_selectable(with_inst):
    with_inst.eval("gui_show")
    w = app.window()
    assert w.object_boxes["cells"].isEnabled() and w.object_boxes["cells"].isChecked()
    box, = w.canvas.inst_items
    assert box.isVisible() and box.data(1) == "inst:u1"
    w.canvas.centerOn(box)
    point = w.canvas.mapFromScene(box.sceneBoundingRect().center())
    assert w.canvas.owner_at(point) == "inst:u1"
    w.on_select(["inst:u1"], "replace")
    assert with_inst.eval("get_db selected") == "inst:u1"
    assert box in w.canvas.highlighted
    assert "Selected inst:u1  INV_D1  at {50 40} N  bbox {50 40 50.6 40.254}" in \
        with_inst.out.getvalue()
    w.object_boxes["cells"].setChecked(False)
    assert not box.isVisible()


def test_create_inst_after_gui_show_appears(loaded):
    loaded.eval(f"read_lef -file {{{CELLS_LEF_PATH}}}")
    loaded.eval("gui_show")
    w = app.window()
    assert w.canvas.inst_items == []
    loaded.eval("create_inst -ref_cell INV_D2 -location {10 10}")
    assert len(w.canvas.inst_items) == 1


def test_rebuilt_layer_list_has_no_stale_widgets(with_inst):
    from PySide6.QtWidgets import QCheckBox
    with_inst.eval("gui_show")
    w = app.window()
    with_inst.eval("create_inst -ref_cell INV_D2 -location {10 10}")   # refresh rebuilds
    shown = [b for b in w.layer_group.findChildren(QCheckBox) if b.isVisibleTo(w)]
    assert len(shown) == 4 * len(w.layer_boxes) + 3       # the layer, then S P G; All layers
    assert len(w.class_boxes) == 3 * len(w.layer_boxes)


def test_layers_dropdown(loaded):
    loaded.eval("gui_show")
    w = app.window()
    assert w.layer_toggle.isChecked() and w.layer_boxes["H1"].isVisibleTo(w)
    w.layer_toggle.setChecked(False)                      # closed: the list is hidden
    assert not w.layer_boxes["H1"].isVisibleTo(w)
    assert not w.class_boxes[("H1", "power")].isVisibleTo(w)
    assert w.layer_boxes["H1"].isChecked()                # still drawn
    w.layer_toggle.setChecked(True)
    assert w.layer_boxes["H1"].isVisibleTo(w)


def test_all_layers_class_boxes(loaded):
    loaded.eval("gui_show")
    w = app.window()
    power = {k: b for k, b in w.class_boxes.items() if k[1] == "power"}
    assert w.all_class_boxes["power"].isChecked()
    w.all_class_boxes["power"].setChecked(False)          # every layer's P goes off
    assert not any(b.isChecked() for b in power.values())
    assert {k for k in power} <= w.canvas.class_hidden
    assert all(b.isChecked() for k, b in w.class_boxes.items() if k[1] != "power")
    power[("H1", "power")].setChecked(True)               # one back on: All stays off
    assert not w.all_class_boxes["power"].isChecked()
    w.all_class_boxes["power"].setChecked(True)
    assert all(b.isChecked() for b in power.values()) and not w.canvas.class_hidden
    w.class_boxes[("H1", "ground")].setChecked(False)     # one off: All G unchecks
    assert not w.all_class_boxes["ground"].isChecked()
    w.class_boxes[("H1", "ground")].setChecked(True)      # all on again: All G checks
    assert w.all_class_boxes["ground"].isChecked()


def test_net_class():
    from core.gui.layout_data import net_class
    assert net_class("VDD_SOC") == net_class("VDD") == net_class("vcc1") == "power"
    assert net_class("VSS") == net_class("GND") == "ground"
    assert net_class("temp_L1_inv1_Y") == net_class("SIGNAL") == net_class(None) == "signal"
    assert net_class("PWR", "POWER") == "power" and net_class("X", "ground") == "ground"
    assert net_class("VDD_SOC", "signal") == "power"      # no power/ground USE: the name


def test_port_classes_from_use(assigned):
    lay = load_layout(assigned.db)
    assert {s.cls for s in lay.shapes} <= {"power"} and all(s.cls == "power" for s in lay.shapes)



# -- Pins checkbox and pin name labels ---------------------------------------------------------

def test_pins_checkbox_is_separate_from_cells(with_inst):
    with_inst.eval("gui_show")
    w = app.window()
    w.layer_boxes["M1"].setChecked(True)
    pins = [i for its in w.canvas.inst_pin_items.values() for i in its]
    box, = w.canvas.inst_items
    assert w.object_boxes["pins"].isEnabled() and all(i.isVisible() for i in pins)
    w.object_boxes["pins"].setChecked(False)                   # pins off, outline stays
    assert not any(i.isVisible() for i in pins) and box.isVisible()
    w.object_boxes["pins"].setChecked(True)
    w.object_boxes["cells"].setChecked(False)                  # outline off, pins stay
    assert all(i.isVisible() for i in pins) and not box.isVisible()


def test_labels(with_inst):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    view = QRectF(scene(49.5, 40.5), scene(51, 39.5))           # around inst u1
    assert w.canvas.label_positions(view) == []                 # labels off by default
    w.object_boxes["labels"].setChecked(True)
    names = sorted(n for n, _ in w.canvas.label_positions(view))
    assert names == ["A", "A"]          # INV_D1 pin A: H1 rect + H1 polygon shown (M1 hidden)
    w.layer_boxes["M1"].setChecked(True)
    names = sorted(n for n, _ in w.canvas.label_positions(view))
    assert names == ["A", "A", "A", "Y"]                        # + A and Y on M1
    # the label sits at the shape centre
    centers = {round(c.x(), 3): n for n, c in w.canvas.label_positions(view) if n == "Y"}
    assert list(centers) == [50.55]                             # Y rect x 50.5..50.6
    w.object_boxes["pins"].setChecked(False)                    # hidden pins: no labels
    assert w.canvas.label_positions(view) == []


def test_port_labels_and_limit(loaded, monkeypatch):
    from core.gui import canvas as canvas_mod
    loaded.eval("gui_show")
    w = app.window()
    w.object_boxes["labels"].setChecked(True)
    names = {n for n, _ in w.canvas.label_positions(w.canvas.sceneRect())}
    assert names == {"a", "b", "c", "d"}                        # H1/H2 ports shown; y[0] on M1 hidden
    monkeypatch.setattr(canvas_mod, "MAX_LABELS", 2)
    assert w.canvas.label_positions(w.canvas.sceneRect()) == []  # too many: zoom in


def test_labels_painted(with_inst):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    w.resize(900, 700)
    w.canvas.fitInView(QRectF(scene(49.8, 40.4), scene(50.8, 39.8)), Qt.KeepAspectRatio)
    QApplication.processEvents()
    before = w.canvas.viewport().grab().toImage()
    w.object_boxes["labels"].setChecked(True)
    QApplication.processEvents()
    after = w.canvas.viewport().grab().toImage()
    # anti-aliased 8 pt text blends with the pin colour, so count changed pixels
    changed = sum(1 for x in range(after.width()) for y in range(after.height())
                  if after.pixelColor(x, y) != before.pixelColor(x, y))
    assert changed > 40                                         # two "A" labels drawn



# -- selecting instance pins -------------------------------------------------------------------

def _zoom_on(w, x1, y1, x2, y2):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    w.resize(900, 700)
    w.canvas.fitInView(QRectF(scene(x1, y2), scene(x2, y1)), Qt.KeepAspectRatio)
    QApplication.processEvents()


def test_click_on_shown_pin_selects_the_pin(with_inst):
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    w.layer_boxes["M1"].setChecked(True)
    _zoom_on(w, 49.9, 39.9, 50.7, 40.35)                        # cell u1 fills the view
    on_y = w.canvas.mapFromScene(scene(50.55, 40.05))           # on pin Y (M1 50.5..50.6)
    assert w.canvas.owner_at(on_y) == "pin:u1/Y"
    _send(w, "press", on_y, *_left())
    _send(w, "release", on_y, _left()[0], _nobutton())
    assert with_inst.eval("get_db selected") == "pin:u1/Y"
    assert "Selected pin:u1/Y  direction out  use signal  layers M1  rect {50.5 40 50.6 40.1}" \
        in with_inst.out.getvalue()
    lit = w.canvas.highlighted
    assert lit and all(i.data(1) == "pin:u1/Y" for i in lit)   # only that pin lights up
    empty = w.canvas.mapFromScene(scene(50.45, 40.22))          # inside the cell, off pins
    assert w.canvas.owner_at(empty) == "inst:u1"


def test_hidden_pins_select_the_instance(with_inst):
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    w.layer_boxes["M1"].setChecked(True)
    _zoom_on(w, 49.9, 39.9, 50.7, 40.35)
    w.object_boxes["pins"].setChecked(False)
    assert w.canvas.owner_at(w.canvas.mapFromScene(scene(50.55, 40.05))) == "inst:u1"


def test_shift_drag_selects_pins_or_whole_instance(with_inst):
    from PySide6.QtCore import QRectF
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    w.layer_boxes["M1"].setChecked(True)
    _zoom_on(w, 49.9, 39.9, 50.7, 40.35)
    around_y = QRectF(scene(50.45, 40.15), scene(50.65, 39.95))
    assert w.canvas.owners_in(around_y) == ["pin:u1/Y"]
    whole = QRectF(scene(49.95, 40.3), scene(50.65, 39.95))
    assert w.canvas.owners_in(whole) == ["inst:u1"]             # not inst + every pin


def test_inst_selection_lights_its_pins(with_inst):
    with_inst.eval("gui_show")
    w = app.window()
    w.on_select(["inst:u1"], "replace")
    owners = {i.data(1) for i in w.canvas.highlighted}
    assert owners == {"inst:u1", "pin:u1/A", "pin:u1/Y"}


def test_pin_objects(with_inst):
    ev = with_inst.eval
    assert ev("get_db inst:u1 .pins") == "pin:u1/A pin:u1/Y"
    assert ev("get_db pin:u1/A .name") == "A"
    assert ev("get_db pin:u1/A .inst") == "inst:u1"
    assert ev("get_db pin:u1/A .lib_pin") == "lib_pin:INV_D1/A"
    assert (ev("get_db pin:u1/A .direction"), ev("get_db pin:u1/A .use")) == ("in", "signal")
    assert ev("get_db pin:u1/A .layers") == "M1 H1"
    assert ev("get_db pin:u1/A .rect") == "50 40 50.4 40.2"
    assert ev("get_db inst:u1 .pins.name -if {.direction == out}") == "Y"
    ev("select_obj pin:u1/Y")
    assert ev("get_db selected .inst") == "inst:u1"
    for bad in ("pin:u1/Z", "pin:nope/A", "pin:u1"):
        with pytest.raises(tkinter.TclError):
            ev(f"get_db {bad} .name")



def test_highlight_pen_does_not_change_picking(with_inst):
    from PySide6.QtCore import QRectF
    from core.gui.canvas import scene
    with_inst.eval("gui_show")
    w = app.window()
    w.layer_boxes["M1"].setChecked(True)
    _zoom_on(w, 49.9, 39.9, 50.7, 40.35)
    w.on_select(["pin:u1/Y"], "replace")                       # Y drawn with a thick outline
    assert w.canvas.owner_at(w.canvas.mapFromScene(scene(50.45, 40.22))) == "inst:u1"
    tight = QRectF(scene(50.49, 40.11), scene(50.61, 39.99))   # just around Y's rect
    assert w.canvas.owners_in(tight) == ["pin:u1/Y"]


# -- create_spine -------------------------------------------------------------------------

SPINE_YAML = """spine_spec:
  name: sp1
  constraints:
    max_drive_length: 30
  placement:
    level_pitch: 2.88
  spine:
    orientation: vertical
    span: 40
  stubs:
    gap: 2
  levels:
    L1:
      cells:
        inv1: {input: net}
    L2:
      cells:
        inv1: {input: L1/inv1/Y, output: stub1}
        inv2: {input: L1/inv1/Y, output: stub2}
"""


@pytest.fixture
def spine_loaded(loaded, write_lef):
    pytest.importorskip("scipy")
    loaded.eval(f"read_lef -file {{{ROOT / 'tests' / 'data' / 'cells.lef'}}}")
    loaded.eval(f"read_spine_spec -file {{{write_lef(SPINE_YAML, 'sp.yaml')}}}")
    return loaded


def test_validate_show_draws_schematic_tab(spine_loaded):
    spine_loaded.eval("create_spine -name sp1 -spec_name sp1 -location {10 5} -validate -show")
    w = app.window()
    assert w.tabs.count() == 2 and w.tabs.currentWidget() is w.schematic
    assert w.tabs.tabText(1) == "Schematic: sp1"
    texts = [i.text() for i in w.schematic.scene().items() if hasattr(i, "text")]
    assert {"L1_inv1", "L2_inv1", "L2_inv2", "stubs"} <= set(texts)
    assert spine_loaded.eval("get_db insts") == ""              # nothing built
    spine_loaded.eval("create_spine -name sp1 -spec_name sp1 -location {20 5} -validate -show")
    assert w.tabs.count() == 2                                  # the same tab, redrawn


def test_built_spine_in_layout_tab(spine_loaded):
    spine_loaded.eval("gui_show")
    w = app.window()
    assert not w.object_boxes["spine"].isEnabled()
    spine_loaded.eval("create_spine -name sp1 -spec_name sp1 -location {10 5} -build "
                      "-ref_cell INV_D1")
    assert w.object_boxes["spine"].isEnabled()
    assert len(w.layout.spines) == 1 and len(w.layout.spines[0].stubs) == 2
    items = w.canvas.spine_items
    assert items and all(i.isVisible() for i in items)
    w.object_boxes["spine"].setChecked(False)
    assert not any(i.isVisible() for i in items)
    assert len(w.layout.insts) == 3                             # the cells are instances


def test_spine_nets_and_stubs_selectable(spine_loaded):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import scene
    spine_loaded.eval("create_spine -name sp1 -spec_name sp1 -location {10 5} -build "
                      "-ref_cell INV_D1")
    w = _view(spine_loaded)
    nets = set(spine_loaded.split_list(spine_loaded.eval("get_db spine:sp1 .spine_nets")))
    stubs = set(spine_loaded.split_list(spine_loaded.eval("get_db spine:sp1 .stubs")))
    assert nets and stubs
    everything = set(w.canvas.owners_in(w.canvas.content.adjusted(-5, -5, 5, 5),
                                        touching=True))
    assert nets | stubs <= everything
    assert set(spine_loaded.split_list(spine_loaded.eval("get_db spine:sp1 .insts"))) \
        <= everything
    # right drag over the middle of one net segment selects that net only
    net, (x1, y1, x2, y2) = w.layout.spines[0].segments[0]
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    w.canvas.zoom_to(QRectF(scene(mx - 0.5, my + 0.5), scene(mx + 0.5, my - 0.5)))
    _drag(w, w.canvas.mapFromScene(scene(mx - 0.05, my + 0.05)),
          w.canvas.mapFromScene(scene(mx + 0.05, my - 0.05)), button=Qt.RightButton)
    assert spine_loaded.eval("get_db selected") == f"spine_net:sp1/{net}"
    lit = [i for i in w.canvas.highlighted if i.data(1) == f"spine_net:sp1/{net}"]
    assert len(lit) == sum(1 for n, _ in w.layout.spines[0].segments if n == net)
    assert f"spine_net:sp1/{net}" in w.sel_label.text() and "driver" in w.sel_label.text()
    # a click on the line selects it too; hiding the spine makes it unpickable
    spine_loaded.eval("deselect_obj -all")
    p = w.canvas.mapFromScene(scene(mx, my))
    _drag(w, p, p)
    assert spine_loaded.eval("get_db selected") == f"spine_net:sp1/{net}"
    w.object_boxes["spine"].setChecked(False)
    assert w.canvas.owners_in(w.canvas.content.adjusted(-5, -5, 5, 5), touching=True) and \
        not (nets | stubs) & set(w.canvas.owners_in(w.canvas.content.adjusted(-5, -5, 5, 5),
                                                    touching=True))


# -- placement rows and sites ---------------------------------------------------------------

def test_load_site_rows(loaded):
    from core.gui.layout_data import load_site_rows, visible_rows
    (sr,) = load_site_rows(loaded.db)                     # small.def: r1 N at 0, r2 FS at 0.2
    assert (sr.site, sr.width, sr.height) == ("core", 0.1, 0.2)   # no cells: the row gap
    assert sr.rows == [(0.0, 0.0, 10, 0.1, "N"), (0.2, 0.0, 10, 0.1, "FS")]
    assert [r[0] for r in visible_rows(sr, 0, 0.05, 1, 0.1)] == [0.0]
    assert [r[0] for r in visible_rows(sr, 0, 0.25, 1, 0.3)] == [0.2]
    assert visible_rows(sr, 2, 0, 3, 1) == []             # right of the rows
    assert visible_rows(sr, 0, 0, 1, 1, limit=1) is None  # too many: none drawn


SITE_LEF = """MACRO INV
  CLASS CORE ;
  SIZE 0.24 BY 0.254 ;
  SITE s60 ;
END INV
"""
SITE_DEF = """DESIGN t ;
UNITS DISTANCE MICRONS 1000 ;
DIEAREA ( 0 0 ) ( 10000 10000 ) ;
ROW r1 s60 0 0 N DO 100 BY 3 STEP 60 127 ;
END DESIGN
"""


def test_site_height_from_cells(tech_session, write_lef):
    from core.gui.layout_data import load_site_rows
    tech_session.eval(f"read_lef -file {write_lef(SITE_LEF, 'c.lef')}")
    tech_session.eval(f"read_def -file {write_lef(SITE_DEF, 'd.def')}")
    (sr,) = load_site_rows(tech_session.db)
    assert (sr.width, sr.height, len(sr.rows)) == (0.06, 0.127, 3)   # BY 3: three rows
    assert [r[0] for r in sr.rows] == [0.0, 0.127, 0.254]             # the pitch, not the cell
    tech_session.eval(f"read_def -file {write_lef(SITE_DEF.replace('BY 3', 'BY 1'), 'e.def')}")
    (sr,) = load_site_rows(tech_session.db)
    assert (sr.height, len(sr.rows)) == (0.254, 1)        # one row: the cell height


def test_rows_drawn_and_site_dropdown(loaded):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import scene
    loaded.eval("gui_show")
    w = app.window()
    w.resize(900, 700)
    box = w.object_boxes["rows"]
    assert box.isEnabled() and not box.isChecked()        # off at start
    assert set(w.site_boxes) == {"core"} and w.site_boxes["core"].isChecked()
    w.rows_toggle.setChecked(True)
    assert w.site_boxes["core"].isVisibleTo(w)
    for key in ("boundary", "ports"):
        w.object_boxes[key].setChecked(False)
    w.canvas.fitInView(QRectF(scene(-0.1, 0.5), scene(1.1, -0.1)), Qt.KeepAspectRatio)
    color = QColor(w.layout.site_rows[0].color).name()

    def drawn():
        QApplication.processEvents()
        img = w.canvas.viewport().grab().toImage()
        p = w.canvas.mapFromScene(scene(0.55, 0.0))       # the bottom edge of r1
        return color in {img.pixelColor(p.x(), p.y() + d).name() for d in (-1, 0, 1)}

    assert not drawn()
    box.setChecked(True)
    assert drawn()
    w.site_boxes["core"].setChecked(False)                # that site hidden
    assert not drawn()
    w.site_boxes["core"].setChecked(True)
    assert drawn()
    w.canvas.fitInView(QRectF(scene(-5000, 5000), scene(5000, -5000)), Qt.KeepAspectRatio)
    QApplication.processEvents()                          # far out: too dense, none drawn
    img = w.canvas.viewport().grab().toImage()
    p = w.canvas.mapFromScene(scene(0.55, 0.0))
    assert img.pixelColor(p.x(), p.y()).name() != color
