"""Zoomable layout view.

Scene coordinates are microns with y negated (scene y = -model y), so the
layout shows y up. model() and scene() are the only conversions.

Mouse: left drag draws a box and zooms to it; Shift+drag selects every object
with a shape inside the box (Ctrl+Shift+drag adds); right drag selects every
object with a shape touching the box (Ctrl+right drag adds). Click selects the
object under the cursor, Ctrl+click adds or removes it, click on empty space
clears. Selectable: ports, instances, instance pins, spine nets and stubs,
route_pin straps and pin wires.
Middle drag and the arrow keys pan (past any edge), the wheel zooms about the
cursor, F fits the design in the window. In ruler mode, left clicks set the
start and end of a ruler (snapped to drawn edges when snapping is on), right
click cancels. Tracks are
painted behind the shapes, and a pattern appears only once its lines are at
least MIN_TRACK_PIXELS apart on screen. Tech layers show only the tracks of
their preferred direction (a horizontal layer: DEF TRACKS Y).
"""

import bisect
import math

from PySide6.QtCore import QLineF, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
                               QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QRubberBand)

from core.gui.layout_data import (BLANK, SIGNAL, clip_line_to_polygon, constrain_orthogonal,
                                  drawn_layers, track_coords, nearest_on_segments, polygon_edges,
                                  ruler_text, segment_touches_rect, visible_assigned_tracks,
                                  visible_rows, visible_track_positions)

ZOOM_STEP = 1.15
MIN_TRACK_PIXELS = 4      # draw a track pattern only when its lines are this far apart
PICK_PIXELS = 3           # click tolerance around the cursor
MIN_ROW_PIXELS = 3        # draw a site's rows only when a row is this tall on screen
MIN_SITE_PIXELS = 4       # ... and its site boundaries when a site is this wide
MAX_SITE_LINES = 6000     # site boundaries drawn at most, per paint
# The view can only pan inside its scene rect, so the scene rect is the design
# padded by PAN_MARGIN design sizes on every side, and zoom-out stops before
# that padded area fits in the window (where panning would lock up again).
PAN_MARGIN = 10
MIN_CONTENT_PIXELS = 20   # zoom-out stops when the design is this small
HANDLE_KEY = 0            # QGraphicsItem.data key holding the shape's handle
OWNER_KEY = 1             # ... and the selectable object it belongs to (port, net, ...)
LABEL_KEY = 2             # ... and the pin name written on it when labels are on
CLASS_KEY = 3             # ... and its net class: signal, power or ground
LAYER_KEY = 4             # ... and, for a route shape, its layer
# Route shapes the Tools > Stretch and Move edit modes change (move_wire, stretch_wire).
EDITABLE = ("net_wire:", "strap:", "pin_wire:")
EDGE_PIXELS = 5           # Stretch: an edge this close to the cursor is picked
MAX_LABELS = 2000         # more pins than this in view: no labels until zoomed in
SELECT_COLOR = "#ffff00"
INST_COLOR = "#26c6da"        # instance outline
SPINE_STUB_COLOR = "#b388ff"  # built spine: stubs (3 px) and net centre lines (1 px)
SPINE_NET_COLOR = "#7bd88f"
BLINK_COLOR = "#ff00ff"
BLINK_TIMES = 4           # on/off cycles
BLINK_MS = 200            # per half cycle
BLINK_MIN_PIXELS = 30     # the blink marker is at least this big on screen
ZOOM_MIN_UM = 5.0         # zoom selected shows at least this much of the layout
RULER_COLOR = "#00e5ff"
SNAP_PIXELS = 10          # the ruler snaps to a drawn edge this close to the cursor


def scene(x, y):
    return QPointF(x, -y)


def _geometry_rect(item):
    """Bounding rect of the item's geometry, without its outline pen."""
    if isinstance(item, QGraphicsRectItem):
        return item.rect()
    if isinstance(item, QGraphicsPolygonItem):
        return item.polygon().boundingRect()
    if isinstance(item, QGraphicsLineItem):
        line = item.line()
        return QRectF(line.p1(), line.p2()).normalized()
    return item.sceneBoundingRect()


def _enclosed(item, rect):
    """True if the item's geometry lies wholly in scene rect. Compared by
    coordinates: a straight net has a zero-width box, which QRectF treats
    as empty."""
    g = _geometry_rect(item)
    return (rect.left() <= g.left() and g.right() <= rect.right()
            and rect.top() <= g.top() and g.bottom() <= rect.bottom())


def _touches(item, rect):
    """True if any part of the item's geometry (not its outline pen) is in
    scene rect."""
    if isinstance(item, QGraphicsLineItem):
        line = item.line()
        return segment_touches_rect((line.x1(), line.y1()), (line.x2(), line.y2()),
                                    (rect.left(), rect.top(), rect.right(), rect.bottom()))
    if isinstance(item, QGraphicsPolygonItem):
        return item.polygon().intersects(QPolygonF(rect)) or \
            rect.contains(item.polygon().boundingRect())
    g = _geometry_rect(item)
    return (g.left() <= rect.right() and rect.left() <= g.right()
            and g.top() <= rect.bottom() and rect.top() <= g.bottom())


def _inside(item, p):
    """True if scene point p is inside the item's geometry. QGraphicsItem
    contains() counts the outline, and a highlight pen 2 'units' wide would
    swallow everything within 2 um, so test the rect or polygon itself."""
    if isinstance(item, QGraphicsRectItem):
        return item.rect().contains(p)
    if isinstance(item, QGraphicsPolygonItem):
        return item.polygon().containsPoint(p, Qt.OddEvenFill)
    return item.contains(item.mapFromScene(p))


def model(p: QPointF):
    return p.x(), -p.y()


class LayoutCanvas(QGraphicsView):
    mouseMoved = Signal(float, float)        # model x, y
    # Objects the user picked and how: "replace", "toggle" (Ctrl+click) or
    # "add". An empty list with "replace" clears the selection.
    selectRequested = Signal(list, str)
    rulerPlaced = Signal(str, tuple, tuple)  # label, start, end (model coordinates)
    # Tools > Move: wires dragged by (dx, dy); Tools > Stretch: an edge of a wire
    # dragged from one coordinate to another (handle, edge, to, from).
    wiresMoved = Signal(list, float, float)
    wireStretched = Signal(str, str, float, float)

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
        self.show = {"boundary": True, "ports": True, "tracks": False, "cells": True,
                     "pins": True, "labels": False, "spine": True, "routes": True,
                     "rows": False}
        self.rows_hidden = set()             # sites whose rows are not drawn
        self.assign_hidden = set()           # (layer, net) of assigned tracks not drawn
        self.class_hidden = set()            # (layer, signal|power|ground) not drawn
        self.highlighted = {}                # item -> (pen, z) before highlighting
        self.owner_items = {}                # owner handle (port) -> [items]
        self._press = None
        self._band_mode = None               # "zoom" or "select" while a box is drawn
        self._pan_from = None                # last point of a middle-button pan
        self._band = QRectF()                # last rubber band, scene coordinates
        self._rband = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self._rband_from = None              # press point of a right-button box
        self.rubberBandChanged.connect(self._on_band)
        self._blink = None                   # (timer, marker item, steps left)
        # Ruler: mode and options, the first point of a ruler in progress, its
        # preview items, the snap marker, and finished rulers (lists of items).
        self.ruler = {"on": False, "diagonal": False, "snap": True}
        self._ruler_start = None
        self._ruler_preview = []
        self._snap_marker = None
        self.rulers = []
        # Edit tools: mode None (select), "move" or "stretch"; snap to tracks and
        # edges; the drag in progress.
        self.edit = {"mode": None, "snap": True}
        self._edit_drag = None
        self.selected = set()                # handles shown as selected

    # -- content ----------------------------------------------------------------
    def set_layout(self, layout, visible_layers):
        self._edit_drag = None
        self.stop_blink()                     # before clear(), which deletes its marker
        sc = self.scene()
        sc.clear()                            # also deletes rulers and their previews
        self.rulers, self._ruler_preview, self._snap_marker = [], [], None
        self._ruler_start = None
        self.layout, self.boundary_item = layout, None
        self.shape_items, self.owner_items, self.highlighted = {}, {}, {}
        self.inst_items, self.inst_pin_items = [], {}       # outlines; layer -> pin items
        self.spine_items = []
        self.strap_items = {}                # layer -> route_pin strap items
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
            item.setData(LABEL_KEY, s.port.rpartition("/")[2])
            item.setData(CLASS_KEY, s.cls)
            item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.shape_items.setdefault(s.layer, []).append(item)
            self.owner_items.setdefault(s.port, []).append(item)
        self._add_insts(layout, colors)
        self._add_spines(layout)
        self._add_straps(layout, colors)
        self.content = self._content_rect()
        if not self.content.isEmpty():
            pad = PAN_MARGIN * max(self.content.width(), self.content.height())
            sc.setSceneRect(self.content.adjusted(-pad, -pad, pad, pad))
        self.apply_visibility()
        self.fit()

    def _add_insts(self, layout, colors):
        """Instances: a cell outline owned by the inst, and the cell's pin
        shapes, each owned by its instance pin (pin:<inst>/<pin>). Clicking a
        shown pin selects the pin; clicking elsewhere in the cell selects the
        instance. Selecting the instance lights up its pins too."""
        sc = self.scene()
        outline = QPen(QColor(INST_COLOR), 0)
        fill = QBrush(QColor(38, 198, 218, 40))
        for inst in layout.insts:
            x1, y1, x2, y2 = inst.bbox
            box = sc.addRect(QRectF(scene(x1, y2), scene(x2, y1)), outline, fill)
            box.setData(HANDLE_KEY, inst.handle)
            box.setData(OWNER_KEY, inst.handle)
            box.setZValue(1)
            self.inst_items.append(box)
            self.owner_items.setdefault(inst.handle, []).append(box)
            for pin, layer, kind, pts in inst.pins:
                color = QColor(colors.get(layer, "#ffffff"))
                if kind == "rect":
                    a, b, c, d = pts
                    item = sc.addRect(QRectF(scene(a, d), scene(c, b)), QPen(color, 0),
                                      QBrush(color))
                else:
                    item = sc.addPolygon(QPolygonF([scene(px, py) for px, py in
                                                    zip(pts[0::2], pts[1::2])]),
                                         QPen(color, 0), QBrush(color))
                pin_handle = f"pin:{inst.handle.partition(':')[2]}/{pin}"
                item.setData(HANDLE_KEY, pin_handle)
                item.setData(OWNER_KEY, pin_handle)
                item.setData(LABEL_KEY, pin)
                item.setData(CLASS_KEY, inst.pin_classes.get(pin, "signal"))
                item.setZValue(2)
                self.inst_pin_items.setdefault(layer, []).append(item)
                self.owner_items[inst.handle].append(item)
                self.owner_items.setdefault(pin_handle, []).append(item)

    def _add_spines(self, layout):
        """Built spines: thick stub bars and thin net centre lines. Each line
        is owned by its stub (stub:<spine>/<stub>) or net
        (spine_net:<spine>/<net>); a net's segments light up together. The
        cells are instances."""
        sc = self.scene()
        stub_pen = QPen(QColor(SPINE_STUB_COLOR), 3)
        stub_pen.setCosmetic(True)
        net_pen = QPen(QColor(SPINE_NET_COLOR), 1)
        net_pen.setCosmetic(True)
        for sp in layout.spines:
            spine = sp.handle.partition(":")[2]
            lines = [(f"stub:{spine}/{n}", p, stub_pen) for n, p in sp.stubs] + \
                [(f"spine_net:{spine}/{n}", p, net_pen) for n, p in sp.segments]
            for owner, (x1, y1, x2, y2), pen in lines:
                item = sc.addLine(QLineF(scene(x1, y1), scene(x2, y2)), pen)
                item.setData(HANDLE_KEY, owner)
                item.setData(OWNER_KEY, owner)
                item.setZValue(3)
                self.spine_items.append(item)
                self.owner_items.setdefault(owner, []).append(item)

    def _add_straps(self, layout, colors):
        """route_pin straps and pin wires: the layer colour, see-through so the
        cell and its pins show beneath. Straps are labelled with the net, pin
        wires with the pin; pin wires are drawn over the straps."""
        self.add_route_shapes(layout.straps + layout.pin_wires + layout.net_wires, colors)

    def add_route_shapes(self, shapes, colors):
        sc = self.scene()
        for st in shapes:
            color = QColor(colors.get(st.layer, "#ffffff"))
            fill = QColor(color)
            fill.setAlpha(110)
            x1, y1, x2, y2 = st.rect
            rect = QRectF(scene(x1, y2), scene(x2, y1))
            if st.outline:                # route_net crossing box, over the wires
                item = sc.addRect(rect, QPen(QColor("#ffffff"), 0), QBrush(Qt.NoBrush))
            else:
                item = sc.addRect(rect, QPen(color, 0), QBrush(fill))
            item.setData(HANDLE_KEY, st.handle)
            item.setData(OWNER_KEY, st.handle)
            item.setData(LABEL_KEY, st.label or st.net)
            item.setData(CLASS_KEY, st.cls)
            item.setData(LAYER_KEY, st.layer)
            item.setZValue(7 if st.outline else 6 if st.handle.startswith("net_wire:")
                           else 5 if st.label else 4)
            self.strap_items.setdefault(st.layer, []).append(item)
            self.owner_items.setdefault(st.handle, []).append(item)

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
                item.setVisible(on and self._class_shown(layer, item))
        for item in self.inst_items:
            item.setVisible(self.show["cells"])
        for item in self.spine_items:
            item.setVisible(self.show["spine"])
        for layer, items in self.inst_pin_items.items():
            on = self.show["pins"] and layer in self.visible_layers
            for item in items:
                item.setVisible(on and self._class_shown(layer, item))
        for layer, items in self.strap_items.items():
            on = self.show["routes"] and layer in self.visible_layers
            for item in items:
                item.setVisible(on and self._class_shown(layer, item))
        self.viewport().update()

    def _class_shown(self, layer, item):
        return (layer, item.data(CLASS_KEY) or "signal") not in self.class_hidden

    def set_show(self, key, on):
        self.show[key] = on
        self.apply_visibility()                   # also repaints (labels, tracks)

    def set_assigned_net_visible(self, layer, net, on):
        (self.assign_hidden.discard if on else self.assign_hidden.add)((layer, net))
        self.viewport().update()

    def set_class_visible(self, layer, cls, on):
        """Show or hide the signal, power or ground shapes of one layer."""
        (self.class_hidden.discard if on else self.class_hidden.add)((layer, cls))
        self.apply_visibility()

    def set_site_rows_visible(self, site, on):
        (self.rows_hidden.discard if on else self.rows_hidden.add)(site)
        self.viewport().update()

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
        self.selected = set(handles)
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
                    old = item.pen()                  # a 3 px stub stays 3 px
                    pen = QPen(QColor(SELECT_COLOR), max(2, old.widthF() if old.isCosmetic() else 0))
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

    def owners_in(self, scene_rect, touching=False):
        """Selectable objects with a visible shape inside scene_rect, or with
        touching, any part of a visible shape in it. An instance selected
        this way is selected as the instance, not pin by pin."""
        hit = _touches if touching else _enclosed          # outline pen not counted
        owners = []
        for item in self.scene().items(scene_rect, Qt.IntersectsItemBoundingRect):
            owner = item.data(OWNER_KEY)
            if owner and item.isVisible() and owner not in owners and hit(item, scene_rect):
                owners.append(owner)
        insts = {o.partition(":")[2] for o in owners if o.startswith("inst:")}
        return [o for o in owners if not (o.startswith("pin:") and
                                          o.partition(":")[2].partition("/")[0] in insts)]

    # -- tracks: painted behind the shapes, only those on screen ---------------------
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setRenderHint(QPainter.Antialiasing, False)
        pens = {}
        styles = {"solid": Qt.SolidLine, "dot": Qt.DotLine, "dash": Qt.DashLine}
        for color, style, a, b in self.track_segments(rect):
            key = (color, style)
            if key not in pens:
                pens[key] = QPen(QColor(color), 0, styles[style])
            painter.setPen(pens[key])
            painter.drawLine(scene(*a), scene(*b))
        self._draw_rows(painter, rect)

    def _draw_rows(self, painter, rect):
        """DEF rows in view: each row's outline in its site's color, a mark at
        its left end for the orientation (bottom corner N, top corner FS),
        and, zoomed in further, the site boundaries."""
        lay = self.layout
        if not (lay and self.show["rows"] and lay.site_rows):
            return
        x_lo, y_hi = model(rect.topLeft())
        x_hi, y_lo = model(rect.bottomRight())
        ppu = abs(self.transform().m11())
        lines = 0
        for sr in lay.site_rows:
            if sr.site in self.rows_hidden or sr.height * ppu < MIN_ROW_PIXELS:
                continue                          # too dense to tell apart: zoom in
            rows = visible_rows(sr, x_lo, y_lo, x_hi, y_hi)
            if not rows:
                continue
            color = QColor(sr.color)
            painter.setPen(QPen(color, 0))
            painter.setBrush(Qt.NoBrush)
            site_pen = QPen(QColor(color.red(), color.green(), color.blue(), 110), 0, Qt.DotLine)
            h = sr.height
            for y, x, n, step, orient in rows:
                w = n * step if step else (sr.width or h)
                painter.drawRect(QRectF(scene(x, y + h), scene(x + w, y)))
                m = min(h, w) / 3
                if orient in ("FS", "S"):               # flipped in y: mark at the top
                    painter.drawLine(scene(x, y + h - m), scene(x + m, y + h))
                else:
                    painter.drawLine(scene(x, y + m), scene(x + m, y))
                if not step or step * ppu < MIN_SITE_PIXELS or lines > MAX_SITE_LINES:
                    continue
                k1 = max(1, math.ceil((x_lo - x) / step))
                k2 = min(n - 1, math.floor((x_hi - x) / step))
                if k2 - k1 + 1 > MAX_SITE_LINES - lines:
                    continue
                painter.setPen(site_pen)
                for k in range(k1, k2 + 1):
                    painter.drawLine(scene(x + k * step, y), scene(x + k * step, y + h))
                lines += max(0, k2 - k1 + 1)
                painter.setPen(QPen(color, 0))

    # -- pin labels: painted in screen pixels, only for shapes in view -------------
    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        labels = self.label_positions(rect)
        if not labels:
            return
        painter.save()
        painter.resetTransform()                  # draw in viewport pixels: fixed size
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        for name, center in labels:
            p = self.mapFromScene(center)
            w = metrics.horizontalAdvance(name)
            x, y = p.x() - w / 2, p.y() + metrics.ascent() / 2 - 1
            painter.setPen(QColor("#000000"))     # dark halo keeps it readable
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                painter.drawText(QPointF(x + dx, y + dy), name)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QPointF(x, y), name)
        painter.restore()

    def label_positions(self, rect):
        """(pin name, scene center) for each shown pin shape in rect, when
        labels are on; [] when off or when more than MAX_LABELS are in view."""
        if not self.show["labels"]:
            return []
        out = []
        for item in self.scene().items(rect):
            name = item.data(LABEL_KEY)
            if name and item.isVisible():
                out.append((name, item.sceneBoundingRect().center()))
                if len(out) > MAX_LABELS:
                    return []
        return out

    def track_segments(self, rect):
        """(color, style, (x1, y1), (x2, y2)) in model coordinates for every
        track segment drawn inside the scene rect. The one place that decides
        which tracks show; the ruler snaps to exactly these."""
        lay = self.layout
        if not (lay and self.show["tracks"] and lay.tracks):
            return
        x_lo, y_hi = model(rect.topLeft())
        x_hi, y_lo = model(rect.bottomRight())
        view = (x_lo, y_lo, x_hi, y_hi)
        colors = {l.name: l.color for l in lay.layers}
        pixels_per_um = abs(self.transform().m11())
        assigned = {(a.layer, a.direction) for a in lay.assignments}
        for a in lay.assignments:                 # assigned tracks: colored by net
            if a.layer not in self.visible_layers or len(a.positions) < 2:
                continue
            gap = min(b - c for b, c in zip(a.positions[1:], a.positions))
            if gap * pixels_per_um < MIN_TRACK_PIXELS:
                continue                          # too dense to tell apart: zoom in
            vertical = a.direction == "x"
            shown = {n for n in a.colors if (a.layer, n) not in self.assign_hidden}
            lines = visible_assigned_tracks(
                a, *((x_lo, x_hi) if vertical else (y_lo, y_hi)), shown) or []
            for c, net in lines:
                for p, q in self._clipped(vertical, c, view):
                    style = "dot" if net == SIGNAL else "dash" if net == BLANK else "solid"
                    yield a.colors[net], style, p, q
        for t in lay.tracks:                      # tech layers: preferred direction only
            shown = [l for l in drawn_layers(t, lay.preferred) if l in self.visible_layers
                     and (l, t.direction) not in assigned]
            if not shown or t.step * pixels_per_um < MIN_TRACK_PIXELS:
                continue
            vertical = t.direction == "x"
            pos = visible_track_positions(t, x_lo, x_hi) if vertical else \
                visible_track_positions(t, y_lo, y_hi)
            for c in pos or []:                   # none here, or too dense
                for p, q in self._clipped(vertical, c, view):
                    yield colors.get(shown[0], "#888888"), "dot", p, q

    def _clipped(self, vertical, c, view):
        """Pieces of the track line x = c (vertical) or y = c inside the
        boundary and the view, as model point pairs."""
        x_lo, y_lo, x_hi, y_hi = view
        lay = self.layout
        spans = clip_line_to_polygon(lay.boundary, vertical, c) if lay.boundary \
            else [(y_lo, y_hi) if vertical else (x_lo, x_hi)]
        for a, b in spans:
            if vertical:
                a, b = max(a, y_lo), min(b, y_hi)
                if a < b:
                    yield (c, a), (c, b)
            else:
                a, b = max(a, x_lo), min(b, x_hi)
                if a < b:
                    yield (a, c), (b, c)

    # -- ruler ------------------------------------------------------------------------
    def set_ruler_mode(self, on):
        self.ruler["on"] = on
        self.cancel_ruler()
        if self._snap_marker is not None:
            self._snap_marker.setVisible(False)
        if on:
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().unsetCursor()

    def ruler_in_progress(self):
        return self._ruler_start is not None

    def cancel_ruler(self):
        for item in self._ruler_preview:
            self.scene().removeItem(item)
        self._ruler_preview = []
        self._ruler_start = None

    def clear_rulers(self):
        self.cancel_ruler()
        for items in self.rulers:
            for item in items:
                self.scene().removeItem(item)
        self.rulers = []

    def ruler_point(self, scene_point):
        """Model point for a ruler click: snapped to the nearest drawn edge when
        snapping is on, then held orthogonal to the start if asked."""
        p = model(scene_point)
        if self.ruler["snap"]:
            p = self.snap(p) or p
        if self._ruler_start is not None and not self.ruler["diagonal"]:
            p = constrain_orthogonal(self._ruler_start, p)
        return p

    def snap(self, p):
        """Nearest point on an edge of something drawn, within SNAP_PIXELS:
        visible port shapes, the boundary when shown, and the tracks drawn at
        this zoom. Hidden objects are never snapped to."""
        px = abs(self.transform().m11()) or 1.0
        radius = SNAP_PIXELS / px
        box = QRectF(scene(p[0] - radius, p[1] + radius), scene(p[0] + radius, p[1] - radius))
        segments = []
        for item in self.scene().items(box):
            if not item.isVisible() or not item.data(HANDLE_KEY):
                continue
            if isinstance(item, QGraphicsRectItem):
                r = item.rect()
                (x1, y2), (x2, y1) = model(r.topLeft()), model(r.bottomRight())
                segments += polygon_edges([x1, y1, x2, y1, x2, y2, x1, y2])
            elif isinstance(item, QGraphicsPolygonItem):
                pts = [c for q in item.polygon() for c in model(q)]
                segments += polygon_edges(pts)
        if self.boundary_item is not None and self.boundary_item.isVisible():
            segments += polygon_edges(self.layout.boundary)
        segments += [(a, b) for _, _, a, b in self.track_segments(box)]
        return nearest_on_segments(p, segments, radius)

    def _ruler_items(self, a, b, text):
        pen = QPen(QColor(RULER_COLOR), 2)
        pen.setCosmetic(True)
        line = QGraphicsLineItem(scene(*a).x(), scene(*a).y(), scene(*b).x(), scene(*b).y())
        line.setPen(pen)
        items = [line]
        for end in (a, b):                       # fixed-size end markers
            dot = QGraphicsEllipseItem(-3, -3, 6, 6)
            dot.setPen(pen)
            dot.setPos(scene(*end))
            dot.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            items.append(dot)
        label = QGraphicsSimpleTextItem(text)
        label.setBrush(QColor(RULER_COLOR))
        font = QFont()
        font.setPointSize(9)
        label.setFont(font)
        label.setPos(scene((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        # In screen pixels (the label ignores zoom): sit just above the line.
        label.setTransform(QTransform.fromTranslate(4, -label.boundingRect().height() - 3))
        items.append(label)
        for item in items:
            item.setZValue(30)
            self.scene().addItem(item)
        return items

    def _ruler_click(self, scene_point):
        p = self.ruler_point(scene_point)
        if self._ruler_start is None:
            self._ruler_start = p
            return
        start = self._ruler_start
        self.cancel_ruler()
        text = ruler_text(start, p, self.ruler["diagonal"])
        self.rulers.append(self._ruler_items(start, p, text))
        self.rulerPlaced.emit(text, start, p)

    def _ruler_move(self, scene_point):
        p = self.ruler_point(scene_point)
        if self._snap_marker is None:
            pen = QPen(QColor(RULER_COLOR), 1)
            pen.setCosmetic(True)
            self._snap_marker = QGraphicsRectItem(-4, -4, 8, 8)
            self._snap_marker.setPen(pen)
            self._snap_marker.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            self._snap_marker.setZValue(31)
            self.scene().addItem(self._snap_marker)
        snapped = self.ruler["snap"] and self.snap(model(scene_point)) is not None
        self._snap_marker.setPos(scene(*p))
        self._snap_marker.setVisible(snapped)     # shows where a click would land
        if self._ruler_start is not None:
            for item in self._ruler_preview:
                self.scene().removeItem(item)
            self._ruler_preview = self._ruler_items(
                self._ruler_start, p, ruler_text(self._ruler_start, p, self.ruler["diagonal"]))

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

    # -- Tools > Move / Stretch: drag route shapes, then run move_wire / stretch_wire --
    def set_edit_mode(self, mode):
        """None (select), "move" or "stretch"."""
        self.cancel_edit()
        self.edit["mode"] = mode
        if mode == "move":
            self.viewport().setCursor(Qt.OpenHandCursor)
        else:
            self.viewport().unsetCursor()

    def cancel_edit(self):
        """Drop a drag in progress; the shapes go back to where they were."""
        drag, self._edit_drag = self._edit_drag, None
        if drag is None:
            return
        if drag["kind"] == "move":
            for item in drag["items"]:
                item.setPos(0, 0)
        else:
            drag["item"].setRect(drag["scene_rect"])

    def update_rects(self, rects):
        """Redraw route shapes at new rects {handle: (x1, y1, x2, y2)}, after
        move_wire or stretch_wire, without reloading the whole layout."""
        for handle, (x1, y1, x2, y2) in rects.items():
            for item in self.owner_items.get(handle, []):
                if isinstance(item, QGraphicsRectItem):
                    item.setPos(0, 0)
                    item.setRect(QRectF(scene(x1, y2), scene(x2, y1)))
        self.viewport().update()

    def replace_route_shapes(self, prefix, shapes):
        """Remove the route shapes whose handle starts with prefix and draw
        shapes (Strap) instead: an edit's auto vias, without a reload."""
        for layer, items in self.strap_items.items():
            keep = []
            for item in items:
                if (item.data(HANDLE_KEY) or "").startswith(prefix):
                    self.highlighted.pop(item, None)
                    self.owner_items.pop(item.data(HANDLE_KEY), None)
                    self.scene().removeItem(item)
                else:
                    keep.append(item)
            items[:] = keep
        if shapes:
            self.add_route_shapes(shapes, {l.name: l.color for l in self.layout.layers})
        self.apply_visibility()

    def editing(self):
        return self._edit_drag is not None

    @staticmethod
    def _editable(item):
        h = item.data(HANDLE_KEY) or ""
        return h.startswith(EDITABLE) and isinstance(item, QGraphicsRectItem)

    def _rect_of(self, item):
        r = item.rect()
        (x1, y2), (x2, y1) = model(r.topLeft()), model(r.bottomRight())
        return x1, y1, x2, y2

    def edge_at(self, view_point):
        """(item, edge) of the editable shape whose edge is nearest the cursor,
        within EDGE_PIXELS; None if there is none."""
        tol = EDGE_PIXELS / (abs(self.transform().m11()) or 1.0)
        px, py = model(self.mapToScene(view_point))
        r = EDGE_PIXELS
        box = QRect(view_point.x() - r, view_point.y() - r, 2 * r + 1, 2 * r + 1)
        best = None
        for item in self.items(box):
            if not (item.isVisible() and self._editable(item)):
                continue
            x1, y1, x2, y2 = self._rect_of(item)
            inside_y = y1 - tol <= py <= y2 + tol
            inside_x = x1 - tol <= px <= x2 + tol
            for edge, d, ok in (("left", abs(px - x1), inside_y), ("right", abs(px - x2), inside_y),
                                ("bottom", abs(py - y1), inside_x), ("top", abs(py - y2), inside_x)):
                if ok and d <= tol and (best is None or (d, -item.zValue()) < best[0]):
                    best = ((d, -item.zValue()), item, edge)
        return (best[1], best[2]) if best else None

    def _edit_press(self, view_point):
        """Start a Move or Stretch drag at view_point; False when nothing
        editable is there (the click then selects as usual)."""
        p = model(self.mapToScene(view_point))
        if self.edit["mode"] == "stretch":
            hit = self.edge_at(view_point)
            if hit is None:
                return False
            item, edge = hit
            r = self._rect_of(item)
            self._edit_drag = {"kind": "stretch", "item": item, "edge": edge,
                               "handle": item.data(HANDLE_KEY), "rect": r,
                               "scene_rect": item.rect(), "to": r[EDGE_INDEX[edge]],
                               "from": r[EDGE_INDEX[edge]]}
            return True
        item = self._item_at(view_point, accept=self._editable)
        if item is None:
            return False
        handle = item.data(HANDLE_KEY)
        handles = [h for h in self.selected if h.startswith(EDITABLE)] \
            if handle in self.selected else [handle]
        items = [i for h in handles for i in self.owner_items.get(h, [])]
        r = self._rect_of(item)
        horizontal = r[2] - r[0] >= r[3] - r[1]
        layer = item.data(LAYER_KEY) or ""
        self._edit_drag = {"kind": "move", "item": item, "handles": sorted(handles),
                           "items": items, "start": p, "rect": r, "horizontal": horizontal,
                           "tracks": track_coords(self.layout, layer, "y" if horizontal else "x")
                           if "/" not in layer else [], "delta": (0.0, 0.0)}
        self.viewport().setCursor(Qt.ClosedHandCursor)
        return True

    def _grid(self, v):
        g = self.layout.grid or 0.001
        return round(round(v / g) * g, 6)

    def _edit_move(self, view_point):
        drag = self._edit_drag
        x, y = model(self.mapToScene(view_point))
        dx, dy = x - drag["start"][0], y - drag["start"][1]
        if self.edit["snap"]:
            x1, y1, x2, y2 = drag["rect"]
            tracks = drag["tracks"]
            if drag["horizontal"]:           # the centre line onto a track, along on the grid
                c = (y1 + y2) / 2
                dy = (_nearest(tracks, c + dy) - c) if tracks else self._grid(dy)
                dx = self._grid(dx)
            else:
                c = (x1 + x2) / 2
                dx = (_nearest(tracks, c + dx) - c) if tracks else self._grid(dx)
                dy = self._grid(dy)
        drag["delta"] = (round(dx, 6), round(dy, 6))
        for item in drag["items"]:
            item.setPos(dx, -dy)              # scene y is model -y

    def _edit_stretch(self, view_point):
        drag = self._edit_drag
        x, y = model(self.mapToScene(view_point))
        edge = drag["edge"]
        vertical_edge = edge in ("left", "right")
        v = x if vertical_edge else y
        if self.edit["snap"]:
            v = self.snap_coord(vertical_edge, v, (x, y), drag["item"])
        x1, y1, x2, y2 = drag["rect"]
        g = self.layout.grid or 0.001        # never at or past the opposite edge
        v = {"left": min(v, x2 - g), "right": max(v, x1 + g),
             "bottom": min(v, y2 - g), "top": max(v, y1 + g)}[edge]
        drag["to"] = round(v, 6)
        r = [x1, y1, x2, y2]
        r[EDGE_INDEX[edge]] = v
        drag["item"].setRect(QRectF(scene(r[0], r[3]), scene(r[2], r[1])))

    def snap_coord(self, vertical_edge, v, p, skip=None):
        """v (an x for a vertical edge, else a y) moved onto the nearest
        edge of a visible shape or drawn track line within SNAP_PIXELS of the
        cursor p; otherwise onto the manufacturing grid."""
        ppu = abs(self.transform().m11()) or 1.0
        radius = SNAP_PIXELS / ppu
        box = QRectF(scene(p[0] - radius, p[1] + radius), scene(p[0] + radius, p[1] - radius))
        found = []
        for item in self.scene().items(box):
            if item is skip or not item.isVisible() or not item.data(HANDLE_KEY):
                continue
            if isinstance(item, QGraphicsRectItem):
                x1, y1, x2, y2 = self._rect_of(item)
                found += [x1, x2] if vertical_edge else [y1, y2]
        for _, _, a, b in self.track_segments(box):
            if vertical_edge and a[0] == b[0]:
                found.append(a[0])
            elif not vertical_edge and a[1] == b[1]:
                found.append(a[1])
        near = [c for c in found if abs(c - v) <= radius]
        return min(near, key=lambda c: abs(c - v)) if near else self._grid(v)

    def _edit_release(self):
        drag = self._edit_drag
        self.cancel_edit()                   # the command redraws it where it goes
        if self.edit["mode"] == "move":
            self.viewport().setCursor(Qt.OpenHandCursor)
        else:
            self.viewport().unsetCursor()
        if drag["kind"] == "move":
            if drag["delta"] != (0.0, 0.0):
                self.wiresMoved.emit(drag["handles"], *drag["delta"])
                return True
        elif abs(drag["to"] - drag["from"]) > 1e-9:
            self.wireStretched.emit(drag["handle"], drag["edge"], drag["to"], drag["from"])
            return True
        return False

    def mousePressEvent(self, ev):
        self._press = ev.position().toPoint()
        if self.edit["mode"] and ev.button() == Qt.LeftButton and \
                self._edit_press(self._press):
            ev.accept()
            return
        if self.ruler["on"] and ev.button() in (Qt.LeftButton, Qt.RightButton):
            if ev.button() == Qt.LeftButton:      # ruler: click start, click end
                self._ruler_click(self.mapToScene(self._press))
            else:
                self.cancel_ruler()               # right click cancels
            self._press = None
            ev.accept()
            return
        if ev.button() == Qt.RightButton:                     # right drag: select touching
            self._rband_from = self._press
            self._rband.setGeometry(QRect(self._press, QSize()))
            self._rband.show()
            ev.accept()
            return
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
        if self._edit_drag is not None and ev.button() == Qt.LeftButton:
            press, self._press = self._press, None
            dragged = (ev.position().toPoint() - press).manhattanLength() >= 4 \
                if press is not None else True
            drag = self._edit_drag
            if dragged and self._edit_release():
                ev.accept()
                return
            self.cancel_edit()               # a click on a wire: select it
            owner = drag["item"].data(OWNER_KEY)
            self.selectRequested.emit([owner], "toggle" if ev.modifiers() & Qt.ControlModifier
                                      else "replace")
            ev.accept()
            return
        if ev.button() == Qt.MiddleButton and self._pan_from is not None:
            self._pan_from = None
            self.viewport().unsetCursor()
            ev.accept()
            return
        if self.ruler["on"] and ev.button() in (Qt.LeftButton, Qt.RightButton):
            ev.accept()
            return
        if ev.button() == Qt.RightButton and self._rband_from is not None:
            start, self._rband_from, self._press = self._rband_from, None, None
            self._rband.hide()
            end = ev.position().toPoint()
            if (end - start).manhattanLength() >= 4:      # a right click alone does nothing
                box = QRectF(self.mapToScene(start), self.mapToScene(end)).normalized()
                self.selectRequested.emit(self.owners_in(box, touching=True),
                                          "add" if ev.modifiers() & Qt.ControlModifier
                                          else "replace")
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

    def _item_at(self, view_point, accept=None):
        """Visible shape item nearest a viewport point. Pins are often smaller
        than a pixel, so shapes within PICK_PIXELS count. accept: only items
        it passes."""
        r = PICK_PIXELS
        box = QRect(view_point.x() - r, view_point.y() - r, 2 * r + 1, 2 * r + 1)
        p = self.mapToScene(view_point)
        best, best_d = None, None
        tol = r / (abs(self.transform().m11()) or 1.0)
        for item in self.items(box):
            if not item.data(HANDLE_KEY) or not item.isVisible():
                continue
            if accept is not None and not accept(item):
                continue
            if isinstance(item, QGraphicsLineItem):       # a net: within r pixels is on it
                line = item.line()
                if nearest_on_segments(model(p), [(model(line.p1()), model(line.p2()))],
                                       tol) is None:
                    continue
                d = 0.0
            elif _inside(item, p):
                d = 0.0                               # inside the actual shape
            else:
                b = item.sceneBoundingRect()
                dx = max(b.left() - p.x(), 0, p.x() - b.right())
                dy = max(b.top() - p.y(), 0, p.y() - b.bottom())
                # inside an L-shaped polygon's bbox but not the polygon: a near
                # miss, so a shape really under the cursor wins
                d = max(dx * dx + dy * dy, 1e-12)
            # Ties: shapes really under the cursor -> the one drawn on top (a
            # pin over its cell); near misses (e.g. a whole cell under one
            # pixel) -> the larger shape, so a zoomed-out click picks the cell.
            b = item.sceneBoundingRect()
            area = b.width() * b.height()
            key = (0.0, -item.zValue(), area) if d == 0 else (d, 0, -area)
            if best_d is None or key < best_d:
                best, best_d = item, key
        return best

    def mouseMoveEvent(self, ev):
        point = ev.position().toPoint()
        if self._pan_from is not None:
            self.pan_by(point.x() - self._pan_from.x(), point.y() - self._pan_from.y())
            self._pan_from = point
        elif self._rband_from is not None:
            self._rband.setGeometry(QRect(self._rband_from, point).normalized())
        elif self._edit_drag is not None:
            if self._edit_drag["kind"] == "move":
                self._edit_move(point)
            else:
                self._edit_stretch(point)
        elif self.edit["mode"] == "stretch":       # the cursor shows the edge it would take
            hit = self.edge_at(point)
            if hit is None:
                self.viewport().unsetCursor()
            else:
                self.viewport().setCursor(Qt.SizeHorCursor if hit[1] in ("left", "right")
                                          else Qt.SizeVerCursor)
        elif self.ruler["on"]:
            self._ruler_move(self.mapToScene(point))
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
        if ev.key() == Qt.Key_Escape and self._edit_drag is not None:
            self.cancel_edit()                    # Esc drops the drag in progress
            ev.accept()
            return
        step_x, step_y = self.viewport().width() // 4, self.viewport().height() // 4
        moves = {Qt.Key_Left: (step_x, 0), Qt.Key_Right: (-step_x, 0),
                 Qt.Key_Up: (0, step_y), Qt.Key_Down: (0, -step_y)}
        if ev.key() in moves:                     # the arrow shows where to look
            # (F is the window's Fit action, so a user shortcut can replace it)
            self.pan_by(*moves[ev.key()])
        else:
            super().keyPressEvent(ev)


EDGE_INDEX = {"left": 0, "bottom": 1, "right": 2, "top": 3}


def _nearest(values, v):
    """The value in sorted values nearest v."""
    i = bisect.bisect_left(values, v)
    return min(values[max(0, i - 1):i + 1], key=lambda c: abs(c - v))
