"""Main window: layout canvas in the middle, visibility panel on the right,
cursor position and selection in the status bar."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from core.gui.canvas import LayoutCanvas
from core.gui.layout_data import load_layout

# Object categories: (key, label). Categories with no data yet are disabled.
OBJECTS = [("boundary", "Boundary"), ("ports", "Ports"), ("tracks", "Tracks"),
           ("nets", "Nets"), ("cells", "Cells"), ("spine", "Spine")]
NOT_YET = {"nets": "No nets in the database yet",
           "cells": "No placed cells in the database yet",
           "spine": "No spine built yet (spine specs are read, not built)"}


class MainWindow(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setWindowTitle("htree4")
        self.resize(1400, 900)
        self.canvas = LayoutCanvas(self)
        self.setCentralWidget(self.canvas)
        self.object_boxes = {}
        self.layer_boxes = {}
        self.layout = None
        self._build_panel()
        self.pos_label = QLabel("")
        self.sel_label = QLabel("")
        self.statusBar().addWidget(self.pos_label)
        self.statusBar().addPermanentWidget(self.sel_label)
        self.canvas.mouseMoved.connect(lambda x, y: self.pos_label.setText(f"x {x:.3f}  y {y:.3f} um"))
        self.canvas.picked.connect(self.on_pick)

    # -- right panel ----------------------------------------------------------------
    def _build_panel(self):
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        objects = QGroupBox("Objects")
        ovbox = QVBoxLayout(objects)
        for key, label in OBJECTS:
            box = QCheckBox(label)
            box.setChecked(self.canvas.show.get(key, False))
            box.toggled.connect(lambda on, k=key: self.canvas.set_show(k, on))
            ovbox.addWidget(box)
            self.object_boxes[key] = box
        vbox.addWidget(objects)

        self.layer_group = QGroupBox("Layers")
        self.layer_vbox = QVBoxLayout(self.layer_group)
        buttons = QHBoxLayout()
        for text, on in (("All", True), ("None", False), ("Tech only", None)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, v=on: self.set_all_layers(v))
            buttons.addWidget(b)
        self.layer_vbox.addLayout(buttons)
        self.layer_list = QVBoxLayout()
        self.layer_vbox.addLayout(self.layer_list)
        vbox.addWidget(self.layer_group)
        hint = QLabel("Wheel: zoom   Drag: pan\nF: fit   Click: select\n"
                      "Tracks show when zoomed in enough.\n"
                      "(n) = port shapes on the layer.\n"
                      "* = not in tech (starts hidden).")
        hint.setStyleSheet("color: #888;")
        vbox.addWidget(hint)
        vbox.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        dock = QDockWidget("View", self)
        dock.setObjectName("view_panel")
        dock.setWidget(scroll)
        dock.setMinimumWidth(240)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _rebuild_layer_boxes(self):
        while self.layer_list.count():
            w = self.layer_list.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        old = {name: box.isChecked() for name, box in self.layer_boxes.items()}
        self.layer_boxes = {}
        for info in self.layout.layers:
            label = info.name + ("" if info.in_tech else " *")
            counts = []
            if info.port_shapes:
                counts.append(f"{info.port_shapes} shapes")
            if info.track_patterns:
                counts.append(f"{info.track_patterns} track patterns")
            box = QCheckBox(f"{label}  ({info.port_shapes})" if info.port_shapes else label)
            box.setToolTip(f"{info.name}: " + (", ".join(counts) or "no objects")
                           + ("" if info.in_tech else "; not in tech, ignored in calculations"))
            pix = QPixmap(12, 12)
            pix.fill(QColor(info.color))
            box.setIcon(QIcon(pix))
            # Keep the user's choice across refreshes; new layers: tech on, others off.
            box.setChecked(old.get(info.name, info.in_tech))
            box.toggled.connect(lambda on, n=info.name: self.canvas.set_layer_visible(n, on))
            self.layer_list.addWidget(box)
            self.layer_boxes[info.name] = box

    def set_all_layers(self, on):
        for name, box in self.layer_boxes.items():
            box.setChecked(self.layout.layer(name).in_tech if on is None else on)

    # -- data ---------------------------------------------------------------------
    def refresh(self):
        """Reload everything from the database (after a command changed it)."""
        self.layout = load_layout(self.session.db)
        self._rebuild_layer_boxes()
        for key, reason in NOT_YET.items():
            box = self.object_boxes[key]
            box.setChecked(False)
            box.setEnabled(False)
            box.setToolTip(reason)
        has = {"boundary": bool(self.layout.boundary), "ports": bool(self.layout.shapes),
               "tracks": bool(self.layout.tracks)}
        for key, present in has.items():
            self.object_boxes[key].setEnabled(present)
            self.object_boxes[key].setToolTip("" if present else "Nothing in the database yet")
        visible = {n for n, b in self.layer_boxes.items() if b.isChecked()}
        self.canvas.set_layout(self.layout, visible)
        title = f"htree4 - {self.layout.design}" if self.layout.design else "htree4"
        self.setWindowTitle(title)

    def on_pick(self, handle):
        self.canvas.select(handle)
        if not handle:
            self.sel_label.setText("")
            return
        from core import objects
        db = self.session.db
        port = objects.get_attr(db, handle, "port")
        text = (f"{port}  layer {objects.get_attr(db, handle, 'layer')}  "
                f"rect {{{objects.get_attr(db, handle, 'rect')}}}  "
                f"direction {objects.format_value(objects.get_attr(db, port, 'direction'))}  "
                f"net {objects.format_value(objects.get_attr(db, port, 'net'))}")
        self.sel_label.setText(text)
        self.session.notify(f"Selected {text}")
