"""Main window: menu bar, a small toolbar under it, the layout canvas in the
middle (a Layout tab, and a Schematic tab once create_spine -validate -show
has drawn one), the visibility panel on the right, cursor position and
selection in the status bar."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QPushButton, QScrollArea, QTabWidget,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from core.gui.canvas import LayoutCanvas
from core.gui.layout_data import load_layout

# Object categories: (key, label). Categories with no data yet are disabled.
OBJECTS = [("boundary", "Boundary"), ("ports", "Ports"), ("tracks", "Tracks"),
           ("nets", "Nets"), ("cells", "Cells (instances)"), ("pins", "Pins"),
           ("spine", "Spine")]
NOT_YET = {"nets": "No nets in the database yet"}


class MainWindow(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setWindowTitle("htree4")
        self.resize(1400, 900)
        self.canvas = LayoutCanvas(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.canvas, "Layout")
        self.schematic = None                # SchematicView, made on first use
        self.setCentralWidget(self.tabs)
        self.object_boxes = {}
        self.layer_boxes = {}
        self.assign_boxes = {}               # (layer, net) -> QCheckBox
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
            self.object_boxes[key] = box
            if key == "pins":                     # Pins, with a Label box beside it
                row = QHBoxLayout()
                row.addWidget(box)
                label = QCheckBox("Label")
                label.setToolTip("Write pin names at the centre of the pins shown")
                label.setChecked(self.canvas.show["labels"])
                label.toggled.connect(lambda on: self.canvas.set_show("labels", on))
                row.addWidget(label)
                row.addStretch(1)
                ovbox.addLayout(row)
                self.object_boxes["labels"] = label
                continue
            if key != "tracks":
                ovbox.addWidget(box)
                continue
            # Tracks: a dropdown arrow opens the per-layer track assignments.
            row = QHBoxLayout()
            row.addWidget(box)
            self.assign_toggle = QToolButton()
            self.assign_toggle.setArrowType(Qt.RightArrow)
            self.assign_toggle.setCheckable(True)
            self.assign_toggle.setAutoRaise(True)
            self.assign_toggle.setToolTip("Track assignments per layer")
            self.assign_toggle.toggled.connect(self._toggle_assignments)
            row.addWidget(self.assign_toggle)
            row.addStretch(1)
            ovbox.addLayout(row)
            self.assign_panel = QWidget()
            self.assign_vbox = QVBoxLayout(self.assign_panel)
            self.assign_vbox.setContentsMargins(18, 0, 0, 4)
            self.assign_panel.setVisible(False)
            ovbox.addWidget(self.assign_panel)
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
                      "(n) = pin shapes on the layer.\n"
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
        self.act_clear_sel = action("Clear Selection", self.on_escape, "Esc",
                                    "Deselect everything (Esc first cancels a ruler in progress)")
        self.act_ruler = QAction("Ruler", self, checkable=True)
        self.act_ruler.setToolTip("Measure: click the start and the end point")
        self.act_ruler.setStatusTip("Measure: click the start and the end point")
        self.act_ruler.toggled.connect(self.canvas.set_ruler_mode)   # also when set from code
        self.act_ortho = QAction("Orthogonal", self, checkable=True, checked=True)
        self.act_diag = QAction("Diagonal", self, checkable=True)
        group = QActionGroup(self)
        group.setExclusive(True)
        for a in (self.act_ortho, self.act_diag):
            group.addAction(a)
        self.act_diag.toggled.connect(lambda on: self.canvas.ruler.update(diagonal=on))
        self.act_snap = QAction("Snap to nearest object edge", self, checkable=True,
                                checked=True)
        self.act_snap.setToolTip("Snap to the nearest edge of an object shown in the layout")
        self.act_snap.toggled.connect(lambda on: self.canvas.ruler.update(snap=on))
        self.act_clear_rulers = action("Clear Rulers", self.canvas.clear_rulers, None,
                                       "Remove all rulers")
        self.act_close = action("Close Window", self.close, "Ctrl+W",
                                "Close the window; the terminal session continues")

        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self.act_close)
        view_menu = bar.addMenu("&View")
        for a in (self.act_fit, self.act_zoom_sel, self.act_blink_sel):
            view_menu.addAction(a)
        view_menu.addSeparator()
        view_menu.addAction(self.act_ruler)
        view_menu.addAction(self.act_clear_rulers)
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
        # Ruler: a toggle button with a small side dropdown for its options.
        self.ruler_menu = QMenu(self)
        self.ruler_menu.addAction(self.act_ortho)
        self.ruler_menu.addAction(self.act_diag)
        self.ruler_menu.addSeparator()
        self.ruler_menu.addAction(self.act_snap)
        self.ruler_menu.addSeparator()
        self.ruler_menu.addAction(self.act_clear_rulers)
        self.ruler_button = QToolButton()
        self.ruler_button.setDefaultAction(self.act_ruler)
        self.ruler_button.setMenu(self.ruler_menu)
        self.ruler_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.ruler_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tools.addWidget(self.ruler_button)
        self.addToolBar(Qt.TopToolBarArea, tools)
        self.toolbar = tools
        self.canvas.rulerPlaced.connect(self.on_ruler)

    def on_escape(self):
        if self.canvas.ruler_in_progress():
            self.canvas.cancel_ruler()
        else:
            self.on_select([], "replace")

    def on_ruler(self, text, start, end):
        from core.gui.layout_data import _fmt
        where = f"from ({_fmt(start[0])}, {_fmt(start[1])}) to ({_fmt(end[0])}, {_fmt(end[1])})"
        self.statusBar().showMessage(f"Ruler: {text}", 10000)
        self.session.notify(f"Ruler: {text}  {where}")

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
            if w is not None:                     # hide now: deleteLater paints until then
                w.hide()
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

    def _toggle_assignments(self, open_):
        self.assign_toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.assign_panel.setVisible(open_)

    def _rebuild_assignments(self):
        """One block per assigned layer: its pattern and a checkbox per net."""
        while self.assign_vbox.count():
            w = self.assign_vbox.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        old = {k: b.isChecked() for k, b in self.assign_boxes.items()}
        self.assign_boxes = {}
        self.canvas.assign_hidden = set()
        if not self.layout.assignments:
            note = QLabel("No track assignments.\nUse assign_track_for_route.")
            note.setStyleSheet("color: #888;")
            self.assign_vbox.addWidget(note)
            return
        for a in self.layout.assignments:
            axis = "horizontal" if a.direction == "y" else "vertical"
            title = QLabel(f"<b>{a.layer}</b>  {axis}, {len(a.positions)} tracks<br>"
                           f"<span style='color:#888'>pattern: {' '.join(a.pattern)}</span>")
            self.assign_vbox.addWidget(title)
            for net, count in a.counts:
                label = {"-": "signal (-)", "NA": "blank (NA)"}.get(net, net)
                box = QCheckBox(f"{label}  ({count})")
                pix = QPixmap(12, 12)
                pix.fill(QColor(a.colors[net]))
                box.setIcon(QIcon(pix))
                # Blank tracks carry nothing, so they start hidden.
                on = old.get((a.layer, net), net != "NA")
                box.setChecked(on)
                if not on:
                    self.canvas.assign_hidden.add((a.layer, net))
                box.toggled.connect(lambda v, l=a.layer, n=net:
                                    self.canvas.set_assigned_net_visible(l, n, v))
                self.assign_vbox.addWidget(box)
                self.assign_boxes[(a.layer, net)] = box

    def set_all_layers(self, on):
        for name, box in self.layer_boxes.items():
            box.setChecked(self.layout.layer(name).in_tech if on is None else on)

    # -- data ---------------------------------------------------------------------
    def refresh(self):
        """Reload everything from the database (after a command changed it)."""
        self.layout = load_layout(self.session.db)
        self._rebuild_layer_boxes()
        self._rebuild_assignments()
        for key, reason in NOT_YET.items():
            box = self.object_boxes[key]
            box.setChecked(False)
            box.setEnabled(False)
            box.setToolTip(reason)
        inst_pins = any(i.pins for i in self.layout.insts)
        has = {"boundary": bool(self.layout.boundary), "ports": bool(self.layout.shapes),
               "tracks": bool(self.layout.tracks), "cells": bool(self.layout.insts),
               "spine": bool(self.layout.spines),
               "pins": inst_pins, "labels": inst_pins or bool(self.layout.shapes)}
        for key, present in has.items():
            self.object_boxes[key].setEnabled(present)
            self.object_boxes[key].setToolTip("" if present else "Nothing in the database yet")
        visible = {n for n, b in self.layer_boxes.items() if b.isChecked()}
        self.canvas.set_layout(self.layout, visible)
        self.show_selection()
        title = f"htree4 - {self.layout.design}" if self.layout.design else "htree4"
        self.setWindowTitle(title)

    def show_schematic(self, plan):
        """Draw a create_spine plan in the Schematic tab and switch to it."""
        from core.gui.schematic import SchematicView
        if self.schematic is None:
            self.schematic = SchematicView(self)
            self.tabs.addTab(self.schematic, "Schematic")
        self.tabs.setTabText(self.tabs.indexOf(self.schematic), f"Schematic: {plan.name}")
        self.tabs.setCurrentWidget(self.schematic)
        self.schematic.set_plan(plan)

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
        if kind == "pin":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  direction {g('direction')}  use {g('use')}  "
                    f"layers {' '.join(objects.get_attr(db, handle, 'layers'))}  "
                    f"rect {{{g('rect')}}}")
        if kind == "inst":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  {g('ref_name')}  at {{{g('location')}}} {g('orient')}  "
                    f"bbox {{{g('bbox')}}}")
        return handle
