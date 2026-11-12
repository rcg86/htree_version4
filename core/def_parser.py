"""DEF reader for the design boundary and pins. Pure: reads a file, returns
dataclasses, never touches the db.

Only the header (VERSION, DESIGN, UNITS, DIVIDERCHAR, BUSBITCHARS), DIEAREA,
ROW, TRACKS and PINS are read. Every other section and statement
(GCELLGRID, COMPONENTS, NETS, ...) is skipped and counted. The file is read line by line,
so a large floorplan DEF is never held as one token list. '.gz' files are
read directly.

Coordinates are converted from DEF database units to microns. Pin shapes are
returned in absolute coordinates: each shape is rotated by its port's
orientation and moved to its placement.
"""

import gzip
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Statements that open a section closed by "END <keyword>".
SECTIONS = {"PROPERTYDEFINITIONS", "VIAS", "STYLES", "NONDEFAULTRULES", "REGIONS",
            "COMPONENTMASKSHIFT", "COMPONENTS", "PINPROPERTIES", "BLOCKAGES", "SLOTS",
            "FILLS", "SPECIALNETS", "NETS", "SCANCHAINS", "GROUPS", "BEGINEXT"}
# COMPONENTMASKSHIFT is a single statement, not a section.
SECTIONS.discard("COMPONENTMASKSHIFT")

# DEF orientation -> (x, y) transform about the placement point.
ORIENTS = {
    "N": lambda x, y: (x, y), "W": lambda x, y: (-y, x),
    "S": lambda x, y: (-x, -y), "E": lambda x, y: (y, -x),
    "FN": lambda x, y: (-x, y), "FW": lambda x, y: (-y, -x),
    "FS": lambda x, y: (x, -y), "FE": lambda x, y: (y, x),
}
DIRECTIONS = {"input": "in", "output": "out", "inout": "inout", "feedthru": "feedthru"}

# A lone '-' (the pin marker) is its own token; '-76' stays one number.
_TOKEN_RE = re.compile(r'"[^"]*"|[()+;*]|[^\s()+;"*]+')
HEADER = {"VERSION", "DESIGN", "DIVIDERCHAR", "BUSBITCHARS", "UNITS", "DIEAREA"}


class DefParseError(Exception):
    def __init__(self, text: str, file: str, line: int):
        super().__init__(f"{file}:{line}: {text}")
        self.text = text
        self.file = file
        self.line = line


@dataclass
class PortShape:
    layer: str
    type: str                       # "rect" or "polygon"
    points: List[float]             # microns, absolute when the port is placed
    mask: Optional[int] = None


@dataclass
class Port:
    name: str
    line: int
    net: Optional[str] = None
    direction: Optional[str] = None
    use: Optional[str] = None
    special: bool = False
    status: str = "unplaced"        # fixed, placed, cover, unplaced (of the first PORT)
    x: Optional[float] = None
    y: Optional[float] = None
    orient: Optional[str] = None
    shapes: List[PortShape] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)


@dataclass
class TrackPattern:
    line: int
    direction: str                  # "x" (vertical tracks at x positions) or "y"
    start: float                    # microns
    num_tracks: int
    step: float                     # microns
    layers: List[str] = field(default_factory=list)
    mask: Optional[int] = None
    same_mask: bool = False


@dataclass
class SiteRow:
    """ROW name site x y orient [DO nx BY ny [STEP sx sy]] ; (microns)."""
    name: str
    site: str
    x: float
    y: float
    orient: str
    num_x: int = 1
    num_y: int = 1
    step_x: float = 0.0
    step_y: float = 0.0


@dataclass
class DefDesign:
    file: str
    name: Optional[str] = None
    version: Optional[str] = None
    units: Optional[int] = None
    divider: Optional[str] = None
    busbit: Optional[str] = None
    boundary: List[float] = field(default_factory=list)    # x y x y ... microns
    ports: List[Port] = field(default_factory=list)
    tracks: List[TrackPattern] = field(default_factory=list)
    rows: List[SiteRow] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)      # keyword -> count


def parse_def(path: str) -> DefDesign:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as fh:
        return _Parser(path, fh).parse()


class _Parser:
    def __init__(self, path, fh):
        self.path = path
        self.fh = fh
        self.lineno = 0
        self.design = DefDesign(file=path)

    def error(self, text, line=None):
        raise DefParseError(text, self.path, line or self.lineno)

    def lines(self):
        for raw in self.fh:
            self.lineno += 1
            yield raw

    def parse(self) -> DefDesign:
        d = self.design
        it = self.lines()
        for raw in it:
            words = raw.split()
            if not words or words[0].startswith("#"):
                continue
            key = words[0].upper()
            if key == "END" and len(words) > 1 and words[1].upper() == "DESIGN":
                break
            if key == "PINS":
                self.pins(it)
            elif key == "ROW":
                start = self.lineno
                self.design.rows.append(self.row(_tokens(self.statement(raw, it)), start))
            elif key == "TRACKS":
                start = self.lineno
                self.design.tracks.append(self.track(_tokens(self.statement(raw, it)), start))
            elif key in SECTIONS:
                d.skipped[key] += 1
                self.skip_section(it, key)
            elif key in HEADER:
                start = self.lineno
                self.header(key, self.statement(raw, it), start)
            else:                               # GCELLGRID, ...
                d.skipped[key] += 1
                self.statement(raw, it)
        if d.units is None:
            self.error("no UNITS DISTANCE MICRONS statement before the data that needs it", 1)
        return d

    def statement(self, first, it):
        """Text of one statement, from 'first' up to its ';' (quote aware)."""
        text = first
        while not _ends_statement(text):
            try:
                text += next(it)
            except StopIteration:
                self.error("statement has no closing ';'")
        return text

    def skip_section(self, it, key):
        start = self.lineno
        for raw in it:
            words = raw.split()
            if len(words) >= 2 and words[0] == "END" and words[1].upper() == key:
                return
        self.error(f"{key} section has no 'END {key}'", start)

    def header(self, key, text, line):
        d = self.design
        words = _tokens(text)
        if key == "VERSION" and len(words) >= 2:
            d.version = words[1]
        elif key == "DESIGN" and len(words) >= 2:
            d.name = words[1]
        elif key == "DIVIDERCHAR" and len(words) >= 2:
            d.divider = words[1].strip('"')
        elif key == "BUSBITCHARS" and len(words) >= 2:
            d.busbit = words[1].strip('"')
        elif key == "UNITS":
            if len(words) < 4 or words[1].upper() != "DISTANCE" or words[2].upper() != "MICRONS":
                self.error("expected 'UNITS DISTANCE MICRONS <n> ;'", line)
            d.units = self.int(words[3], line)
        elif key == "DIEAREA":
            d.boundary = self.diearea(words[1:], line)

    def diearea(self, words, line):
        pts = self.points(words, line)
        if len(pts) == 2:                   # a rectangle given by two corners
            (x1, y1), (x2, y2) = pts
            pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        elif len(pts) < 4:
            self.error(f"DIEAREA needs 2 points (rectangle) or 4 or more (polygon), "
                       f"got {len(pts)}", line)
        return [c for p in pts for c in self.um(p)]

    def points(self, words, line):
        """Parse '( x y ) ( x y ) ...' into DBU pairs. '*' repeats the previous
        value of that coordinate (DEF polygon shorthand)."""
        pts, i = [], 0
        while i < len(words) and words[i] == "(":
            if i + 3 >= len(words) or words[i + 3] != ")":
                self.error("expected '( x y )'", line)
            x, y = words[i + 1], words[i + 2]
            px, py = pts[-1] if pts else (None, None)
            if (x == "*" and px is None) or (y == "*" and py is None):
                self.error("'*' needs a previous point", line)
            pts.append((px if x == "*" else self.int(x, line),
                        py if y == "*" else self.int(y, line)))
            i += 4
        return pts

    def um(self, p):
        return (p[0] / self.design.units, p[1] / self.design.units)

    def int(self, word, line):
        try:
            return int(word)
        except ValueError:
            try:
                return round(float(word))    # some writers emit 100.0
            except ValueError:
                self.error(f"expected a number, got '{word}'", line)

    # -- TRACKS ----------------------------------------------------------------
    def track(self, words, line) -> TrackPattern:
        """TRACKS [MASK n [SAMEMASK]] {X|Y} start DO n STEP s
        [MASK n [SAMEMASK]] [LAYER name ...] ;"""
        if self.design.units is None:
            self.error("TRACKS before UNITS DISTANCE MICRONS", line)
        w = [x for x in words[1:] if x != ";"]
        mask, same = None, False

        def take_mask(w):
            nonlocal mask, same
            if w and w[0].upper() == "MASK":
                if len(w) < 2:
                    self.error("TRACKS MASK needs a number", line)
                mask = self.int(w[1], line)
                w = w[2:]
                if w and w[0].upper() == "SAMEMASK":
                    same, w = True, w[1:]
            return w

        w = take_mask(w)
        if len(w) < 6 or w[0].upper() not in ("X", "Y") or w[2].upper() != "DO" \
                or w[4].upper() != "STEP":
            self.error("expected 'TRACKS {X|Y} <start> DO <count> STEP <step> LAYER <name> ;'",
                       line)
        direction, start, count, step = w[0].lower(), self.int(w[1], line), \
            self.int(w[3], line), self.int(w[5], line)
        if count < 1:
            self.error(f"TRACKS DO count must be 1 or more, got {count}", line)
        w = take_mask(w[6:])
        layers = []
        if w:
            if w[0].upper() != "LAYER" or len(w) < 2:
                self.error(f"unexpected '{w[0]}' in TRACKS", line)
            layers = w[1:]
        u = self.design.units
        return TrackPattern(line, direction, start / u, count, step / u, layers, mask, same)

    def row(self, words, line) -> SiteRow:
        """ROW name site x y orient [DO nx BY ny [STEP sx sy]] [+ PROPERTY ...] ;"""
        if self.design.units is None:
            self.error("ROW before UNITS DISTANCE MICRONS", line)
        w = [x for x in words[1:] if x != ";"]
        if len(w) < 5:
            self.error("expected 'ROW <name> <site> <x> <y> <orient> ...'", line)
        u = self.design.units
        row = SiteRow(w[0], w[1], self.int(w[2], line) / u, self.int(w[3], line) / u,
                      w[4].upper())
        if len(w) >= 9 and w[5].upper() == "DO" and w[7].upper() == "BY":
            row.num_x, row.num_y = self.int(w[6], line), self.int(w[8], line)
            if len(w) >= 12 and w[9].upper() == "STEP":
                row.step_x, row.step_y = self.int(w[10], line) / u, self.int(w[11], line) / u
        return row

    # -- PINS ------------------------------------------------------------------
    def pins(self, it):
        if self.design.units is None:
            self.error("PINS before UNITS DISTANCE MICRONS")
        start = self.lineno
        buf, first = "", 0
        for raw in it:
            stripped = raw.strip()
            if not buf:
                if not stripped or stripped.startswith("#"):
                    continue
                words = stripped.split()
                if words[0] == "END" and len(words) > 1 and words[1].upper() == "PINS":
                    return
                if not stripped.startswith("-"):
                    self.error(f"expected '- <pin name>' in PINS, got '{stripped[:40]}'")
                first = self.lineno
            buf += raw
            if _ends_statement(buf):
                self.design.ports.append(self.pin(_tokens(buf), first))
                buf = ""
        self.error("PINS section has no 'END PINS'", start)

    def pin(self, toks, line) -> Port:
        if len(toks) < 2 or toks[0] != "-":
            self.error("expected '- <pin name>'", line)
        port = Port(name=toks[1], line=line)
        groups = _plus_groups(toks[2:-1] if toks[-1] == ";" else toks[2:])
        current = {"shapes": [], "place": None}     # one PORT block
        blocks = [current]
        for g in groups:
            key = g[0].upper()
            args = g[1:]
            if key == "NET" and args:
                port.net = args[0]
            elif key == "SPECIAL":
                port.special = True
            elif key == "DIRECTION" and args:
                port.direction = DIRECTIONS.get(args[0].lower(), args[0].lower())
                if len(args) > 1:
                    port.extra.append("+ " + " ".join(g))
            elif key == "USE" and args:
                port.use = args[0].lower()
            elif key == "PORT":
                if current["shapes"] or current["place"]:
                    current = {"shapes": [], "place": None}
                    blocks.append(current)
            elif key in ("LAYER", "POLYGON"):
                current["shapes"].append(self.shape(key, args, line))
            elif key in ("FIXED", "PLACED", "COVER"):
                pts = self.points(args, line)
                rest = args[4:]
                if len(pts) != 1 or len(rest) != 1 or rest[0].upper() not in ORIENTS:
                    self.error(f"expected '+ {key} ( x y ) <orient>'", line)
                current["place"] = (key.lower(), pts[0], rest[0].upper())
            else:
                port.extra.append("+ " + " ".join(g))

        for block in blocks:
            place = block["place"]
            if place and port.x is None:
                port.status = place[0]
                port.x, port.y = self.um(place[1])
                port.orient = place[2]
            for layer, kind, pts, mask in block["shapes"]:
                if place:
                    t = ORIENTS[place[2]]
                    ox, oy = place[1]
                    pts = [(ox + tx, oy + ty) for tx, ty in (t(x, y) for x, y in pts)]
                if kind == "rect":       # store lower left, upper right
                    (x1, y1), (x2, y2) = pts
                    pts = [(min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))]
                port.shapes.append(PortShape(layer, kind,
                                             [c for p in pts for c in self.um(p)], mask))
        return port

    def shape(self, key, args, line):
        if not args:
            self.error(f"+ {key} needs a layer name", line)
        layer, rest, mask = args[0], args[1:], None
        while rest and rest[0] != "(":
            word = rest[0].upper()
            if word == "MASK" and len(rest) > 1:
                mask = self.int(rest[1], line)
                rest = rest[2:]
            elif word in ("SPACING", "DESIGNRULEWIDTH") and len(rest) > 1:
                rest = rest[2:]
            else:
                self.error(f"unexpected '{rest[0]}' in + {key}", line)
        pts = self.points(rest, line)
        if key == "LAYER":
            if len(pts) != 2:
                self.error(f"+ LAYER needs 2 points, got {len(pts)}", line)
            return layer, "rect", pts, mask
        if len(pts) < 3:
            self.error(f"+ POLYGON needs 3 or more points, got {len(pts)}", line)
        return layer, "polygon", pts, mask


def _tokens(text: str) -> List[str]:
    """Tokens of a statement. '#' starts a comment outside quotes, also after
    a statement on the same line ('... ; # WIDTH 192')."""
    out = []
    for line in text.splitlines():
        out.extend(_TOKEN_RE.findall(_strip_comment(line)))
    return out


def _strip_comment(line: str) -> str:
    if "#" not in line:
        return line
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == "#" and not in_quote:
            return line[:i]
    return line


def _plus_groups(toks) -> List[List[str]]:
    """Split pin tokens at '+': [['NET', 'a'], ['DIRECTION', 'INPUT'], ...]."""
    groups = []
    for tok in toks:
        if tok == "+":
            groups.append([])
        elif groups:
            groups[-1].append(tok)
    return [g for g in groups if g]


def _ends_statement(text: str) -> bool:
    """True when text holds a ';' outside double quotes."""
    if ";" not in text:
        return False
    in_quote = False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
        elif ch == ";" and not in_quote:
            return True
    return False


def polygon_area(points: List[float]) -> float:
    xs, ys = points[0::2], points[1::2]
    n = len(xs)
    return abs(sum(xs[i] * ys[(i + 1) % n] - xs[(i + 1) % n] * ys[i] for i in range(n))) / 2
