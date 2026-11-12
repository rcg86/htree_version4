"""Snake moves of a built spine, for move_spine_to_boundary. No Tcl, no Qt.

The spine is a body of fixed length lying on a path: the line of its stubs,
from its bottom (left) end to its top (right) end, the mirror included. Every
cell, stub and net centre line keeps where create_spine put it on the
straight spine (um along the stub line and across it), so bending the path
moves everything while the stub lengths and gaps, the spacing of the cells
and the drive lengths stay. Across the path, the columns keep their side as
seen along it: a cell right of the stubs on the way up is below them on a
stretch running right.

A move pulls one end, the head, in a direction, and the body follows along
the path the head has drawn, like the snake of the game:
    ahead (the way the head points)   the path grows straight on
    to a side                         the path turns a corner at the head
    back (into the body)              the spine backs up along its own path, as
                                      far as its next corner; its other end
                                      goes back out the way it came (straight
                                      on where that is not known any more)

The head lands on a signal track of the layer whose tracks it crosses
(assign_track_for_route: the '-' tracks; without tracks, the manufacturing
grid), so every corner of the path is on signal tracks. Hard stops, for the
head only: each side of the design boundary keeps its clearance (the side
ahead, and the two beside the move where they are kept now), and a move
that would lay the body over itself is refused. What ends up outside the
boundary behind the head is reported by outside(), not stopped.
"""

import bisect
import math
from dataclasses import dataclass
from typing import List, Tuple

from core.placement import point_in_polygon

TOL = 1e-6
DIRS = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
NAMES = {v: k for k, v in DIRS.items()}
ENDS = {"vertical": ("bottom", "top"), "horizontal": ("left", "right")}
SIDES = ("left", "right", "top", "bottom")          # the order of -clearance
SIDE_OF = {"left": "left", "right": "right", "up": "top", "down": "bottom"}


class SnakeError(Exception):
    pass


@dataclass
class Step:
    """What one move did."""
    direction: str
    asked: float
    moved: float
    head: Tuple[float, float]        # where the head is now
    note: str = ""                   # why it moved less than asked, or not at all


class Line:
    """A polyline of axis-parallel segments with its arc lengths."""

    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        self.dirs = []
        for a, b in zip(pts, pts[1:]):
            d = abs(b[0] - a[0]) + abs(b[1] - a[1])
            self.cum.append(self.cum[-1] + d)
            self.dirs.append((_sign(b[0] - a[0]), _sign(b[1] - a[1])))
        self.total = self.cum[-1]

    def seg(self, u, before=False):
        """The segment holding arc u; the end segments run on beyond the ends.
        At a corner: the segment after it, or with before the one that ends
        there."""
        k = bisect.bisect_left(self.cum, u - TOL) if before else \
            bisect.bisect_right(self.cum, u + TOL)
        return min(max(k - 1, 0), len(self.dirs) - 1)

    def at(self, u, before=False):
        """(point, direction) at arc u."""
        k = self.seg(u, before)
        t = self.dirs[k]
        d = u - self.cum[k]
        return (self.pts[k][0] + d * t[0], self.pts[k][1] + d * t[1]), t

    def corners(self, u1, u2):
        """Indices of the points strictly between arcs u1 and u2."""
        return [k for k in range(1, len(self.pts) - 1) if u1 + TOL < self.cum[k] < u2 - TOL]

    def part(self, u1, u2):
        """The points from arc u1 to arc u2."""
        return _clean([self.at(u1)[0]] + [self.pts[k] for k in self.corners(u1, u2)]
                      + [self.at(u2)[0]])


def _sign(v):
    return 0 if abs(v) < TOL else (1 if v > 0 else -1)


def _clean(pts):
    """Rounded, without repeated points or points inside a straight run."""
    out = []
    for p in pts:
        p = (round(p[0], 6), round(p[1], 6))
        if out and abs(out[-1][0] - p[0]) < TOL and abs(out[-1][1] - p[1]) < TOL:
            continue
        if len(out) >= 2 and _unit(out[-2], out[-1]) == _unit(out[-1], p):
            out[-1] = p
        else:
            out.append(p)
    return out


def _unit(a, b):
    return _sign(b[0] - a[0]), _sign(b[1] - a[1])


def _num(v):
    text = repr(round(float(v), 6))
    return text[:-2] if text.endswith(".0") else text


class Snake:
    """A built spine and the path it lies on. Moves change only this object;
    commit() writes the result to the database."""

    def __init__(self, db, name, clearance=(0.0, 0.0, 0.0, 0.0), limits=True):
        """limits False: only where things are (no boundary, no tracks)."""
        spine = db.spine_row(name)
        if spine is None:
            raise SnakeError(f"no built spine '{name}' (create_spine -build; get_db spines)")
        self.name = name
        self.vertical = (spine["orientation"] or "").lower() != "horizontal"
        self.ends = ENDS["vertical" if self.vertical else "horizontal"]
        self.clearance = dict(zip(SIDES, clearance))
        self.members = [(m["inst"], m["along"], m["across"])
                        for m in db.spine_members(spine["id"])]
        self.stubs = []                  # (row id, name, along lo, along hi)
        for r in db.spine_stub_rows(spine["id"]):
            lo, hi, across = (float(v) for v in (r["ref"] or "").split() or (0, 0, 0))
            self.stubs.append((r["id"], r["name"], lo, hi))
            self.across = across         # the stub line: every stub has the same
        self.nets = [(r["id"], r["name"], [tuple(float(v) for v in seg.split())
                                           for seg in (r["ref_route"] or "").split(";") if seg])
                     for r in db.spine_net_rows(spine["id"])]
        if not self.stubs or any(a is None for _, a, _ in self.members):
            raise SnakeError(f"spine {name} has no straight-spine coordinates; build it again "
                             f"(create_spine -build)")
        self.lo = min(s[2] for s in self.stubs)      # the body: the stub line, end to end
        self.hi = max(s[3] for s in self.stubs)
        self.length = self.hi - self.lo
        if spine["path"]:
            v = [float(c) for c in spine["path"].split()]
            self.pts = _clean(list(zip(v[0::2], v[1::2])))
        elif self.vertical:
            x = spine["x"] + self.across
            self.pts = _clean([(x, spine["y"] + self.lo), (x, spine["y"] + self.hi)])
        else:
            y = spine["y"] + self.across
            self.pts = _clean([(spine["x"] + self.lo, y), (spine["x"] + self.hi, y)])
        self.start = 0.0                 # arc of the body's bottom / left end on pts
        self.head = "lo"                 # the end that moves: lo (bottom / left) or hi
        self.moves = []                  # ("head", end name) | (direction, distance)
        self._backed = None              # the last move backed up (None: no move yet)
        self._undo = []

        cell = db.lib_cell_row(spine["ref_cell"]) if spine["ref_cell"] else None
        self.cell = (cell["size_x"], cell["size_y"]) if cell is not None and \
            cell["size_x"] is not None else (0.0, 0.0)
        half = max(self.cell) / 2
        offsets = [c - self.across for _, _, c in self.members]
        self.width = (min(0.0, min(offsets) - half), max(0.0, max(offsets) + half))

        self.grid = (db.tech_row()["manufacturing_grid"] if db.has_tech() else None) or 0.001
        self.boundary = []
        self.edges = []
        self.tracks, self.track_layers, self.periods = {}, {}, {}
        if not limits:
            return
        if db.has_design() and db.design_row()["boundary"]:
            self.boundary = [float(v) for v in db.design_row()["boundary"].split()]
        pts = list(zip(self.boundary[0::2], self.boundary[1::2]))
        self.edges = [a + b for a, b in zip(pts, pts[1:] + pts[:1])]
        for layer in db.track_assignment_layers():
            row = db.track_assignment_row(layer)
            axis = row["direction"]
            raw = db.track_positions(layer, axis)
            pattern = row["pattern"].split()
            signal = [p for k, p in enumerate(raw) if pattern[k % len(pattern)] == "-"]
            if axis in self.tracks or not signal:
                continue                 # the first assigned layer of each direction
            self.tracks[axis] = signal
            self.track_layers[axis] = layer
            if len(raw) > 1:
                self.periods[axis] = round((raw[1] - raw[0]) * len(pattern), 6)

    # -- the head --------------------------------------------------------------------
    def end_name(self, end=None):
        return self.ends[0 if (end or self.head) == "lo" else 1]

    def set_head(self, end_name):
        """Make the bottom / top (left / right) end the head."""
        if end_name not in self.ends:
            raise SnakeError(f"the ends of a {'vertical' if self.vertical else 'horizontal'} "
                             f"spine are {' and '.join(self.ends)}, not '{end_name}'")
        end = "lo" if end_name == self.ends[0] else "hi"
        if end != self.head or not self.moves:
            self._undo.append(self._state())
            self.head = end
            self._backed = None
            if self.moves and self.moves[-1][0] == "head":
                self.moves[-1] = ("head", end_name)
            else:
                self.moves.append(("head", end_name))

    def swap_head(self):
        """Make the other end the head; the path stays."""
        self.set_head(self.end_name("hi" if self.head == "lo" else "lo"))

    def body(self):
        """The points of the path under the body, bottom / left end first."""
        return Line(self.pts).part(self.start, self.start + self.length)

    def head_point(self):
        body = self.body()
        return body[0] if self.head == "lo" else body[-1]

    def heading(self):
        """The direction the head points: on along the path, out of the body."""
        body = self.body()
        return _unit(body[1], body[0]) if self.head == "lo" else _unit(body[-2], body[-1])

    def period(self, direction):
        """The track pattern period a step in direction is a whole number of
        (None without assigned tracks across the move)."""
        return self.periods.get("x" if DIRS[direction][0] else "y")

    def round_step(self, direction, step):
        """step as a whole number of track pattern periods, at least one."""
        period = self.period(direction)
        if not period:
            return round(max(1, round(step / self.grid)) * self.grid, 6)
        return round(max(1, round(step / period)) * period, 6)

    # -- moving ----------------------------------------------------------------------
    def move(self, direction, distance):
        """Pull the head distance um in direction (up, down, left, right), as
        far as the tracks and the hard stops allow. Returns a Step."""
        if direction not in DIRS:
            raise SnakeError(f"a move is up, down, left or right, not '{direction}'")
        if distance <= 0:
            raise SnakeError(f"the distance of a move must be positive, got {_num(distance)}")
        d = DIRS[direction]
        pos, out = self.head_point(), self.heading()
        back = d == (-out[0], -out[1])
        axis = 0 if d[0] else 1
        if back:
            limit, why = self._room_back(), "the next corner of its own path"
        else:
            limit, why = self._room(pos, d)
        to = self._landing(axis, pos[axis], d[axis], distance, limit, exact=back)
        if to is None:
            return Step(direction, distance, 0.0, pos, f"stopped by {why}")
        moved = round(abs(to - pos[axis]), 6)
        pts, start = self._advanced(d, moved, back)
        hit = self._overlap(pts, start)
        if hit:
            return Step(direction, distance, 0.0, pos, hit)
        self._undo.append(self._state())
        self.pts, self.start = pts, start
        # two moves the same way are one, unless the first backed up to a corner
        # and the second turns there: repeating the list must repeat the moves
        if self.moves and self.moves[-1][0] == direction and self._backed == back:
            self.moves[-1] = (direction, round(self.moves[-1][1] + moved, 6))
        else:
            if not self.moves:
                self.moves.append(("head", self.end_name()))
            self.moves.append((direction, moved))
        self._backed = back
        note = ""
        if moved < distance - self._slack(axis) - TOL:
            note = f"stopped by {why}"
        return Step(direction, distance, moved, self.head_point(), note)

    def undo(self):
        """Take back the last move or head change; False when there is none."""
        if not self._undo:
            return False
        self.pts, self.start, self.head, self.moves, self._backed = self._undo.pop()
        return True

    def _state(self):
        return list(self.pts), self.start, self.head, list(self.moves), self._backed

    def moves_text(self):
        """The moves so far, as the -moves value that repeats them."""
        return " ".join(f"{a} {b if a == 'head' else _num(b)}" for a, b in self.moves)

    def _slack(self, axis):
        """How much short of the asked distance a landing on a track may be."""
        tracks = self.tracks.get("xy"[axis])
        if not tracks or len(tracks) < 2:
            return self.grid
        return max(b - a for a, b in zip(tracks[:9], tracks[1:10]))

    def _landing(self, axis, pos, sign, distance, limit, exact=False):
        """The coordinate the head lands on, moving from pos by distance in
        direction sign along axis and no farther than limit: the signal track
        nearest the target, at least one track on and the last one before the
        limit at most (the manufacturing grid without a track ahead, or for a
        head outside the track area that stays outside). exact: where the limit cuts
        the move short the head stops at the limit itself (backing up to a
        corner). None: no room to move."""
        if limit <= TOL:
            return None
        if exact and distance >= limit - TOL:
            return pos + sign * limit
        tracks = self.tracks.get("xy"[axis]) or []
        reach = min(distance, limit)
        ahead = [t for t in tracks if sign * (t - pos) > TOL]
        first = (ahead[0] if sign > 0 else ahead[-1]) if ahead else None
        # on the grid: no track ahead, or a head outside the track area that
        # does not reach it with this move
        if first is None or (not tracks[0] - TOL <= pos <= tracks[-1] + TOL
                             and sign * (first - pos) > reach + TOL):
            d = math.floor(reach / self.grid + TOL) * self.grid
            return pos + sign * d if d > TOL else None
        inside = [t for t in ahead if sign * (t - pos) <= limit + TOL]
        if not inside:
            return None
        return min(inside, key=lambda t: abs(t - (pos + sign * distance)))

    def _room_back(self):
        """How far the head can back up: to the next corner of the path."""
        pts, start = self._oriented()
        line = Line(pts)
        ahead = [line.cum[k] - start for k in range(1, len(pts) - 1)
                 if line.cum[k] > start + TOL]
        return min(ahead) if ahead else math.inf

    def _room(self, pos, d):
        """(how far the head may go from pos in direction d, what stops it):
        the clearance of the side ahead, and of each side beside the move
        that is kept at pos."""
        if not self.edges or not point_in_polygon(pos[0], pos[1], self.boundary):
            return math.inf, ""
        side = SIDE_OF[NAMES[d]]
        near = (pos[0] + 1e-4 * d[0], pos[1] + 1e-4 * d[1])
        if not point_in_polygon(near[0], near[1], self.boundary):
            return 0.0, f"the design boundary (the head is on it; {side} clearance " \
                        f"{_num(self.clearance[side])})"
        ahead = self._ray(pos, d)
        if ahead is None:
            return math.inf, ""
        axis = 0 if d[0] else 1
        limit = ahead - self.clearance[side]
        why = (f"the {side} clearance {_num(self.clearance[side])} to the boundary at "
               f"{'xy'[axis]} {_num(pos[axis] + d[axis] * ahead)}")
        if limit <= TOL:
            return 0.0, why
        for s in ((0, 1), (0, -1)) if d[0] else ((1, 0), (-1, 0)):
            name = SIDE_OF[NAMES[s]]
            need = self.clearance[name]
            now = self._ray(pos, s)
            if now is None or now < need - TOL:
                continue                 # not kept here: this move cannot lose it
            cuts = sorted({round(d[axis] * (e[axis] - pos[axis]), 6) for e in self.edges
                           if TOL < d[axis] * (e[axis] - pos[axis]) < limit - TOL})
            before = 0.0
            for cut in cuts + [limit]:
                mid = (before + cut) / 2
                gap = self._ray((pos[0] + mid * d[0], pos[1] + mid * d[1]), s)
                if gap is not None and gap < need - TOL:
                    limit = before
                    why = (f"the {name} clearance {_num(need)}: beyond {'xy'[axis]} "
                           f"{_num(pos[axis] + d[axis] * before)} the boundary is "
                           f"{_num(gap)} to the {name}")
                    break
                before = cut
        return limit, why

    def _ray(self, p, d):
        """Distance from p in direction d to the nearest boundary edge; None
        when there is none that way."""
        best = None
        a, b = (1, 0) if d[0] else (0, 1)        # a: the axis the edge must span
        for e in self.edges:
            p1, p2 = e[0:2], e[2:4]
            if abs(p2[a] - p1[a]) < TOL:
                continue                         # parallel to the ray
            if not min(p1[a], p2[a]) - TOL <= p[a] <= max(p1[a], p2[a]) + TOL:
                continue
            c = p1[b] + (p[a] - p1[a]) * (p2[b] - p1[b]) / (p2[a] - p1[a])
            s = (c - p[b]) * d[b]
            if s > TOL and (best is None or s < best):
                best = s
        return best

    def _oriented(self):
        """(points, body start) with the head's end first."""
        if self.head == "lo":
            return self.pts, self.start
        return self.pts[::-1], Line(self.pts).total - self.start - self.length

    def _advanced(self, d, dist, back):
        """(points, body start) after the head moves dist in direction d."""
        pts, start = self._oriented()
        line = Line(pts)
        if back:
            short = start + dist + self.length - line.total
            if short > TOL:                      # the far end runs straight on
                t = line.dirs[-1]
                pts = pts[:-1] + [(pts[-1][0] + short * t[0], pts[-1][1] + short * t[1])]
            start += dist
        else:                                    # what lay beyond the head is dropped
            head = line.at(start)[0]
            pts = [(head[0] + dist * d[0], head[1] + dist * d[1])] + \
                line.part(start, line.total)
            start = 0.0
        pts = _clean(pts)
        if self.head == "hi":
            start = Line(pts).total - start - self.length
            pts = pts[::-1]
        return pts, round(max(start, 0.0), 6)

    def _overlap(self, pts, start):
        """Why the body on this path would lie over itself, or ''. Each
        stretch is as wide as the columns of cells beside the stubs."""
        body = Line(pts).part(start, start + self.length)
        rects = []
        for a, b in zip(body, body[1:]):
            n = self._normal(_unit(a, b))
            xs = [p[0] + w * n[0] for p in (a, b) for w in self.width]
            ys = [p[1] + w * n[1] for p in (a, b) for w in self.width]
            rects.append((min(xs), min(ys), max(xs), max(ys)))
        for i, r in enumerate(rects):
            for q in rects[i + 2:]:
                if r[0] < q[2] - TOL and q[0] < r[2] - TOL and \
                        r[1] < q[3] - TOL and q[1] < r[3] - TOL:
                    return (f"refused: the spine would run into its own body (it is "
                            f"{_num(self.width[1] - self.width[0])} wide with its cells)")
        return ""

    # -- where everything is -----------------------------------------------------------
    def _normal(self, t):
        """The across direction on a stretch running in direction t."""
        return (t[1], -t[0]) if self.vertical else (-t[1], t[0])

    def _place(self, line, along, across, before=False):
        (x, y), t = line.at(along - self.lo, before)
        n = self._normal(t)
        w = across - self.across
        return round(x + w * n[0], 6), round(y + w * n[1], 6)

    def _run(self, line, a1, a2, across):
        """The points of a line along the spine from a1 to a2, at across:
        mitred where the path turns."""
        if a1 > a2:
            return self._run(line, a2, a1, across)[::-1]
        w = across - self.across
        pts = [self._place(line, a1, across)]
        for k in line.corners(a1 - self.lo, a2 - self.lo):
            n1, n2 = self._normal(line.dirs[k - 1]), self._normal(line.dirs[k])
            pts.append((line.pts[k][0] + w * (n1[0] + n2[0]), line.pts[k][1] + w * (n1[1] + n2[1])))
        return _clean(pts + [self._place(line, a2, across, before=True)])

    def cells(self):
        """[(inst, centre x, centre y)] on the path as it is."""
        line = Line(self.body())
        return [(inst,) + self._place(line, a, c) for inst, a, c in self.members]

    def stub_lines(self):
        """[(row id, name, points)]: each stub along the path."""
        line = Line(self.body())
        return [(k, name, self._run(line, lo, hi, self.across)) for k, name, lo, hi in self.stubs]

    def net_lines(self):
        """[(row id, name, [(x1, y1, x2, y2)])]: the net centre lines."""
        line = Line(self.body())
        found = []
        for k, name, segs in self.nets:
            lines = []
            for a1, c1, a2, c2 in segs:
                if abs(c1 - c2) < TOL:           # along the spine: follows the path
                    pts = self._run(line, a1, a2, c1)
                else:                            # across it: one straight line
                    pts = [self._place(line, a1, c1), self._place(line, a2, c2)]
                lines += [a + b for a, b in zip(pts, pts[1:]) if a != b]
            found.append((k, name, lines))
        return found

    def axis_of(self, inst):
        """x or y: the way the path runs where this cell sits."""
        line = Line(self.body())
        along = next(a for name, a, _ in self.members if name == inst)
        return "x" if line.dirs[line.seg(along - self.lo)][0] else "y"

    def cell_overlaps(self):
        """Pairs of the spine's cells that overlap on the path as it is (in
        the inside of a bend, where the columns of the two stretches meet)."""
        w, h = self.cell
        boxes = [(n, x - w / 2, y - h / 2, x + w / 2, y + h / 2) for n, x, y in self.cells()]
        return [(a[0], b[0]) for i, a in enumerate(boxes) for b in boxes[i + 1:]
                if a[1] < b[3] - TOL and b[1] < a[3] - TOL and a[2] < b[4] - TOL
                and b[2] < a[4] - TOL]

    def outside(self):
        """Names of the cells (centre) and stubs (any point) outside the design
        boundary; empty without one."""
        if not self.boundary:
            return []
        inside = lambda p: point_in_polygon(p[0], p[1], self.boundary)
        return [n for n, x, y in self.cells() if not inside((x, y))] + \
            [n for _, n, pts in self.stub_lines() if not all(inside(p) for p in pts)]

    def commit(self, db):
        """Write the spine as it lies now: the instances (corner on the
        manufacturing grid), stubs, net centre lines, path and location. Its
        routing goes (Database.set_spine_shape). Returns what was removed."""
        line = Line(self.body())
        snap = lambda v: round(round(v / self.grid) * self.grid, 6)
        w, h = self.cell
        insts = [(n, snap(x - w / 2), snap(y - h / 2)) for n, x, y in self.cells()]
        text = lambda pts: " ".join(_num(c) for p in pts for c in p)
        stubs = [(k, text(pts)) for k, _, pts in self.stub_lines()]
        nets = [(k, ";".join(" ".join(_num(c) for c in seg) for seg in segs))
                for k, _, segs in self.net_lines()]
        location = self._place(line, 0.0, 0.0)
        return db.set_spine_shape(self.name, location, text(line.pts), insts, stubs, nets)


def member_axes(db):
    """{inst: 'x' | 'y'}: the way each spine cell may be moved by the
    legalizer, along its spine: y on a vertical stretch, x on a horizontal
    one (a bent spine has both)."""
    axes = {}
    for name in db.spine_names():
        spine = db.spine_row(name)
        straight = "x" if (spine["orientation"] or "") == "horizontal" else "y"
        snake = Snake(db, name, limits=False) if spine["path"] else None
        for m in db.spine_members(spine["id"]):
            axes[m["inst"]] = snake.axis_of(m["inst"]) if snake else straight
    return axes


def stub_points(text):
    """[(x, y)] of a spine_stub's points: two for a straight stub, more for
    one that follows a bent path."""
    v = [float(c) for c in text.split()]
    return list(zip(v[0::2], v[1::2]))


def stub_middle(pts):
    """The point half way along a stub's line (its tap)."""
    line = Line(list(pts))
    return line.at(line.total / 2)[0]
