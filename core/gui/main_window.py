"""Main window: menu bar, a small toolbar under it, the layout canvas in the
middle, the visibility panel on the right, cursor position and selection in
the status bar."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QScrollArea, QToolBar, QVBoxLayout,
                               QWidget)

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
        self._build_actions()
        self.pos_label = QLabel("")
        self.sel_label = QLabel("")
        self.statusBar().addWidget(self.pos_label)
        self.statusBar().addPermanentWidget(self.sel_label)
        self.canvas.mouseMoved.connect(lambda x, y: self.pos_label.setText(f"x {x:.3f}  y {y:.3f} um"))
        self.canvas.selectRequested.connect(self.on_select)

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
        hint = QLabel("Drag: zoom to box   Wheel: zoom   F: fit\n"
                      "Middle drag / arrows: pan\n"
                      "Click: select   Ctrl+click: add/remove\n"
                      "Shift+drag: select in box   get_db selected\n"
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

    # -- menu and toolbar ----------------------------------------------------------
    def _build_actions(self):
        def action(text, slot, shortcut=None, tip=""):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setStatusTip(tip)
            a.setToolTip(tip or text)
            return a

        self.act_fit = action("Fit", self.canvas.fit, "F", "Fit the design in the window")
        self.act_zoom_sel = action("Zoom Selected", self.zoom_selected, None,
                                   "Zoom to the selected objects")
        self.act_blink_sel = action("Blink Selected", self.blink_selected, None,
                                    "Flash the selected objects to find them")
        self.act_clear_sel = action("Clear Selection", lambda: self.on_select([], "replace"),
                                    "Esc", "Deselect everything")
        self.act_close = action("Close Window", self.close, "Ctrl+W",
                                "Close the window; the terminal session continues")

        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self.act_close)
        view_menu = bar.addMenu("&View")
        for a in (self.act_fit, self.act_zoom_sel, self.act_blink_sel):
            view_menu.addAction(a)
        view_menu.addSeparator()
        panel = self.findChild(QDockWidget, "view_panel").toggleViewAction()
        panel.setText("Show View Panel")
        view_menu.addAction(panel)
        select_menu = bar.addMenu("&Select")
        select_menu.addAction(self.act_clear_sel)

        tools = QToolBar("Actions", self)
        tools.setObjectName("actions_toolbar")
        tools.setMovable(False)
        tools.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tools.setIconSize(QSize(12, 12))
        tools.setStyleSheet("QToolButton { padding: 1px 6px; font-size: 11px; }")
        for a in (self.act_fit, self.act_zoom_sel, self.act_blink_sel):
            tools.addAction(a)
        self.addToolBar(Qt.TopToolBarArea, tools)
        self.toolbar = tools

    def zoom_selected(self):
        rect = self.canvas.selection_rect()
        if rect.isNull():
            self.statusBar().showMessage(self._nothing_drawn(), 4000)
            return
        self.canvas.zoom_to(rect)

    def blink_selected(self):
        rect = self.canvas.selection_rect()
        if rect.isNull():
            self.statusBar().showMessage(self._nothing_drawn(), 4000)
            return
        self.canvas.blink(rect)

    def _nothing_drawn(self):
        if self.session.db.selection:
            return "The selected objects are not drawn in the layout"
        return "Nothing selected"

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
        self.show_selection()
        title = f"htree4 - {self.layout.design}" if self.layout.design else "htree4"
        self.setWindowTitle(title)

    # -- selection: lives in the session, so get_db selected sees it -------------
    def on_select(self, handles, mode):
        from core import objects
        db = self.session.db
        sel = db.selection
        if mode == "replace":
            sel[:] = list(handles)
        elif mode == "add":
            sel.extend(h for h in handles if h not in sel)
        else:                                          # toggle
            for h in handles:
                sel.remove(h) if h in sel else sel.append(h)
        self.show_selection()
        if not sel:
            self.session.notify("Selection cleared")
        elif len(sel) == 1:
            self.session.notify(f"Selected {self.describe(sel[0])}")
        else:
            self.session.notify(f"Selected {len(sel)} objects (get_db selected)")

    def show_selection(self):
        from core import objects
        sel = objects.selected(self.session.db)
        self.canvas.highlight(sel)
        if not sel:
            self.sel_label.setText("")
        elif len(sel) == 1:
            self.sel_label.setText(self.describe(sel[0]))
        else:
            self.sel_label.setText(f"{len(sel)} objects selected")

    def describe(self, handle):
        """One line about a selected object for the terminal and status bar."""
        from core import objects
        db = self.session.db
        kind = objects.obj_type(handle)
        if kind == "port":
            fv = objects.format_value
            return (f"{handle}  layers {' '.join(objects.get_attr(db, handle, 'layers'))}  "
                    f"rect {{{fv(objects.get_attr(db, handle, 'rect'))}}}  "
                    f"direction {fv(objects.get_attr(db, handle, 'direction'))}  "
                    f"net {fv(objects.get_attr(db, handle, 'net'))}")
        return handle
