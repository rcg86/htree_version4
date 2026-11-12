"""SQLite design database. Lives in memory; write_db/read_db move it to and from disk."""

import os
import sqlite3

from core.lef import CellLef, TechLef

SCHEMA_VERSION = 20  # 2: read_lef; 3: lib pins/shapes; 4: spine specs; 5: read_def; 6: tracks;
                     # 7: track assignments; 8: instances; 9: route rules;
                     # 10: level_pitch, deviation, built spines; 11: spine cell location;
                     # 12: named route rules with several layers, net route rules;
                     # 13: route_pin straps; 14: route_pin pin wires;
                     # 15: spine origin and -mirror; 16: route_net wires;
                     # 17: strap max_extension; 18: route_net shields; 19: DEF rows;
                     # 20: spine path and straight-spine coordinates (move_spine_to_boundary)

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE tech (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    lef_version TEXT,
    db_units INTEGER,
    manufacturing_grid REAL,
    file TEXT
);

CREATE TABLE layer (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    direction TEXT,
    pitch_x REAL, pitch_y REAL,
    offset_x REAL, offset_y REAL,
    width REAL, min_width REAL, max_width REAL,
    area REAL, min_enclosed_area REAL,
    min_step REAL, min_step_max_edges INTEGER,
    min_spacing REAL,
    lef_text TEXT
);

CREATE TABLE layer_extra (
    layer_id INTEGER REFERENCES layer(id),
    seq INTEGER,
    statement TEXT
);

CREATE TABLE tech_extra (
    seq INTEGER PRIMARY KEY,
    kind TEXT,
    line INTEGER,
    text TEXT
);

CREATE TABLE lef_file (
    id INTEGER PRIMARY KEY,
    file TEXT,
    lef_version TEXT
);

CREATE TABLE lib_cell (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    file_id INTEGER REFERENCES lef_file(id),
    line INTEGER,
    class TEXT,
    size_x REAL, size_y REAL,
    site TEXT,
    lef_text TEXT
);

CREATE TABLE lib_pin (
    id INTEGER PRIMARY KEY,
    cell_id INTEGER REFERENCES lib_cell(id),
    name TEXT NOT NULL,
    direction TEXT,
    use TEXT,
    UNIQUE (cell_id, name)
);

CREATE TABLE lib_port (
    id INTEGER PRIMARY KEY,
    pin_id INTEGER REFERENCES lib_pin(id),
    seq INTEGER                          -- 1-based within the pin
);

CREATE TABLE layer_shape (
    id INTEGER PRIMARY KEY,
    port_id INTEGER REFERENCES lib_port(id),
    seq INTEGER,                         -- 1-based within the port
    layer TEXT,
    type TEXT,                           -- rect | polygon
    points TEXT,                         -- "x1 y1 x2 y2" or "x y x y ..."
    mask INTEGER
);
CREATE INDEX layer_shape_port ON layer_shape (port_id);

-- Unmodeled statements, verbatim. owner is lib_cell, lib_pin or lib_port.
CREATE TABLE lib_extra (
    owner TEXT,
    owner_id INTEGER,
    seq INTEGER,
    statement TEXT
);

CREATE TABLE spine_spec (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    file TEXT,
    line INTEGER,
    type TEXT, units TEXT, point TEXT, root_net TEXT,
    -- NUMERIC keeps numbers as written in the YAML: 1020 stays 1020, not 1020.0
    max_drive_length NUMERIC, count_stub_in_drive TEXT,
    origin_x NUMERIC, origin NUMERIC, level_pitch NUMERIC, deviation NUMERIC,
    orientation TEXT, span NUMERIC,
    stub_count INTEGER, stub_gap NUMERIC, stub_tap TEXT,
    stub_order TEXT,                     -- Tcl list text
    yaml_text TEXT
);

CREATE TABLE spine_level (
    id INTEGER PRIMARY KEY,
    spec_id INTEGER REFERENCES spine_spec(id),
    name TEXT NOT NULL
);

CREATE TABLE spine_cell (
    id INTEGER PRIMARY KEY,
    level_id INTEGER REFERENCES spine_level(id),
    name TEXT NOT NULL,
    input TEXT,
    output TEXT,
    location NUMERIC            -- um along the spine from the cell's driver
);

-- Unmodeled spine spec keys, verbatim. owner is spine_spec or spine_cell.
CREATE TABLE spine_extra (
    owner TEXT,
    owner_id INTEGER,
    seq INTEGER,
    statement TEXT
);

CREATE TABLE design (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    file TEXT,
    def_version TEXT,
    units INTEGER,                       -- DEF database units per micron
    boundary TEXT                        -- "x y x y ..." microns
);

CREATE TABLE port (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    net TEXT, direction TEXT, use TEXT,
    special TEXT,                        -- true | false
    status TEXT,                         -- fixed | placed | cover | unplaced
    x REAL, y REAL, orient TEXT
);

CREATE TABLE port_shape (
    id INTEGER PRIMARY KEY,
    port_id INTEGER REFERENCES port(id),
    seq INTEGER,                         -- 1-based within the port
    layer TEXT,
    type TEXT,                           -- rect | polygon
    points TEXT,                         -- microns, absolute
    mask INTEGER
);
CREATE INDEX port_shape_port ON port_shape (port_id);

CREATE TABLE track_pattern (
    id INTEGER PRIMARY KEY,              -- 1-based, file order
    line INTEGER,
    direction TEXT,                      -- x | y (as in DEF TRACKS X / Y)
    start REAL, num_tracks INTEGER, step REAL,   -- microns
    mask INTEGER,
    same_mask TEXT,                      -- true | false
    layers TEXT                          -- space separated
);

-- DEF ROW statements: the placement sites (microns).
CREATE TABLE site_row (
    id INTEGER PRIMARY KEY,
    name TEXT, site TEXT,
    x REAL, y REAL, orient TEXT,
    num_x INTEGER, num_y INTEGER, step_x REAL, step_y REAL
);
CREATE INDEX site_row_y ON site_row (y);

-- assign_track_for_route: a repeating net pattern over a layer's routing
-- tracks. Kept as a rule; track positions come from track_pattern.
CREATE TABLE track_assignment (
    id INTEGER PRIMARY KEY,
    layer TEXT UNIQUE NOT NULL,
    direction TEXT,                      -- x | y: which DEF TRACKS are numbered
    pattern TEXT                         -- space separated; '-' = any signal
);

-- create_inst: placed instances of library cells. x, y: lower-left corner
-- of the placed cell (microns), as in DEF placement.
CREATE TABLE inst (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    ref_cell TEXT NOT NULL,
    x REAL, y REAL,
    orient TEXT,
    status TEXT                          -- placed | fixed | cover (set_db .place_status)
);

-- create_route_rule: a named rule; per layer, the wire width and the
-- spacing kept on each side of a route (microns). One row per (rule, layer).
CREATE TABLE route_rule (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    layer TEXT NOT NULL,
    width REAL NOT NULL,
    spacing REAL NOT NULL,
    spacing_given TEXT,                  -- true: -spacing; false: from tech
    UNIQUE (name, layer)
);

-- set_db <nets> .route_rule: the rule a net is routed with. Keyed by net
-- name, so a net rebuilt with the same name keeps it. No row: the default rule.
CREATE TABLE net_route_rule (
    net TEXT PRIMARY KEY,
    rule TEXT NOT NULL
);

-- create_spine -build: a built spine. Its cells are inst rows; spine_member
-- maps them back to the spec. Stubs and net routes are centre lines (microns).
-- along / across: where each sits on the straight spine as built, in um from
-- -location along the spine and across it (+ up / right); these never change.
-- move_spine_to_boundary bends the spine along path and maps them onto it
-- (core/spine_snake.py).
CREATE TABLE spine (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    spec TEXT,
    orientation TEXT,
    build_direction TEXT,
    x REAL, y REAL,                      -- -location: the root cell is origin from it
    origin REAL,                         -- um along the spine from -location to the root
    mirror INTEGER,                      -- 1: a mirrored copy on the other side (-mirror)
    ref_cell TEXT,
    level_pitch REAL, deviation REAL, max_drive REAL,
    stub_length REAL,
    path TEXT                            -- "x y x y ...": the stub line, bottom / left end
                                         -- first, once bent; NULL: straight as built
);

CREATE TABLE spine_member (
    spine_id INTEGER REFERENCES spine(id),
    inst TEXT,
    level TEXT,
    cell TEXT,
    driver TEXT,                         -- inst name; empty for the root
    along REAL, across REAL              -- the cell centre on the straight spine
);

CREATE TABLE spine_stub (
    id INTEGER PRIMARY KEY,
    spine_id INTEGER REFERENCES spine(id),
    name TEXT,
    driver TEXT,                         -- inst name of the leaf
    points TEXT,                         -- "x1 y1 x2 y2"; more points when bent
    ref TEXT                             -- "<along lo> <along hi> <across>"
);

CREATE TABLE spine_net (
    id INTEGER PRIMARY KEY,
    spine_id INTEGER REFERENCES spine(id),
    name TEXT,
    driver TEXT,                         -- inst name
    loads TEXT,                          -- inst names, or the stub name
    grp TEXT,                            -- L1-L2, L2-L3, ..., L4-stubs
    length REAL,
    detour REAL,
    route TEXT,                          -- "x1 y1 x2 y2" per segment, ';' between
    ref_route TEXT                       -- "along across along across" per segment
);

-- route_pin: horizontal straps over an instance, numbered from the top.
CREATE TABLE strap (
    id INTEGER PRIMARY KEY,
    inst TEXT NOT NULL,
    seq INTEGER,                         -- 1 = top strap
    net TEXT,
    layer TEXT,
    rect TEXT,                           -- "x1 y1 x2 y2" (microns)
    max_extension REAL                   -- route_net may lengthen it this far each side
);

-- route_pin: a vertical wire from a cell pin to the strap of its net.
CREATE TABLE pin_wire (
    id INTEGER PRIMARY KEY,
    inst TEXT NOT NULL,
    pin TEXT,
    net TEXT,
    layer TEXT,
    rect TEXT,                           -- "x1 y1 x2 y2" (microns)
    strap INTEGER                        -- strap seq it reaches
);

-- route_net: the wires of a routed net, and the boxes where two of them
-- (or a wire and a route_pin strap) cross. Keyed by net name.
CREATE TABLE net_wire (
    id INTEGER PRIMARY KEY,
    net TEXT NOT NULL,
    seq INTEGER,                         -- 1, 2, ... per net
    kind TEXT,                           -- wire | extension | cross | shield |
                                         -- shield_ext | stub | stub_cross | stub_shield |
                                         -- pg_ext | pg_cross (net pg:<inst>)
    layer TEXT,                          -- a cross: "<layer>/<layer>"
    rect TEXT,                           -- "x1 y1 x2 y2" (microns)
    shield_net TEXT                      -- a shield: its power net (VDD_SOC, VSS)
);

CREATE TABLE port_extra (
    port_id INTEGER REFERENCES port(id),
    seq INTEGER,
    statement TEXT
);

CREATE TABLE lef_extra (
    seq INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES lef_file(id),
    kind TEXT,
    line INTEGER,
    text TEXT
);
"""

LAYER_COLUMNS = ["name", "type", "direction", "pitch_x", "pitch_y", "offset_x", "offset_y",
                 "width", "min_width", "max_width", "area", "min_enclosed_area",
                 "min_step", "min_step_max_edges", "min_spacing", "lef_text"]


def _num(value: float) -> str:
    """Shortest text that reads back as the same float ('3.12', '0')."""
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


class SchemaMismatch(Exception):
    pass


class Database:
    def __init__(self):
        # Selected object handles, in selection order. Session state, not design
        # data: kept in memory only, never written by write_db.
        self.selection = []
        self.conn = self._new_memory()
        with self.conn:
            self.conn.executescript(SCHEMA)
            self.conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    @staticmethod
    def _new_memory() -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

    # -- tech ----------------------------------------------------------------
    def has_tech(self) -> bool:
        return self.conn.execute("SELECT 1 FROM tech").fetchone() is not None

    def load_tech(self, tech: TechLef):
        """Replace all tech data with tech, atomically."""
        with self.conn:
            for table in ("layer_extra", "layer", "tech_extra", "tech"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute(
                "INSERT INTO tech (id, lef_version, db_units, manufacturing_grid, file) "
                "VALUES (1, ?, ?, ?, ?)",
                (tech.lef_version, tech.db_units, tech.manufacturing_grid, os.path.abspath(tech.file)))
            cols = ", ".join(LAYER_COLUMNS)
            marks = ", ".join("?" for _ in LAYER_COLUMNS)
            for idx, layer in enumerate(tech.layers, start=1):
                self.conn.execute(f"INSERT INTO layer (id, {cols}) VALUES (?, {marks})",
                                  [idx] + [getattr(layer, c) for c in LAYER_COLUMNS])
                for seq, stmt in enumerate(layer.extra, start=1):
                    self.conn.execute("INSERT INTO layer_extra VALUES (?, ?, ?)", (idx, seq, stmt))
            for seq, extra in enumerate(tech.extras, start=1):
                self.conn.execute("INSERT INTO tech_extra VALUES (?, ?, ?, ?)",
                                  (seq, extra.kind, extra.line, extra.text))

    def tech_row(self):
        return self.conn.execute("SELECT * FROM tech").fetchone()

    def layer_names(self):
        return [r["name"] for r in self.conn.execute("SELECT name FROM layer ORDER BY id")]

    def layer_row(self, name: str):
        return self.conn.execute("SELECT * FROM layer WHERE name = ?", (name,)).fetchone()

    def layer_extra(self, layer_id: int):
        return [r["statement"] for r in self.conn.execute(
            "SELECT statement FROM layer_extra WHERE layer_id = ? ORDER BY seq", (layer_id,))]

    def tech_extra(self):
        return self.conn.execute("SELECT kind, line, text FROM tech_extra ORDER BY seq").fetchall()

    # -- physical library (cell LEF) ------------------------------------------
    def has_library(self) -> bool:
        return self.conn.execute("SELECT 1 FROM lef_file").fetchone() is not None

    def add_cell_lef(self, lib: CellLef):
        """Append a cell LEF, atomically. Macros whose name is already present
        are skipped; their names are returned."""
        skipped = []
        with self.conn:
            cur = self.conn.execute("INSERT INTO lef_file (file, lef_version) VALUES (?, ?)",
                                    (os.path.abspath(lib.file), lib.lef_version))
            file_id = cur.lastrowid
            for macro in lib.macros:
                if self.lib_cell_row(macro.name) is not None:
                    skipped.append(macro.name)
                    continue
                self._add_macro(file_id, macro)
            for extra in lib.extras:
                self.conn.execute("INSERT INTO lef_extra (file_id, kind, line, text) "
                                  "VALUES (?, ?, ?, ?)", (file_id, extra.kind, extra.line, extra.text))
        return skipped

    def _add_macro(self, file_id, macro):
        ex = self.conn.execute
        cell_id = ex("INSERT INTO lib_cell (name, file_id, line, class, size_x, size_y, site, "
                     "lef_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (macro.name, file_id, macro.line, macro.cls, macro.size_x, macro.size_y,
                      macro.site, macro.lef_text)).lastrowid
        self._add_extra("lib_cell", cell_id, macro.extra)
        for pin in macro.pins:
            pin_id = ex("INSERT INTO lib_pin (cell_id, name, direction, use) VALUES (?, ?, ?, ?)",
                        (cell_id, pin.name, pin.direction, pin.use)).lastrowid
            self._add_extra("lib_pin", pin_id, pin.extra)
            for pseq, port in enumerate(pin.ports, start=1):
                port_id = ex("INSERT INTO lib_port (pin_id, seq) VALUES (?, ?)",
                             (pin_id, pseq)).lastrowid
                self._add_extra("lib_port", port_id, port.extra)
                for sseq, shape in enumerate(port.shapes, start=1):
                    ex("INSERT INTO layer_shape (port_id, seq, layer, type, points, mask) "
                       "VALUES (?, ?, ?, ?, ?, ?)",
                       (port_id, sseq, shape.layer, shape.type,
                        " ".join(_num(v) for v in shape.points), shape.mask))

    def _add_extra(self, owner, owner_id, statements):
        for seq, stmt in enumerate(statements, start=1):
            self.conn.execute("INSERT INTO lib_extra VALUES (?, ?, ?, ?)",
                              (owner, owner_id, seq, stmt))

    def lib_extra(self, owner, owner_id):
        return [r["statement"] for r in self.conn.execute(
            "SELECT statement FROM lib_extra WHERE owner = ? AND owner_id = ? ORDER BY seq",
            (owner, owner_id))]

    def lef_files(self):
        return [r["file"] for r in self.conn.execute("SELECT file FROM lef_file ORDER BY id")]

    def lib_cell_names(self):
        return [r["name"] for r in self.conn.execute("SELECT name FROM lib_cell ORDER BY id")]

    def lib_cell_row(self, name: str):
        return self.conn.execute(
            "SELECT lib_cell.*, lef_file.file AS file FROM lib_cell "
            "JOIN lef_file ON lef_file.id = lib_cell.file_id WHERE name = ?", (name,)).fetchone()

    def lib_pin_names(self, cell_id: int):
        return [r["name"] for r in self.conn.execute(
            "SELECT name FROM lib_pin WHERE cell_id = ? ORDER BY id", (cell_id,))]

    def all_lib_pins(self):
        """(cell, pin) for every pin, in library order."""
        return [(r[0], r[1]) for r in self.conn.execute(
            "SELECT c.name, p.name FROM lib_pin p JOIN lib_cell c ON c.id = p.cell_id "
            "ORDER BY p.id")]

    def lib_pin_row(self, cell: str, pin: str):
        return self.conn.execute(
            "SELECT p.* FROM lib_pin p JOIN lib_cell c ON c.id = p.cell_id "
            "WHERE c.name = ? AND p.name = ?", (cell, pin)).fetchone()

    def lib_port_seqs(self, pin_id: int):
        return [r["seq"] for r in self.conn.execute(
            "SELECT seq FROM lib_port WHERE pin_id = ? ORDER BY seq", (pin_id,))]

    def lib_port_row(self, pin_id: int, seq: int):
        return self.conn.execute("SELECT * FROM lib_port WHERE pin_id = ? AND seq = ?",
                                 (pin_id, seq)).fetchone()

    def shape_rows(self, port_id: int):
        return self.conn.execute("SELECT * FROM layer_shape WHERE port_id = ? ORDER BY seq",
                                 (port_id,)).fetchall()

    def pin_layers(self, pin_id: int):
        """Distinct shape layers of a pin, in first-use order."""
        return [r["layer"] for r in self.conn.execute(
            "SELECT s.layer FROM layer_shape s JOIN lib_port p ON p.id = s.port_id "
            "WHERE p.pin_id = ? GROUP BY s.layer ORDER BY MIN(s.id)", (pin_id,))]

    def pin_shape_layer_counts(self, file_id=None):
        """{layer: shape count} over pin shapes (of one file, or all)."""
        sql = ("SELECT s.layer, COUNT(*) FROM layer_shape s JOIN lib_port pt ON pt.id = s.port_id "
               "JOIN lib_pin p ON p.id = pt.pin_id JOIN lib_cell c ON c.id = p.cell_id ")
        args = ()
        if file_id is not None:
            sql += "WHERE c.file_id = ? "
            args = (file_id,)
        sql += "GROUP BY s.layer ORDER BY MIN(s.id)"
        return {r[0]: r[1] for r in self.conn.execute(sql, args)}

    def last_lef_file_id(self):
        return self.conn.execute("SELECT MAX(id) FROM lef_file").fetchone()[0]

    def lef_extra(self):
        return self.conn.execute(
            "SELECT lef_file.file AS file, kind, line, text FROM lef_extra "
            "JOIN lef_file ON lef_file.id = lef_extra.file_id ORDER BY seq").fetchall()

    # -- spine specs -----------------------------------------------------------
    SPINE_COLUMNS = ["type", "units", "point", "root_net", "max_drive_length",
                     "count_stub_in_drive", "origin_x", "origin", "level_pitch", "deviation",
                     "orientation", "span", "stub_count", "stub_gap", "stub_tap", "stub_order"]

    def has_spine_specs(self) -> bool:
        return self.conn.execute("SELECT 1 FROM spine_spec").fetchone() is not None

    def add_spine_specs(self, path: str, specs, list_text):
        """Add specs, atomically. A spec whose name is present replaces the old
        one; the replaced names are returned. list_text(list) -> Tcl list text."""
        replaced = []
        with self.conn:
            for spec in specs:
                old = self.spine_spec_row(spec.name)
                if old is not None:
                    replaced.append(spec.name)
                    self._delete_spine_spec(old["id"])
                values = []
                for col in self.SPINE_COLUMNS:
                    v = getattr(spec, col)
                    if isinstance(v, bool):
                        v = "true" if v else "false"
                    elif isinstance(v, list):
                        v = list_text(v)
                    values.append(v)
                cols = ", ".join(self.SPINE_COLUMNS)
                marks = ", ".join("?" for _ in self.SPINE_COLUMNS)
                spec_id = self.conn.execute(
                    f"INSERT INTO spine_spec (name, file, line, yaml_text, {cols}) "
                    f"VALUES (?, ?, ?, ?, {marks})",
                    [spec.name, os.path.abspath(path), spec.line, spec.yaml_text] + values
                ).lastrowid
                self._add_spine_extra("spine_spec", spec_id, spec.extra)
                for level in spec.levels:
                    level_id = self.conn.execute(
                        "INSERT INTO spine_level (spec_id, name) VALUES (?, ?)",
                        (spec_id, level.name)).lastrowid
                    for cell in level.cells:
                        cell_id = self.conn.execute(
                            "INSERT INTO spine_cell (level_id, name, input, output, location) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (level_id, cell.name, cell.input, cell.output,
                             cell.location)).lastrowid
                        self._add_spine_extra("spine_cell", cell_id, cell.extra)
        return replaced

    def _delete_spine_spec(self, spec_id):
        ex = self.conn.execute
        cells = "SELECT c.id FROM spine_cell c JOIN spine_level l ON l.id = c.level_id " \
                "WHERE l.spec_id = ?"
        ex(f"DELETE FROM spine_extra WHERE owner = 'spine_cell' AND owner_id IN ({cells})",
           (spec_id,))
        ex("DELETE FROM spine_extra WHERE owner = 'spine_spec' AND owner_id = ?", (spec_id,))
        ex(f"DELETE FROM spine_cell WHERE id IN ({cells})", (spec_id,))
        ex("DELETE FROM spine_level WHERE spec_id = ?", (spec_id,))
        ex("DELETE FROM spine_spec WHERE id = ?", (spec_id,))

    def _add_spine_extra(self, owner, owner_id, statements):
        for seq, stmt in enumerate(statements, start=1):
            self.conn.execute("INSERT INTO spine_extra VALUES (?, ?, ?, ?)",
                              (owner, owner_id, seq, stmt))

    def spine_extra(self, owner, owner_id):
        return [r["statement"] for r in self.conn.execute(
            "SELECT statement FROM spine_extra WHERE owner = ? AND owner_id = ? ORDER BY seq",
            (owner, owner_id))]

    def spine_spec_names(self):
        return [r["name"] for r in self.conn.execute("SELECT name FROM spine_spec ORDER BY id")]

    def spine_spec_row(self, name: str):
        return self.conn.execute("SELECT * FROM spine_spec WHERE name = ?", (name,)).fetchone()

    def spine_level_names(self, spec_id: int):
        return [r["name"] for r in self.conn.execute(
            "SELECT name FROM spine_level WHERE spec_id = ? ORDER BY id", (spec_id,))]

    def spine_level_row(self, spec: str, level: str):
        return self.conn.execute(
            "SELECT l.* FROM spine_level l JOIN spine_spec s ON s.id = l.spec_id "
            "WHERE s.name = ? AND l.name = ?", (spec, level)).fetchone()

    def spine_cell_names(self, level_id: int):
        return [r["name"] for r in self.conn.execute(
            "SELECT name FROM spine_cell WHERE level_id = ? ORDER BY id", (level_id,))]

    def spine_cell_row(self, level_id: int, name: str):
        return self.conn.execute("SELECT * FROM spine_cell WHERE level_id = ? AND name = ?",
                                 (level_id, name)).fetchone()

    # -- design (DEF) ----------------------------------------------------------
    def has_design(self) -> bool:
        return self.conn.execute("SELECT 1 FROM design").fetchone() is not None

    def load_def(self, d):
        """Replace the design with d (a DefDesign), atomically."""
        with self.conn:
            for table in ("track_pattern", "site_row", "port_extra", "port_shape", "port",
                          "design"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute(
                "INSERT INTO design (id, name, file, def_version, units, boundary) "
                "VALUES (1, ?, ?, ?, ?, ?)",
                (d.name, os.path.abspath(d.file), d.version, d.units,
                 " ".join(_num(v) for v in d.boundary)))
            self.conn.executemany(
                "INSERT INTO port (id, name, net, direction, use, special, status, x, y, orient) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(i, p.name, p.net, p.direction, p.use, "true" if p.special else "false",
                  p.status, p.x, p.y, p.orient) for i, p in enumerate(d.ports, start=1)])
            self.conn.executemany(
                "INSERT INTO port_shape (port_id, seq, layer, type, points, mask) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(i, k, sh.layer, sh.type, " ".join(_num(v) for v in sh.points), sh.mask)
                 for i, p in enumerate(d.ports, start=1)
                 for k, sh in enumerate(p.shapes, start=1)])
            self.conn.executemany(
                "INSERT INTO track_pattern (id, line, direction, start, num_tracks, step, mask, "
                "same_mask, layers) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(i, t.line, t.direction, t.start, t.num_tracks, t.step, t.mask,
                  "true" if t.same_mask else "false", " ".join(t.layers))
                 for i, t in enumerate(d.tracks, start=1)])
            self.conn.executemany(
                "INSERT INTO site_row (name, site, x, y, orient, num_x, num_y, step_x, step_y) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(r.name, r.site, r.x, r.y, r.orient, r.num_x, r.num_y, r.step_x, r.step_y)
                 for r in getattr(d, "rows", [])])
            self.conn.executemany(
                "INSERT INTO port_extra VALUES (?, ?, ?)",
                [(i, k, e) for i, p in enumerate(d.ports, start=1)
                 for k, e in enumerate(p.extra, start=1)])

    def site_rows_of(self, site) -> bool:
        return bool(site) and self.conn.execute("SELECT 1 FROM site_row WHERE site = ?",
                                                (site,)).fetchone() is not None

    def has_site_rows(self) -> bool:
        return self.conn.execute("SELECT 1 FROM site_row").fetchone() is not None

    def legal_site(self, x: float, y: float, width: float, orient: str, site=None):
        """(x, y, row name) of the placement site nearest lower-left (x, y)
        for a cell width wide: in a row of the cell's site (when given) and
        orientation (N in N rows, FS in FS rows), the cell inside the row;
        None when no row fits."""
        best = None
        query = "SELECT * FROM site_row WHERE orient = ?" + (" AND site = ?" if site else "") + \
            " ORDER BY ABS(y - ?) LIMIT 400"
        for r in self.conn.execute(query, (orient, site, y) if site else (orient, y)):
            step = r["step_x"] or 0.0
            last = r["x"] + (r["num_x"] - 1) * step if step else r["x"]
            if step:
                k = round((x - r["x"]) / step)
                k = max(0, min(k, int((last + step - width - r["x"]) / step + 1e-9)))
                sx = r["x"] + k * step
            else:
                sx = r["x"]
            if sx + width > last + step + 1e-6 or sx < r["x"] - 1e-6:
                continue                 # the cell does not fit in the row
            d = abs(sx - x) + abs(r["y"] - y)
            if best is None or d < best[0]:
                best = (d, round(sx, 6), round(r["y"], 6), r["name"])
        return None if best is None else best[1:]

    def design_row(self):
        return self.conn.execute("SELECT * FROM design").fetchone()

    def port_names(self):
        return [r[0] for r in self.conn.execute("SELECT name FROM port ORDER BY id")]

    def port_row(self, name: str):
        return self.conn.execute("SELECT * FROM port WHERE name = ?", (name,)).fetchone()

    def port_shape_rows(self, port_id: int):
        return self.conn.execute("SELECT * FROM port_shape WHERE port_id = ? ORDER BY seq",
                                 (port_id,)).fetchall()

    def port_extra(self, port_id: int):
        return [r[0] for r in self.conn.execute(
            "SELECT statement FROM port_extra WHERE port_id = ? ORDER BY seq", (port_id,))]

    def track_pattern_ids(self):
        return [r[0] for r in self.conn.execute("SELECT id FROM track_pattern ORDER BY id")]

    def track_pattern_row(self, seq: int):
        return self.conn.execute("SELECT * FROM track_pattern WHERE id = ?", (seq,)).fetchone()

    def track_layers(self):
        """Layers with tracks, in first-use order."""
        seen = {}
        for (layers,) in self.conn.execute("SELECT layers FROM track_pattern ORDER BY id"):
            for layer in layers.split():
                seen.setdefault(layer, None)
        return list(seen)

    def track_positions(self, layer: str, direction: str):
        """Sorted, distinct track coordinates of all patterns on layer in
        direction (several patterns, e.g. per-mask ones, are merged)."""
        found = set()
        for r in self.conn.execute("SELECT * FROM track_pattern WHERE direction = ?",
                                   (direction,)):
            if layer in r["layers"].split():
                found.update(round(r["start"] + i * r["step"], 6)
                             for i in range(r["num_tracks"]))
        return sorted(found)

    def track_directions(self, layer: str):
        """Directions (x, y) in which layer has DEF tracks."""
        return sorted({r["direction"] for r in self.conn.execute(
            "SELECT direction, layers FROM track_pattern") if layer in r["layers"].split()})

    def set_track_assignment(self, layer, direction, pattern):
        """Store a layer's assignment; returns True if it replaced one."""
        with self.conn:
            old = self.conn.execute("DELETE FROM track_assignment WHERE layer = ?",
                                    (layer,)).rowcount
            self.conn.execute("INSERT INTO track_assignment (layer, direction, pattern) "
                              "VALUES (?, ?, ?)", (layer, direction, " ".join(pattern)))
        return old > 0

    def track_assignment_layers(self):
        return [r[0] for r in self.conn.execute("SELECT layer FROM track_assignment ORDER BY id")]

    def track_assignment_row(self, layer: str):
        return self.conn.execute("SELECT * FROM track_assignment WHERE layer = ?",
                                 (layer,)).fetchone()

    def set_route_rule(self, name, layer, width, spacing, spacing_given, append):
        """Store one layer of a rule. append False: the rule is replaced by this
        layer alone. Returns the layers of the old rule that were replaced (all
        of them without append, the same layer with append)."""
        given = "true" if spacing_given else "false"
        with self.conn:
            if append and self.route_rule_layer_row(name, layer):
                self.conn.execute("UPDATE route_rule SET width = ?, spacing = ?, "
                                  "spacing_given = ? WHERE name = ? AND layer = ?",
                                  (width, spacing, given, name, layer))
                return [layer]                 # keeps its place in the rule
            old = [] if append else self.route_rule_layers(name)
            if old:
                self.conn.execute("DELETE FROM route_rule WHERE name = ?", (name,))
            self.conn.execute("INSERT INTO route_rule (name, layer, width, spacing, "
                              "spacing_given) VALUES (?, ?, ?, ?, ?)",
                              (name, layer, width, spacing, given))
        return old

    def route_rule_names(self):
        return [r[0] for r in self.conn.execute(
            "SELECT name FROM route_rule GROUP BY name ORDER BY MIN(id)")]

    def route_rule_layers(self, name: str):
        return [r[0] for r in self.conn.execute(
            "SELECT layer FROM route_rule WHERE name = ? ORDER BY id", (name,))]

    def route_rule_layer_row(self, name: str, layer: str):
        return self.conn.execute("SELECT * FROM route_rule WHERE name = ? AND layer = ?",
                                 (name, layer)).fetchone()

    def set_net_route_rule(self, net: str, rule):
        """rule None: back to the default rule."""
        with self.conn:
            self.conn.execute("DELETE FROM net_route_rule WHERE net = ?", (net,))
            if rule is not None:
                self.conn.execute("INSERT INTO net_route_rule (net, rule) VALUES (?, ?)",
                                  (net, rule))

    def net_route_rule(self, net: str):
        row = self.conn.execute("SELECT rule FROM net_route_rule WHERE net = ?",
                                (net,)).fetchone()
        return row[0] if row else None

    def add_spine(self, spine, insts, members, stubs, nets):
        """Store a built spine and its instances, atomically."""
        with self.conn:
            ex = self.conn.execute
            sid = ex("INSERT INTO spine (name, spec, orientation, build_direction, x, y, origin, "
                     "mirror, ref_cell, level_pitch, deviation, max_drive, stub_length) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", spine).lastrowid
            self.conn.executemany("INSERT INTO inst (name, ref_cell, x, y, orient, status) "
                                  "VALUES (?, ?, ?, ?, ?, 'placed')", insts)
            self.conn.executemany("INSERT INTO spine_member VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  [(sid,) + tuple(m) for m in members])
            self.conn.executemany("INSERT INTO spine_stub (spine_id, name, driver, points, ref) "
                                  "VALUES (?, ?, ?, ?, ?)", [(sid,) + tuple(s) for s in stubs])
            self.conn.executemany("INSERT INTO spine_net (spine_id, name, driver, loads, grp, "
                                  "length, detour, route, ref_route) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  [(sid,) + tuple(n) for n in nets])

    def spine_names(self):
        return [r[0] for r in self.conn.execute("SELECT name FROM spine ORDER BY id")]

    def spine_row(self, name: str):
        return self.conn.execute("SELECT * FROM spine WHERE name = ?", (name,)).fetchone()

    def spine_members(self, spine_id: int):
        return self.conn.execute("SELECT * FROM spine_member WHERE spine_id = ? ORDER BY rowid",
                                 (spine_id,)).fetchall()

    def spine_stub_rows(self, spine_id: int):
        return self.conn.execute("SELECT * FROM spine_stub WHERE spine_id = ? ORDER BY id",
                                 (spine_id,)).fetchall()

    def spine_net_rows(self, spine_id: int):
        return self.conn.execute("SELECT * FROM spine_net WHERE spine_id = ? ORDER BY id",
                                 (spine_id,)).fetchall()

    def move_insts(self, names, dx: float, dy: float, pin_routes=False):
        """Move instances by (dx, dy) microns; with pin_routes, their route_pin
        straps and pin wires too."""
        with self.conn:
            self.conn.executemany("UPDATE inst SET x = ROUND(x + ?, 6), y = ROUND(y + ?, 6) "
                                  "WHERE name = ?", [(dx, dy, n) for n in names])
            if not pin_routes:
                return
            self._move_auto_vias(_via_prefixes(names), dx, dy)
            for table, key in (("strap", "inst"), ("pin_wire", "inst"), ("net_wire", "net")):
                for n in names:
                    n = f"pg:{n}" if table == "net_wire" else n   # optimize_pg_connection's
                    for r in self.conn.execute(f"SELECT id, rect FROM {table} WHERE {key} = ?",
                                               (n,)).fetchall():
                        v = [float(c) for c in r["rect"].split()]
                        rect = " ".join(_num(round(c + (dy if k % 2 else dx), 6))
                                        for k, c in enumerate(v))
                        self.conn.execute(f"UPDATE {table} SET rect = ? WHERE id = ?",
                                          (rect, r["id"]))

    def move_spine(self, name: str, dx: float, dy: float):
        """Move a built spine by (dx, dy) microns, with everything it owns: its
        location, instances, their route_pin straps and pin wires, stubs, net
        centre lines and the routed wires of its nets (stub wires and shields
        included). Atomic."""
        spine = self.spine_row(name)
        insts = [m["inst"] for m in self.spine_members(spine["id"])]
        nets = [r["name"] for r in self.spine_net_rows(spine["id"])]
        ex = self.conn.execute

        def moved(text):         # "x y x y ..." pairs, ';' between segments
            return ";".join(" ".join(_num(round(float(v) + (dy if k % 2 else dx), 6))
                                     for k, v in enumerate(part.split()))
                            for part in text.split(";")) if text else text

        with self.conn:
            ex("UPDATE spine SET x = ?, y = ?, path = ? WHERE id = ?",
               (round(spine["x"] + dx, 6), round(spine["y"] + dy, 6), moved(spine["path"]),
                spine["id"]))
            self.conn.executemany("UPDATE inst SET x = ROUND(x + ?, 6), y = ROUND(y + ?, 6) "
                                  "WHERE name = ?", [(dx, dy, n) for n in insts])
            owners = nets + [f"pg:{n}" for n in insts]    # optimize_pg_connection's too
            self._move_auto_vias(_via_prefixes(insts) + [f"auto_via:net_wire:{n}/"
                                                         for n in nets], dx, dy)
            for table, key in (("strap", "inst"), ("pin_wire", "inst"), ("net_wire", "net")):
                for value in (insts if key == "inst" else owners):
                    for r in ex(f"SELECT id, rect FROM {table} WHERE {key} = ?",
                                (value,)).fetchall():
                        ex(f"UPDATE {table} SET rect = ? WHERE id = ?", (moved(r["rect"]), r["id"]))
            for r in ex("SELECT id, points FROM spine_stub WHERE spine_id = ?",
                        (spine["id"],)).fetchall():
                ex("UPDATE spine_stub SET points = ? WHERE id = ?", (moved(r["points"]), r["id"]))
            for r in ex("SELECT id, route FROM spine_net WHERE spine_id = ?",
                        (spine["id"],)).fetchall():
                ex("UPDATE spine_net SET route = ? WHERE id = ?", (moved(r["route"]), r["id"]))
        return insts, nets

    def set_spine_shape(self, name: str, location, path: str, insts, stubs, nets):
        """A spine bent along path (move_spine_to_boundary): its new location
        (x, y), instance corners [(inst, x, y)], stub points [(stub id, text)]
        and net centre lines [(net id, text)]. Its routing no longer fits and
        goes: the route_pin straps and pin wires of its instances, their
        optimize_pg_connection wires, the route_net and route_final_stub
        wires of its nets, and the auto vias on any of them. Atomic. Returns
        (straps, pin wires, net wires) removed."""
        spine = self.spine_row(name)
        members = [m["inst"] for m in self.spine_members(spine["id"])]
        owners = [r["name"] for r in self.spine_net_rows(spine["id"])] + \
            [f"pg:{n}" for n in members]
        ex = self.conn.execute
        gone = [0, 0, 0]
        with self.conn:
            ex("UPDATE spine SET x = ?, y = ?, path = ? WHERE id = ?",
               (location[0], location[1], path, spine["id"]))
            self.conn.executemany("UPDATE inst SET x = ?, y = ? WHERE name = ?",
                                  [(x, y, n) for n, x, y in insts])
            self.conn.executemany("UPDATE spine_stub SET points = ? WHERE id = ?",
                                  [(text, k) for k, text in stubs])
            self.conn.executemany("UPDATE spine_net SET route = ? WHERE id = ?",
                                  [(text, k) for k, text in nets])
            self._drop_auto_vias(_via_prefixes(members) + [f"auto_via:net_wire:{n}/"
                                                           for n in owners])
            for n in members:
                gone[0] += ex("DELETE FROM strap WHERE inst = ?", (n,)).rowcount
                gone[1] += ex("DELETE FROM pin_wire WHERE inst = ?", (n,)).rowcount
            for n in owners:
                gone[2] += ex("DELETE FROM net_wire WHERE net = ?", (n,)).rowcount
        return tuple(gone)

    def _move_auto_vias(self, prefixes, dx, dy):
        """Move the auto vias (stretch_wire) of the wires whose owner net
        starts with one of prefixes."""
        for p in prefixes:
            for r in self.conn.execute("SELECT id, rect FROM net_wire WHERE substr(net, 1, ?) = ?",
                                       (len(p), p)).fetchall():
                rect = " ".join(_num(round(float(c) + (dy if k % 2 else dx), 6))
                                for k, c in enumerate(r["rect"].split()))
                self.conn.execute("UPDATE net_wire SET rect = ? WHERE id = ?", (rect, r["id"]))

    def _drop_auto_vias(self, prefixes):
        for p in prefixes:
            self.conn.execute("DELETE FROM net_wire WHERE substr(net, 1, ?) = ?", (len(p), p))

    def set_inst_status(self, name: str, status: str):
        with self.conn:
            self.conn.execute("UPDATE inst SET status = ? WHERE name = ?", (status, name))

    def add_inst(self, name, ref_cell, x, y, orient, status="placed"):
        with self.conn:
            self.conn.execute("INSERT INTO inst (name, ref_cell, x, y, orient, status) "
                              "VALUES (?, ?, ?, ?, ?, ?)", (name, ref_cell, x, y, orient, status))

    def has_insts(self) -> bool:
        return self.conn.execute("SELECT 1 FROM inst").fetchone() is not None

    def inst_names(self):
        return [r[0] for r in self.conn.execute("SELECT name FROM inst ORDER BY id")]

    def inst_row(self, name: str):
        return self.conn.execute("SELECT * FROM inst WHERE name = ?", (name,)).fetchone()

    def inst_rows(self):
        return self.conn.execute("SELECT * FROM inst ORDER BY id").fetchall()

    def set_straps(self, inst: str, straps, wires=(), max_extension=0.0):
        """Replace an instance's straps with (net, layer, rect text), top first,
        and its pin wires with (pin, net, layer, rect text, strap seq).
        max_extension: how far route_net may lengthen each strap at each end.
        Returns the number of straps replaced."""
        with self.conn:
            old = self.conn.execute("DELETE FROM strap WHERE inst = ?", (inst,)).rowcount
            self.conn.execute("DELETE FROM pin_wire WHERE inst = ?", (inst,))
            self.conn.execute("DELETE FROM net_wire WHERE net = ?", (f"pg:{inst}",))
            self._drop_auto_vias(_via_prefixes([inst]))       # their wires are rebuilt
            self.conn.executemany("INSERT INTO strap (inst, seq, net, layer, rect, "
                                  "max_extension) VALUES (?, ?, ?, ?, ?, ?)",
                                  [(inst, k, net, layer, rect, max_extension)
                                   for k, (net, layer, rect) in enumerate(straps, start=1)])
            self.conn.executemany("INSERT INTO pin_wire (inst, pin, net, layer, rect, strap) "
                                  "VALUES (?, ?, ?, ?, ?, ?)",
                                  [(inst,) + tuple(w) for w in wires])
        return old

    def set_net_wires(self, net: str, wires, stub=False):
        """Replace a net's wires with (kind, layer, rect text[, shield net]):
        its route_net wires, or with stub=True its route_final_stub ones
        (kind stub, and their crossings); each keeps the other's. Returns how
        many it replaced."""
        part = "kind LIKE 'stub%'" if stub else "kind NOT LIKE 'stub%'"
        with self.conn:
            if not net.startswith("auto_via:"):     # the wires are rebuilt: their vias go
                self._drop_auto_vias([f"auto_via:net_wire:{net}/"])
            old = self.conn.execute(f"DELETE FROM net_wire WHERE net = ? AND {part}",
                                    (net,)).rowcount
            first = self.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM net_wire "
                                      "WHERE net = ?", (net,)).fetchone()[0]
            self.conn.executemany("INSERT INTO net_wire (net, seq, kind, layer, rect, "
                                  "shield_net) VALUES (?, ?, ?, ?, ?, ?)",
                                  [(net, k) + tuple(w) + (None,) * (4 - len(w))
                                   for k, w in enumerate(wires, start=first + 1)])
        return old

    def unname_pins(self, net: str, to: str = "SIGNAL"):
        """Put the straps and pin wires route_net named after net back on to
        (its routing is gone, so they connect to nothing). Returns how many."""
        with self.conn:
            n = self.conn.execute("UPDATE strap SET net = ? WHERE net = ?", (to, net)).rowcount
            n += self.conn.execute("UPDATE pin_wire SET net = ? WHERE net = ?",
                                   (to, net)).rowcount
        return n

    def set_pin_net(self, inst: str, pin: str, strap: int, net: str):
        """Give a route_pin strap and the pin wire of pin the net they are now
        part of (route_net connected them)."""
        with self.conn:
            self.conn.execute("UPDATE strap SET net = ? WHERE inst = ? AND seq = ?",
                              (net, inst, strap))
            self.conn.execute("UPDATE pin_wire SET net = ? WHERE inst = ? AND pin = ?",
                              (net, inst, pin))

    def net_wire_rows(self, net=None):
        if net is None:
            return self.conn.execute("SELECT * FROM net_wire ORDER BY id").fetchall()
        return self.conn.execute("SELECT * FROM net_wire WHERE net = ? ORDER BY id",
                                 (net,)).fetchall()

    def set_wire_rect(self, table: str, row_id: int, rect: str):
        """A new rect for one route shape (move_wire, stretch_wire)."""
        assert table in ("net_wire", "strap", "pin_wire")
        with self.conn:
            self.conn.execute(f"UPDATE {table} SET rect = ? WHERE id = ?", (rect, row_id))

    def net_wire_row(self, net: str, seq: int):
        return self.conn.execute("SELECT * FROM net_wire WHERE net = ? AND seq = ?",
                                 (net, seq)).fetchone()

    def pin_wire_rows(self, inst=None):
        if inst is None:
            return self.conn.execute("SELECT * FROM pin_wire ORDER BY id").fetchall()
        return self.conn.execute("SELECT * FROM pin_wire WHERE inst = ? ORDER BY id",
                                 (inst,)).fetchall()

    def pin_wire_row(self, inst: str, pin: str):
        return self.conn.execute("SELECT * FROM pin_wire WHERE inst = ? AND pin = ?",
                                 (inst, pin)).fetchone()

    def strap_rows(self, inst=None):
        if inst is None:
            return self.conn.execute("SELECT * FROM strap ORDER BY id").fetchall()
        return self.conn.execute("SELECT * FROM strap WHERE inst = ? ORDER BY seq",
                                 (inst,)).fetchall()

    def strap_row(self, inst: str, seq: int):
        return self.conn.execute("SELECT * FROM strap WHERE inst = ? AND seq = ?",
                                 (inst, seq)).fetchone()

    def lib_cell_shapes(self, cell: str):
        """(pin, layer, type, points text) for every pin shape of a lib cell."""
        return [(r[0], r[1], r[2], r[3]) for r in self.conn.execute(
            "SELECT p.name, s.layer, s.type, s.points FROM layer_shape s "
            "JOIN lib_port pt ON pt.id = s.port_id JOIN lib_pin p ON p.id = pt.pin_id "
            "JOIN lib_cell c ON c.id = p.cell_id WHERE c.name = ? ORDER BY s.id", (cell,))]

    def port_counts(self, column: str):
        """{value: count} of a port column (direction, use, status)."""
        return {r[0]: r[1] for r in self.conn.execute(
            f"SELECT {column}, COUNT(*) FROM port GROUP BY {column} "
            f"ORDER BY COUNT(*) DESC, {column}")}

    def port_shape_layer_counts(self):
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT layer, COUNT(*) FROM port_shape GROUP BY layer ORDER BY MIN(id)")}

    # -- persistence ---------------------------------------------------------
    def write(self, path: str):
        dst = sqlite3.connect(path)
        try:
            self.conn.backup(dst)
        finally:
            dst.close()

    def read(self, path: str):
        """Replace the in-memory database with the file at path."""
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            try:
                row = src.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            except sqlite3.DatabaseError as exc:
                raise SchemaMismatch(f"not an htree database ({exc})")
            if row is None or row[0] != str(SCHEMA_VERSION):
                found = row[0] if row else "none"
                raise SchemaMismatch(f"schema version {found}, expected {SCHEMA_VERSION}")
            conn = self._new_memory()
            src.backup(conn)
        finally:
            src.close()
        self.conn.close()
        self.conn = conn


def _via_prefixes(insts):
    """Owner-net prefixes of the auto vias (stretch_wire) on the route_pin
    and optimize_pg_connection shapes of instances."""
    return [p for n in insts for p in (f"auto_via:strap:{n}/", f"auto_via:pin_wire:{n}/",
                                       f"auto_via:net_wire:pg:{n}/")]
