"""add_buffer_on_net on a routed net (of no spine): buffers along its routed
wires, the wires cut at each buffer and the pieces put on the nets the
buffers drive.

The route is a graph of the net's signal wires (kind wire), joined where a
crossing box lies on two of them and where two wires of one layer overlap on
one track. It is followed from the driver (the route end nearest the input
port or the output pin): the points first, first + distance, ... um along it
that lie before the last load of their branch get a buffer.

Each buffer is centred under its point, oriented so that its input pin is on
the driver's side of its output pin along the wire, put on a site
(legalize_placement) and given its pin routes (route_pin). The wire is cut
there: a gap over the cell (and its straps' reach, across a wire on the
straps' layer) and the rule spacing each side. Each piece goes on the net of
the nearest buffer before it (<buffer>_<output pin>), or stays on the net when
there is none. route_net then routes every net touched, all pieces held as
they are (fixed wires): it only joins them to the pins of the buffers and
loads, and makes the crossing boxes, extensions and (when the net had them)
shields and power links again. A piece cut from a fixed wire stays fixed; the
others are freed again.
"""

import heapq
import math
from types import SimpleNamespace

from core import objects
from core.db import _num, base_rect
from core.messages import HtreeError, info, warn

TOL = 1e-6
KEY = 4                      # decimals of a node's coordinates


def _rect(r):
    return tuple(float(c) for c in r["rect"].split())


def _key(x, y):
    return round(x, KEY), round(y, KEY)


class Line:
    """The centre line of a signal wire: horizontal (along x) or vertical."""

    def __init__(self, row, horizontal, c, lo, hi):
        self.row, self.horizontal, self.c = row, horizontal, c
        self.lo, self.hi = min(lo, hi), max(lo, hi)
        self.points = {self.lo, self.hi}
        self.spans = []                      # (lo, hi, label) along it, from the tree

    def at(self, p):
        return _key(p, self.c) if self.horizontal else _key(self.c, p)

    def holds(self, x, y):
        along, across = (x, y) if self.horizontal else (y, x)
        return abs(across - self.c) < TOL and self.lo - TOL <= along <= self.hi + TOL


def graph(db, net, h, v):
    """(lines, {node: [(node, length, line)]}) of the net's signal wires on
    the rule's two layers h and v."""
    rows = db.net_wire_rows(net)
    lines = []
    for r in rows:
        if r["kind"] != "wire" or r["layer"] not in (h.name, v.name):
            continue
        x1, y1, x2, y2 = _rect(r)
        if r["layer"] == h.name:
            lo, hi = x1 + v.width / 2, x2 - v.width / 2
            lines.append(Line(r, True, (y1 + y2) / 2, *((lo, hi) if lo <= hi else ((x1 + x2) / 2,) * 2)))
        else:
            lo, hi = y1 + h.width / 2, y2 - h.width / 2
            lines.append(Line(r, False, (x1 + x2) / 2, *((lo, hi) if lo <= hi else ((y1 + y2) / 2,) * 2)))
    boxes = [_rect(r) for r in rows if r["kind"] == "cross" and not r["shield_net"]]
    joins = []                               # (node on a line, the box's node): one point
    for x1, y1, x2, y2 in boxes:             # a layer change: joins the wires it touches
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        for line in lines:
            r = _rect(line.row)
            if r[0] > x2 + TOL or r[2] < x1 - TOL or r[1] > y2 + TOL or r[3] < y1 - TOL:
                continue
            p = min(max(cx if line.horizontal else cy, line.lo), line.hi)
            line.points.add(p)
            joins.append((line.at(p), _key(cx, cy)))
    for line in lines:
        for other in lines:                  # a wire of its layer overlapping it
            if other is not line and other.horizontal == line.horizontal and \
                    abs(other.c - line.c) < TOL and other.row["layer"] == line.row["layer"]:
                line.points.update(p for p in (other.lo, other.hi)
                                   if line.lo - TOL <= p <= line.hi + TOL)
    adj = {}
    for line in lines:
        pts = sorted(line.points)
        for a, b in zip(pts, pts[1:]):
            ka, kb = line.at(a), line.at(b)
            adj.setdefault(ka, []).append((kb, b - a, line))
            adj.setdefault(kb, []).append((ka, b - a, line))
        for p in pts:
            adj.setdefault(line.at(p), [])
    for a, b in joins:                       # no length: the via
        if a != b:
            adj.setdefault(a, []).append((b, 0.0, None))
            adj.setdefault(b, []).append((a, 0.0, None))
        else:
            adj.setdefault(a, [])
    return lines, adj


def nearest(adj, point):
    return min(adj, key=lambda k: abs(k[0] - point[0]) + abs(k[1] - point[1]))


def tree(adj, start):
    """{node: distance}, {node: (parent, line)} from start along the route."""
    dist, parent, todo = {start: 0.0}, {}, [(0.0, start)]
    while todo:
        d, k = heapq.heappop(todo)
        if d > dist[k] + TOL:
            continue
        for k2, length, line in adj[k]:
            if d + length < dist.get(k2, math.inf) - TOL:
                dist[k2], parent[k2] = d + length, (k, line)
                heapq.heappush(todo, (d + length, k2))
    return dist, parent


def plan(db, net, plain, cell, pin_in, pin_out, grid, first, step, out, count=None,
         spread=False):
    """The buffers of a routed net of no spine: SimpleNamespaces with name
    (set later), point, dist, line, upstream (unit vector toward the driver),
    up / down (label: None for the net, else the buffer before), loads.
    count: at most that many in a row from the driver (plan.capped: the
    points left without one); spread: count of them every L / (count + 1) um,
    L the way along the route to the farthest load."""
    plan.capped, plan.ways, plan.start = 0, {}, None
    lines, adj = graph(db, net, grid.h, grid.v)
    if not adj:
        raise HtreeError(260, f"add_buffer_on_net: net {net} has no signal wires on "
                         f"{grid.h.name} and {grid.v.name} to follow")
    start = nearest(adj, plain.root)
    dist, parent = tree(adj, start)
    loads = {key: nearest(adj, p) for key, p in plain.pins.items()}
    apart = [k for k, node in loads.items() if node not in dist]
    if apart:
        warn(260, f"add_buffer_on_net: net {net}: the route does not reach {' '.join(apart)} "
             f"from the driver; no buffer behind them", out)
    far = {}                                 # node -> farthest load at or behind it
    for key, node in loads.items():
        k = node
        while k in dist:
            far[k] = max(far.get(k, -1.0), dist[node])
            if k not in parent:
                break
            k = parent[k][0]
    plan.ways = {key: dist.get(node) for key, node in loads.items()}   # um along the route
    plan.start = start
    if spread:
        first = step = max([dist[node] for node in loads.values() if node in dist] + [0.0]) \
            / (count + 1) or 1e18
    bufs = []
    label = {start: None}
    for k in sorted(dist, key=dist.get):     # parents first
        if k == start:
            continue
        p, line = parent[k]
        if line is None:                     # through a via: no length
            label[k] = label[p]
            continue
        a, b = dist[p], dist[k]
        pa = p[0] if line.horizontal else p[1]
        pb = k[0] if line.horizontal else k[1]
        sign = 1.0 if pb >= pa else -1.0
        cur, lo = label[p], pa
        n = 0 if a < first - TOL else math.floor((a - first) / step + TOL) + 1
        while True:                          # the points after a, up to b
            d = first + n * step
            if d > b + TOL or d >= far.get(k, -1.0) - TOL:
                break
            if d > a + TOL and count is not None and (cur.depth if cur else 0) >= count:
                plan.capped += 1             # max buffer count reached: no more in this row
            elif d > a + TOL:
                at = pa + sign * (d - a)
                x, y = (at, line.c) if line.horizontal else (line.c, at)
                buf = SimpleNamespace(name=None, net=None, point=(x, y), dist=d, line=line,
                                      upstream=(-sign, 0.0) if line.horizontal else (0.0, -sign),
                                      up=cur, loads=[], index=len(bufs), at=at, sign=sign,
                                      edge=(min(pa, pb), max(pa, pb)), slid=0.0,
                                      depth=(cur.depth if cur else 0) + 1)
                bufs.append(buf)
                line.spans.append((min(lo, at), max(lo, at), cur))
                cur, lo = buf, at
            n += 1
        line.spans.append((min(lo, pb), max(lo, pb), cur))
        label[k] = cur
    for line in lines:                       # wires off the tree: the label of an end
        if not line.spans:
            k = line.at(line.lo)
            line.spans.append((line.lo, line.hi, label.get(k, label.get(line.at(line.hi)))))
    for key, node in loads.items():
        if node in label and label[node] is not None:
            label[node].loads.append(key)
    top_loads = [key for key, node in loads.items() if label.get(node) is None]
    return lines, adj, bufs, top_loads


def free_spot(buf, box_at, taken, step):
    """Slide the buffer along its wire (within its edge, at most step / 2) to
    the nearest place where its cell overlaps none of taken [(x1, y1, x2,
    y2)]; box_at(x, y): its cell's box centred there. True when it found one
    (buf.point, buf.dist and buf.slid are then set)."""
    line = buf.line
    x1, y1, x2, y2 = box_at(*buf.point)
    q = (x2 - x1) if line.horizontal else (y2 - y1)
    k = 0
    while k * q <= step / 2 + TOL:
        for off in ((0.0,) if k == 0 else (k * q, -k * q)):
            at = buf.at + buf.sign * off
            if not buf.edge[0] - TOL <= at <= buf.edge[1] + TOL:
                continue
            point = (at, line.c) if line.horizontal else (line.c, at)
            box = box_at(*point)
            if not any(box[0] < r[2] - TOL and r[0] < box[2] - TOL and box[1] < r[3] - TOL
                       and r[1] < box[3] - TOL for r in taken):
                if off:                      # the nets now part where it is
                    line.spans = [(at if abs(lo - buf.at) < TOL else lo,
                                   at if abs(hi - buf.at) < TOL else hi, lab)
                                  for lo, hi, lab in line.spans]
                buf.point, buf.dist, buf.slid, buf.at = point, buf.dist + off, off, at
                return True
        k += 1
    return False


def drop(buf, bufs, lines, top_loads):
    """Take a buffer out of the plan: what it was to drive stays on the net
    before it."""
    for other in bufs:
        if other.up is buf:
            other.up = buf.up
    for line in lines:
        line.spans = [(lo, hi, buf.up if lab is buf else lab) for lo, hi, lab in line.spans]
    (top_loads if buf.up is None else buf.up.loads).extend(buf.loads)
    bufs.remove(buf)


def footprint(db, row):
    """The box of an instance with its pin routes: its cell, its straps as
    far as they may be extended, and its pin wires; None without a SIZE."""
    box = objects.inst_bbox(db, row)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    for s in db.strap_rows(row["name"]):
        r, reach = base_rect(s), s["max_extension"] or 0.0
        x1, y1, x2, y2 = min(x1, r[0] - reach), min(y1, r[1]), max(x2, r[2] + reach), max(y2, r[3])
    for w in db.pin_wire_rows(row["name"]):
        r = _rect(w)
        x1, y1, x2, y2 = min(x1, r[0]), min(y1, r[1]), max(x2, r[2]), max(y2, r[3])
    return x1, y1, x2, y2


def margins(db, ref):
    """How far the pin routes of a cell of ref reach past its box (left,
    bottom, right, top), from an instance of it route_pin was run on; zero
    when there is none."""
    for row in db.inst_rows():
        if row["ref_cell"] == ref and db.strap_rows(row["name"]):
            box, foot = objects.inst_bbox(db, row), footprint(db, row)
            return (box[0] - foot[0], box[1] - foot[1], foot[2] - box[2], foot[3] - box[3])
    return 0.0, 0.0, 0.0, 0.0


def orient_for(db, cell, pin_in, pin_out, upstream, offset):
    """N or FS: the one with the input pin on the driver's side of the output
    pin (along the wire); N when it makes no difference."""
    for orient in ("N", "FS"):
        ai, ao = offset(db, cell, pin_in, orient), offset(db, cell, pin_out, orient)
        if (ai[0] - ao[0]) * upstream[0] + (ai[1] - ao[1]) * upstream[1] > TOL:
            return orient
    return "N"


def gap(db, buf, grid):
    """(lo, hi) along the buffer's wire to cut away: the cell, and on the
    straps' layer their reach, with the rule spacing each side."""
    box = objects.inst_bbox(db, db.inst_row(buf.name))
    line = buf.line
    lay = grid.h if line.horizontal else grid.v
    lo, hi = (box[0], box[2]) if line.horizontal else (box[1], box[3])
    straps = db.strap_rows(buf.name)
    if line.horizontal and straps and straps[0]["layer"] == line.row["layer"]:
        reach = max((r["max_extension"] or 0.0) for r in straps)
        lo, hi = lo - reach, hi + reach
    return lo - lay.spacing - lay.width / 2, hi + lay.spacing + lay.width / 2


def pieces(line, gaps):
    """[(lo, hi, label)] of the wire of line along its axis (its rect, the
    ends past the centre line included) once the gaps are cut away."""
    x1, y1, x2, y2 = _rect(line.row)
    a1, a2 = (x1, x2) if line.horizontal else (y1, y2)
    parts = [(a1, a2)]
    for g1, g2 in sorted(gaps):
        nxt = []
        for p1, p2 in parts:
            if g2 <= p1 + TOL or g1 >= p2 - TOL:
                nxt.append((p1, p2))
                continue
            if g1 > p1 + TOL:
                nxt.append((p1, g1))
            if g2 < p2 - TOL:
                nxt.append((g2, p2))
        parts = nxt
    found = []
    for p1, p2 in parts:
        mid = min(max((p1 + p2) / 2, line.lo), line.hi)
        lab = next((s[2] for s in line.spans if s[0] - TOL <= mid <= s[1] + TOL),
                   line.spans[0][2] if line.spans else None)
        found.append((p1, p2, lab))
    return found


def piece_rect(line, p1, p2):
    x1, y1, x2, y2 = _rect(line.row)
    return (p1, y1, p2, y2) if line.horizontal else (x1, p1, x2, p2)


def text(r):
    return " ".join(_num(round(c, 6)) for c in r)


def junctions_in(adj, line, lo, hi):
    """Nodes of the route other than plain wire points inside (lo, hi) on
    line: where the route turns or branches. A cut there would split them."""
    found = []
    for p in line.points:
        if lo + TOL < p < hi - TOL:
            k = line.at(p)
            if len(adj.get(k, [])) != 2 or any(l is not line for _, _, l in adj.get(k, [])):
                found.append(k)
    return found
