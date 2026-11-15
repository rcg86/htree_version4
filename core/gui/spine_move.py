"""Move Spine: the panel of the interactive move_spine_to_boundary.

The form takes a built spine, its head (the end that moves), the clearances
to the design boundary and a step. After Start, Shift+arrow on the layout
pulls the head one step (core/spine_snake.py) and H swaps the head. Only a
preview moves: the database stays as it is until Done, which runs the moves
made as one move_spine_to_boundary command, as if typed (the spine is stored
on its path, its routing removed, its cells legalized), and writes that
command to spine_move.tcl in the working directory. Cancel drops the moves.
"""

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from core.db import _num
from core.spine_snake import ENDS, NAMES, SIDES, Snake, SnakeError

FILE = "spine_move.tcl"      # written by Done in the working directory
DEFAULT_STEP = 10.0          # um, before it is rounded to the track period
TOL = 1e-6


class SpineMover(QDockWidget):
    def __init__(self, window):
        super().__init__("Move Spine", window)
        self.setObjectName("spine_move_panel")
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.win, self.session, self.canvas = window, window.session, window.canvas
        self.snake = None                    # the spine being moved; None: not started
        self.probe = None                    # the chosen spine before Start (its track periods)
        self.way = None                      # the direction of the last move of this head
        self._stored = None                  # the spine's row values at Start
        self._base = 0                       # the snake's undoable() at Start
        self._running = False                # Done is running its command

        panel = QWidget()
        vbox = QVBoxLayout(panel)
        form = QFormLayout()
        self.spine_box = QComboBox()
        self.spine_box.currentTextChanged.connect(self._spine_chosen)
        form.addRow("Spine", self.spine_box)
        self.head_box = QComboBox()
        self.head_box.setToolTip("The end that moves; the body follows it")
        self.head_box.activated.connect(self._head_chosen)
        form.addRow("Head", self.head_box)
        grid = QGridLayout()
        self.clear_boxes = {}
        for k, side in enumerate(SIDES):
            box = QDoubleSpinBox()
            box.setRange(0.0, 1e6)
            box.setDecimals(3)
            box.setToolTip(f"Least distance of the head from the {side} of the design "
                           f"boundary, um")
            grid.addWidget(QLabel(side), k // 2, 2 * (k % 2))
            grid.addWidget(box, k // 2, 2 * (k % 2) + 1)
            self.clear_boxes[side] = box
        form.addRow("Clearance", grid)
        self.step_box = QDoubleSpinBox()
        self.step_box.setRange(0.001, 1e6)
        self.step_box.setDecimals(3)
        self.step_box.setValue(DEFAULT_STEP)
        self.step_box.setToolTip("Distance of one Shift+arrow move, um: a whole number of "
                                 "track pattern periods is used")
        self.step_box.valueChanged.connect(lambda _: self._show_step())
        self.step_box.editingFinished.connect(self._to_canvas)
        form.addRow("Step", self.step_box)
        self.step_label = QLabel("")
        self.step_label.setStyleSheet("color: #888;")
        form.addRow("", self.step_label)
        vbox.addLayout(form)

        def button(text, slot, tip):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)      # the keys stay with the layout
            b.clicked.connect(slot)
            return b

        self.start_button = button("Start", self.start, "Start moving: Shift+arrow pulls "
                                   "the head one step")
        self.swap_button = button("Swap head (H)", self.swap_head,
                                  "Make the other end the head")
        self.undo_button = button("Undo step", self.undo_step,
                                  "Take back the last move or head change")
        self.done_button = button("Done", self.done, "Store the spine where it is now: runs "
                                  f"move_spine_to_boundary and writes {FILE}")
        self.cancel_button = button("Cancel", self.cancel, "Drop the moves; nothing changes")
        self.close_button = button("Close", self.hide, "Close this panel")
        for row in ((self.start_button, self.swap_button, self.undo_button),
                    (self.done_button, self.cancel_button, self.close_button)):
            hbox = QHBoxLayout()
            for b in row:
                hbox.addWidget(b)
            vbox.addLayout(hbox)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        vbox.addWidget(self.note_label)
        self.moves_label = QLabel("")
        self.moves_label.setWordWrap(True)
        self.moves_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.moves_label.setStyleSheet("color: #888;")
        vbox.addWidget(self.moves_label)
        hint = QLabel("Shift+arrow: move the head one step\n"
                      "Arrow: pan   H: swap head\n"
                      "A move into the body backs the spine up\nalong its path.")
        hint.setStyleSheet("color: #888;")
        vbox.addWidget(hint)
        vbox.addStretch(1)
        self.setWidget(panel)
        self._enable()

    # -- the form --------------------------------------------------------------------
    def active(self):
        return self.snake is not None

    def open(self):
        """Show the panel, on the selected spine if one is selected."""
        if not self.active():
            self.reload_spines()
            picked = [h.partition(":")[2] for h in self.session.db.selection
                      if h.startswith("spine:")]
            if picked and self.spine_box.findText(picked[0]) >= 0:
                self.spine_box.setCurrentText(picked[0])
        self.show()
        self.raise_()

    def reload_spines(self):
        """The built spines of the database, keeping the one chosen."""
        names = list(self.session.db.spine_names())
        if names == [self.spine_box.itemText(k) for k in range(self.spine_box.count())]:
            self._spine_chosen(self.spine_box.currentText())    # it may have moved
            return
        chosen = self.spine_box.currentText()
        self.spine_box.blockSignals(True)
        self.spine_box.clear()
        self.spine_box.addItems(names)
        if chosen in names:
            self.spine_box.setCurrentText(chosen)
        self.spine_box.blockSignals(False)
        self._spine_chosen(self.spine_box.currentText())

    def _spine_chosen(self, name):
        """The ends of this spine in the Head box, and its track periods."""
        self.probe = None
        row = self.session.db.spine_row(name) if name else None
        ends = () if row is None else \
            ENDS["horizontal" if (row["orientation"] or "").lower() == "horizontal"
                 else "vertical"]
        if ends != tuple(self.head_box.itemText(k) for k in range(self.head_box.count())):
            self.head_box.clear()
            self.head_box.addItems(ends)
        note = "" if name else "No built spine (create_spine -build)."
        if row is not None:
            try:
                self.probe = Snake(self.session.db, name)
            except SnakeError as exc:
                note = str(exc)
        self.note_label.setText(note)
        self._show_step()
        self._enable()

    def _show_step(self):
        sn = self.snake or self.probe
        if sn is None:
            self.step_label.setText("")
            return
        step = self.step_box.value()
        v, h = sn.round_step("up", step), sn.round_step("left", step)
        on = "track periods" if sn.period("up") or sn.period("left") else \
            "the grid (no assigned tracks)"
        self.step_label.setText(f"moves {_num(v)} up / down, {_num(h)} left / right\n"
                                f"(whole {on})")

    def _enable(self):
        on = self.active()
        for w in (self.spine_box, *self.clear_boxes.values()):
            w.setEnabled(not on)
        self.head_box.setEnabled(self.head_box.count() > 0)
        self.start_button.setEnabled(not on and self.probe is not None)
        for b in (self.swap_button, self.done_button, self.cancel_button):
            b.setEnabled(on)
        self.undo_button.setEnabled(on and self.snake.undoable() > self._base)
        self.close_button.setEnabled(not on)
        self.win.act_swap_head.setEnabled(on)

    def _to_canvas(self):
        if self.active():
            self.canvas.setFocus()

    def clearance(self):
        return tuple(self.clear_boxes[side].value() for side in SIDES)

    # -- moving ------------------------------------------------------------------------
    def start(self):
        name = self.spine_box.currentText()
        if self.active() or not name:
            return
        try:
            snake = Snake(self.session.db, name, self.clearance())
            snake.set_head(self.head_box.currentText())
        except SnakeError as exc:
            self.note_label.setText(str(exc))
            return
        self.snake, self.way = snake, None
        self._stored, self._base = self._spine_state(), snake.undoable()
        self.canvas.shift_arrow = self.move
        self.canvas.setFocus()
        self._update("Shift+arrow moves the head")

    def move(self, direction):
        """Pull the head one step in direction (Shift+arrow)."""
        sn = self.snake
        if sn is None:
            return
        step = sn.move(direction, sn.round_step(direction, self.step_box.value()))
        if step.moved > TOL:
            self.way = direction
            note = f"moved {_num(step.moved)}" + (f", {step.note}" if step.note else "")
        else:
            note = f"{direction}: not moved, {step.note.removeprefix('refused: ')}"
        self._update(note)
        self.canvas.show_point(*sn.head_point())

    def swap_head(self):
        if self.active():
            self.snake.swap_head()
            self.way = None
            self._update("")
            self._to_canvas()

    def _head_chosen(self, _index):
        if self.active() and self.head_box.currentText() != self.snake.end_name():
            self.snake.set_head(self.head_box.currentText())
            self.way = None
            self._update("")
        self._to_canvas()

    def undo_step(self):
        if self.active() and self.snake.undoable() > self._base and self.snake.undo():
            self.way = None
            self._update("took back the last step")
            self.canvas.show_point(*self.snake.head_point())

    def _update(self, note):
        """The preview, the Head box, the status texts and the buttons, from
        the snake as it is."""
        sn = self.snake
        self.head_box.setCurrentText(sn.end_name())
        self.draw()
        x, y = sn.head_point()
        where = f"moving {self.way}" if self.way else f"pointing {NAMES[sn.heading()]}"
        text = f"head: {sn.end_name()}, {where}; at {_num(x)} {_num(y)}"
        self.note_label.setText(text + (f"\n{note}" if note else ""))
        self.win.statusBar().showMessage(f"Move Spine {sn.name}: {text}"
                                         + (f"; {note}" if note else ""))
        moves = sn.moves_text()
        self.moves_label.setText(f"-moves {{{moves}}}" if self.moved() else "no move yet")
        self._show_step()
        self._enable()

    def moved(self):
        return self.active() and any(word != "head" for word, _ in self.snake.moves)

    def draw(self):
        """The preview of the spine where the moves put it."""
        sn = self.snake
        boxes = [box[1:] for box in sn.boxes()]
        lines = [(True, pts) for _, _, pts in sn.stub_lines()]
        lines += [(False, [seg[:2], seg[2:]]) for _, _, segs in sn.net_lines() for seg in segs]
        self.canvas.set_move_preview(boxes, lines, sn.body(), sn.head_point(), sn.heading())

    # -- the end -----------------------------------------------------------------------
    def command(self):
        """The moves made, as the command that repeats them."""
        sn = self.snake
        clearance = " ".join(_num(v) for v in (sn.clearance[side] for side in SIDES))
        return (f"move_spine_to_boundary -spine {sn.name} -clearance {{{clearance}}} "
                f"-moves {{{sn.moves_text()}}}")

    def done(self):
        """Run the moves as one command, as if typed, and write it to FILE.
        Returns True when the spine was stored."""
        if not self.active():
            return False
        if not self.moved():
            self._end("Move Spine: no move made, nothing changed")
            return False
        sn, cmd = self.snake, self.command()
        want = [c for p in sn.body() for c in p]
        view = self.canvas.transform(), self.canvas.mapToScene(
            self.canvas.viewport().rect().center())
        self._running = True
        try:
            ok, _ = self.win.run_command(cmd)
        finally:
            self._running = False
        if not ok:                            # the moves stay, to try again or cancel
            self.draw()
            self.note_label.setText("move_spine_to_boundary failed; see the terminal")
            return False
        self.canvas.setTransform(view[0])     # the reload fitted the design: back to the view
        self.canvas.centerOn(view[1])
        row = self.session.db.spine_row(sn.name)
        got = [float(c) for c in (row["path"] or "").split()] if row is not None else []
        if len(got) != len(want) or any(abs(a - b) > 1e-4 for a, b in zip(got, want)):
            self.session.notify(f"Move Spine: the path stored ({row['path'] if row else ''}) "
                                f"is not the one previewed ({' '.join(map(_num, want))})")
        path = os.path.join(os.getcwd(), FILE)
        try:
            with open(path, "w") as f:
                f.write(f"# Move Spine (GUI), {time.strftime('%Y-%m-%d %H:%M:%S')}: the moves "
                        f"made, as one command.\n{cmd}\n")
        except OSError as exc:
            self.session.notify(f"Move Spine: cannot write {path}: {exc}")
            self._end(f"Move Spine: spine {sn.name} stored; {FILE} not written: {exc}")
            return True
        self.session.notify(f"Move Spine: wrote {path}")
        self._end(f"Move Spine: spine {sn.name} stored; wrote {path}")
        return True

    def cancel(self):
        if self.active():
            self._end("Move Spine: cancelled, nothing changed")

    def _end(self, text):
        self.snake, self.way, self._stored = None, None, None
        self.canvas.shift_arrow = None
        self.canvas.clear_move_preview()
        self.moves_label.setText("")
        self.win.statusBar().showMessage(text, 10000)
        self.reload_spines()
        self.head_box.setCurrentIndex(0)      # the default head again
        self.note_label.setText(text.removeprefix("Move Spine: "))

    def _spine_state(self):
        """What a command changing the spine being moved would change."""
        row = self.session.db.spine_row(self.snake.name)
        return None if row is None else (row["x"], row["y"], row["path"], row["orientation"])

    def reloaded(self):
        """The window reloaded the layout (a command changed the database):
        draw the preview again, or end the move when the spine itself changed."""
        if self._running:
            return
        if not self.active():
            if not self.isHidden():
                self.reload_spines()
        elif self._spine_state() != self._stored:
            self._end(f"Move Spine: spine {self.snake.name} was changed by a command; its "
                      f"moves here are dropped")
        else:
            self.draw()
