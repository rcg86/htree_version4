"""Zoomable layout view.

Scene coordinates are microns with y negated (scene y = -model y), so the
layout shows y up. model() and scene() are the only conversions.

Mouse: left drag draws a box and zooms to it; Shift+drag selects every port
with a shape inside the box (Ctrl+Shift+drag adds). Click selects the port
under the cursor, Ctrl+click adds or removes it, click on empty space clears.
Middle drag and the arrow keys pan (past any edge), the wheel zooms about the
cursor, F fits the design in the window. Tracks are
painted behind the shapes, and a pattern appears only once its lines are at
least MIN_TRACK_PIXELS apart on screen.
"""

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from core.gui.layout_data import clip_line_to_polygon, visible_track_positions

ZOOM_STEP = 1.15
MIN_TRACK_PIXELS = 4      # draw a track pattern only when its lines are this far apart
PICK_PIXELS = 3           # click tolerance around the cursor
# The view can only pan inside its scene rect, so the scene rect is the design
# padded by PAN_MARGIN design sizes on every side, and zoom-out stops before
# that padded area fits in the window (where panning would lock up again).
PAN_MARGIN = 10
MIN_CONTENT_PIXELS = 20   # zoom-out stops when the design is this small
HANDLE_KEY = 0            # QGraphicsItem.data key holding the shape's handle
OWNER_KEY = 1             # ... and the selectable object it belongs to (its port)
SELECT_COLOR = "#ffff00"
BLINK_COLOR = "#ff00ff"
BLINK_TIMES = 4           # on/off cycles
BLINK_MS = 200            # per half cycle
BLINK_MIN_PIXELS = 30     # the blink marker is at least this big on screen
ZOOM_MIN_UM = 5.0         # zoom selected shows at least this much of the layout


def scene(x, y):
    return QPointF(x, -y)


def model(p: QPointF):
    return p.x(), -p.y()


class LayoutCanvas(QGraphicsView):
    mouseMoved = Signal(float, float)        # model x, y
    # Objects the user picked and how: "replace", "toggle" (Ctrl+click) or
    # "add". An empty list with "replace" clears the selection.
    selectRequested = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#101418"))
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setMouseTracking(True)
        # Panning is by drag; scrollbars over a padded scene would only confuse.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QRectF()               # design extent in scene coordinates
        self.layout = None
        self.boundary_item = None
        self.shape_items = {}                # layer -> [items]
        self.visible_layers = set()
        self.show = {"boundary": True, "ports": True, "tracks": False}
        self.highlighted = {}                # item -> (pen, z) before highlighting
        self.owner_items = {}                # owner handle (port) -> [items]
        self._press = None
        self._band_mode = None               # "zoom" or "select" while a box is drawn
        self._pan_from = None                # last point of a middle-button pan
        self._band = QRectF()                # last rubber band, scene coordinates
        self.rubberBandChanged.connect(self._on_band)
        self._blink = None                   # (timer, marker item, steps left)

    # -- content ----------------------------------------------------------------
    def set_layout(self, layout, visible_layers):
        self.stop_blink()                     # before clear(), which deletes its marker
        sc = self.scene()
        sc.clear()
        self.layout, self.boundary_item = layout, None
        self.shape_items, self.owner_items, self.highlighted = {}, {}, {}
        self.visible_layers = set(visible_layers)
        if layout.boundary:
            poly = QPolygonF([scene(x, y) for x, y in
                              zip(layout.boundary[0::2], layout.boundary[1::2])])
            pen = QPen(QColor("#e0e0e0"), 0)          # cosmetic: 1 px at any zoom
            self.boundary_item = sc.addPolygon(poly, pen, QBrush(QColor(255, 255, 255, 12)))
            self.boundary_item.setZValue(-1)
        colors = {l.name: l.color for l in layout.layers}
        for s in layout.shapes:
            color = QColor(colors.get(s.layer, "#ffffff"))
            pen = QPen(color, 0)                      # tiny pins still show as 1 px
            if s.type == "rect":
                x1, y1, x2, y2 = s.points
                item = sc.addRect(QRectF(scene(x1, y2), scene(x2, y1)), pen, QBrush(color))
            else:
                item = sc.addPolygon(QPolygonF([scene(x, y) for x, y in
                                                zip(s.points[0::2], s.points[1::2])]),
                                     pen, QBrush(color))
            item.setData(HANDLE_KEY, s.handle)
            item.setData(OWNER_KEY, s.port)
            item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.shape_items.setdefault(s.layer, []).append(item)
            self.owner_items.setdefault(s.port, []).append(item)
        self.content = self._content_rect()
        if not self.content.isEmpty():
            pad = PAN_MARGIN * max(self.content.width(), self.content.height())
            sc.setSceneRect(self.content.adjusted(-pad, -pad, pad, pad))
        self.apply_visibility()
        self.fit()

    def _content_rect(self):
        lay = self.layout
        if lay.bbox:
            x1, y1, x2, y2 = lay.bbox
            return QRectF(scene(x1, y2), scene(x2, y1))
        return self.scene().itemsBoundingRect()

    def apply_visibility(self):
        if self.boundary_item is not None:
            self.boundary_item.setVisible(self.show["boundary"])
        for layer, items in self.shape_items.items():
            on = self.show["ports"] and layer in self.visible_layers
            for item in items:
                item.setVisible(on)
        self.viewport().update()

    def set_show(self, key, on):
        self.show[key] = on
        self.apply_visibility()

    def set_layer_visible(self, layer, on):
        (self.visible_layers.add if on else self.visible_layers.discard)(layer)
        self.apply_visibility()

    def fit(self):
        if self.layout is None:
            return
        rect = self.content
        if rect.isValid() and not rect.isEmpty():
            margin = 0.02 * max(rect.width(), rect.height())
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)

    # -- selection ----------------------------------------------------------------
    def highlight(self, handles):
        """Show handles as selected: a port lights up all its shapes, a
        port_shape just itself. Handles the view does not draw are ignored."""
        for item, (pen, z) in self.highlighted.items():
            item.setPen(pen)
            item.setZValue(z)
        self.highlighted = {}
        by_shape = None
        for h in handles:
            items = self.owner_items.get(h)
            if items is None and h.startswith("port_shape:"):
                if by_shape is None:
                    by_shape = {i.data(HANDLE_KEY): i for its in self.shape_items.values()
                                for i in its}
                items = [by_shape[h]] if h in by_shape else []
            for item in items or []:
                if item not in self.highlighted:
                    self.highlighted[item] = (item.pen(), item.zValue())
                    pen = QPen(QColor(SELECT_COLOR), 2)
                    pen.setCosmetic(True)
                    item.setPen(pen)
                    item.setZValue(10)
        self.viewport().update()

    def selection_rect(self):
        """Scene rect around the highlighted (selected) shapes, or an empty rect."""
        rect = QRectF()
        for item in self.highlighted:
            rect = rect.united(item.sceneBoundingRect())
        return rect

    def zoom_to(self, rect):
        """Fit rect with a margin, showing at least ZOOM_MIN_UM of the layout."""
        if rect.isNull():
            return
        side = max(rect.width(), rect.height(), ZOOM_MIN_UM)
        margin = 0.15 * side
        c = rect.center()
        half = side / 2 + margin
        self.fitInView(QRectF(c.x() - half, c.y() - half, 2 * half, 2 * half),
                       Qt.KeepAspectRatio)

    def blink(self, rect, times=BLINK_TIMES, ms=BLINK_MS):
        """Flash the highlighted shapes and a marker around rect. The marker is
        at least BLINK_MIN_PIXELS on screen, so a sub-pixel pin is still found."""
        self.stop_blink()
        if rect.isNull():
            return
        px = abs(self.transform().m11()) or 1.0
        min_side = BLINK_MIN_PIXELS / px
        w, h = max(rect.width(), min_side), max(rect.height(), min_side)
        c = rect.center()
        pen = QPen(QColor(BLINK_COLOR), 3)
        pen.setCosmetic(True)
        marker = self.scene().addRect(QRectF(c.x() - w / 2, c.y() - h / 2, w, h), pen)
        marker.setZValue(20)
        timer = QTimer(self)
        self._blink = [timer, marker, 2 * times]
        timer.timeout.connect(self._blink_step)
        timer.start(ms)

    def _blink_step(self):
        timer, marker, left = self._blink
        left -= 1
        self._blink[2] = left
        on = left % 2 == 0
        marker.setVisible(on)
        for item in self.highlighted:              # dim, not hide: layer checkboxes
            item.setOpacity(1.0 if on else 0.15)   # still decide what is visible
        if left <= 0:
            self.stop_blink()

    def stop_blink(self):
        if self._blink is None:
            return
        timer, marker, _ = self._blink
        timer.stop()
        self.scene().removeItem(marker)
        for item in self.highlighted:
            item.setOpacity(1.0)
        self._blink = None
        self.viewport().update()

    def owners_in(self, scene_rect):
        """Selectable objects with a visible shape inside scene_rect."""
        owners = []
        for item in self.scene().items(scene_rect, Qt.ContainsItemShape):
            owner = item.data(OWNER_KEY)
            if owner and item.isVisible() and owner not in owners:
                owners.append(owner)
        return owners

    # -- tracks: painted behind the shapes, only those on screen ---------------------
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        lay = self.layout
        if not (lay and self.show["tracks"] and lay.tracks):
            return
        x_lo, y_hi = model(rect.topLeft())
        x_hi, y_lo = model(rect.bottomRight())
        colors = {l.name: l.color for l in lay.layers}
        painter.setRenderHint(QPainter.Antialiasing, False)
        pixels_per_um = abs(self.transform().m11())
        for t in lay.tracks:
            shown = [l for l in t.layers if l in self.visible_layers]
            if not shown or t.step * pixels_per_um < MIN_TRACK_PIXELS:
                continue
            vertical = t.direction == "x"
            pos = visible_track_positions(t, x_lo, x_hi) if vertical else \
                visible_track_positions(t, y_lo, y_hi)
            if not pos:
                continue                              # none here, or too dense
            pen = QPen(QColor(colors.get(shown[0], "#888888")), 0, Qt.DotLine)
            painter.setPen(pen)
            for c in pos:
                spans = clip_line_to_polygon(lay.boundary, vertical, c) if lay.boundary \
                    else [(y_lo, y_hi) if vertical else (x_lo, x_hi)]
                for a, b in spans:
                    if vertical:
                        a, b = max(a, y_lo), min(b, y_hi)
                        if a < b:
                            painter.drawLine(scene(c, a), scene(c, b))
                    else:
                        a, b = max(a, x_lo), min(b, x_hi)
                        if a < b:
                            painter.drawLine(scene(a, c), scene(b, c))

    # -- mouse and keys -------------------------------------------------------------
    def wheelEvent(self, ev):
        self.zoom(ZOOM_STEP if ev.angleDelta().y() > 0 else 1 / ZOOM_STEP)

    def zoom(self, factor):
        """Scale about the cursor; zoom-out stops at MIN_CONTENT_PIXELS."""
        if factor < 1 and not self.content.isEmpty():
            size = max(self.content.width(), self.content.height())
            if size * abs(self.transform().m11()) * factor < MIN_CONTENT_PIXELS:
                return
        self.scale(factor, factor)

    def mousePressEvent(self, ev):
        self._press = ev.position().toPoint()
        if ev.button() == Qt.MiddleButton:                    # middle drag: pan
            self._pan_from = self._press
            self.viewport().setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        if ev.button() == Qt.LeftButton:                      # left drag: draw a box
            self._band = QRectF()
            self._band_mode = "select" if ev.modifiers() & Qt.ShiftModifier else "zoom"
            self.setDragMode(QGraphicsView.RubberBandDrag)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MiddleButton and self._pan_from is not None:
            self._pan_from = None
            self.viewport().unsetCursor()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)
        mode, self._band_mode = self._band_mode, None
        self.setDragMode(QGraphicsView.NoDrag)
        if ev.button() != Qt.LeftButton or self._press is None:
            return
        mods = ev.modifiers()
        dragged = (ev.position().toPoint() - self._press).manhattanLength() >= 4
        self._press = None
        if dragged and not self._band.isEmpty():
            if mode == "zoom":
                self.fitInView(self._band, Qt.KeepAspectRatio)
            else:
                self.selectRequested.emit(self.owners_in(self._band),
                                          "add" if mods & Qt.ControlModifier else "replace")
            return
        owner = self.owner_at(ev.position().toPoint())        # a click: select
        if mods & Qt.ControlModifier:
            if owner:
                self.selectRequested.emit([owner], "toggle")
        else:
            self.selectRequested.emit([owner] if owner else [], "replace")

    def _on_band(self, view_rect, from_scene, to_scene):
        if not view_rect.isNull():               # the final signal is a null rect
            self._band = QRectF(from_scene, to_scene).normalized()

    def owner_at(self, view_point) -> str:
        """The selectable object (port) of the shape nearest a viewport point."""
        item = self._item_at(view_point)
        return item.data(OWNER_KEY) if item is not None else ""

    def handle_at(self, view_point) -> str:
        """Handle of the visible port shape nearest a viewport point."""
        item = self._item_at(view_point)
        return item.data(HANDLE_KEY) if item is not None else ""

    def _item_at(self, view_point):
        """Visible shape item nearest a viewport point. Pins are often smaller
        than a pixel, so shapes within PICK_PIXELS count."""
        r = PICK_PIXELS
        box = QRect(view_point.x() - r, view_point.y() - r, 2 * r + 1, 2 * r + 1)
        p = self.mapToScene(view_point)
        best, best_d = None, None
        for item in self.items(box):
            if not item.data(HANDLE_KEY) or not item.isVisible():
                continue
            b = item.sceneBoundingRect()
            dx = max(b.left() - p.x(), 0, p.x() - b.right())
            dy = max(b.top() - p.y(), 0, p.y() - b.bottom())
            d = dx * dx + dy * dy                     # 0 when the point is inside
            if best_d is None or d < best_d:
                best, best_d = item, d
        return best

    def mouseMoveEvent(self, ev):
        point = ev.position().toPoint()
        if self._pan_from is not None:
            self.pan_by(point.x() - self._pan_from.x(), point.y() - self._pan_from.y())
            self._pan_from = point
        else:
            super().mouseMoveEvent(ev)
        x, y = model(self.mapToScene(point))
        self.mouseMoved.emit(x, y)

    def pan_by(self, dx, dy):
        """Move the layout by (dx, dy) pixels, as if dragged."""
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() - dx)
        v.setValue(v.value() - dy)

    def keyPressEvent(self, ev):
        step_x, step_y = self.viewport().width() // 4, self.viewport().height() // 4
        moves = {Qt.Key_Left: (step_x, 0), Qt.Key_Right: (-step_x, 0),
                 Qt.Key_Up: (0, step_y), Qt.Key_Down: (0, -step_y)}
        if ev.key() == Qt.Key_F:
            self.fit()
        elif ev.key() in moves:                   # the arrow shows where to look
            self.pan_by(*moves[ev.key()])
        else:
            super().keyPressEvent(ev)
