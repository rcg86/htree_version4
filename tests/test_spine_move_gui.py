"""The GUI's Move Spine: the panel, Shift+arrow moves of the head with their
preview, Done (move_spine_to_boundary as if typed, spine_move.tcl) and Cancel."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("scipy")

from core.gui import app
from core.spine_snake import Snake
from test_move_spine import DEF, LEF, ROWS, build, near
from test_route_net import SPEC, _floats, out_of


@pytest.fixture(autouse=True)
def fresh_window(tmp_path, monkeypatch):
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))  # not ~/.config
    monkeypatch.chdir(tmp_path)                  # Done writes spine_move.tcl here
    yield
    app.close()


@pytest.fixture
def spine(tech_session, write_lef):
    return build(tech_session, write_lef)


def view(s):
    s.eval("gui_show")
    w = app.window()
    w.resize(1000, 700)
    w.canvas.fit()
    return w


def key(w, name, shift=True):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    keys = {"left": Qt.Key_Left, "right": Qt.Key_Right, "up": Qt.Key_Up, "down": Qt.Key_Down}
    QApplication.sendEvent(w.canvas, QKeyEvent(QEvent.KeyPress, keys[name],
                                               Qt.ShiftModifier if shift else Qt.NoModifier))


def started(s, step=7.0, clearance=(0, 0, 0, 0), head=None):
    w = view(s)
    m = w.mover
    w.act_move_spine.trigger()
    for side, value in zip(("left", "right", "top", "bottom"), clearance):
        m.clear_boxes[side].setValue(value)
    m.step_box.setValue(step)
    if head:
        m.head_box.setCurrentText(head)
    m.start_button.click()
    return w, m


def stored(s):
    """What move_spine_to_boundary changes, from the database."""
    sid = s.db.spine_row("sp")["id"]
    return (s.eval("get_db spine:sp .path"),
            sorted((r["name"], r["x"], r["y"]) for r in s.db.inst_rows()),
            sorted((r["name"], r["points"]) for r in s.db.spine_stub_rows(sid)))


# -- the panel ---------------------------------------------------------------------------

def test_panel_lists_the_spines_and_their_ends(spine):
    w = view(spine)
    m = w.mover
    assert m.isHidden() and not w.act_swap_head.isEnabled()
    w.act_move_spine.trigger()
    assert not m.isHidden()
    assert [m.spine_box.itemText(k) for k in range(m.spine_box.count())] == ["sp"]
    assert [m.head_box.itemText(k) for k in range(2)] == ["bottom", "top"]
    assert m.head_box.currentText() == "bottom"                 # the default head
    assert m.clearance() == (0.0, 0.0, 0.0, 0.0)
    m.step_box.setValue(7)                                      # shown as one track period
    assert m.step_label.text().startswith("moves 5.76 up / down, 5.76 left / right")
    m.step_box.setValue(20)                                     # 3.47 periods: 3
    assert m.step_label.text().startswith("moves 17.28 up / down")
    assert m.start_button.isEnabled() and not m.done_button.isEnabled()
    assert w.act_move_spine in w.all_actions() and w.act_swap_head in w.all_actions()
    assert w.act_swap_head.shortcut().toString() == "H"
    from core.gui import shortcuts
    assert ("Move Spine: move the head", "Shift+Arrow keys", "built in", None) in \
        shortcuts.ShortcutsDialog(w).rows()


def test_panel_without_a_spine_and_a_spine_built_later(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF % ROWS, 'd.def')}}}")
    w = view(s)
    m = w.mover
    w.act_move_spine.trigger()
    assert m.spine_box.count() == 0 and not m.start_button.isEnabled()
    assert "No built spine" in m.note_label.text()
    spec = SPEC.replace("vertical", "horizontal")
    s.eval(f"read_spine_spec -file {{{write_lef(spec, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {10 10} -build -ref_cell INV_RP")
    assert m.spine_box.currentText() == "sp" and m.start_button.isEnabled()
    assert [m.head_box.itemText(k) for k in range(2)] == ["left", "right"]   # horizontal
    m.head_box.setCurrentText("right")
    m.start_button.click()
    key(w, "right")
    assert m.snake.moves_text().startswith("head right right ")
    assert "head: right, moving right" in m.note_label.text()


def test_open_takes_the_selected_spine(spine):
    s = spine
    s.eval("create_spine -name aa -spec_name sp -location {70 150} -build -ref_cell INV_RP")
    w = view(s)
    s.eval("select_obj spine:sp")
    w.act_move_spine.trigger()
    assert w.mover.spine_box.count() == 2 and w.mover.spine_box.currentText() == "sp"


# -- moving ------------------------------------------------------------------------------

def test_shift_arrow_moves_the_head_and_arrow_pans(spine):
    from core.gui.canvas import scene
    s = spine
    w = view(s)
    before = stored(s)
    x0 = w.canvas.mapFromScene(scene(0, 0)).x()
    key(w, "left")                                # no move in progress: Shift+arrow pans
    assert w.canvas.mapFromScene(scene(0, 0)).x() == x0 + w.canvas.viewport().width() // 4
    w, m = started(s)
    assert m.active() and w.act_swap_head.isEnabled() and not m.spine_box.isEnabled()
    assert not m.clear_boxes["left"].isEnabled() and not m.start_button.isEnabled()
    assert "head: bottom, pointing down; at 78.64 100" in m.note_label.text()
    assert w.canvas.move_items                    # the preview, on the spine as built
    key(w, "down")                                # 94.24: the signal track at 93.96
    near([m.snake.head_point()], [(78.64, 93.96)])
    assert "head: bottom, moving down; at 78.64 93.96" in m.note_label.text()
    assert "moved 6.04" in m.note_label.text()
    assert "Move Spine sp: head: bottom, moving down" in w.statusBar().currentMessage()
    key(w, "down")
    near([m.snake.head_point()], [(78.64, 88.2)])
    assert m.moves_label.text() == "-moves {head bottom down 11.8}"
    x0 = w.canvas.mapFromScene(scene(0, 0)).x()
    key(w, "left", shift=False)                   # a plain arrow still pans
    assert w.canvas.mapFromScene(scene(0, 0)).x() == x0 + w.canvas.viewport().width() // 4
    near([m.snake.head_point()], [(78.64, 88.2)])
    key(w, "left")                                # a turn: x 72.88, the track at 73.8
    near(m.snake.body(), [(73.8, 88.2), (78.64, 88.2), (78.64, 123.36)])
    assert stored(s) == before                    # only the preview moved
    assert not os.path.exists("spine_move.tcl")


def test_preview_follows_the_snake(spine):
    from PySide6.QtWidgets import QGraphicsPolygonItem, QGraphicsRectItem
    from core.gui.canvas import scene
    w, m = started(spine)
    for d in ("down", "down", "left"):
        key(w, d)
    items = w.canvas.move_items
    boxes = [i for i in items if isinstance(i, QGraphicsRectItem)]
    assert len(boxes) == len(m.snake.members) == 4
    centres = sorted((round(b.rect().center().x(), 3), round(-b.rect().center().y(), 3))
                     for b in boxes)
    assert centres == sorted((round(x, 3), round(y, 3)) for _, x, y in m.snake.cells())
    assert boxes[0].rect().width() == pytest.approx(3.12)       # INV_RP, not turned
    assert boxes[0].rect().height() == pytest.approx(1.778)
    arrow = [i for i in items if isinstance(i, QGraphicsPolygonItem)]
    assert len(arrow) == 1 and arrow[0].pos() == scene(*m.snake.head_point())
    assert arrow[0].rotation() == pytest.approx(180)            # the head points left
    assert all(not i.data(0) for i in items)                    # nothing of it selectable
    key(w, "down")                                              # the head now points down
    arrow = [i for i in w.canvas.move_items if isinstance(i, QGraphicsPolygonItem)]
    assert arrow[0].rotation() == pytest.approx(90)             # the scene's y is down
    # an unrelated command reloads the layout: the preview is drawn again
    spine.eval("create_inst -name extra -ref_cell INV_RP -location {90 180}")
    assert m.active() and w.canvas.move_items
    assert all(i.scene() is w.canvas.scene() for i in w.canvas.move_items)


def test_stops_refusals_and_backing_up(spine):
    s = spine
    w, m = started(s, step=200, clearance=(0, 0, 0, 10))
    key(w, "down")                                # 100 to the bottom edge, 10 kept
    near([m.snake.head_point()], [(78.64, 10.44)])
    assert "stopped by the bottom clearance 10" in m.note_label.text()
    key(w, "down")                                # no signal track left before the limit
    near([m.snake.head_point()], [(78.64, 10.44)])
    assert "down: not moved, stopped by the bottom clearance 10" in m.note_label.text()
    assert m.moves_label.text() == "-moves {head bottom down 89.56}"
    m.step_box.setValue(7)
    key(w, "up")                                  # the opposite way: backs up its path
    near(m.snake.body(), [(78.64, 16.2), (78.64, 56.2)])
    assert "moving up" in m.note_label.text()
    key(w, "left")
    body, moves = m.snake.body(), m.moves_label.text()
    key(w, "up")                                  # a U-turn 4.84 beside the body: refused
    assert m.snake.body() == body and m.moves_label.text() == moves
    assert "up: not moved, the spine would run into its own body" in m.note_label.text()
    assert "not moved" in w.statusBar().currentMessage()
    key(w, "right")                               # back to the corner: straight again
    near(m.snake.body(), [(78.64, 16.2), (78.64, 56.2)])


def test_swap_head_and_undo_step(spine):
    w, m = started(spine)
    assert not m.undo_button.isEnabled()          # nothing to take back yet
    key(w, "down")
    w.act_swap_head.trigger()                     # the H key
    assert m.snake.end_name() == "top" and m.head_box.currentText() == "top"
    assert "head: top, pointing up" in m.note_label.text()
    key(w, "up")
    assert m.moves_label.text() == "-moves {head bottom down 6.04 head top up 6.08}"
    m.swap_button.click()
    assert m.snake.end_name() == "bottom"
    m.head_box.setCurrentText("top")              # the Head box does the same
    m.head_box.activated.emit(1)
    assert m.snake.end_name() == "top"
    m.undo_button.click()                         # back to bottom
    m.undo_button.click()                         # the swap to bottom
    m.undo_button.click()                         # the move up
    assert m.moves_label.text() == "-moves {head bottom down 6.04 head top}"
    assert m.head_box.currentText() == "top"
    m.undo_button.click()
    m.undo_button.click()
    assert m.moves_label.text() == "no move yet" and m.head_box.currentText() == "bottom"
    assert not m.undo_button.isEnabled()
    near(m.snake.body(), [(78.64, 100), (78.64, 140)])
    m.undo_step()                                 # nothing more: the head chosen at Start stays
    assert m.snake.moves_text() == "head bottom"


# -- Done and Cancel ---------------------------------------------------------------------

def test_done_stores_the_spine_and_writes_the_command(spine, tmp_path, tech_session):
    s = spine
    s.eval("route_pin -inst [get_db spine:sp .insts]")
    w, m = started(s, clearance=(5, 5, 5, 5))
    for d in ("down", "down", "left", "left"):
        key(w, d)
    w.act_swap_head.trigger()
    key(w, "down")
    want = [c for p in m.snake.body() for c in p]
    cells = {n: (x, y) for n, x, y in m.snake.cells()}
    w.canvas.zoom(3.0)
    zoom = w.canvas.transform().m11()
    out_of(s)
    assert m.done_button.isEnabled()
    m.done_button.click()
    cmd = ("move_spine_to_boundary -spine sp -clearance {5 5 5 5} -moves {head bottom down "
           "11.8 left 10.6 head top down 6.36}")
    text = out_of(s)
    assert cmd in text and "Moved spine:sp onto a path with 1 corner(s)" in text   # as typed
    assert "legalize_placement:" in text
    path = tmp_path / "spine_move.tcl"
    assert f"Move Spine: wrote {path}" in text and "is not the one previewed" not in text
    lines = path.read_text().splitlines()
    assert lines[0].startswith("# Move Spine (GUI), ") and lines[1:] == [cmd]
    assert _floats(s.eval("get_db spine:sp .path")) == pytest.approx(want)
    for r in s.db.inst_rows():                    # where previewed, then put on sites
        x, y = cells[r["name"]]
        assert abs(r["x"] + 1.56 - x) <= 3.12 + 1e-6 and abs(r["y"] + 0.889 - y) <= 1.778 + 1e-6
    assert s.eval("get_db straps") == ""          # its routing is removed
    assert not m.active() and not w.canvas.move_items and w.canvas.shift_arrow is None
    assert m.spine_box.isEnabled() and m.start_button.isEnabled()
    assert not w.act_swap_head.isEnabled()
    assert w.canvas.transform().m11() == pytest.approx(zoom)    # the view stays
    assert f"wrote {path}" in w.statusBar().currentMessage()
    # the layout shows the stored spine: a stub over the corner is two lines
    assert len(w.layout.spines[0].stubs) == 3
    # the file repeats the move on the spine as built
    from core.htree_builder import Session
    import io
    other = Session(out=io.StringIO())
    other.eval(f"read_tech -file {{{os.path.join(os.path.dirname(__file__), 'data', 'tech.lef')}}}")
    lef = lambda body, name: _write(tmp_path / "again", body, name)
    build(other, lef)
    other.eval(f"source {{{path}}}")
    assert stored(other) == stored(s)
    # a second move starts from the stored path, and overwrites the file
    assert m.head_box.currentText() == "bottom"   # the default head again
    m.start_button.click()
    near(m.snake.body(), list(zip(want[0::2], want[1::2])))
    key(w, "down")
    assert m.done()
    assert path.read_text().splitlines()[1] == (
        "move_spine_to_boundary -spine sp -clearance {5 5 5 5} -moves {head bottom down 5.76}")


def _write(folder, body, name):
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(body)
    return str(folder / name)


def test_cancel_and_done_without_a_move_change_nothing(spine, tmp_path):
    s = spine
    w, m = started(s)
    before = stored(s)
    for d in ("down", "left"):
        key(w, d)
    out_of(s)
    m.cancel_button.click()
    assert not m.active() and not w.canvas.move_items and w.canvas.shift_arrow is None
    assert stored(s) == before and out_of(s) == ""
    assert "cancelled, nothing changed" in w.statusBar().currentMessage()
    m.start_button.click()                        # again, from the spine as built
    near(m.snake.body(), [(78.64, 100), (78.64, 140)])
    w.act_swap_head.trigger()                     # a head change is no move
    assert not m.done()
    assert not m.active() and stored(s) == before and out_of(s) == ""
    assert "no move made" in w.statusBar().currentMessage()
    assert not (tmp_path / "spine_move.tcl").exists()


def test_esc_does_not_drop_the_moves(spine):
    s = spine
    w, m = started(s)
    key(w, "down")
    s.eval("select_obj inst:sp_L1_inv1")
    w.act_clear_sel.trigger()                     # Esc: clears the selection only
    assert s.eval("get_db selected") == "" and m.active()
    assert m.moves_label.text() == "-moves {head bottom down 6.04}"


def test_a_command_that_changes_the_spine_ends_the_move(spine):
    s = spine
    w, m = started(s)
    key(w, "down")
    s.eval("move_obj -direction up -distance 5.76 sp")
    assert not m.active() and not w.canvas.move_items
    assert "was changed by a command" in w.statusBar().currentMessage()
    m.start_button.click()                        # from where move_obj put it
    assert Snake(s.db, "sp").body() == m.snake.body()
    near(m.snake.body(), [(78.64, 105.76), (78.64, 145.76)])


def test_done_that_fails_keeps_the_moves(spine, monkeypatch):
    w, m = started(spine)
    key(w, "down")
    monkeypatch.setattr(m, "command", lambda: "move_spine_to_boundary -spine sp -moves {up}")
    assert not m.done()
    assert m.active() and w.canvas.move_items and "failed" in m.note_label.text()
    assert "HT4-231" in w.statusBar().currentMessage()
    assert not os.path.exists("spine_move.tcl")
