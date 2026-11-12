"""Schematic tab: a rough picture of a spine from create_spine -validate -show.

Columns (levels, then the stubs) are spread far apart so the tree reads
easily; the spine axis is to scale. Inverters are dots, nets are their
centre lines, stubs are thick bars with a dot at the tap. Nets over the
limit, and the nets of a level out of balance, are red; a cell that drives
nothing is a hollow dot. A horizontal spine is drawn lying down.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

COL_GAP = 160.0            # scene units between columns
SPINE_LEN = 1000.0         # scene units the whole span is scaled to
DOT = 9                    # px
OK_COLOR = "#7bd88f"
BAD_COLOR = "#ff5c5c"
CELL_COLOR = "#26c6da"
ROOT_COLOR = "#ffd54f"
STUB_COLOR = "#b388ff"
TEXT_COLOR = "#d0d0d0"
GRID_COLOR = "#2c333a"


class SchematicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#101418"))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.plan = None

    # -- drawing --------------------------------------------------------------------
    def set_plan(self, p):
        self.plan = p
        sc = self.scene()
        sc.clear()
        k = SPINE_LEN / p.span
        vertical = p.orientation == "vertical"

        def at(col, s):
            # columns step to the build side; the spine axis runs up / right
            c = col * COL_GAP * p.direction
            return QPointF(c, -s * k) if vertical else QPointF(s * k, -c)

        by_name = {n.name: n for n in p.nets}
        bad_groups = set()
        for label, names in p.groups:
            lengths = [by_name[n].length for n in names]
            if max(lengths) - min(lengths) > p.deviation + 1e-3:
                bad_groups.add(label)

        # column guides and labels, spine ticks every 1000 um
        names = p.levels + ["stubs"]
        for col, label in enumerate(names):
            a, b = at(col, 0), at(col, p.span)
            sc.addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor(GRID_COLOR), 0, Qt.DashLine))
            self._text(label, b + (QPointF(0, -28) if vertical else QPointF(12, 0)), bold=True)
        tick = 0.0
        while tick <= p.span + 1e-6:
            a = at(-0.6, tick)
            real = (p.y0 if vertical else p.x0) + p.sign * (p.origin + tick)
            self._text(f"{real:.0f}", a, color="#8a939b", anchor="right" if vertical else "top")
            tick += 1000.0

        # stubs
        for stub in p.stubs:
            a, b = at(p.stub_col, stub.lo), at(p.stub_col, stub.hi)
            pen = QPen(QColor(STUB_COLOR), 5)
            pen.setCosmetic(True)
            sc.addLine(a.x(), a.y(), b.x(), b.y(), pen)
            self._dot(at(p.stub_col, stub.tap), STUB_COLOR)
            self._text(f"{stub.name}  {stub.lo:.1f}..{stub.hi:.1f}",
                       at(p.stub_col, stub.tap) + QPointF(14, 0))

        # nets
        for n in p.nets:
            bad = n.length > p.limit + 1e-3 or n.group in bad_groups
            pen = QPen(QColor(BAD_COLOR if bad else OK_COLOR), 2)
            pen.setCosmetic(True)
            for c1, s1, c2, s2 in n.segments:
                a, b = at(c1, s1), at(c2, s2)
                sc.addLine(a.x(), a.y(), b.x(), b.y(), pen)
            d = p.cells[n.driver]
            text = f"{n.length:.1f}" + (f" (+{n.detour:.1f} detour)" if n.detour else "")
            self._text(text, at(d.col, d.s) + QPointF(8, 14),
                       color=BAD_COLOR if bad else "#9fdcaa")

        # cells on top
        for c in p.cells.values():
            color = ROOT_COLOR if c.driver is None else CELL_COLOR
            self._dot(at(c.col, c.s), color, hollow=c.dummy)
            short = c.inst[len(p.name) + 1:] if c.inst.startswith(p.name + "_") else c.inst
            self._text(short, at(c.col, c.s) + QPointF(8, -4))

        warn = f"{len(p.warnings)} warning(s)" if p.warnings else "no warnings"
        top = sc.itemsBoundingRect()
        self._text(f"{p.name} (spec {p.spec}): {warn} (see the terminal). Not built.",
                   QPointF(top.left(), top.top() - 30), bold=True)
        rect = sc.itemsBoundingRect()
        sc.setSceneRect(rect.adjusted(-200, -200, 200, 200))
        self.fit()

    def _dot(self, point, color, hollow=False):
        item = self.scene().addEllipse(QRectF(-DOT / 2, -DOT / 2, DOT, DOT),
                                       QPen(QColor(color), 2),
                                       Qt.NoBrush if hollow else QBrush(QColor(color)))
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        item.setPos(point)
        item.setZValue(3)
        return item

    def _text(self, text, point, color=TEXT_COLOR, bold=False, anchor="left"):
        item = self.scene().addSimpleText(text)
        font = QFont()
        font.setPointSize(8)
        font.setBold(bold)
        item.setFont(font)
        item.setBrush(QColor(color))
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        item.setPos(point)
        w = item.boundingRect().width()
        if anchor == "right":
            item.setPos(point - QPointF(w + 6, 6))
        elif anchor == "top":
            item.setPos(point - QPointF(w / 2, 0))
        item.setZValue(4)
        return item

    # -- view -----------------------------------------------------------------------
    def fit(self):
        rect = self.scene().itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.IgnoreAspectRatio)

    def wheelEvent(self, ev):
        factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_F:
            self.fit()
            return
        super().keyPressEvent(ev)
