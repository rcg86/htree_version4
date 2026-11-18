"""The signal tracks a spine spec gives its cells: track: {input: k, output: k}.

Track k is the k-th signal track (a '-' track of the layer's track
assignment) past the spine's location, counted in its build direction: on a
vertical stretch of the spine the tracks of the layer numbered in x (IB), on
a horizontal one those numbered in y (IA). On a spine bent by
move_spine_to_boundary each stretch counts from its own location line (where
-location lies on the straight spine, the line of the L1 cells) the same
way, so a net keeps its number round the bends. The input net of a cell runs
into it on its input track, its output net leaves it on its output track.
"""

import math
from types import SimpleNamespace

from core.spine_snake import Line, Snake, SnakeError

TOL = 1e-6


def _signal(db, axis):
    """(layer, sorted coordinates of its '-' tracks) of the first layer whose
    track assignment numbers its tracks in axis; (None, []) without one."""
    for layer in db.track_assignment_layers():
        row = db.track_assignment_row(layer)
        if row["direction"] == axis:
            pattern = row["pattern"].split()
            return layer, [c for k, c in enumerate(db.track_positions(layer, axis))
                           if pattern[k % len(pattern)] == "-"]
    return None, []


def stretches(db, spine):
    """The stretches of a built spine's path, each a SimpleNamespace: a, b
    (its ends), vertical, layer, loc (the location line's coordinate across
    it), sign (+1 / -1: the build direction across it), tracks, lo / hi
    (along, on the straight spine) and coord(k) (track k, or None)."""
    try:
        snake = Snake(db, spine, limits=False)
    except SnakeError:
        return []
    pts = snake.body()
    line = Line(pts)
    found = []
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        lo, hi = snake.lo + line.cum[k], snake.lo + line.cum[k + 1]
        mid = (lo + hi) / 2              # toward the stub line: the build direction
        p0 = snake.place(mid, 0.0)
        p1 = snake.place(mid, 1.0 if snake.across > 0 else -1.0)
        vertical = abs(a[0] - b[0]) < TOL
        axis = 0 if vertical else 1
        layer, tracks = _signal(db, "x" if vertical else "y")
        sign = 1 if p1[axis] > p0[axis] else -1
        s = SimpleNamespace(a=a, b=b, vertical=vertical, layer=layer, loc=p0[axis], sign=sign,
                            tracks=tracks, lo=lo, hi=hi, index=k)
        past = sorted((t for t in tracks if (t - s.loc) * sign > TOL),
                      key=lambda t, s=s: (t - s.loc) * s.sign)
        s.coord = lambda n, past=past: past[n - 1] if 1 <= n <= len(past) else None
        found.append(s)
    return found


def stretch_at(found, x, y):
    """The stretch nearest the point (x, y)."""
    def gap(s):
        (x1, y1), (x2, y2) = s.a, s.b
        cx = min(max(x, min(x1, x2)), max(x1, x2))
        cy = min(max(y, min(y1, y2)), max(y1, y2))
        return abs(x - cx) + abs(y - cy)
    return min(found, key=gap) if found else None


def cell_tracks(db, spine):
    """{inst: (input k or None, output k or None)} of the cells of a built
    spine whose spec cell gives track: {...}."""
    row = db.spine_row(spine)
    found = {}
    for m in db.spine_members(row["id"]):
        level = db.spine_level_row(row["spec"], m["level"])
        cell = db.spine_cell_row(level["id"], m["cell"]) if level is not None else None
        if cell is not None and (cell["track_in"] or cell["track_out"]):
            found[m["inst"]] = (cell["track_in"], cell["track_out"])
    return found


def placed(db, spine):
    """{inst: (stretch, input coordinate or None, output coordinate or None,
    input k, output k)} of the cells with tracks, on the stretch they sit on."""
    tracks = cell_tracks(db, spine)
    if not tracks:
        return {}
    found = stretches(db, spine)
    if not found:
        return {}
    row = db.spine_row(spine)
    along = {m["inst"]: m["along"] for m in db.spine_members(row["id"])}
    result = {}
    for inst, (kin, kout) in tracks.items():
        a = along.get(inst)
        s = next((s for s in found if s.lo - TOL <= a <= s.hi + TOL), None) if a is not None \
            else None
        if s is None:                    # past the ends: the nearest stretch
            s = min(found, key=lambda s: min(abs(a - s.lo), abs(a - s.hi)) if a is not None
                    else math.inf)
        result[inst] = (s, s.coord(kin) if kin else None, s.coord(kout) if kout else None,
                        kin, kout)
    return result
