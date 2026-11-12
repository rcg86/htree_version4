"""Main window: menu bar, a small toolbar under it, the layout canvas in the
middle (a Layout tab, and a Schematic tab once create_spine -validate -show
has drawn one), the visibility panel on the right, cursor position and
selection in the status bar."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QPushButton, QScrollArea, QTabWidget,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

import io
import tkinter

from core.gui import shortcuts
from core.gui.canvas import LayoutCanvas
from core.gui.layout_data import load_layout

# Object categories: (key, label). Categories with no data yet are disabled.
OBJECTS = [("boundary", "Boundary"), ("ports", "Ports"), ("tracks", "Tracks"),
           ("rows", "Rows (sites)"),
           ("nets", "Nets"), ("cells", "Cells (instances)"), ("pins", "Pins"),
           ("spine", "Spine"), ("routes", "Routes (route_pin, route_net)")]
NOT_YET = {"nets": "No nets in the database yet"}
BUTTON_ZOOM = 1.5            # Zoom In / Zoom Out step
NAMES_SHOWN = 3              # status bar centre: names of a multiple selection shown
# The small boxes beside each layer: (net class, text, tooltip). All start on.
CLASS_BOXES = [("signal", "S", "Signal nets on this layer"),
               ("power", "P", "Power nets on this layer (VDD_SOC, USE POWER)"),
               ("ground", "G", "Ground nets on this layer (VSS, USE GROUND)")]


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
        self.class_boxes = {}                # (layer, signal|power|ground) -> QCheckBox
        self.all_class_boxes = {}            # signal|power|ground -> the All layers box
        self.assign_boxes = {}               # (layer, net) -> QCheckBox
        self.site_boxes = {}                 # site -> QCheckBox (Rows dropdown)
        self.layout = None
        self.undo_edits = []                 # Tools > Undo Edit: commands that undo, last last
        self._edited = None                  # wires an edit here is changing: redraw just them
        self._build_panel()
        self._build_actions()
        self.pos_label = QLabel("")
        self.sel_label = QLabel("")
        # Centre: the selected object's name (a wire's net, inst/pin for a pin).
        self.name_label = QLabel("")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.statusBar().addWidget(self.pos_label)
        self.statusBar().addWidget(self.name_label, 1)
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
            if key == "rows":                     # Rows: a dropdown arrow opens the sites
                row = QHBoxLayout()
                row.addWidget(box)
                self.rows_toggle = QToolButton()
                self.rows_toggle.setArrowType(Qt.RightArrow)
                self.rows_toggle.setCheckable(True)
                self.rows_toggle.setAutoRaise(True)
                self.rows_toggle.setToolTip("Placement rows per site (DEF ROW)")
                self.rows_toggle.toggled.connect(self._toggle_rows)
                row.addWidget(self.rows_toggle)
                row.addStretch(1)
                ovbox.addLayout(row)
                self.rows_panel = QWidget()
                self.rows_vbox = QVBoxLayout(self.rows_panel)
                self.rows_vbox.setContentsMargins(18, 0, 0, 4)
                self.rows_panel.setVisible(False)
                ovbox.addWidget(self.rows_panel)
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

        # Layers: a dropdown arrow opens and closes the layer list.
        self.layer_group = QGroupBox()
        group_vbox = QVBoxLayout(self.layer_group)
        self.layer_toggle = QToolButton()
        self.layer_toggle.setText("Layers")
        self.layer_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.layer_toggle.setArrowType(Qt.DownArrow)
        self.layer_toggle.setCheckable(True)
        self.layer_toggle.setChecked(True)
        self.layer_toggle.setAutoRaise(True)
        self.layer_toggle.setToolTip("Show or hide the layer list")
        self.layer_toggle.toggled.connect(self._toggle_layers)
        group_vbox.addWidget(self.layer_toggle)
        self.layer_body = QWidget()
        self.layer_vbox = QVBoxLayout(self.layer_body)
        self.layer_vbox.setContentsMargins(0, 0, 0, 0)
        group_vbox.addWidget(self.layer_body)
        buttons = QHBoxLayout()
        for text, on in (("All", True), ("None", False), ("Tech only", None)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, v=on: self.set_all_layers(v))
            buttons.addWidget(b)
        self.layer_vbox.addLayout(buttons)
        # All layers: S P G boxes over the layer rows' boxes, for every layer at once.
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(4)
        head.addWidget(QLabel("All layers"), 1)
        for cls, text, tip in CLASS_BOXES:
            small = QCheckBox(text)
            small.setStyleSheet("QCheckBox { font-size: 8pt; }")
            small.setToolTip(tip.replace("on this layer", "on every layer"))
            small.setChecked(True)
            small.toggled.connect(lambda on, c=cls: self.set_all_classes(c, on))
            head.addWidget(small)
            self.all_class_boxes[cls] = small
        self.layer_vbox.addLayout(head)
        self.layer_list = QVBoxLayout()
        self.layer_vbox.addLayout(self.layer_list)
        vbox.addWidget(self.layer_group)
        hint = QLabel("Drag: zoom to box   Wheel: zoom   F: fit\n"
                      "Edit > Shortcuts: list and create shortcuts\n"
                      "Middle drag / arrows: pan\n"
                      "Click: select   Ctrl+click: add/remove\n"
                      "Shift+drag: select in box   get_db selected\n"
                      "Right drag: select all touching box\n"
                      "Tracks and rows show when zoomed in enough;\n"
                      "sites when zoomed in further.\n"
                      "(n) = pin shapes on the layer.\n"
                      "* = not in tech (starts hidden).\n"
                      "S P G = the layer's signal, power (VDD_SOC)\n"
                      "and ground (VSS) shapes.")
        hint.setStyleSheet("color: #888;")
        vbox.addWidget(hint)
        vbox.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        dock = QDockWidget("View", self)
        dock.setObjectName("view_panel")
        dock.setWidget(scroll)
        dock.setMinimumWidth(300)
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
        self.act_zoom_in = action("Zoom In", lambda: self.canvas.zoom(BUTTON_ZOOM), None,
                                  "Zoom in (about the cursor when it is over the layout)")
        self.act_zoom_out = action("Zoom Out", lambda: self.canvas.zoom(1 / BUTTON_ZOOM), None,
                                   "Zoom out (about the cursor when it is over the layout)")
        # Tools: edit route shapes by hand (move_wire, stretch_wire), one mode at a time.
        self.act_tool_select = QAction("Select", self, checkable=True, checked=True)
        self.act_tool_select.setToolTip("Click and drag select and zoom as usual")
        self.act_tool_stretch = QAction("Stretch", self, checkable=True)
        self.act_tool_stretch.setToolTip("Drag an edge of a wire, strap or pin wire to "
                                         "lengthen or shorten it (stretch_wire)")
        self.act_tool_move = QAction("Move", self, checkable=True)
        self.act_tool_move.setToolTip("Drag a wire, strap or pin wire (all selected ones when "
                                      "it is selected) to move it (move_wire)")
        self.tool_group = QActionGroup(self)
        # Optional: the key of the mode in use (S again in Stretch) turns it off,
        # which goes back to Select.
        self.tool_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        for a, mode in ((self.act_tool_select, None), (self.act_tool_stretch, "stretch"),
                        (self.act_tool_move, "move")):
            self.tool_group.addAction(a)
            a.toggled.connect(lambda on, m=mode: on and self.set_tool(m))
        self.tool_group.triggered.connect(
            lambda a: None if self.tool_group.checkedAction() else
            self.act_tool_select.setChecked(True))
        self.act_edit_snap = QAction("Snap (tracks, edges, grid)", self, checkable=True,
                                     checked=True)
        self.act_edit_snap.setToolTip("Move: a wire's centre line onto a track of its layer; "
                                      "Stretch: the edge onto a nearby edge or track; else "
                                      "the manufacturing grid")
        self.act_edit_snap.toggled.connect(lambda on: self.canvas.edit.update(snap=on))
        self.act_undo_edit = action("Undo Edit", self.undo_edit, None,
                                    "Undo the last Stretch or Move")
        self.act_undo_edit.setEnabled(False)
        self.canvas.wiresMoved.connect(self.on_wires_moved)
        self.canvas.wireStretched.connect(self.on_wire_stretched)
        self.act_ruler.toggled.connect(lambda on: on and self.act_tool_select.setChecked(True))
        self.act_shortcuts = action("Shortcuts...", self.show_shortcuts, None,
                                    "List the keyboard shortcuts and create new ones")
        # Actions Edit > Shortcuts can give a shortcut to, by the key it is saved
        # under, and their built in shortcuts (a user one replaces it; removing
        # the user one brings it back).
        self.creatable = {
            "fit": self.act_fit, "zoom_in": self.act_zoom_in, "zoom_out": self.act_zoom_out,
            "zoom_selected": self.act_zoom_sel, "blink_selected": self.act_blink_sel,
            "ruler": self.act_ruler, "clear_rulers": self.act_clear_rulers,
            "tool_select": self.act_tool_select, "tool_stretch": self.act_tool_stretch,
            "tool_move": self.act_tool_move, "edit_snap": self.act_edit_snap,
            "undo_edit": self.act_undo_edit, "clear_selection": self.act_clear_sel,
            "shortcuts": self.act_shortcuts}
        self.default_shortcuts = {"fit": "F", "ruler": "K", "clear_rulers": "Shift+K",
                                  "tool_stretch": "S", "tool_move": "M",
                                  "clear_selection": "Esc"}
        for key, seq in self.default_shortcuts.items():
            self.creatable[key].setShortcut(QKeySequence(seq))
        self.user_shortcuts = {}
        for key, seq in shortcuts.load().items():
            if key in self.creatable and not shortcuts.owner_of(
                    self, seq, skip=self.creatable[key]):
                self.creatable[key].setShortcut(QKeySequence(seq))
                self.user_shortcuts[key] = seq

        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self.act_close)
        edit_menu = bar.addMenu("&Edit")
        for a in (self.act_tool_select, self.act_tool_stretch, self.act_tool_move):
            edit_menu.addAction(a)            # also makes their shortcuts work
        edit_menu.addAction(self.act_edit_snap)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_undo_edit)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_shortcuts)
        view_menu = bar.addMenu("&View")
        for a in (self.act_fit, self.act_zoom_in, self.act_zoom_out, self.act_zoom_sel,
                  self.act_blink_sel):
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
        tools.addAction(self.act_zoom_in)
        tools.addAction(self.act_zoom_out)
        # Tools: the route editing toolbox, a dropdown of modes and options.
        self.tools_menu = QMenu(self)
        for a in (self.act_tool_select, self.act_tool_stretch, self.act_tool_move):
            self.tools_menu.addAction(a)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.act_edit_snap)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.act_undo_edit)
        self.tools_button = QToolButton()
        self.tools_button.setText("Tools")
        self.tools_button.setToolTip("Fix routes by hand: Stretch an edge, Move a wire")
        self.tools_button.setMenu(self.tools_menu)
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        self.tools_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tools.addWidget(self.tools_button)
        self.addToolBar(Qt.TopToolBarArea, tools)
        self.toolbar = tools
        self.canvas.rulerPlaced.connect(self.on_ruler)

    # -- shortcuts ------------------------------------------------------------------
    def all_actions(self):
        """The window's actions, in menu order, for the shortcut list."""
        return [self.act_close, self.act_tool_select, self.act_tool_stretch, self.act_tool_move,
                self.act_edit_snap, self.act_undo_edit, self.act_shortcuts, self.act_fit,
                self.act_zoom_in, self.act_zoom_out, self.act_zoom_sel, self.act_blink_sel,
                self.act_ruler, self.act_clear_rulers, self.act_clear_sel]

    def creatable_key(self, act):
        return next((k for k, a in self.creatable.items() if a is act), None)

    def set_user_shortcut(self, key, seq):
        """Give creatable action key the shortcut seq ('' or None removes it)
        and save. Returns an error text, or None when done."""
        act = self.creatable[key]
        if seq:
            owner = shortcuts.owner_of(self, seq, skip=act)
            if owner:
                return f"{shortcuts.text_of(seq)} is already the shortcut of {owner}."
            act.setShortcut(QKeySequence(seq))
            self.user_shortcuts[key] = QKeySequence(seq).toString()
        else:                                 # back to the built in one, if any
            act.setShortcut(QKeySequence(self.default_shortcuts.get(key, "")))
            self.user_shortcuts.pop(key, None)
        try:
            shortcuts.save(self.user_shortcuts)
        except OSError as exc:
            return f"Set for this session, but not saved to {shortcuts.store_path()}: {exc}"
        return None

    def show_shortcuts(self):
        shortcuts.ShortcutsDialog(self).exec()

    # -- Tools: Stretch and Move run move_wire / stretch_wire ------------------------
    def set_tool(self, mode):
        """None (select), "stretch" or "move"."""
        if mode and self.act_ruler.isChecked():
            self.act_ruler.setChecked(False)
        self.canvas.set_edit_mode(mode)
        self.tools_button.setText("Tools" if mode is None else f"Tools: {mode.capitalize()}")

    def on_wires_moved(self, handles, dx, dy):
        wires = " ".join(handles)
        self.run_edit(f"move_wire -wires {{{wires}}} -delta {{{_n(dx)} {_n(dy)}}}",
                      f"move_wire -wires {{{wires}}} -delta {{{_n(-dx)} {_n(-dy)}}}")

    def on_wire_stretched(self, handle, edge, to, old):
        self.run_edit(f"stretch_wire -wire {handle} -edge {edge} -to {_n(to)}",
                      f"stretch_wire -wire {handle} -edge {edge} -to {_n(old)}")

    def undo_edit(self):
        if self.undo_edits:
            self.run_edit(self.undo_edits.pop(), None)

    def run_edit(self, cmd, undo):
        """Run an edit command as if typed: it is echoed with its output in
        the terminal, only the wires it changes are redrawn (the view stays
        where it is), and undo (the command that reverses it) is kept for
        Undo Edit. Returns True when it ran."""
        session = self.session
        out, session.out = session.out, io.StringIO()
        words = session.split_list(cmd)
        self._edited = session.split_list(words[words.index("-wires" if "-wires" in words
                                                            else "-wire") + 1])
        ok = True
        try:
            session.eval(cmd)
        except tkinter.TclError:
            ok = False
        finally:
            text, session.out = session.out.getvalue(), out
            self._edited = None
        session.notify(f"{cmd}\n{text.rstrip()}" if text.strip() else cmd)
        if ok and undo:
            self.undo_edits.append(undo)
        self.act_undo_edit.setEnabled(bool(self.undo_edits))
        if not ok:
            self.statusBar().showMessage(text.strip().splitlines()[-1] if text.strip()
                                         else f"failed: {cmd}", 8000)
        return ok

    def on_escape(self):
        if self.canvas.editing():
            self.canvas.cancel_edit()
        elif self.canvas.ruler_in_progress():
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
        old_classes = {k: box.isChecked() for k, box in self.class_boxes.items()}
        self.layer_boxes, self.class_boxes = {}, {}
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
            # The layer, then small Signal / Power / Ground boxes on the same row.
            row = QWidget()
            hbox = QHBoxLayout(row)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(4)
            hbox.addWidget(box, 1)
            for cls, text, tip in CLASS_BOXES:
                small = QCheckBox(text)
                small.setStyleSheet("QCheckBox { font-size: 8pt; }")
                small.setToolTip(tip)
                small.setChecked(old_classes.get((info.name, cls), True))
                small.toggled.connect(lambda on, n=info.name, c=cls:
                                      self._class_toggled(n, c, on))
                hbox.addWidget(small)
                self.class_boxes[(info.name, cls)] = small
            self.layer_list.addWidget(row)
            self.layer_boxes[info.name] = box
        self.canvas.class_hidden = {k for k, b in self.class_boxes.items() if not b.isChecked()}
        for cls in self.all_class_boxes:
            self._sync_all_class(cls)

    def set_all_classes(self, cls, on):
        """The All layers box of cls: every layer's cls box follows it."""
        for (layer, c), box in self.class_boxes.items():
            if c == cls:
                box.blockSignals(True)
                box.setChecked(on)
                box.blockSignals(False)
                (self.canvas.class_hidden.discard if on else self.canvas.class_hidden.add)(
                    (layer, cls))
        self.canvas.apply_visibility()

    def _class_toggled(self, layer, cls, on):
        self.canvas.set_class_visible(layer, cls, on)
        self._sync_all_class(cls)

    def _sync_all_class(self, cls):
        """The All layers box is checked while every layer's cls box is."""
        box = self.all_class_boxes[cls]
        box.blockSignals(True)
        box.setChecked(all(b.isChecked() for (_, c), b in self.class_boxes.items() if c == cls))
        box.blockSignals(False)

    def _toggle_layers(self, open_):
        self.layer_toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.layer_body.setVisible(open_)

    def _toggle_assignments(self, open_):
        self.assign_toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.assign_panel.setVisible(open_)

    def _toggle_rows(self, open_):
        self.rows_toggle.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.rows_panel.setVisible(open_)

    def _rebuild_site_rows(self):
        """One checkbox per site of the DEF rows, with its color and size."""
        while self.rows_vbox.count():
            w = self.rows_vbox.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        old = {k: b.isChecked() for k, b in self.site_boxes.items()}
        self.site_boxes = {}
        if not self.layout.site_rows:
            note = QLabel("No placement rows.\nUse read_def with ROW statements.")
            note.setStyleSheet("color: #888;")
            self.rows_vbox.addWidget(note)
            return
        for sr in self.layout.site_rows:
            box = QCheckBox(f"{sr.site}  ({len(sr.rows)})")
            box.setToolTip(f"{sr.site}: {len(sr.rows)} rows, site {sr.width:g} x {sr.height:g} um")
            pix = QPixmap(12, 12)
            pix.fill(QColor(sr.color))
            box.setIcon(QIcon(pix))
            box.setChecked(old.get(sr.site, True))
            box.toggled.connect(lambda on, n=sr.site: self.canvas.set_site_rows_visible(n, on))
            self.rows_vbox.addWidget(box)
            self.site_boxes[sr.site] = box
        self.canvas.rows_hidden = {k for k, b in self.site_boxes.items() if not b.isChecked()}

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
        """Reload everything from the database (after a command changed it).
        During an edit made here, only the edited wires are redrawn."""
        if self._edited is not None:
            from core import objects
            rects = {}
            for h in self._edited:
                row = objects.wire_row(self.session.db, h)
                if row is not None:
                    rects[h] = tuple(float(c) for c in row["rect"].split())
            self.canvas.update_rects(rects)
            from core import auto_via
            from core.gui.layout_data import net_wire_strap
            for h in self._edited:                # its auto vias (stretch_wire)
                self.canvas.replace_route_shapes(
                    f"net_wire:{auto_via.owner(h)}/",
                    [net_wire_strap(r) for r in self.session.db.net_wire_rows(auto_via.owner(h))])
            self.show_selection()
            return
        self.layout = load_layout(self.session.db)
        self._rebuild_layer_boxes()
        self._rebuild_assignments()
        self._rebuild_site_rows()
        for key, reason in NOT_YET.items():
            box = self.object_boxes[key]
            box.setChecked(False)
            box.setEnabled(False)
            box.setToolTip(reason)
        inst_pins = any(i.pins for i in self.layout.insts)
        has = {"boundary": bool(self.layout.boundary), "ports": bool(self.layout.shapes),
               "tracks": bool(self.layout.tracks), "cells": bool(self.layout.insts),
               "rows": bool(self.layout.site_rows),
               "spine": bool(self.layout.spines),
               "routes": bool(self.layout.straps or self.layout.pin_wires
                              or self.layout.net_wires),
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
        names = list(dict.fromkeys(self.object_name(h) for h in sel))
        more = f"  +{len(names) - NAMES_SHOWN} more" if len(names) > NAMES_SHOWN else ""
        self.name_label.setText(", ".join(names[:NAMES_SHOWN]) + more)
        self.name_label.setToolTip("\n".join(names) if more else "")

    def object_name(self, handle):
        """The name the status bar shows in its centre: a wire's net (a
        shield's, a power extension's or a via's: its power net), an
        instance's name, inst/pin for a pin, a port's pin name. A strap or pin
        wire of an unrouted signal pin (net SIGNAL) shows its inst/pin."""
        from core import objects
        db = self.session.db
        kind = objects.obj_type(handle)
        rest = handle.partition(":")[2]
        if kind in objects.WIRE_TABLES:
            row = objects.wire_row(db, handle)
            if row is None:
                return rest
            net = (row["shield_net"] or row["net"]) if kind == "net_wire" else row["net"]
            if net != "SIGNAL":
                return net
            pin = row["pin"] if kind == "pin_wire" else next(
                (w["pin"] for w in db.pin_wire_rows(row["inst"]) if w["strap"] == row["seq"]),
                None)
            return f"{row['inst']}/{pin}" if pin else f"{row['inst']} (unrouted)"
        if kind in ("port", "port_shape"):                 # <design>/<pin>[/<k>]
            return rest.split("/")[1] if "/" in rest else rest
        if kind == "spine_net":                            # <spine>/<net>
            return rest.partition("/")[2] or rest
        return rest or handle                              # inst, pin (inst/pin), net, stub

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
        if kind == "spine_net":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  driver {g('driver')}  loads {{{g('loads')}}}  "
                    f"group {g('group')}  length {g('length')}  route_rule {g('route_rule')}")
        if kind == "strap":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  net {g('net')}  layer {g('layer')}  rect {{{g('rect')}}}  "
                    f"width {g('width')}")
        if kind == "pin_wire":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  net {g('net')}  layer {g('layer')}  rect {{{g('rect')}}}  "
                    f"width {g('width')}  to {g('strap')}")
        if kind == "net_wire":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            shield = f"  {g('shield_net')} shielding {g('net')}" if g("kind") == "shield" else ""
            return (f"{handle}  {g('kind')}  layer {g('layer')}  rect {{{g('rect')}}}  "
                    f"{g('width')} x {g('length')}{shield}")
        if kind == "stub":
            g = lambda a: objects.format_value(objects.get_attr(db, handle, a))
            return (f"{handle}  driver {g('driver')}  points {{{g('points')}}}  "
                    f"length {g('length')}")
        return handle


def _n(v):
    """A coordinate for a command line: no float noise, no trailing zeros."""
    text = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text
