"""The DRC Violations table of the GUI: check_drc keeps its run, the window
lists it, and a click on a violation shows only its nets (show_only), selects
its shapes and zooms to its box."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import tkinter

import pytest

pytest.importorskip("scipy")

from core import drc
from test_check_drc import rules, wires  # noqa: F401  (rules is a fixture)
from test_gui_vias import shown  # noqa: F401  (a fixture)
from test_route_pin import out_of
from test_vias import routed, via_session  # noqa: F401  (fixtures)

N1, N2, N3 = (f"spine_net:sp/sp_L{k}_inv1_Y" for k in (1, 2, 3))
# The shorts of the routed test spine, in the order of the report.
FIRST = ("IA", (4.14, 7.7, 4.5, 8.42), ("sp_L1_inv1_Y", "sp_L2_inv1_Y"),
         ("strap:sp_L2_inv1/5", "strap:sp_L3_inv1/5"))


# -- what check_drc keeps ------------------------------------------------------------

def test_violations_carry_their_nets_and_shapes(rules):
    s = rules
    wires(s, "a", ("wire", "MA", "0 0 10 0.2"), ("wire", "MA", "0 5 10 5.05"))   # one thin
    wires(s, "b", ("wire", "MA", "8 0.1 12 0.3"),                                # over a
          ("shield", "MA", "20 0 30 0.2", "VSS"))                                # tied to no cell
    assert s.db.drc is None
    count = int(s.eval("check_drc"))
    text = out_of(s)
    report = s.db.drc
    assert len(report.rows) == count == 3
    assert report.head[0] == "check_drc: every layer" and report.head[0] in text
    assert report.summary[-1].split() == ["Total", "3"]
    got = {title: v for title, v in report.rows}
    short = got["Shorts"]
    assert (short.check, short.source, short.layer) == ("short", "", "MA")
    assert short.nets == ("a", "b") and short.handles == ("net_wire:a/1", "net_wire:b/1")
    assert short.bbox == (8.0, 0.1, 10.0, 0.2)
    width = got["Tech width (tech LEF)"]
    assert width.nets == ("a",) and width.handles == ("net_wire:a/2",)
    is_open = got["Opens, power nets"]
    assert (is_open.check, is_open.source, is_open.layer) == ("open", "power", "")
    assert is_open.nets == ("VSS",) and is_open.handles == ("net_wire:b/2",)
    # The rows are the lines of the report, in its order.
    lines = [line.strip() for line in text.splitlines() if line.startswith("  ") and "{" in line]
    assert [f"{v.layer + ' ' if v.layer else ''}{drc.box_text(v.bbox)}  {v.text}"
            for _, v in report.rows] == lines


def test_the_last_run_is_kept(rules, tmp_path):
    s = rules
    assert s.eval("check_drc") == "0"
    first = s.db.drc
    assert first.rows == [] and first.summary[-1].split() == ["Total", "0"]
    wires(s, "a", ("wire", "MA", "0 0 10 0.2"))
    wires(s, "b", ("wire", "MA", "8 0.1 12 0.3"))
    with pytest.raises(tkinter.TclError):                # no run: the one before stays
        s.eval("check_drc -layer_range nope")
    assert s.db.drc is first
    path = tmp_path / "drc.rpt"
    assert s.eval(f"check_drc -check_shorts_only -layer_range MA -file {{{path}}}") == "1"
    assert s.db.drc is not first and [t for t, _ in s.db.drc.rows] == ["Shorts"]
    assert s.db.drc.head[0] == "check_drc: layers MA"
    saved = tmp_path / "a.deb"
    s.eval(f"write_db -file {{{saved}}}")                # session state: not saved
    s.eval(f"read_db -file {{{saved}}}")
    assert s.db.drc is None


def test_objects_shown_for_a_violation(routed):
    from core.gui.drc_table import debug_objects
    db = routed.db
    v = lambda nets, handles: drc.Violation("short", "", "IA", (0, 0, 1, 1), "", nets, handles)
    assert debug_objects(db, v(*FIRST[2:])) == [N1, N2]
    # A power net is no net object: by its name.
    assert debug_objects(db, v(("VSS", "sp_L1_inv1_Y"), ())) == ["net:VSS", N1]
    # A strap not routed yet and a pin nothing is connected to: the instance.
    assert debug_objects(db, v(("sp_L1_inv1_Y", "sp_L2_inv1/strap9"),
                               ("net_wire:sp_L1_inv1_Y/1", "strap:sp_L2_inv1/9"))) == \
        [N1, "inst:sp_L2_inv1"]
    assert debug_objects(db, v(("sp_L3_inv1/B",), ("pin:sp_L3_inv1/B",))) == ["inst:sp_L3_inv1"]
    # A pin of the netlist is drawn with its net, a power pin with its instance.
    assert debug_objects(db, v(("sp_L1_inv1_Y",), ("pin:sp_L1_inv1/Y",))) == [N1]
    assert debug_objects(db, v(("sp_L1_inv1_Y", "VSS"),
                               ("net_wire:sp_L1_inv1_Y/1", "pin:sp_L3_inv1/VSS"))) == \
        [N1, "net:VSS", "inst:sp_L3_inv1"]
    assert debug_objects(db, v(("gone", "u9/A"), ("net_wire:gone/1", "pin:u9/A"))) == []


# -- the window -------------------------------------------------------------------------

def view_box(w):
    """(x1, y1, x2, y2) of the layout the window shows."""
    r = w.canvas.mapToScene(w.canvas.viewport().rect()).boundingRect()
    return r.left(), -r.bottom(), r.right(), -r.top()


def inside(box, view):
    return view[0] <= box[0] and view[1] <= box[1] and box[2] <= view[2] and box[3] <= view[3]


def cells(t, row):
    return [t.table.item(row, c).text() for c in range(t.table.columnCount())]


def test_check_drc_opens_the_table(shown):
    s, w = shown
    t = w.drc_table
    assert t.isHidden() and t.table.rowCount() == 0
    assert s.eval("check_drc") == "2"
    assert not t.isHidden() and t.table.rowCount() == 2
    assert t.summary.text() == "2 violation(s), every layer"
    assert "short     -       IA      2" in t.summary.toolTip()
    assert [t.filter_box.itemText(k) for k in range(t.filter_box.count())] == \
        ["All (2)", "Shorts (2)"]
    assert cells(t, 0) == [
        "1", "short", "-", "IA", "sp_L1_inv1_Y, sp_L2_inv1_Y", "{4.14 7.7 4.5 8.42}",
        "strap:sp_L2_inv1/5 (sp_L1_inv1_Y) and strap:sp_L3_inv1/5 (sp_L2_inv1_Y) "
        "overlap 0.36 x 0.72"]
    assert [t.violation(row) for row in range(2)] == [v for _, v in s.db.drc.rows]
    # Nothing on the layout changes until a violation is clicked.
    assert s.db.show_only == [] and s.db.selection == []
    # The next run is listed in its place; one with nothing to list too.
    assert s.eval("check_drc -check_open_only -layer_range IA") == "0"
    assert not t.isHidden() and t.table.rowCount() == 0
    assert t.summary.text() == "No violations, layers IA"
    assert not t.filter_box.isEnabled()


def test_a_click_shows_the_nets_of_the_violation(shown):
    from test_show_only import seen
    s, w = shown
    s.eval("check_drc")
    out_of(s)
    whole, everything = view_box(w), seen(w)
    t = w.drc_table
    t.table.cellClicked.emit(0, 5)
    layer, box, nets, handles = FIRST
    assert s.db.show_only == [N1, N2]                    # show_only, as if typed
    assert f"show_only -object {{{N1} {N2}}}" in out_of(s)
    assert w.only_label.text() == "Showing only: sp/sp_L1_inv1_Y, sp/sp_L2_inv1_Y"
    routes = [h for h in seen(w) if h.startswith(("net_wire:", "strap:"))]
    assert set(handles) <= set(routes) and len(seen(w)) < len(everything)
    assert not [h for h in routes if h.startswith("net_wire:sp_L3")]
    assert s.db.selection == list(handles)               # its shapes, selected
    assert w.name_label.text() == "sp_L1_inv1_Y, sp_L2_inv1_Y"
    view = view_box(w)                                   # zoomed to its box
    assert inside(box, view) and view[2] - view[0] < (whole[2] - whole[0]) / 2
    # Another violation: its nets in place of the first ones.
    t.table.cellClicked.emit(1, 0)
    assert s.db.show_only == [N2, N3]
    assert s.db.selection == ["strap:sp_L2_inv1/3", "strap:sp_L3_inv1/3"]
    assert inside(t.violation(1).bbox, view_box(w))
    # Show All; a click on the same row shows it again.
    t.all_button.click()
    assert s.db.show_only == [] and seen(w) == everything and w.only_label.text() == ""
    assert "show_only -show_all" in out_of(s)
    t.table.cellClicked.emit(1, 0)
    assert s.db.show_only == [N2, N3]


def test_arrow_keys_step_through_the_violations(shown):
    s, w = shown
    s.eval("check_drc")
    t = w.drc_table
    t.table.setCurrentCell(0, 0)
    assert s.db.show_only == [N1, N2]
    assert s.db.selection == ["strap:sp_L2_inv1/5", "strap:sp_L3_inv1/5"]
    t.table.setCurrentCell(1, 0)
    assert s.db.show_only == [N2, N3] and inside(t.violation(1).bbox, view_box(w))
    s.eval("show_only -show_all")
    t.table.setCurrentCell(1, 4)                         # the same row: nothing new
    assert s.db.show_only == []


def test_sorted_and_filtered_rows_keep_their_violation(shown):
    from PySide6.QtCore import Qt
    s, w = shown
    s.db.set_net_wires("a", [("wire", "IA", "30 30 40 30.36")])
    s.db.set_net_wires("b", [("wire", "IA", "35 30.2 45 30.56"),       # over a's wire
                             ("wire", "IA", "35 33 45 33.1")])         # thin
    assert s.eval("check_drc") == "4"
    t = w.drc_table
    titles = [title for title, _ in s.db.drc.rows]
    assert titles == ["Shorts"] * 3 + ["Tech width (tech LEF)"]
    assert [t.filter_box.itemText(k) for k in range(t.filter_box.count())] == \
        ["All (4)", "Shorts (3)", "Tech width (tech LEF) (1)"]
    t.filter_box.setCurrentIndex(2)
    assert [t.table.isRowHidden(row) for row in range(4)] == [True] * 3 + [False]
    t.filter_box.setCurrentIndex(0)
    assert not any(t.table.isRowHidden(row) for row in range(4))
    t.table.sortByColumn(0, Qt.DescendingOrder)          # by number: as numbers
    assert [t.table.item(row, 0).text() for row in range(4)] == [str(k) for k in range(4, 0, -1)]
    assert t.violation(0).check == "width" and t.table.item(0, 2).text() == "tech"
    t.table.cellClicked.emit(0, 0)
    assert s.db.show_only == ["net:b"]                   # a net of no spine, one net only
    assert s.db.selection == ["net_wire:b/2"]
    assert inside(t.violation(0).bbox, view_box(w))
    t.filter_box.setCurrentIndex(1)                      # the sorted rows, filtered
    assert [t.table.isRowHidden(row) for row in range(4)] == [True] + [False] * 3


def test_a_violation_whose_shapes_are_gone(shown):
    s, w = shown
    s.eval("check_drc")
    t = w.drc_table
    s.eval("delete_route -nets sp_L2_inv1_Y")            # the table is the run as it was
    assert t.table.rowCount() == 2 and not t.isHidden()
    t.table.cellClicked.emit(1, 0)
    assert s.db.show_only == [N2, N3]                    # the nets are still there
    assert s.db.selection == ["strap:sp_L2_inv1/3", "strap:sp_L3_inv1/3"]
    # Nets that are gone: nothing is shown alone, the status bar says why.
    s.eval("show_only -show_all")
    w.show_violation(drc.Violation("short", "", "IA", (1, 1, 2, 2), "", ("gone", "too"),
                                   ("net_wire:gone/1", "net_wire:too/1")))
    assert s.db.show_only == [] and s.db.selection == []
    assert "check_drc again" in w.statusBar().currentMessage()
    # A violation without shapes (a stub with no wire): its net is selected.
    w.show_violation(drc.Violation("open", "signal", "", (1, 1, 1, 1), "", ("sp_L1_inv1_Y",)))
    assert s.db.show_only == [N1] and s.db.selection == [N1]
    assert inside((1, 1, 1, 1), view_box(w))             # a point is zoomed to as well


# -- violation markers ---------------------------------------------------------------

def marks(w):
    """The markers the layout draws now: [((x1, y1, x2, y2) in viewport pixels, current)]."""
    c = w.canvas
    return [(b.getCoords(), cur)
            for b, cur in c.marker_boxes(c.mapToScene(c.viewport().rect()).boundingRect())]


def pixel_box(w, box):
    """A layout box in viewport pixels, as getCoords gives it: x1, y1 (top), x2, y2."""
    x1, y1, x2, y2 = box
    t = w.canvas.viewportTransform()
    p, q = t.map(scene(x1, y2)), t.map(scene(x2, y1))
    return p.x(), p.y(), q.x(), q.y()


def scene(x, y):
    from core.gui.canvas import scene as to_scene
    return to_scene(x, y)


def test_markers_at_the_violation_boxes(shown):
    from PySide6.QtCore import QRectF, Qt
    from core.gui.canvas import MARKER_MIN_PIXELS
    s, w = shown
    box = w.object_boxes["violation_marker"]
    assert box.text() == "Violation markers" and box.isChecked()
    assert not box.isEnabled() and "check_drc has not run" in box.toolTip()
    assert marks(w) == []
    s.eval("check_drc")
    assert box.isEnabled() and "every violation" in box.toolTip()
    boxes = [v.bbox for _, v in s.db.drc.rows]
    assert w.canvas.markers == boxes
    got = marks(w)
    assert len(got) == 2 and not any(current for _, current in got)
    # Zoomed out a 0.06 um short is under a pixel wide: its marker is still seen, about
    # the centre of the box.
    for ((x1, y1, x2, y2), _), want in zip(got, [pixel_box(w, b) for b in boxes]):
        assert x2 - x1 >= MARKER_MIN_PIXELS and y2 - y1 >= MARKER_MIN_PIXELS
        assert abs((x1 + x2) - (want[0] + want[2])) <= 2
        assert abs((y1 + y2) - (want[1] + want[3])) <= 2
    # The clicked one is the current one: drawn wide, last (on top).
    w.drc_table.table.cellClicked.emit(0, 0)
    got = marks(w)
    assert w.canvas.marker_current == boxes[0]
    assert [current for _, current in got] == [False] + [True]
    # Zoomed in the marker is the box itself; one out of view is not drawn.
    x1, y1, x2, y2 = boxes[0]
    w.canvas.fitInView(QRectF(scene(x1 - 0.1, y2 + 0.1), scene(x2 + 0.1, y1 - 0.1)),
                       Qt.KeepAspectRatio)
    got = marks(w)
    assert 1 <= len(got) <= 2
    mine, current = got[-1]
    assert current and max(abs(a - b) for a, b in zip(mine, pixel_box(w, boxes[0]))) <= 1
    assert mine[2] - mine[0] > MARKER_MIN_PIXELS
    w.drc_table.table.cellClicked.emit(1, 0)                 # the next one in its place
    assert w.canvas.marker_current == boxes[1] and marks(w)[-1][1]
    # Not instances, not net routing: Show All and show_only leave them.
    shown_before = marks(w)
    s.eval("show_only -object sp_L3_inv1")
    assert marks(w) == shown_before and shown_before
    w.drc_table.all_button.click()
    assert marks(w) == shown_before and w.canvas.markers == boxes


def test_markers_are_drawn_only_while_ticked(shown):
    from PySide6.QtWidgets import QApplication
    from core.gui.canvas import MARKER_COLOR
    s, w = shown
    w.show()
    s.eval("check_drc")
    box = w.object_boxes["violation_marker"]

    x1, y1, x2, y2 = (int(c) for c in marks(w)[0][0])

    def corners():
        """The colours of the layout at the corners of the first marker."""
        QApplication.processEvents()
        img = w.canvas.viewport().grab().toImage()
        return {img.pixelColor(x, y).name() for x in (x1, x2) for y in (y1, y2)}

    assert corners() == {MARKER_COLOR}
    box.setChecked(False)                                # unticked: no marker
    assert marks(w) == [] and not w.canvas.show["violation_marker"]
    assert MARKER_COLOR not in corners()
    w.canvas.set_marker_current(s.db.drc.rows[0][1].bbox)        # nor the one debugged
    assert marks(w) == [] and MARKER_COLOR not in corners()
    box.setChecked(True)
    assert marks(w)[-1][1] and corners() == {MARKER_COLOR}


def test_markers_follow_the_last_run(shown, tmp_path):
    s, w = shown
    path = tmp_path / "a.deb"
    s.eval(f"write_db -file {{{path}}}")
    box = w.object_boxes["violation_marker"]
    s.eval("check_drc")
    w.drc_table.table.cellClicked.emit(0, 0)
    box.setChecked(False)
    # A reload of the layout (any command that changes the database) keeps them.
    s.eval("delete_route -nets sp_L3_inv1_Y")
    assert len(w.canvas.markers) == 2 and box.isEnabled() and not box.isChecked()
    # The next run: its markers, none of them the current one; the box as it was left.
    assert s.eval("check_drc -check_shorts_only") == str(len(s.db.drc.rows))
    assert w.canvas.markers == [v.bbox for _, v in s.db.drc.rows]
    assert len(w.canvas.markers) == 2 and w.canvas.marker_current is None
    assert not box.isChecked()
    # A run with no violations, and read_db: no markers, nothing to tick.
    assert s.eval("check_drc -check_open_only -layer_range IA") == "0"
    assert w.canvas.markers == [] and not box.isEnabled()
    assert "found none" in box.toolTip()
    s.eval("check_drc")
    assert w.canvas.markers and box.isEnabled()
    s.eval(f"read_db -file {{{path}}}")
    assert w.canvas.markers == [] and not box.isEnabled()


def test_read_db_closes_the_table(shown, tmp_path):
    s, w = shown
    path = tmp_path / "a.deb"
    s.eval(f"write_db -file {{{path}}}")
    s.eval("check_drc")
    t = w.drc_table
    assert not t.isHidden()
    s.eval(f"read_db -file {{{path}}}")
    assert t.isHidden() and t.table.rowCount() == 0 and t.report is None
    assert t.summary.text() == "check_drc has not run"
    w.findChild(type(t), "drc_table").toggleViewAction().trigger()     # View > Show DRC Violations
    assert not t.isHidden()


def test_window_opens_with_the_table_of_a_run_before(routed, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    s = routed
    s.eval("check_drc")
    try:
        s.eval("gui_show")
        t = app.window().drc_table
        assert not t.isHidden() and t.table.rowCount() == 2
        assert len(app.window().canvas.markers) == 2
        assert app.window().object_boxes["violation_marker"].isEnabled()
    finally:
        app.close()
