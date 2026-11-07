"""Zoomable layout view.

Scene coordinates are microns with y negated (scene y = -model y), so the
layout shows y up. model() and scene() are the only conversions.

Mouse: wheel zooms about the cursor, left drag pans, left click selects the
port shape under the cursor. F fits the design in the window. Tracks are
painted behind the shapes, and a pattern appears only once its lines are at
least MIN_TRACK_PIXELS apart on screen.
"""

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from core.gui.layout_data import clip_line_to_polygon, visible_track_positions

ZOOM_STEP = 1.15
MIN_TRACK_PIXELS = 4      # draw a track pattern only when its lines are this far apart
PICK_PIXELS = 3           # click tolerance around the cursor
HANDLE_KEY = 0            # QGraphicsItem.data key holding the object's handle


def scene(x, y):
    return QPointF(x, -y)


def model(p: QPointF):
    return p.x(), -p.y()


class LayoutCanvas(QGraphicsView):
    mouseMoved = Signal(float, float)        # model x, y
    picked = Signal(str)                     # handle of the clicked object, "" for none

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#101418"))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setMouseTracking(True)
        self.layout = None
        self.boundary_item = None
        self.shape_items = {}                # layer -> [items]
        self.visible_layers = set()
        self.show = {"boundary": True, "ports": True, "tracks": False}
        self.selected = None
        self._press = None

    # -- content ----------------------------------------------------------------
    def set_layout(self, layout, visible_layers):
        sc = self.scene()
        sc.clear()
        self.layout, self.boundary_item, self.selected = layout, None, None
        self.shape_items = {}
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
            item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.shape_items.setdefault(s.layer, []).append(item)
        self.apply_visibility()
        self.fit()

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
        lay = self.layout
        if lay is None:
            return
        if lay.bbox:
            x1, y1, x2, y2 = lay.bbox
            rect = QRectF(scene(x1, y2), scene(x2, y1))
        else:
            rect = self.scene().itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            margin = 0.02 * max(rect.width(), rect.height())
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)

    # -- selection ----------------------------------------------------------------
    def select(self, handle):
        """Highlight the item for handle ('' clears)."""
        if self.selected is not None:
            item, pen, z = self.selected
            item.setPen(pen)
            item.setZValue(z)
            self.selected = None
        if not handle:
            return
        for items in self.shape_items.values():
            for item in items:
                if item.data(HANDLE_KEY) == handle:
                    self.selected = (item, item.pen(), item.zValue())
                    item.setPen(QPen(QColor("#ffff00"), 3))
                    item.setZValue(10)
                    return

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
        factor = ZOOM_STEP if ev.angleDelta().y() > 0 else 1 / ZOOM_STEP
        self.scale(factor, factor)

    def mousePressEvent(self, ev):
        self._press = ev.position().toPoint()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.LeftButton and self._press is not None and \
                (ev.position().toPoint() - self._press).manhattanLength() < 4:
            self.picked.emit(self.handle_at(ev.position().toPoint()))
        self._press = None

    def handle_at(self, view_point) -> str:
        """Handle of the visible port shape nearest a viewport point. Pins are
        often smaller than a pixel, so shapes within a few pixels count."""
        r = PICK_PIXELS
        box = QRect(view_point.x() - r, view_point.y() - r, 2 * r + 1, 2 * r + 1)
        p = self.mapToScene(view_point)
        best, best_d = "", None
        for item in self.items(box):
            handle = item.data(HANDLE_KEY)
            if not handle or not item.isVisible():
                continue
            b = item.sceneBoundingRect()
            dx = max(b.left() - p.x(), 0, p.x() - b.right())
            dy = max(b.top() - p.y(), 0, p.y() - b.bottom())
            d = dx * dx + dy * dy                     # 0 when the point is inside
            if best_d is None or d < best_d:
                best, best_d = handle, d
        return best

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        x, y = model(self.mapToScene(ev.position().toPoint()))
        self.mouseMoved.emit(x, y)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_F:
            self.fit()
        else:
            super().keyPressEvent(ev)
