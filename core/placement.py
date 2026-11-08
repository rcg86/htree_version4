"""Placement geometry: where a cell's shapes land for a location and orientation.

A placed cell's location is the lower-left corner of its placed (rotated or
flipped) bounding box, as in DEF. Cell coordinates are LEF macro coordinates
(origin at the cell's lower-left, ORIGIN 0 0).
"""

from core.def_parser import ORIENTS

ORIENT_NAMES = list(ORIENTS)          # N W S E FN FW FS FE


def placer(size_x, size_y, orient, x, y):
    """A function mapping cell coordinates to placed coordinates."""
    t = ORIENTS[orient]
    corners = [t(cx, cy) for cx, cy in ((0, 0), (size_x, 0), (0, size_y), (size_x, size_y))]
    min_x = min(c[0] for c in corners)
    min_y = min(c[1] for c in corners)

    def place(cx, cy):
        px, py = t(cx, cy)
        return round(px - min_x + x, 6), round(py - min_y + y, 6)
    return place


def placed_bbox(size_x, size_y, orient, x, y):
    place = placer(size_x, size_y, orient, x, y)
    pts = [place(cx, cy) for cx, cy in ((0, 0), (size_x, size_y))]
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def placed_points(points, place):
    """Cell-coordinate points [x y x y ...] placed; rects stay lower-left first."""
    pts = [place(px, py) for px, py in zip(points[0::2], points[1::2])]
    if len(pts) == 2:                          # a rect: keep it normalized
        (x1, y1), (x2, y2) = pts
        pts = [(min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))]
    return [c for p in pts for c in p]


def point_in_polygon(x, y, polygon):
    """True if (x, y) is inside or on the boundary of a simple polygon."""
    pts = list(zip(polygon[0::2], polygon[1::2]))
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2) and \
                (x2 - x1) * (y - y1) == (y2 - y1) * (x - x1):
            return True                         # on an edge
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def rect_in_polygon(rect, polygon):
    """True if the rect lies inside the polygon: all corners inside and no
    polygon vertex strictly inside the rect (enough for rectilinear shapes)."""
    x1, y1, x2, y2 = rect
    if not all(point_in_polygon(x, y, polygon) for x, y in
               ((x1, y1), (x2, y1), (x2, y2), (x1, y2))):
        return False
    return not any(x1 < vx < x2 and y1 < vy < y2
                   for vx, vy in zip(polygon[0::2], polygon[1::2]))


def rects_overlap(a, b):
    """True if two rects share area (touching edges do not count)."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
