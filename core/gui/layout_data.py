"""Database -> drawing data for the layout view. No Qt here.

Model coordinates are microns with y up, as in the database.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Distinct colors for layers, assigned in layer order.
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
           "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ffe119"]

MAX_TRACK_LINES = 300        # per pattern; denser patterns are not drawn until zoomed in


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
class Layout:
    design: Optional[str] = None
    boundary: List[float] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None
    layers: List[LayerInfo] = field(default_factory=list)
    shapes: List[PortShape] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)

    def layer(self, name) -> Optional[LayerInfo]:
        return next((l for l in self.layers if l.name == name), None)


def load_layout(db) -> Layout:
    """Read what the view draws. Tech layers come first in tech order, then
    other layers that carry port shapes or tracks, in first-use order."""
    lay = Layout()
    tech = db.layer_names() if db.has_tech() else []
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
            for name in layers:
                counts.setdefault(name, [0, 0])[1] += 1
    for i, (name, (shapes, tracks)) in enumerate(counts.items()):
        lay.layers.append(LayerInfo(name, name in tech, PALETTE[i % len(PALETTE)],
                                    shapes, tracks))
    return lay


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
