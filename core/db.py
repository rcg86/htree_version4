"""SQLite design database. Lives in memory; write_db/read_db move it to and from disk."""

import os
import sqlite3

from core.lef import CellLef, TechLef

SCHEMA_VERSION = 8   # 2: read_lef; 3: lib pins/shapes; 4: spine specs; 5: read_def; 6: tracks;
                     # 7: track assignments; 8: instances

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
    origin_x NUMERIC, level_pitch_x NUMERIC,
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
    output TEXT
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
    status TEXT                          -- placed
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
                     "count_stub_in_drive", "origin_x", "level_pitch_x", "orientation",
                     "span", "stub_count", "stub_gap", "stub_tap", "stub_order"]

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
                            "INSERT INTO spine_cell (level_id, name, input, output) "
                            "VALUES (?, ?, ?, ?)",
                            (level_id, cell.name, cell.input, cell.output)).lastrowid
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
            for table in ("track_pattern", "port_extra", "port_shape", "port", "design"):
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
                "INSERT INTO port_extra VALUES (?, ?, ?)",
                [(i, k, e) for i, p in enumerate(d.ports, start=1)
                 for k, e in enumerate(p.extra, start=1)])

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
