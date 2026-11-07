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


def test_pick_selects_and_reports(loaded):
    loaded.eval("gui_show")
    w = app.window()
    from core.gui.canvas import scene
    item = next(i for i in w.canvas.shape_items["H1"]
                if i.data(0) == "port_shape:top/a/1")
    w.canvas.centerOn(item)
    point = w.canvas.mapFromScene(item.sceneBoundingRect().center())
    assert w.canvas.handle_at(point) == "port_shape:top/a/1"
    w.on_pick("port_shape:top/a/1")
    assert w.canvas.selected[0] is item
    out = loaded.out.getvalue()
    assert "Selected port:top/a  layer H1  rect {9.95 0 10.05 0.4}  direction in  net a" in out
    assert "port:top/a" in w.sel_label.text()
    w.on_pick("")
    assert w.canvas.selected is None and w.sel_label.text() == ""


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
