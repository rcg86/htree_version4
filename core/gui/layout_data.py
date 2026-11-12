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
# Placement rows (DEF ROW): one color per site, in first-row order.
ROW_PALETTE = ["#a1887f", "#90a4ae", "#aed581", "#ffb74d", "#f48fb1", "#80deea"]
MAX_ROWS = 3000              # per site; more rows in view are not drawn until zoomed in
# Net classes of the per-layer Signal / Power / Ground view filters.
NET_CLASSES = ("signal", "power", "ground")
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
    cls: str = "signal"          # signal | power | ground (net_class)


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
    pin_classes: Dict[str, str] = field(default_factory=dict)   # pin -> net_class


@dataclass
class SpineDraw:
    """A built spine (create_spine -build): stubs and net centre lines."""
    handle: str                  # spine:<name>
    stubs: List[Tuple[str, List[float]]] = field(default_factory=list)   # (name, x1 y1 x2 y2)
    #                              a stub over a bend of its spine: one entry per stretch
    segments: List[Tuple[str, List[float]]] = field(default_factory=list)  # (net, x1 y1 x2 y2)


@dataclass
class Strap:
    """A route_pin wire: a horizontal strap, or a vertical pin wire."""
    handle: str                  # strap:<inst>/<n> or pin_wire:<inst>/<pin>
    net: str
    layer: str
    rect: Tuple[float, float, float, float]
    label: str = ""              # written on it when labels are on; default the net
    outline: bool = False        # a route_net crossing box: drawn as an outline
    cls: str = "signal"          # signal | power | ground (net_class)


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
class SiteRows:
    """The DEF rows of one site (read_def), lowest first."""
    site: str
    color: str
    width: float                 # site width: the rows' STEP
    height: float                # site height: the row pitch, else its cells' height
    rows: List[Tuple[float, float, int, float, str]] = field(default_factory=list)
    # (y, x, sites, step, orient)
    ys: List[float] = field(default_factory=list)              # the rows' y, for bisect


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
    straps: List[Strap] = field(default_factory=list)
    pin_wires: List[Strap] = field(default_factory=list)
    net_wires: List[Strap] = field(default_factory=list)     # route_net wires and crossings
    site_rows: List[SiteRows] = field(default_factory=list)  # per site
    grid: float = 0.001                                       # manufacturing grid

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
                "SELECT p.name AS pin, p.net, p.use, s.seq, s.layer, s.type, s.points "
                "FROM port_shape s "
                "JOIN port p ON p.id = s.port_id ORDER BY s.id"):
            port = f"port:{lay.design}/{r['pin']}"
            lay.shapes.append(PortShape(f"port_shape:{lay.design}/{r['pin']}/{r['seq']}",
                                        port, r["layer"], r["type"],
                                        [float(v) for v in r["points"].split()],
                                        net_class(r["net"] or r["pin"], r["use"])))
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
    lay.site_rows = _cached_site_rows(db)
    if db.has_tech() and db.tech_row()["manufacturing_grid"]:
        lay.grid = db.tech_row()["manufacturing_grid"]
    for r in db.strap_rows():
        lay.straps.append(Strap(f"strap:{r['inst']}/{r['seq']}", r["net"], r["layer"],
                                tuple(float(v) for v in r["rect"].split()),
                                cls=net_class(r["net"])))
        counts.setdefault(r["layer"], [0, 0])[0] += 1
    for r in db.pin_wire_rows():
        lay.pin_wires.append(Strap(f"pin_wire:{r['inst']}/{r['pin']}", r["net"], r["layer"],
                                   tuple(float(v) for v in r["rect"].split()), r["pin"],
                                   cls=net_class(r["net"])))
        counts.setdefault(r["layer"], [0, 0])[0] += 1
    for r in db.net_wire_rows():
        st = net_wire_strap(r)
        lay.net_wires.append(st)
        if not st.outline:
            counts.setdefault(st.layer, [0, 0])[0] += 1
    for i, (name, (shapes, tracks)) in enumerate(counts.items()):
        lay.layers.append(LayerInfo(name, name in tech, PALETTE[i % len(PALETTE)],
                                    shapes, tracks))
    return lay


def net_wire_strap(r) -> Strap:
    """The drawing of a net_wire row: crossing boxes and vias as outlines
    shown with their first layer; shields and power extensions labelled with
    their power net."""
    cross = r["kind"].endswith("cross") or r["kind"] == "via"
    shield = r["shield_net"] if r["kind"] in ("shield", "shield_ext", "stub_shield", "pg_ext",
                                              "via") else None
    return Strap(f"net_wire:{r['net']}/{r['seq']}", shield or r["net"], r["layer"].split("/")[0],
                 tuple(float(v) for v in r["rect"].split()), label=shield or "",
                 outline=cross, cls=net_class(r["shield_net"] or r["net"]))


def net_class(net, use=None) -> str:
    """power, ground or signal: a LEF/DEF USE POWER or GROUND first, else the
    net (or pin) name: VDD* and VCC* are power, VSS* and GND* ground."""
    use = (use or "").lower()
    if use in ("power", "ground"):
        return use
    name = (net or "").upper()
    if name.startswith(("VDD", "VCC")):
        return "power"
    if name.startswith(("VSS", "GND")):
        return "ground"
    return "signal"


def load_insts(db) -> List[Inst]:
    """Placed instances with their bbox and their cell's pin shapes placed."""
    from core.objects import inst_bbox
    from core.placement import placed_points, placer
    out = []
    shapes_of, classes_of = {}, {}
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
        if row["ref_cell"] not in classes_of:
            classes_of[row["ref_cell"]] = {p: net_class(p, use) for p, use in db.conn.execute(
                "SELECT p.name, p.use FROM lib_pin p JOIN lib_cell c ON c.id = p.cell_id "
                "WHERE c.name = ?", (row["ref_cell"],))}
        out.append(Inst(f"inst:{row['name']}", row["ref_cell"], box, pins,
                        classes_of[row["ref_cell"]]))
    return out


def load_spines(db) -> List[SpineDraw]:
    out = []
    for name in db.spine_names():
        row = db.spine_row(name)
        sp = SpineDraw(f"spine:{name}")
        for s in db.spine_stub_rows(row["id"]):
            v = [float(c) for c in s["points"].split()]   # a line per stretch when bent
            sp.stubs += [(s["name"], v[k:k + 4]) for k in range(0, len(v) - 2, 2)]
        for n in db.spine_net_rows(row["id"]):
            sp.segments += [(n["name"], [float(v) for v in seg.split()])
                            for seg in (n["route"] or "").split(";") if seg]
        out.append(sp)
    return out


_rows_cache = {}             # the last site rows loaded, and what they were loaded from


def _cached_site_rows(db) -> List[SiteRows]:
    """load_site_rows, reused while the rows and cells are unchanged: a
    design has 100k+ rows and the view reloads after every command."""
    key = (id(db.conn),) + tuple(db.conn.execute(
        "SELECT COUNT(*), MAX(id) FROM site_row").fetchone()) + tuple(db.conn.execute(
            "SELECT COUNT(*), MAX(id) FROM lib_cell").fetchone())
    if _rows_cache.get("key") != key:
        _rows_cache.update(key=key, rows=load_site_rows(db))
    return _rows_cache["rows"]


def track_coords(lay: "Layout", layer: str, direction: str) -> List[float]:
    """Sorted positions of the DEF tracks of layer running as direction
    (y: horizontal lines at y positions, x: vertical ones)."""
    out = set()
    for t in lay.tracks:
        if t.direction == direction and layer in t.layers:
            out.update(round(t.start + i * t.step, 6) for i in range(t.num))
    return sorted(out)


def load_site_rows(db) -> List[SiteRows]:
    """DEF rows grouped by site, a ROW ... BY n with n > 1 as n rows. The
    site height is the smallest gap between its rows (cells may span several
    rows: a 7-track cell is 7 rows tall); for a single row, the smallest
    height of the cells on that site (LEF SITE)."""
    groups: Dict[str, List[Tuple[float, float, int, float, str]]] = {}
    for r in db.conn.execute("SELECT site, x, y, orient, num_x, num_y, step_x, step_y "
                             "FROM site_row ORDER BY id"):
        rows = groups.setdefault(r["site"], [])
        for k in range(max(1, r["num_y"] or 1)):
            rows.append((r["y"] + k * (r["step_y"] or 0.0), r["x"], max(1, r["num_x"] or 1),
                         r["step_x"] or 0.0, r["orient"] or "N"))
    out = []
    for i, (site, rows) in enumerate(groups.items()):
        rows.sort()
        ys = [r[0] for r in rows]
        cell = db.conn.execute("SELECT MIN(size_y) FROM lib_cell WHERE site = ? AND size_y > 0",
                               (site,)).fetchone()[0]
        gaps = [b - a for a, b in zip(ys, ys[1:]) if b - a > 1e-9]
        height = (min(gaps) if gaps else cell) or 1.0
        width = min((r[3] for r in rows if r[3] > 0), default=0.0)
        out.append(SiteRows(site, ROW_PALETTE[i % len(ROW_PALETTE)], width, round(height, 6),
                            rows, ys))
    return out


def visible_rows(sr: SiteRows, x_lo: float, y_lo: float, x_hi: float, y_hi: float,
                 limit: int = MAX_ROWS):
    """The rows of sr touching the view box, as (y, x, sites, step, orient);
    None when more than limit are in range (too dense to draw)."""
    first = bisect.bisect_left(sr.ys, y_lo - sr.height - 1e-9)
    last = bisect.bisect_right(sr.ys, y_hi + 1e-9)
    if last - first > limit:
        return None
    return [r for r in sr.rows[first:last] if r[0] + sr.height >= y_lo
            and r[1] <= x_hi and r[1] + r[2] * (r[3] or 0.0) >= x_lo]


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


def segment_touches_rect(a, b, rect):
    """True if the segment a-b crosses or lies in rect (x1, y1, x2, y2, lowest
    first). Liang-Barsky clipping; a zero-length segment is a point."""
    (x0, y0), (x1, y1) = a, b
    rx1, ry1, rx2, ry2 = rect
    t0, t1 = 0.0, 1.0
    dx, dy = x1 - x0, y1 - y0
    for p, q in ((-dx, x0 - rx1), (dx, rx2 - x0), (-dy, y0 - ry1), (dy, ry2 - y0)):
        if p == 0:
            if q < 0:
                return False                          # parallel and outside
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


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
