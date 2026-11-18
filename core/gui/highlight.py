"""Highlight: the panel that colours the selected objects (Edit > Highlight).

Highlight opens a palette; a click on a colour paints the selected objects in
it: a wire, strap, pin wire, via, pin or port alone, an instance with its
pins, a net with all its wires, shields and vias and the pins on it, a stub
with its wires and vias, a spine with its cells, nets and stubs. A net keeps
its colour on the wires it is routed with later. Clear takes the colour off
the selected objects, Clear All off every object, Close closes the panel.
The colours are the display's only: the database does not change. They are
session state (db.highlights, core/highlight.py), shared with the highlight
command.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QDockWidget, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from core import highlight, objects

PALETTE = list(highlight.COLORS.values())
COLUMNS = 4


class Highlighter(QDockWidget):
    def __init__(self, window):
        super().__init__("Highlight", window)
        self.setObjectName("highlight_panel")
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.win, self.session, self.canvas = window, window.session, window.canvas

        panel = QWidget()
        vbox = QVBoxLayout(panel)
        hint = QLabel("Select objects, then Highlight and a colour.")
        hint.setWordWrap(True)
        vbox.addWidget(hint)

        def button(text, slot, tip):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)      # the keys stay with the layout
            b.clicked.connect(slot)
            return b

        self.highlight_button = button("Highlight", self.show_palette,
                                       "Open the palette: a colour paints the selected "
                                       "objects")
        vbox.addWidget(self.highlight_button)
        self.palette = QWidget()
        grid = QGridLayout(self.palette)
        grid.setSpacing(3)
        self.swatches = []
        for k, (name, color) in enumerate(highlight.COLORS.items()):
            b = button("", lambda _=False, c=color: self.paint(c), f"{name} {color}")
            b.setFixedSize(28, 22)
            b.setStyleSheet(f"background-color: {color}; border: 1px solid #555;")
            grid.addWidget(b, k // COLUMNS, k % COLUMNS)
            self.swatches.append(b)
        self.more_button = button("More...", self.pick_color, "Any colour")
        grid.addWidget(self.more_button, len(PALETTE) // COLUMNS, 0, 1, COLUMNS)
        self.palette.hide()
        vbox.addWidget(self.palette)
        self.clear_button = button("Clear", self.clear, "Take the colour off the selected "
                                   "objects")
        self.clear_all_button = button("Clear All", self.clear_all,
                                       "Take the colour off every object")
        self.close_button = button("Close", self.hide, "Close this panel (the colours stay)")
        hbox = QHBoxLayout()
        for b in (self.clear_button, self.clear_all_button, self.close_button):
            hbox.addWidget(b)
        vbox.addLayout(hbox)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #888;")
        vbox.addWidget(self.note_label)
        vbox.addStretch(1)
        self.setWidget(panel)

    def open(self):
        self.show()
        self.raise_()

    def show_palette(self):
        self.palette.setVisible(not self.palette.isVisible())

    def pick_color(self):
        color = QColorDialog.getColor(QColor(PALETTE[0]), self, "Highlight colour")
        if color.isValid():
            self.paint(color.name())

    def _selected(self):
        sel = objects.selected(self.session.db)
        if not sel:
            self.note_label.setText("Nothing selected")
        return sel

    def paint(self, color):
        """Colour the selected objects."""
        sel = self._selected()
        if not sel:
            return
        highlight.paint(self.session.db, sel, color)
        self._apply()
        self.note_label.setText(f"{len(sel)} object(s) coloured {color}")

    def clear(self):
        """Take the colour off the selected objects; one coloured with its net
        or spine goes back to its own colour too."""
        sel = self._selected()
        if not sel:
            return
        highlight.clear(self.session.db, sel)
        self._apply()
        self.note_label.setText(f"Colour taken off {len(sel)} object(s)")

    def clear_all(self):
        highlight.clear(self.session.db)
        self._apply()
        self.note_label.setText("Every colour taken off")

    def reloaded(self):
        """After the layout is drawn again: paint it again, from the database
        as it is now (a net routed again keeps its colour)."""
        highlight.drop_gone(self.session.db)
        self._apply()

    def _apply(self):
        """Paint what db.highlights says (also after a highlight command)."""
        db = self.session.db
        self.canvas.set_paint([(highlight.covers(db, h), c) for h, c in db.highlights])
