"""Database -> drawing data for the layout view. No Qt here.

Model coordinates are microns with y up, as in the database.
"""

import bisect
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Distinct colors for layers, assigned in layer order.
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
           "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ffe119"]

MAX_TRACK_LINES = 300        # per pattern; denser patterns are not drawn until zoomed in
# Colors for the nets of a track assignment, in pattern order; signal tracks
# ('-') are grey, blank tracks ('NA') dark grey.
NET_PALETTE = ["#ff4d4d", "#4da6ff", "#4dff88", "#ffd24d", "#d24dff", "#4dffff"]
SIGNAL = "-"
SIGNAL_COLOR = "#9e9e9e"
BLANK = "NA"                 # track left blank (assign_track_for_route)
BLANK_COLOR = "#5f5f5f"
# Tech DIRECTION -> the DEF TRACKS that run that way (TRACKS Y are horizontal lines).
PREFERRED_TRACKS = {"horizontal": "y", "vertical": "x"}


@dataclass
class LayerInfo:
    name: str
    in_tech: bool
    color: str
    port_shapes: int = 0
    track_patterns: int = 0


@dataclass
class PortShape:
    handle: str                  # port_shape:<design>/<pin>/<k>
    port: str                    # port:<design>/<pin>
    layer: str
    type: str                    # rect | polygon
    points: List[float]          # x y x y ... (rect: x1 y1 x2 y2)


@dataclass
class Track:
    handle: str
    direction: str               # x: vertical lines at x positions; y: horizontal
    start: float
    num: int
    step: float
    layers: List[str]


@dataclass
class Inst:
    handle: str                  # inst:<name>
    ref: str
    bbox: Tuple[float, float, float, float]
    pins: List[Tuple[str, str, str, List[float]]] = field(default_factory=list)
    # (pin, layer, type, placed points)


@dataclass
class SpineDraw:
    """A built spine (create_spine -build): stubs and net centre lines."""
    handle: str                  # spine:<name>
    stubs: List[Tuple[str, List[float]]] = field(default_factory=list)   # (name, x1 y1 x2 y2)
    segments: List[List[float]] = field(default_factory=list)            # x1 y1 x2 y2


@dataclass
class TrackAssignment:
    layer: str
    direction: str               # x | y: which tracks are numbered
    pattern: List[str]
    positions: List[float]       # every numbered track, lowest first
    colors: Dict[str, str] = field(default_factory=dict)       # net -> color
    counts: List[Tuple[str, int]] = field(default_factory=list)  # (net, tracks), pattern order

    def nets(self) -> List[str]:
        return [n for n, _ in self.counts]


@dataclass
class Layout:
    design: Optional[str] = None
    boundary: List[float] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None
    layers: List[LayerInfo] = field(default_factory=list)
    shapes: List[PortShape] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    assignments: List[TrackAssignment] = field(default_factory=list)
    preferred: Dict[str, str] = field(default_factory=dict)   # tech layer -> x | y
    insts: List[Inst] = field(default_factory=list)
    spines: List[SpineDraw] = field(default_factory=list)

    def layer(self, name) -> Optional[LayerInfo]:
        return next((l for l in self.layers if l.name == name), None)


def load_layout(db) -> Layout:
    """Read what the view draws. Tech layers come first in tech order, then
    other layers that carry port shapes or tracks, in first-use order."""
    lay = Layout()
    tech = db.layer_names() if db.has_tech() else []
    for name in tech:
        d = PREFERRED_TRACKS.get(db.layer_row(name)["direction"] or "")
        if d:
            lay.preferred[name] = d
    counts: Dict[str, List[int]] = {name: [0, 0] for name in tech}
    if db.has_design():
        row = db.design_row()
        lay.design = row["name"]
        lay.boundary = [float(v) for v in (row["boundary"] or "").split()]
        if lay.boundary:
            xs, ys = lay.boundary[0::2], lay.boundary[1::2]
            lay.bbox = (min(xs), min(ys), max(xs), max(ys))
        for r in db.conn.execute(
                "SELECT p.name AS pin, s.seq, s.layer, s.type, s.points FROM port_shape s "
                "JOIN port p ON p.id = s.port_id ORDER BY s.id"):
            port = f"port:{lay.design}/{r['pin']}"
            lay.shapes.append(PortShape(f"port_shape:{lay.design}/{r['pin']}/{r['seq']}",
                                        port, r["layer"], r["type"],
                                        [float(v) for v in r["points"].split()]))
            counts.setdefault(r["layer"], [0, 0])[0] += 1
        for r in db.conn.execute("SELECT * FROM track_pattern ORDER BY id"):
            layers = r["layers"].split()
            lay.tracks.append(Track(f"track_pattern:{lay.design}/{r['id']}", r["direction"],
                                    r["start"], r["num_tracks"], r["step"], layers))
            for name in drawn_layers(lay.tracks[-1], lay.preferred):
                counts.setdefault(name, [0, 0])[1] += 1
        for name in db.track_assignment_layers():
            lay.assignments.append(load_assignment(db, name))
    for inst in load_insts(db):
        lay.insts.append(inst)
        for _, layer, _, _ in inst.pins:
            counts.setdefault(layer, [0, 0])[0] += 1
    lay.spines = load_spines(db)
    for i, (name, (shapes, tracks)) in enumerate(counts.items()):
        lay.layers.append(LayerInfo(name, name in tech, PALETTE[i % len(PALETTE)],
                                    shapes, tracks))
    return lay


def load_insts(db) -> List[Inst]:
    """Placed instances with their bbox and their cell's pin shapes placed."""
    from core.objects import inst_bbox
    from core.placement import placed_points, placer
    out = []
    shapes_of = {}
    for row in db.inst_rows():
        cell = db.lib_cell_row(row["ref_cell"])
        box = inst_bbox(db, row)
        if cell is None or box is None:
            continue
        place = placer(cell["size_x"], cell["size_y"], row["orient"], row["x"], row["y"])
        if row["ref_cell"] not in shapes_of:
            shapes_of[row["ref_cell"]] = db.lib_cell_shapes(row["ref_cell"])
        pins = [(pin, layer, kind, placed_points([float(v) for v in pts.split()], place))
                for pin, layer, kind, pts in shapes_of[row["ref_cell"]]]
        out.append(Inst(f"inst:{row['name']}", row["ref_cell"], box, pins))
    return out


def load_spines(db) -> List[SpineDraw]:
    out = []
    for name in db.spine_names():
        row = db.spine_row(name)
        sp = SpineDraw(f"spine:{name}")
        for s in db.spine_stub_rows(row["id"]):
            sp.stubs.append((s["name"], [float(v) for v in s["points"].split()]))
        for n in db.spine_net_rows(row["id"]):
            sp.segments += [[float(v) for v in seg.split()]
                            for seg in (n["route"] or "").split(";") if seg]
        out.append(sp)
    return out


def drawn_layers(track: "Track", preferred: Dict[str, str]) -> List[str]:
    """Layers of a track pattern that the view draws: a tech layer only when
    the pattern runs in its preferred direction (IA horizontal: TRACKS Y);
    a layer with no tech direction always."""
    return [l for l in track.layers if preferred.get(l, track.direction) == track.direction]


def load_assignment(db, layer) -> TrackAssignment:
    row = db.track_assignment_row(layer)
    pattern = row["pattern"].split()
    positions = db.track_positions(layer, row["direction"])
    nets = [n for n in dict.fromkeys(pattern) if n not in (SIGNAL, BLANK)]
    colors = {n: NET_PALETTE[i % len(NET_PALETTE)] for i, n in enumerate(nets)}
    colors[SIGNAL] = SIGNAL_COLOR
    colors[BLANK] = BLANK_COLOR
    per = {n: 0 for n in nets + [r for r in (SIGNAL, BLANK) if r in pattern]}
    for i in range(len(positions)):
        per[pattern[i % len(pattern)]] += 1
    return TrackAssignment(layer, row["direction"], pattern, positions, colors,
                           list(per.items()))


def visible_assigned_tracks(a: TrackAssignment, lo: float, hi: float, shown_nets,
                            limit: int = MAX_TRACK_LINES):
    """(coordinate, net) for the tracks of a inside [lo, hi] whose net is in
    shown_nets. None when more than limit tracks are in range (too dense)."""
    first = bisect.bisect_left(a.positions, lo - 1e-9)
    last = bisect.bisect_right(a.positions, hi + 1e-9)
    if last - first > limit:
        return None
    period = len(a.pattern)
    out = []
    for i in range(first, last):
        net = a.pattern[i % period]
        if net in shown_nets:
            out.append((a.positions[i], net))
    return out


def visible_track_positions(track: Track, lo: float, hi: float,
                            limit: int = MAX_TRACK_LINES) -> Optional[List[float]]:
    """Track coordinates inside [lo, hi] (x for direction x, y for y). None when
    more than limit would be drawn: the caller shows nothing until zoomed in."""
    if track.step <= 0:
        return []
    first = max(0, math.ceil((lo - track.start) / track.step - 1e-9))
    last = min(track.num - 1, math.floor((hi - track.start) / track.step + 1e-9))
    if last < first:
        return []
    if last - first + 1 > limit:
        return None
    return [track.start + i * track.step for i in range(first, last + 1)]


def clip_line_to_polygon(polygon: List[float], vertical: bool, c: float) -> List[Tuple[float, float]]:
    """Inside spans of the line x = c (vertical) or y = c, as (from, to) pairs
    along the other axis. Works for any simple polygon; an empty list means
    the line misses it. Uses half-open edge spans so vertices are not counted
    twice."""
    pts = list(zip(polygon[0::2], polygon[1::2]))
    hits = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a1, a2, b1, b2 = (x1, x2, y1, y2) if vertical else (y1, y2, x1, x2)
        if a1 == a2:
            continue                                  # edge parallel to the line
        if (a1 <= c < a2) or (a2 <= c < a1):
            hits.append(b1 + (c - a1) * (b2 - b1) / (a2 - a1))
    hits.sort()
    return [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]


# -- ruler geometry (model coordinates, microns) --------------------------------------

def nearest_on_segments(point, segments, radius):
    """Nearest point to point on any segment ((x1, y1), (x2, y2)) within
    radius, or None. Corners are covered: they are segment ends."""
    px, py = point
    best, best_d = None, radius * radius
    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length2))
        qx, qy = x1 + t * dx, y1 + t * dy
        d = (qx - px) ** 2 + (qy - py) ** 2
        if d <= best_d:
            best, best_d = (qx, qy), d
    return best


def polygon_edges(points):
    pts = list(zip(points[0::2], points[1::2]))
    return list(zip(pts, pts[1:] + pts[:1]))


def constrain_orthogonal(start, end):
    """end moved onto the horizontal or vertical line through start, whichever
    is closer to the mouse movement."""
    (x0, y0), (x1, y1) = start, end
    return (x1, y0) if abs(x1 - x0) >= abs(y1 - y0) else (x0, y1)


def ruler_text(start, end, diagonal):
    """Label for a ruler: its length, and dx dy for a diagonal one."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if not diagonal:
        return f"{_fmt(length)} um"
    return f"{_fmt(length)} um  (dx {_fmt(abs(dx))}, dy {_fmt(abs(dy))})"


def _fmt(v):
    text = f"{v:.5f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"
