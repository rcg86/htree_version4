"""LEF parsers (tech and cell). Pure: read a file, return dataclasses, never touch the db.

Nothing is dropped. Layer statements that are not modeled as columns go to
Layer.extra verbatim; top-level statements and blocks that are not modeled go to
the extras list verbatim; each layer, via and macro keeps its full original text
in lef_text.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Top-level keywords that open a block closed by "END <name>" (or "END <keyword>"
# when the block has no name).
NAMED_BLOCKS = {"VIA", "VIARULE", "SITE", "MACRO", "NONDEFAULTRULE", "ARRAY"}
UNNAMED_BLOCKS = {"PROPERTYDEFINITIONS", "SPACING", "UNITS"}
# LEF pin DIRECTION -> the value Cadence tools report.
PIN_DIRECTIONS = {"input": "in", "output": "out", "inout": "inout", "feedthru": "feedthru"}


# Number of values of each VIARULE parameter of a generated via (LEF VIA, DEF VIAS).
VIA_PARAMETERS = {"CUTSIZE": 2, "CUTSPACING": 2, "ENCLOSURE": 4, "ROWCOL": 2, "ORIGIN": 2,
                  "OFFSET": 4}


class LefParseError(Exception):
    def __init__(self, text: str, file: str, line: int):
        super().__init__(f"{file}:{line}: {text}")
        self.text = text
        self.file = file
        self.line = line


@dataclass
class Layer:
    name: str
    line: int
    type: Optional[str] = None
    direction: Optional[str] = None
    pitch_x: Optional[float] = None
    pitch_y: Optional[float] = None
    offset_x: Optional[float] = None
    offset_y: Optional[float] = None
    width: Optional[float] = None
    min_width: Optional[float] = None
    max_width: Optional[float] = None
    area: Optional[float] = None
    min_enclosed_area: Optional[float] = None
    min_step: Optional[float] = None
    min_step_max_edges: Optional[int] = None
    min_spacing: Optional[float] = None
    extra: List[str] = field(default_factory=list)
    lef_text: str = ""


@dataclass
class Extra:
    kind: str
    line: int
    text: str


@dataclass
class Shape:
    layer: str
    type: str                     # "rect" or "polygon"
    points: List[float]           # rect: x1 y1 x2 y2; polygon: x y x y ...
    mask: Optional[int] = None


@dataclass
class ViaDef:
    """A via definition: a LEF VIA block or an entry of DEF VIAS. Shapes are
    about the via's origin (microns). A via given by VIARULE parameters has
    its shapes generated (generated_via_shapes) and keeps the rule's name."""
    name: str
    line: int
    default: bool = False         # LEF: VIA <name> DEFAULT
    shapes: List[Shape] = field(default_factory=list)
    via_rule: Optional[str] = None
    extra: List[str] = field(default_factory=list)
    lef_text: str = ""


@dataclass
class TechLef:
    file: str
    lef_version: Optional[str] = None
    db_units: Optional[int] = None
    manufacturing_grid: Optional[float] = None
    layers: List[Layer] = field(default_factory=list)
    vias: List[ViaDef] = field(default_factory=list)
    extras: List[Extra] = field(default_factory=list)


@dataclass
class Port:
    shapes: List[Shape] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)


@dataclass
class Pin:
    name: str
    line: int
    direction: Optional[str] = None
    use: Optional[str] = None
    ports: List[Port] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)


@dataclass
class Macro:
    name: str
    line: int
    cls: Optional[str] = None     # CLASS, lowercase, subclass kept ("pad inout")
    size_x: Optional[float] = None
    size_y: Optional[float] = None
    site: Optional[str] = None
    pins: List[Pin] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)
    lef_text: str = ""


@dataclass
class CellLef:
    file: str
    lef_version: Optional[str] = None
    macros: List[Macro] = field(default_factory=list)
    extras: List[Extra] = field(default_factory=list)


_TOKEN_RE = re.compile(r'\n|[^\S\n]+|#[^\n]*|"[^"]*"|;|[^\s;"#]+|"')


def _tokenize(text: str, path: str) -> List[Tuple[str, int]]:
    """Split into (token, line) pairs; a token's line is where it starts.

    '#' starts a comment outside quotes. A quoted string may span lines
    (LEF58 PROPERTY values do), and ';' or '#' inside it are plain text.
    """
    tokens = []
    lineno = 1
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok == "\n":
            lineno += 1
        elif tok == '"':           # only matches when no closing quote follows
            raise LefParseError("quoted string has no closing '\"'", path, lineno)
        elif tok[0] == '"':
            tokens.append((tok, lineno))
            lineno += tok.count("\n")
        elif not tok[0].isspace() and tok[0] != "#":
            tokens.append((tok, lineno))
    return tokens


class _Parser:
    def __init__(self, path: str, text: str):
        self.path = path
        self.lines = text.splitlines()
        self.toks = _tokenize(text, path)
        self.pos = 0

    # -- token helpers -------------------------------------------------------
    def error(self, text: str, line: Optional[int] = None):
        if line is None:
            line = self.toks[self.pos][1] if self.pos < len(self.toks) else len(self.lines)
        raise LefParseError(text, self.path, line)

    def peek(self) -> Optional[str]:
        return self.toks[self.pos][0] if self.pos < len(self.toks) else None

    def next(self) -> Tuple[str, int]:
        if self.pos >= len(self.toks):
            self.error("unexpected end of file")
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def statement(self) -> Tuple[List[str], int, int]:
        """Read tokens up to and including ';'. Returns (tokens, first, last line)."""
        words = []
        first = self.toks[self.pos][1] if self.pos < len(self.toks) else len(self.lines)
        while True:
            tok, line = self.next()
            if tok == ";":
                return words, first, line
            words.append(tok)

    def raw(self, first: int, last: int) -> str:
        return "\n".join(self.lines[first - 1:last])

    def number(self, word: str, line: int, as_int: bool = False):
        try:
            return int(word) if as_int else float(word)
        except ValueError:
            self.error(f"expected a number, got '{word}'", line)

    # -- grammar -------------------------------------------------------------
    def parse(self) -> TechLef:
        tech = TechLef(file=self.path)
        names = set()
        while self.pos < len(self.toks):
            kw, line = self.toks[self.pos]
            key = kw.upper()
            if key == "END":
                self.pos += 1
                tok, eline = self.next()
                if tok.upper() == "LIBRARY":
                    return tech
                self.error(f"unexpected 'END {tok}'", eline)
            elif key == "VERSION":
                words, _, _ = self.statement()
                if len(words) != 2:
                    self.error("VERSION needs one value", line)
                tech.lef_version = words[1]
            elif key == "MANUFACTURINGGRID":
                words, _, _ = self.statement()
                if len(words) != 2:
                    self.error("MANUFACTURINGGRID needs one value", line)
                tech.manufacturing_grid = self.number(words[1], line)
            elif key == "UNITS":
                self.units(tech)
            elif key == "LAYER":
                layer = self.layer()
                if layer.name in names:
                    self.error(f"duplicate layer '{layer.name}'", layer.line)
                names.add(layer.name)
                tech.layers.append(layer)
            elif key == "VIA":
                tech.vias.append(self.via())
            elif key in NAMED_BLOCKS or key in UNNAMED_BLOCKS:
                tech.extras.append(self.block(key))
            else:
                words, first, last = self.statement()
                tech.extras.append(Extra(key, first, self.raw(first, last)))
        # Reaching EOF without END LIBRARY is accepted (LEF 5.6+ makes it optional).
        return tech

    def parse_cells(self) -> CellLef:
        """Cell LEF: MACRO blocks become Macros; everything else goes to extras."""
        lib = CellLef(file=self.path)
        while self.pos < len(self.toks):
            kw, line = self.toks[self.pos]
            key = kw.upper()
            if key == "END":
                self.pos += 1
                tok, eline = self.next()
                if tok.upper() == "LIBRARY":
                    return lib
                self.error(f"unexpected 'END {tok}'", eline)
            elif key == "VERSION":
                words, _, _ = self.statement()
                if len(words) != 2:
                    self.error("VERSION needs one value", line)
                lib.lef_version = words[1]
            elif key == "MACRO":
                lib.macros.append(self.macro())
            elif key in NAMED_BLOCKS or key in UNNAMED_BLOCKS or key == "LAYER":
                lib.extras.append(self.block(key))
            else:
                words, first, last = self.statement()
                lib.extras.append(Extra(key, first, self.raw(first, last)))
        return lib

    def macro(self) -> Macro:
        _, first = self.next()  # MACRO
        name, _ = self.next()
        macro = Macro(name=name, line=first)
        while True:
            tok = self.peek()
            if tok is None:
                self.error(f"MACRO {name} has no 'END {name}'", first)
            key = tok.upper()
            if key == "END":
                self.next()
                end, last = self.next()
                if end != name:
                    self.error(f"expected 'END {name}', got 'END {end}'", last)
                macro.lef_text = self.raw(first, last)
                return macro
            if key == "PIN":
                macro.pins.append(self.pin())
            elif key in ("OBS", "DENSITY"):
                self.skip_to_bare_end(key)      # kept in lef_text
            else:
                words, line, _ = self.statement()
                if not self.macro_statement(macro, words, line):
                    macro.extra.append(" ".join(words) + " ;")

    def macro_statement(self, macro: Macro, words: List[str], line: int) -> bool:
        key = words[0].upper() if words else ""
        if key == "CLASS" and len(words) >= 2:
            macro.cls = " ".join(w.lower() for w in words[1:])
            return True
        if key == "SIZE" and len(words) == 4 and words[2].upper() == "BY":
            macro.size_x = self.number(words[1], line)
            macro.size_y = self.number(words[3], line)
            return True
        if key == "SITE" and len(words) == 2 and macro.site is None:
            macro.site = words[1]
            return True
        return False

    def pin(self) -> Pin:
        _, first = self.next()  # PIN
        name, _ = self.next()
        pin = Pin(name=name, line=first)
        while True:
            tok = self.peek()
            if tok is None:
                self.error(f"PIN {name} has no 'END {name}'", first)
            key = tok.upper()
            if key == "END":
                self.next()
                end, last = self.next()
                if end != name:
                    self.error(f"expected 'END {name}' for PIN {name}, got 'END {end}'", last)
                return pin
            if key == "PORT":
                pin.ports.append(self.port())
                continue
            words, line, _ = self.statement()
            key = words[0].upper() if words else ""
            if key in ("DIRECTION", "USE") and len(words) >= 2:
                value = words[1].lower()
                if key == "DIRECTION":          # Cadence values: in, out, inout, feedthru
                    value = PIN_DIRECTIONS.get(value, value)
                setattr(pin, key.lower(), value)
                if len(words) > 2:              # DIRECTION OUTPUT TRISTATE: keep it all
                    pin.extra.append(" ".join(words) + " ;")
            else:
                pin.extra.append(" ".join(words) + " ;")

    def port(self) -> Port:
        _, first = self.next()  # PORT
        port = Port()
        layer = None
        while True:
            tok = self.peek()
            if tok is None:
                self.error("PORT has no END", first)
            if tok.upper() == "END":
                self.next()
                return port
            words, line, _ = self.statement()
            key = words[0].upper() if words else ""
            if key == "LAYER" and len(words) >= 2:
                layer = words[1]
                if len(words) > 2:              # SPACING, DESIGNRULEWIDTH, ...
                    port.extra.append(" ".join(words) + " ;")
            elif key in ("RECT", "POLYGON") and "ITERATE" not in (w.upper() for w in words):
                port.shapes.append(self.shape(key, words[1:], layer, line))
            else:
                port.extra.append(" ".join(words) + " ;")

    def shape(self, key: str, args: List[str], layer: Optional[str], line: int,
              owner: str = "PORT") -> Shape:
        if layer is None:
            self.error(f"{key} before any LAYER in {owner}", line)
        mask = None
        if args and args[0].upper() == "MASK":
            if len(args) < 2:
                self.error(f"{key} MASK needs a number", line)
            mask = self.number(args[1], line, as_int=True)
            args = args[2:]
        points = [self.number(a, line) for a in args]
        if key == "RECT" and len(points) != 4:
            self.error(f"RECT needs 4 numbers, got {len(points)}", line)
        if key == "POLYGON" and (len(points) < 6 or len(points) % 2):
            self.error(f"POLYGON needs 3 or more x y pairs, got {len(points)} numbers", line)
        return Shape(layer, key.lower(), points, mask)

    def skip_to_bare_end(self, key: str):
        _, first = self.next()
        while True:
            tok = self.peek()
            if tok is None:
                self.error(f"{key} has no END", first)
            if tok.upper() == "END":
                self.next()
                return
            self.statement()

    def units(self, tech: TechLef):
        _, first = self.next()  # UNITS
        while True:
            tok = self.peek()
            if tok is None:
                self.error("UNITS block has no END UNITS", first)
            if tok.upper() == "END":
                self.next()
                end, eline = self.next()
                if end.upper() != "UNITS":
                    self.error(f"expected 'END UNITS', got 'END {end}'", eline)
                return
            words, sfirst, slast = self.statement()
            if len(words) == 3 and words[0].upper() == "DATABASE" and words[1].upper() == "MICRONS":
                tech.db_units = self.number(words[2], sfirst, as_int=True)
            else:
                tech.extras.append(Extra("UNITS", sfirst, self.raw(sfirst, slast)))

    def block(self, key: str) -> Extra:
        _, first = self.next()
        if key in NAMED_BLOCKS or key == "LAYER":
            name, _ = self.next()
        else:
            name = key
        while self.pos < len(self.toks):
            tok, line = self.next()
            after = self.peek()
            if tok.upper() == "END" and after is not None and (
                    after == name or (key in UNNAMED_BLOCKS and after.upper() == name)):
                _, last = self.next()
                return Extra(key, first, self.raw(first, last))
        self.error(f"{key} block has no 'END {name}'", first)

    def via(self) -> ViaDef:
        """VIA <name> [DEFAULT] ... END <name>: LAYER / RECT / POLYGON shapes,
        or the VIARULE parameters the shapes are generated from."""
        _, first = self.next()  # VIA
        name, _ = self.next()
        via = ViaDef(name=name, line=first)
        if (self.peek() or "").upper() in ("DEFAULT", "GENERATED"):
            via.default = self.next()[0].upper() == "DEFAULT"
        layer, params = None, {}
        while True:
            tok = self.peek()
            if tok is None:
                self.error(f"VIA {name} has no 'END {name}'", first)
            if tok.upper() == "END":
                self.next()
                end, last = self.next()
                if end != name:
                    self.error(f"expected 'END {name}', got 'END {end}'", last)
                via.lef_text = self.raw(first, last)
                break
            words, line, _ = self.statement()
            key = words[0].upper() if words else ""
            if key == "LAYER" and len(words) == 2:
                layer = words[1]
            elif key in ("RECT", "POLYGON"):
                via.shapes.append(self.shape(key, words[1:], layer, line, "VIA"))
            elif key == "VIARULE" and len(words) == 2:
                via.via_rule = words[1]
            elif key == "LAYERS" and len(words) == 4:
                params["layers"] = words[1:]
            elif key in VIA_PARAMETERS and len(words) == 1 + VIA_PARAMETERS[key]:
                params[key.lower()] = [self.number(w, line) for w in words[1:]]
            else:
                via.extra.append(" ".join(words) + " ;")
        if via.via_rule is not None:
            missing = [k for k in ("layers", "cutsize", "cutspacing", "enclosure")
                       if k not in params]
            if missing:
                self.error(f"VIA {name} names VIARULE {via.via_rule} but has no "
                           f"{' '.join(k.upper() for k in missing)}", first)
            via.shapes = generated_via_shapes(**params)
        return via

    def layer(self) -> Layer:
        _, first = self.next()  # LAYER
        name, _ = self.next()
        layer = Layer(name=name, line=first)
        while True:
            tok = self.peek()
            if tok is None:
                self.error(f"LAYER {name} has no 'END {name}'", first)
            if tok.upper() == "END":
                self.next()
                end, last = self.next()
                if end != name:
                    self.error(f"expected 'END {name}', got 'END {end}'", last)
                layer.lef_text = self.raw(first, last)
                return layer
            words, sfirst, slast = self.statement()
            if not self.layer_statement(layer, words, sfirst):
                layer.extra.append(" ".join(words) + " ;")

    def layer_statement(self, layer: Layer, words: List[str], line: int) -> bool:
        """Apply a modeled statement. Returns False if it is not modeled."""
        if not words:
            return False
        key = words[0].upper()
        args = words[1:]
        if key in ("TYPE", "DIRECTION") and len(args) == 1:
            setattr(layer, key.lower(), args[0].lower())
            return True
        if key in ("PITCH", "OFFSET") and len(args) in (1, 2):
            x = self.number(args[0], line)
            y = self.number(args[-1], line)
            setattr(layer, f"{key.lower()}_x", x)
            setattr(layer, f"{key.lower()}_y", y)
            return True
        simple = {"WIDTH": "width", "MINWIDTH": "min_width", "MAXWIDTH": "max_width",
                  "AREA": "area", "MINENCLOSEDAREA": "min_enclosed_area"}
        if key in simple and len(args) == 1:
            setattr(layer, simple[key], self.number(args[0], line))
            return True
        if key == "MINSTEP" and len(args) == 1:
            layer.min_step = self.number(args[0], line)
            return True
        if key == "MINSTEP" and len(args) == 3 and args[1].upper() == "MAXEDGES":
            layer.min_step = self.number(args[0], line)
            layer.min_step_max_edges = self.number(args[2], line, as_int=True)
            return True
        if key == "SPACING" and len(args) == 1:
            value = self.number(args[0], line)
            if layer.min_spacing is None or value < layer.min_spacing:
                layer.min_spacing = value
            return True
        return False


def generated_via_shapes(layers, cutsize, cutspacing, enclosure, rowcol=(1, 1),
                         origin=(0, 0), offset=(0, 0, 0, 0)) -> List[Shape]:
    """The shapes of a via given by VIARULE parameters (LEF / DEF 5.8), in
    microns: layers (bottom, cut, top); a rowcol (rows, columns) array of
    cutsize cuts cutspacing apart, centred on origin; each metal the array
    grown by its enclosure (x bottom, y bottom, x top, y top) and moved by
    its offset. A PATTERN (cuts left out) is not applied: every cut is made."""
    bottom, cut, top = layers
    rows, cols = int(rowcol[0]), int(rowcol[1])
    w = cols * cutsize[0] + (cols - 1) * cutspacing[0]
    h = rows * cutsize[1] + (rows - 1) * cutspacing[1]
    ox, oy = origin
    r = lambda *v: [round(c, 6) for c in v]
    shapes = [Shape(bottom, "rect", r(ox + offset[0] - w / 2 - enclosure[0],
                                      oy + offset[1] - h / 2 - enclosure[1],
                                      ox + offset[0] + w / 2 + enclosure[0],
                                      oy + offset[1] + h / 2 + enclosure[1]))]
    for j in range(rows):
        for i in range(cols):
            x = ox - w / 2 + i * (cutsize[0] + cutspacing[0])
            y = oy - h / 2 + j * (cutsize[1] + cutspacing[1])
            shapes.append(Shape(cut, "rect", r(x, y, x + cutsize[0], y + cutsize[1])))
    shapes.append(Shape(top, "rect", r(ox + offset[2] - w / 2 - enclosure[2],
                                       oy + offset[3] - h / 2 - enclosure[3],
                                       ox + offset[2] + w / 2 + enclosure[2],
                                       oy + offset[3] + h / 2 + enclosure[3])))
    return shapes


def parse_tech_lef(path: str) -> TechLef:
    with open(path) as fh:
        text = fh.read()
    return _Parser(path, text).parse()


def parse_cell_lef(path: str) -> CellLef:
    with open(path) as fh:
        text = fh.read()
    return _Parser(path, text).parse_cells()
