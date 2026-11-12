"""Edit > Shortcuts: list the keyboard shortcuts and create new ones.

Every action of the window but Close Window can be given a shortcut here
(the window's creatable). A user shortcut replaces the action's built in one
(Ruler K, Stretch S, Move M, ...); removing it brings that back. User shortcuts are kept in a JSON file, so they come back the
next time the GUI opens: $HTREE4_SHORTCUTS, or ~/.config/htree4/shortcuts.json.
"""

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

# Keys handled by the canvas itself, not by an action: shown, not editable.
FIXED = [("Pan", "Arrow keys"), ("Zoom", "Mouse wheel")]


def store_path():
    return os.environ.get("HTREE4_SHORTCUTS") or \
        os.path.expanduser("~/.config/htree4/shortcuts.json")


def load():
    """{action key: key sequence text} saved by the user; {} if none or unreadable."""
    try:
        with open(store_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} \
        if isinstance(data, dict) else {}


def save(shortcuts):
    path = store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(shortcuts, f, indent=2, sort_keys=True)


def text_of(seq):
    return QKeySequence(seq).toString(QKeySequence.NativeText)


def owner_of(window, seq, skip=None):
    """The text of the action (other than skip) already using seq, or None."""
    want = QKeySequence(seq)
    for a in window.all_actions():
        if a is not skip and any(s == want for s in a.shortcuts()):
            return a.text()
    return None


class ShortcutsDialog(QDialog):
    """Every shortcut: built in ones and those made here. New... makes one for a
    creatable action; Remove deletes a user one."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Shortcuts")
        self.resize(460, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut", "Kind"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        layout.addWidget(QLabel(f"Saved in {store_path()}"))
        buttons = QHBoxLayout()
        self.new_button = QPushButton("New...")
        self.new_button.clicked.connect(self.new)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        for b in (self.new_button, self.remove_button):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.table.itemSelectionChanged.connect(self._selection)
        self.fill()

    def rows(self):
        """(action text, shortcut text, kind, creatable key or None) per row."""
        user = self.window.user_shortcuts
        rows = []
        for a in self.window.all_actions():
            key = self.window.creatable_key(a)
            for s in a.shortcuts():
                kind = "user" if key is not None and key in user else "built in"
                rows.append((a.text(), s.toString(QKeySequence.NativeText), kind, key))
        rows += [(name, keys, "built in", None) for name, keys in FIXED]
        return rows

    def fill(self):
        rows = self.rows()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row[:3]):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row[3] if row[2] == "user" else None)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()
        self._selection()

    def _selection(self):
        items = self.table.selectedItems()
        self.remove_button.setEnabled(bool(items) and items[0].data(Qt.UserRole) is not None)

    def new(self):
        dialog = NewShortcutDialog(self.window, self)
        if dialog.exec() == QDialog.Accepted:
            self.fill()

    def remove(self):
        items = self.table.selectedItems()
        if items and items[0].data(Qt.UserRole) is not None:
            self.window.set_user_shortcut(items[0].data(Qt.UserRole), None)
            self.fill()


class NewShortcutDialog(QDialog):
    """Pick a creatable action and press the keys; OK assigns them, unless
    another action already uses them."""

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.window = window
        self.setWindowTitle("New Shortcut")
        form = QFormLayout(self)
        self.action_box = QComboBox()
        for key, a in window.creatable.items():
            self.action_box.addItem(a.text().replace("&", ""), key)
        self.keys = QKeySequenceEdit()
        self.keys.setMaximumSequenceLength(1)
        form.addRow("Action", self.action_box)
        form.addRow("Keys", self.keys)
        form.addRow(QLabel("Click Keys, then press the combination (Ctrl+Shift+Z for Ctrl+Z "
                           "with Shift)."))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        seq = self.keys.keySequence().toString()
        error = "Press the keys for the shortcut first." if not seq else \
            self.window.set_user_shortcut(self.action_box.currentData(), seq)
        if error:
            QMessageBox.warning(self, "New Shortcut", error)
            return
        super().accept()
