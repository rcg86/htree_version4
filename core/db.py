"""SQLite design database. Lives in memory; write_db/read_db move it to and from disk."""

import os
import sqlite3

from core.lef import CellLef, TechLef

SCHEMA_VERSION = 26  # 2: read_lef; 3: lib pins/shapes; 4: spine specs; 5: read_def; 6: tracks;
                     # 7: track assignments; 8: instances; 9: route rules;
                     # 10: level_pitch, deviation, built spines; 11: spine cell location;
                     # 12: named route rules with several layers, net route rules;
                     # 13: route_pin straps; 14: route_pin pin wires;
                     # 15: spine origin and -mirror; 16: route_net wires;
                     # 17: strap max_extension; 18: route_net shields; 19: DEF rows;
                     # 20: spine path and straight-spine coordinates (move_spine_to_boundary);
                     # 21: via definitions, via assignments and vias (VIA_SCHEMA; a
                     #     version 20 file gets these tables when it is read)
                     # 22: connect_pin connections (CONNECTION_SCHEMA; a version 20
                     #     or 21 file gets the table when it is read)
                     # 23: net_wire.via_def, the definitions of an insert_vias via (an
                     #     older file gets the column when it is read)
                     # 24: net route status, fixed nets (ROUTE_STATUS_SCHEMA),
                     #     net_wire.status, fixed wires, and spine_cell.track_in /
                     #     track_out (an older file gets them when it is read)
                     # 25: spine.root_net, the root net rename_obj gave a spine (an
                     #     older file gets the column when it is read)
                     # 26: strap stretches (STRETCH_SCHEMA, strap.base_rect): a route
                     #     lengthens the strap, no extension piece (an older file's
                     #     pieces become stretches when it is read)

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
    location NUMERIC,           -- um along the spine from the cell's driver
    track_in INTEGER,           -- track: {input, output}: the k-th signal track past
    track_out INTEGER           -- the spine's location (core/spine_tracks.py)
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
    path TEXT,                           -- "x y x y ...": the stub line, bottom / left end
                                         -- first, once bent; NULL: straight as built
    root_net TEXT                        -- the net on the root's input, renamed by
                                         -- rename_obj; NULL: core/netlist.py root_net
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
    rect TEXT,                           -- "x1 y1 x2 y2" (microns): base_rect with
                                         -- its stretches (strap_stretch)
    max_extension REAL,                  -- route_net may lengthen it this far each side
    base_rect TEXT                       -- route_pin's rect; NULL: not stretched
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
                                         -- pg_ext | pg_cross (net pg:<inst>) |
                                         -- via (stretch_wire) | insert_via (insert_vias),
                                         -- both under net auto_via:<wire handle>
    layer TEXT,                          -- a cross or a via: "<layer>/<layer>"
    rect TEXT,                           -- "x1 y1 x2 y2" (microns)
    shield_net TEXT,                     -- a shield: its power net (VDD_SOC, VSS)
    via_def TEXT,                        -- insert_vias -via_ref: the definitions of its vias
    status TEXT                          -- fixed: set_db .route_status (a wire alone)
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

# Schema version 21. Kept apart so that a version 20 database can be given
# these tables when it is read (Database.read).
VIA_SCHEMA = """
-- Via definitions: the VIA blocks of the tech LEF (read_tech) and the VIAS
-- of the DEF (read_def). A name is held once; the DEF's replaces the LEF's.
CREATE TABLE via_def (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    source TEXT,                         -- lef | def
    is_default TEXT,                     -- true | false (LEF: VIA <name> DEFAULT)
    via_rule TEXT,                       -- shapes generated from this VIARULE's parameters
    line INTEGER,
    extra TEXT,                          -- statements not modeled, one per line
    text TEXT                            -- as in the file
);

CREATE TABLE via_def_shape (
    id INTEGER PRIMARY KEY,
    via_def_id INTEGER REFERENCES via_def(id),
    seq INTEGER,                         -- 1-based within the via
    layer TEXT,
    type TEXT,                           -- rect | polygon
    points TEXT,                         -- microns, about the via's origin
    mask INTEGER
);
CREATE INDEX via_def_shape_def ON via_def_shape (via_def_id);

-- assign_via_for_route: the definition a route uses between two routing
-- layers (through one cut layer), for one net or for every net.
CREATE TABLE via_assignment (
    id INTEGER PRIMARY KEY,
    bottom TEXT NOT NULL, cut TEXT NOT NULL, top TEXT NOT NULL,
    net TEXT NOT NULL,                   -- '': every net without one of its own
    via_def TEXT NOT NULL,
    UNIQUE (bottom, top, net)
);

-- The vias of the routing: one per cut layer where a route changes layer.
-- Derived (core/vias.py) from the crossing boxes of net_wire and from the
-- pin wires, and rebuilt when those change; never edited directly.
CREATE TABLE via (
    id INTEGER PRIMARY KEY,
    net TEXT NOT NULL,                   -- the net it carries (a shield's via: the power net)
    seq INTEGER,                         -- 1, 2, ... per net
    kind TEXT,                           -- cross | stub_cross | pg_cross | auto | pin | strap
    via_def TEXT,                        -- NULL: no definition assigned for its layers
    bottom TEXT, cut TEXT, top TEXT,     -- cut NULL: no definition joins the two layers
    x REAL, y REAL,                      -- its origin: the centre of rect
    rect TEXT,                           -- the box the two shapes it joins share
    source TEXT                          -- the crossing box or pin wire it comes from
);
CREATE INDEX via_net ON via (net);
"""
SCHEMA += VIA_SCHEMA

# Schema version 22. Kept apart as VIA_SCHEMA is: an older database gets the
# table, empty, when it is read.
CONNECTION_SCHEMA = """
-- connect_pin / disconnect_pin: the connections made by hand, one row per
-- load pin (core/netlist.py). The connections of a built spine are in
-- spine_net; a row here overrules the spine spec's root_net for its pin.
CREATE TABLE connection (
    id INTEGER PRIMARY KEY,
    inst TEXT NOT NULL,                  -- the load: an instance
    pin TEXT NOT NULL,                   -- and its input pin
    net TEXT,                            -- NULL: disconnected by hand
    driver TEXT,                         -- "<inst>/<pin>" or "port:<port>"
    UNIQUE (inst, pin)
);
"""
SCHEMA += CONNECTION_SCHEMA

# Schema version 24. Kept apart as CONNECTION_SCHEMA is.
ROUTE_STATUS_SCHEMA = """
-- set_db <nets> .route_status fixed: the nets (and stubs, keyed
-- stub:<spine>/<stub>) whose routes no routing command may change. No row:
-- not fixed (routed or unrouted, from its wires).
CREATE TABLE net_route_status (
    net TEXT PRIMARY KEY,
    status TEXT NOT NULL                 -- fixed
);
"""
SCHEMA += ROUTE_STATUS_SCHEMA

# Schema version 26. Kept apart as ROUTE_STATUS_SCHEMA is.
STRETCH_SCHEMA = """
-- A route_pin strap lengthened by a route, not a piece of metal beside it:
-- route_net to a signal track (kind extension), route_net -shield to a
-- shield (shield_ext), optimize_pg_connection (pg_ext). owner: the net whose
-- route it is (pg:<inst> for optimize_pg_connection), so routing the net
-- again or deleting its route takes the stretch back. The strap's rect is
-- its base_rect from the least x1 to the greatest x2.
CREATE TABLE strap_stretch (
    id INTEGER PRIMARY KEY,
    inst TEXT NOT NULL,
    seq INTEGER NOT NULL,                -- the strap
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- extension | shield_ext | pg_ext
    x1 REAL NOT NULL, x2 REAL NOT NULL
);
CREATE INDEX strap_stretch_owner ON strap_stretch (owner);
"""
SCHEMA += STRETCH_SCHEMA
STRETCH_KINDS = ("extension", "shield_ext", "pg_ext")

LAYER_COLUMNS = ["name", "type", "direction", "pitch_x", "pitch_y", "offset_x", "offset_y",
                 "width", "min_width", "max_width", "area", "min_enclosed_area",
                 "min_step", "min_step_max_edges", "min_spacing", "lef_text"]
REMOVED_LAYERS = "tech:removed_layers"      # meta key: names, blank separated (remove_layer)


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
        # The wires of each delete_wire, last last, as [(handle, table, row dict)],
        # for delete_wire -undo. Session state too.
        self.deleted_wires = []
        # Route shapes the last move_wire removed or added besides its wires (the
        # shields it made again), for the GUI to redraw. Session state too.
        self.redrawn = []
        # The nets whose strap stretches the last set_straps (route_pin) took
        # back with the straps it replaced: to be routed again. Session state too.
        self.dropped_stretches = []
        # show_only: the handles of the objects the GUI is to draw alone (the other
        # instances and net routing hidden); empty: everything. Session state too.
        self.show_only = []
        # highlight: [(handle, colour '#rrggbb' or None)], the last that covers a
        # drawn shape giving its colour in the GUI (None: its own). Session state too.
        self.highlights = []
        # What the last check_drc found (core/drc.py Report), for the DRC table of
        # the GUI; None: not run. Session state too.
        self.drc = None
        # (connection, its change count) when the via table was last brought
        # in step with the routing (core/vias.py).
        self.via_stamp = None
        # ((connection, its change count), {inst: {pin: net}}): the net of every
        # pin as last worked out (core/netlist.py), good until the data changes.
        self.netlist = None
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

    def load_tech(self, tech: TechLef, min_layer=None, max_layer=None, removed=()):
        """Replace all tech data with tech, atomically. Returns the names of
        its vias left out because the DEF defines a via of that name.
        min_layer, max_layer: the layer range tech was cut down to
        (read_tech), kept for tech_layer_range. removed: the layers of
        remove_layer still out of it (add_layer), kept for removed_layers."""
        with self.conn:
            for table in ("layer_extra", "layer", "tech_extra", "tech"):
                self.conn.execute(f"DELETE FROM {table}")
            for key, name in (("tech:min_layer", min_layer), ("tech:max_layer", max_layer),
                              (REMOVED_LAYERS, " ".join(removed))):
                self.conn.execute("DELETE FROM meta WHERE key = ?", (key,))
                if name:
                    self.conn.execute("INSERT INTO meta VALUES (?, ?)", (key, name))
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
            return self._set_via_defs("lef", tech.vias)

    # -- via definitions -------------------------------------------------------
    def _set_via_defs(self, source: str, vias):
        """Replace the via definitions of source (lef | def) with vias
        (ViaDef). A name both files define is the DEF's. Returns those names.
        Inside the caller's transaction."""
        ex = self.conn.execute
        ex("DELETE FROM via_def_shape WHERE via_def_id IN "
           "(SELECT id FROM via_def WHERE source = ?)", (source,))
        ex("DELETE FROM via_def WHERE source = ?", (source,))
        both = []
        for via in vias:
            old = ex("SELECT id FROM via_def WHERE name = ?", (via.name,)).fetchone()
            if old is not None:
                both.append(via.name)
                if source == "lef":
                    continue
                ex("DELETE FROM via_def_shape WHERE via_def_id = ?", (old["id"],))
                ex("DELETE FROM via_def WHERE id = ?", (old["id"],))
            key = ex("INSERT INTO via_def (name, source, is_default, via_rule, line, extra, "
                     "text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (via.name, source, "true" if via.default else "false", via.via_rule,
                      via.line, "\n".join(via.extra), via.lef_text)).lastrowid
            self.conn.executemany(
                "INSERT INTO via_def_shape (via_def_id, seq, layer, type, points, mask) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(key, k, sh.layer, sh.type, " ".join(_num(v) for v in sh.points), sh.mask)
                 for k, sh in enumerate(via.shapes, start=1)])
        return both

    def via_def_names(self):
        return [r["name"] for r in self.conn.execute("SELECT name FROM via_def ORDER BY id")]

    def via_def_row(self, name: str):
        return self.conn.execute("SELECT * FROM via_def WHERE name = ?", (name,)).fetchone()

    def via_def_shapes(self, via_def_id: int):
        return self.conn.execute("SELECT * FROM via_def_shape WHERE via_def_id = ? "
                                 "ORDER BY seq", (via_def_id,)).fetchall()

    def all_via_def_shapes(self):
        """(via name, layer, type, points text) of every definition's shapes."""
        return self.conn.execute(
            "SELECT d.name, s.layer, s.type, s.points FROM via_def_shape s "
            "JOIN via_def d ON d.id = s.via_def_id ORDER BY d.id, s.seq").fetchall()

    def set_via_assignment(self, bottom, cut, top, net, via_def):
        """The definition for the routes of net ('' = every net) between
        bottom and top. Returns the name it replaces, or None."""
        with self.conn:
            old = self.conn.execute("SELECT via_def FROM via_assignment WHERE bottom = ? "
                                    "AND top = ? AND net = ?", (bottom, top, net)).fetchone()
            self.conn.execute("DELETE FROM via_assignment WHERE bottom = ? AND top = ? "
                              "AND net = ?", (bottom, top, net))
            self.conn.execute("INSERT INTO via_assignment (bottom, cut, top, net, via_def) "
                              "VALUES (?, ?, ?, ?, ?)", (bottom, cut, top, net, via_def))
        return old["via_def"] if old is not None else None

    def clear_via_assignments(self, nets=None):
        """Remove the assignments of nets ('' = the one for every net), or all."""
        with self.conn:
            if nets is None:
                return self.conn.execute("DELETE FROM via_assignment").rowcount
            return sum(self.conn.execute("DELETE FROM via_assignment WHERE net = ?",
                                         (n,)).rowcount for n in nets)

    def via_assignment_rows(self):
        return self.conn.execute("SELECT * FROM via_assignment ORDER BY id").fetchall()

    def set_vias(self, rows):
        """Replace the via table with rows of (net, seq, kind, via_def, bottom,
        cut, top, x, y, rect, source) (core/vias.py)."""
        with self.conn:
            self.conn.execute("DELETE FROM via")
            self.conn.executemany(
                "INSERT INTO via (net, seq, kind, via_def, bottom, cut, top, x, y, rect, "
                "source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def tech_row(self):
        return self.conn.execute("SELECT * FROM tech").fetchone()

    def tech_layer_range(self):
        """(min_layer, max_layer) the tech data was read with (read_tech),
        None for one not given."""
        found = dict(self.conn.execute(
            "SELECT key, value FROM meta WHERE key IN ('tech:min_layer', 'tech:max_layer')"))
        return found.get("tech:min_layer"), found.get("tech:max_layer")

    def removed_layers(self):
        """The layers remove_layer took out of the tech data and add_layer has
        not put back, in the order removed."""
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?",
                                (REMOVED_LAYERS,)).fetchone()
        return row["value"].split() if row else []

    def remove_layers(self, names):
        """Take the layers out of the tech data, atomically, and with them
        the via definitions of the tech LEF that have a shape on one (the
        DEF's stay). Returns the names of those vias."""
        marks = ", ".join("?" for _ in names)
        with self.conn:
            ex = self.conn.execute
            vias = ex("SELECT DISTINCT d.id, d.name FROM via_def d JOIN via_def_shape s "
                      f"ON s.via_def_id = d.id WHERE d.source = 'lef' AND s.layer IN ({marks}) "
                      "ORDER BY d.id", names).fetchall()
            for via in vias:
                ex("DELETE FROM via_def_shape WHERE via_def_id = ?", (via["id"],))
                ex("DELETE FROM via_def WHERE id = ?", (via["id"],))
            ex(f"DELETE FROM layer_extra WHERE layer_id IN (SELECT id FROM layer WHERE name "
               f"IN ({marks}))", names)
            ex(f"DELETE FROM layer WHERE name IN ({marks})", names)
            out = self.removed_layers()
            ex("INSERT OR REPLACE INTO meta VALUES (?, ?)",
               (REMOVED_LAYERS, " ".join(out + [n for n in names if n not in out])))
        return [via["name"] for via in vias]

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
                            "INSERT INTO spine_cell (level_id, name, input, output, location, "
                            "track_in, track_out) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (level_id, cell.name, cell.input, cell.output,
                             cell.location, cell.track_in, cell.track_out)).lastrowid
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
        """Replace the design with d (a DefDesign), atomically. Returns the
        names of its vias that replace a tech LEF via of the same name."""
        with self.conn:
            for table in ("track_pattern", "site_row", "port_extra", "port_shape", "port",
                          "design"):
                self.conn.execute(f"DELETE FROM {table}")
            both = self._set_via_defs("def", getattr(d, "vias", []))
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
        return both

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

    def port_of_net(self, net: str):
        """A port whose net this is (its DEF net, else its own name), or None."""
        return self.conn.execute("SELECT * FROM port WHERE COALESCE(NULLIF(net, ''), name) = ? "
                                 "ORDER BY id", (net,)).fetchone()

    def port_net_names(self):
        """The net of every port (its DEF net, else its own name), in one query."""
        return [r[0] for r in self.conn.execute(
            "SELECT COALESCE(NULLIF(net, ''), name) FROM port ORDER BY id")]

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

    def set_net_fixed(self, net: str, fixed: bool):
        """Fix a net's (or a stub's, objects.stub_key) routes, or free them."""
        with self.conn:
            self.conn.execute("DELETE FROM net_route_status WHERE net = ?", (net,))
            if fixed:
                self.conn.execute("INSERT INTO net_route_status (net, status) "
                                  "VALUES (?, 'fixed')", (net,))

    def fixed_nets(self):
        """The keys of the fixed nets and stubs (set_db .route_status fixed)."""
        return {r[0] for r in self.conn.execute("SELECT net FROM net_route_status")}

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

    def add_net_buffers(self, insts, members, nets, cut, moved, links=()):
        """Buffers put on nets (add_buffer_on_net), atomically. insts as for
        add_spine. On the nets of built spines: members and nets (the nets the
        buffers drive) too, each with its spine id first; cut [(spine_net id,
        loads, length, route, ref_route)]: the nets given, which now end at
        their first buffers; moved [(connection id, net, driver)]: the
        connect_pin loads that are behind a buffer now. On the nets of no
        spine: links [(inst, pin, net, driver)], the connection of the input
        of each buffer and of each load behind one."""
        with self.conn:
            self.conn.executemany("INSERT INTO inst (name, ref_cell, x, y, orient, status) "
                                  "VALUES (?, ?, ?, ?, ?, 'placed')", insts)
            self.conn.executemany("INSERT INTO spine_member VALUES (?, ?, ?, ?, ?, ?, ?)", members)
            self.conn.executemany("INSERT INTO spine_net (spine_id, name, driver, loads, grp, "
                                  "length, detour, route, ref_route) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", nets)
            self.conn.executemany("UPDATE spine_net SET loads = ?, length = ?, detour = 0, "
                                  "route = ?, ref_route = ? WHERE id = ?",
                                  [tuple(c[1:]) + (c[0],) for c in cut])
            self.conn.executemany("UPDATE connection SET net = ?, driver = ? WHERE id = ?",
                                  [(net, driver, k) for k, net, driver in moved])
            self.conn.executemany("DELETE FROM connection WHERE inst = ? AND pin = ?",
                                  [link[:2] for link in links])
            self.conn.executemany("INSERT INTO connection (inst, pin, net, driver) "
                                  "VALUES (?, ?, ?, ?)", links)

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

    def connection_rows(self):
        """The connections made by hand (connect_pin), oldest first."""
        return self.conn.execute("SELECT * FROM connection ORDER BY id").fetchall()

    def move_insts(self, names, dx: float, dy: float, pin_routes=False):
        """Move instances by (dx, dy) microns; with pin_routes, their route_pin
        straps and pin wires too."""
        with self.conn:
            self.conn.executemany("UPDATE inst SET x = ROUND(x + ?, 6), y = ROUND(y + ?, 6) "
                                  "WHERE name = ?", [(dx, dy, n) for n in names])
            if not pin_routes:
                return
            self._move_auto_vias(_via_prefixes(names), dx, dy)
            self._move_stretches(names, dx, dy)
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
            owners = nets + [stub_owner(n) for n in nets] + \
                [f"pg:{n}" for n in insts]     # its stubs' and optimize_pg_connection's too
            self._move_auto_vias(_via_prefixes(insts) + [f"auto_via:net_wire:{n}/"
                                                         for n in owners[:2 * len(nets)]],
                                 dx, dy)
            self._move_stretches(insts, dx, dy)
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

    def copy_spine(self, name: str, new: str, inst_map, net_map, dx: float, dy: float):
        """Copy a built spine as spine new, (dx, dy) microns away, with
        everything move_spine moves: its instances (inst_map: old name -> new),
        their route_pin straps and pin wires, stubs, net centre lines, the
        routed wires of its nets (net_map: old name -> new) and stubs, the
        optimize_pg_connection wires and auto vias of all of these, the route
        rules and route status of its nets and stubs, and the connect_pin
        rows of its instances (not an output put on a port's net: a net has
        one driver). Shapes on
        other nets (power, SIGNAL, the root net) keep their net; the net an auto
        via carries (.shield_net) is renamed with its net. Atomic.
        Returns the number of (straps, pin wires, net wires, strap stretches)
        copied."""
        spine = self.spine_row(name)
        ex = self.conn.execute

        def moved(text):         # "x y x y ...", ';' between segments
            return ";".join(" ".join(_num(round(float(v) + (dy if k % 2 else dx), 6))
                                     for k, v in enumerate(part.split()))
                            for part in text.split(";")) if text else text

        def owner(net):          # a net_wire owner: a net, <net>_stub, pg:<inst>, auto_via:
            if net in net_map:
                return net_map[net]
            if net.endswith(STUB) and net[:-len(STUB)] in net_map:
                return stub_owner(net_map[net[:-len(STUB)]])
            if net.startswith("pg:") and net[3:] in inst_map:
                return "pg:" + inst_map[net[3:]]
            if net.startswith("auto_via:"):
                kind, _, rest = net[len("auto_via:"):].partition(":")
                head, _, tail = rest.rpartition("/")
                mapped = owner(head) if kind == "net_wire" else inst_map.get(head)
                if mapped is not None:
                    return f"auto_via:{kind}:{mapped}/{tail}"
            return None

        def net_of(net):
            return net_map.get(net, net)

        counts = [0, 0, 0, 0]
        with self.conn:
            sid = ex("INSERT INTO spine (name, spec, orientation, build_direction, x, y, origin, "
                     "mirror, ref_cell, level_pitch, deviation, max_drive, stub_length, path) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (new, spine["spec"], spine["orientation"], spine["build_direction"],
                      round(spine["x"] + dx, 6), round(spine["y"] + dy, 6), spine["origin"],
                      spine["mirror"], spine["ref_cell"], spine["level_pitch"],
                      spine["deviation"], spine["max_drive"], spine["stub_length"],
                      moved(spine["path"]))).lastrowid
            for old, name_new in inst_map.items():
                r = self.inst_row(old)
                ex("INSERT INTO inst (name, ref_cell, x, y, orient, status) "
                   "VALUES (?, ?, ?, ?, ?, ?)", (name_new, r["ref_cell"], round(r["x"] + dx, 6),
                                                 round(r["y"] + dy, 6), r["orient"], r["status"]))
                for s in ex("SELECT * FROM strap WHERE inst = ? ORDER BY id", (old,)).fetchall():
                    ex("INSERT INTO strap (inst, seq, net, layer, rect, max_extension, "
                       "base_rect) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (name_new, s["seq"], net_of(s["net"]), s["layer"], moved(s["rect"]),
                        s["max_extension"], moved(s["base_rect"])))
                    counts[0] += 1
                for st in ex("SELECT * FROM strap_stretch WHERE inst = ?", (old,)).fetchall():
                    ex("INSERT INTO strap_stretch (inst, seq, owner, kind, x1, x2) VALUES "
                       "(?, ?, ?, ?, ?, ?)", (name_new, st["seq"], owner(st["owner"]) or
                                              st["owner"], st["kind"], round(st["x1"] + dx, 6),
                                              round(st["x2"] + dx, 6)))
                    counts[3] += 1
                for w in ex("SELECT * FROM pin_wire WHERE inst = ? ORDER BY id", (old,)).fetchall():
                    ex("INSERT INTO pin_wire (inst, pin, net, layer, rect, strap) "
                       "VALUES (?, ?, ?, ?, ?, ?)", (name_new, w["pin"], net_of(w["net"]),
                                                     w["layer"], moved(w["rect"]), w["strap"]))
                    counts[1] += 1
                for c in ex("SELECT * FROM connection WHERE inst = ?", (old,)).fetchall():
                    driver = c["driver"] or ""
                    if driver == f"{old}/{c['pin']}":
                        continue         # it drives a port (connect_port): one driver only
                    d_inst, _, d_pin = driver.partition("/")
                    if d_inst in inst_map:
                        driver = f"{inst_map[d_inst]}/{d_pin}"
                    ex("INSERT INTO connection (inst, pin, net, driver) VALUES (?, ?, ?, ?)",
                       (name_new, c["pin"], c["net"] if c["net"] is None else net_of(c["net"]),
                        driver or c["driver"]))
            for m in self.spine_members(spine["id"]):
                ex("INSERT INTO spine_member VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (sid, inst_map[m["inst"]], m["level"], m["cell"],
                    inst_map.get(m["driver"], m["driver"]), m["along"], m["across"]))
            for s in self.spine_stub_rows(spine["id"]):
                ex("INSERT INTO spine_stub (spine_id, name, driver, points, ref) "
                   "VALUES (?, ?, ?, ?, ?)", (sid, s["name"], inst_map.get(s["driver"], s["driver"]),
                                              moved(s["points"]), s["ref"]))
            for n in self.spine_net_rows(spine["id"]):
                ex("INSERT INTO spine_net (spine_id, name, driver, loads, grp, length, detour, "
                   "route, ref_route) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (sid, net_map[n["name"]], inst_map.get(n["driver"], n["driver"]),
                    " ".join(inst_map.get(w, w) for w in n["loads"].split()), n["grp"],
                    n["length"], n["detour"], moved(n["route"]), n["ref_route"]))
            stub_keys = {f"stub:{name}/{s['name']}": f"stub:{new}/{s['name']}"
                         for s in self.spine_stub_rows(spine["id"])}
            for table in ("net_route_rule", "net_route_status"):
                for r in ex(f"SELECT * FROM {table}").fetchall():
                    key = net_map.get(r[0], stub_keys.get(r[0]))
                    if key is not None:
                        ex(f"INSERT OR REPLACE INTO {table} VALUES (?, ?)", (key, r[1]))
            for w in ex("SELECT * FROM net_wire ORDER BY id").fetchall():
                new_owner = owner(w["net"])
                if new_owner is not None:
                    ex("INSERT INTO net_wire (net, seq, kind, layer, rect, shield_net, via_def, "
                       "status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (new_owner, w["seq"], w["kind"], w["layer"], moved(w["rect"]),
                        net_of(w["shield_net"]), w["via_def"], w["status"]))
                    counts[2] += 1
        return tuple(counts)

    def rename_net(self, old: str, new: str, roots=()):
        """rename_obj: net old is net new everywhere it is named: a spine net,
        the root net of the spines roots (their spine.root_net), connect_pin's
        connections, the route_pin straps and pin wires on it, its wires and
        its stub's (<net>_stub), the auto vias on them and the net they carry,
        its route rule, route status and via assignments. The vias are derived
        again. Atomic. Returns the number of wires renamed."""
        ex = self.conn.execute
        with self.conn:
            ex("UPDATE spine_net SET name = ? WHERE name = ?", (new, old))
            for spine in roots:
                ex("UPDATE spine SET root_net = ? WHERE name = ?", (new, spine))
            ex("UPDATE connection SET net = ? WHERE net = ?", (new, old))
            ex("UPDATE strap SET net = ? WHERE net = ?", (new, old))
            ex("UPDATE pin_wire SET net = ? WHERE net = ?", (new, old))
            n = 0
            for was, now in ((old, new), (stub_owner(old), stub_owner(new))):
                n += ex("UPDATE net_wire SET net = ? WHERE net = ?", (now, was)).rowcount
                prefix = f"auto_via:net_wire:{was}/"
                ex("UPDATE net_wire SET net = ? || substr(net, ?) WHERE substr(net, 1, ?) = ?",
                   (f"auto_via:net_wire:{now}/", len(prefix) + 1, len(prefix), prefix))
            ex("UPDATE net_wire SET shield_net = ? WHERE shield_net = ?", (new, old))
            ex("UPDATE strap_stretch SET owner = ? WHERE owner = ?", (new, old))
            for table in ("net_route_rule", "net_route_status", "via_assignment"):
                ex(f"UPDATE {table} SET net = ? WHERE net = ?", (new, old))
            ex("DELETE FROM via")
        self.via_stamp = None                 # derived again from the wires
        self.netlist = None
        return n

    def rename_inst(self, old: str, new: str):
        """rename_obj: instance old is instance new everywhere it is named:
        its spine membership (as a member and a driver), the stub and spine
        nets it drives or loads, its route_pin straps and pin wires,
        connect_pin's connections (as load and driver), its
        optimize_pg_connection wires (pg:<inst>) and the auto vias on its
        straps and pin wires. The nets keep their names. The vias are derived
        again. Atomic."""
        ex = self.conn.execute
        with self.conn:
            ex("UPDATE inst SET name = ? WHERE name = ?", (new, old))
            ex("UPDATE spine_member SET inst = ? WHERE inst = ?", (new, old))
            ex("UPDATE spine_member SET driver = ? WHERE driver = ?", (new, old))
            ex("UPDATE spine_stub SET driver = ? WHERE driver = ?", (new, old))
            ex("UPDATE spine_net SET driver = ? WHERE driver = ?", (new, old))
            for r in ex("SELECT id, loads FROM spine_net").fetchall():
                words = (r["loads"] or "").split()
                if old in words:
                    ex("UPDATE spine_net SET loads = ? WHERE id = ?",
                       (" ".join(new if w == old else w for w in words), r["id"]))
            ex("UPDATE strap SET inst = ? WHERE inst = ?", (new, old))
            ex("UPDATE strap_stretch SET inst = ? WHERE inst = ?", (new, old))
            ex("UPDATE strap_stretch SET owner = ? WHERE owner = ?", (f"pg:{new}", f"pg:{old}"))
            ex("UPDATE pin_wire SET inst = ? WHERE inst = ?", (new, old))
            ex("UPDATE connection SET inst = ? WHERE inst = ?", (new, old))
            prefix = f"{old}/"
            ex("UPDATE connection SET driver = ? || substr(driver, ?) "
               "WHERE substr(driver, 1, ?) = ?", (f"{new}/", len(prefix) + 1, len(prefix),
                                                  prefix))
            for was, now in ((f"pg:{old}", f"pg:{new}"),):
                ex("UPDATE net_wire SET net = ? WHERE net = ?", (now, was))
            for was, now in ((f"auto_via:strap:{old}/", f"auto_via:strap:{new}/"),
                             (f"auto_via:pin_wire:{old}/", f"auto_via:pin_wire:{new}/"),
                             (f"auto_via:net_wire:pg:{old}/", f"auto_via:net_wire:pg:{new}/")):
                ex("UPDATE net_wire SET net = ? || substr(net, ?) WHERE substr(net, 1, ?) = ?",
                   (now, len(was) + 1, len(was), was))
            ex("DELETE FROM via")
        self.via_stamp = None
        self.netlist = None

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
        names = [r["name"] for r in self.spine_net_rows(spine["id"])]
        owners = names + [stub_owner(n) for n in names] + [f"pg:{n}" for n in members]
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
                ex("DELETE FROM strap_stretch WHERE inst = ?", (n,))
            for n in owners:
                gone[2] += ex("DELETE FROM net_wire WHERE net = ?", (n,)).rowcount
            _unstretch(self.conn, owners)
        return tuple(gone)

    def _move_stretches(self, insts, dx, dy):
        """Move the stretches and base rects of the straps of insts (their
        rects are moved with the straps)."""
        for n in insts:
            self.conn.execute("UPDATE strap_stretch SET x1 = ROUND(x1 + ?, 6), "
                              "x2 = ROUND(x2 + ?, 6) WHERE inst = ?", (dx, dx, n))
            for r in self.conn.execute("SELECT id, base_rect FROM strap WHERE inst = ? AND "
                                       "base_rect IS NOT NULL", (n,)).fetchall():
                self.conn.execute("UPDATE strap SET base_rect = ? WHERE id = ?", (" ".join(
                    _num(round(float(c) + (dy if k % 2 else dx), 6))
                    for k, c in enumerate(r["base_rect"].split())), r["id"]))

    def _move_auto_vias(self, prefixes, dx, dy):
        """Move the auto vias (stretch_wire) of the wires whose owner net
        starts with one of prefixes."""
        for p in prefixes:
            for r in self.conn.execute("SELECT id, rect FROM net_wire WHERE substr(net, 1, ?) = ?",
                                       (len(p), p)).fetchall():
                rect = " ".join(_num(round(float(c) + (dy if k % 2 else dx), 6))
                                for k, c in enumerate(r["rect"].split()))
                self.conn.execute("UPDATE net_wire SET rect = ? WHERE id = ?", (rect, r["id"]))

    def _drop_auto_vias(self, prefixes, keep=()):
        """Remove the auto vias whose owner starts with one of prefixes, but
        not those owned by a wire in keep (a fixed wire's)."""
        for p in prefixes:
            for r in self.conn.execute("SELECT id, net FROM net_wire WHERE substr(net, 1, ?) = ?",
                                       (len(p), p)).fetchall():
                if r["net"] not in keep:
                    self.conn.execute("DELETE FROM net_wire WHERE id = ?", (r["id"],))

    def set_inst_orient(self, name: str, orient: str):
        with self.conn:
            self.conn.execute("UPDATE inst SET orient = ? WHERE name = ?", (orient, name))

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
        Returns the number of straps replaced. The stretches routes made of
        the old straps go; dropped_stretches: the nets whose they were (to be
        routed again)."""
        with self.conn:
            old = self.conn.execute("DELETE FROM strap WHERE inst = ?", (inst,)).rowcount
            self.dropped_stretches = sorted({r[0] for r in self.conn.execute(
                "SELECT owner FROM strap_stretch WHERE inst = ? AND owner != ?",
                (inst, f"pg:{inst}"))})
            self.conn.execute("DELETE FROM strap_stretch WHERE inst = ?", (inst,))
            self.conn.execute("DELETE FROM strap_stretch WHERE owner = ?", (f"pg:{inst}",))
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
        """Replace a net's wires with (kind, layer, rect text[, shield net[,
        via definitions]]): its route_net wires, or with stub=True its
        route_final_stub ones (kind stub, their crossings and shields),
        stored under <net>_stub (stub_owner), a stub wire and crossing with
        net as its shield_net: the net it carries. Fixed wires (set_db
        .route_status fixed) stay, with their auto vias. Returns how many it
        replaced."""
        if stub:
            net = stub_owner(net[:-len(STUB)] if net.endswith(STUB) else net)
            leaf = net[:-len(STUB)]
            wires = [tuple(w[:3]) + ((w[3] if len(w) > 3 and w[3] else leaf),) + tuple(w[4:])
                     if w[0] in ("stub", "stub_cross") else w for w in wires]
        part = ("kind LIKE 'stub%'" if stub else "kind NOT LIKE 'stub%'") + \
            " AND COALESCE(status, '') != 'fixed'"
        with self.conn:
            if not net.startswith("auto_via:"):     # the wires are rebuilt: their vias go
                kept = {r[0] for r in self.conn.execute(
                    "SELECT seq FROM net_wire WHERE net = ? AND status = 'fixed'", (net,))}
                self._drop_auto_vias([f"auto_via:net_wire:{net}/"], keep=[
                    f"auto_via:net_wire:{net}/{seq}" for seq in kept])
            old = self.conn.execute(f"DELETE FROM net_wire WHERE net = ? AND {part}",
                                    (net,)).rowcount
            old += _unstretch(self.conn, [net])     # its stretches of straps go too
            wires = [w for w in wires if w[0] not in STRETCH_KINDS or not _stretch(
                self.conn, net, w[0], w[1], w[2], w[3] if len(w) > 3 and w[3] else net)]
            first = self.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM net_wire "
                                      "WHERE net = ?", (net,)).fetchone()[0]
            self.conn.executemany("INSERT INTO net_wire (net, seq, kind, layer, rect, "
                                  "shield_net, via_def) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  [(net, k) + tuple(w) + (None,) * (5 - len(w))
                                   for k, w in enumerate(wires, start=first + 1)])
        return old

    def stub_wire_rows(self, net: str):
        """The route_final_stub rows of the stub a leaf net drives (stored
        under <net>_stub: its wires, crossings and shields)."""
        return self.conn.execute("SELECT * FROM net_wire WHERE net = ? ORDER BY id",
                                 (stub_owner(net),)).fetchall()

    def add_net_wires(self, wires):
        """Add wires (net, kind, layer, rect text, shield net, via definitions)
        after the ones their nets have (insert_vias: the vias of a wire, under
        its auto_via: net). Returns their (net, seq)."""
        last, made = {}, []
        with self.conn:
            for net, *rest in wires:
                if rest[0] in STRETCH_KINDS and _stretch(self.conn, net, rest[0], rest[1],
                                                         rest[2], rest[3] or net):
                    continue             # a strap lengthened, not a piece
                if net not in last:
                    last[net] = self.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM net_wire "
                                                  "WHERE net = ?", (net,)).fetchone()[0]
                last[net] += 1
                self.conn.execute("INSERT INTO net_wire (net, seq, kind, layer, rect, "
                                  "shield_net, via_def) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (net, last[net], *rest))
                made.append((net, last[net]))
        return made

    def set_net_wire_via_def(self, row_id: int, via_def):
        """The via definitions of an insert_vias via (None: as assigned)."""
        with self.conn:
            self.conn.execute("UPDATE net_wire SET via_def = ? WHERE id = ?", (via_def, row_id))

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
            if table == "strap":         # edited by hand: its shape now, stretches and all
                s = self.conn.execute("SELECT inst, seq FROM strap WHERE id = ?",
                                      (row_id,)).fetchone()
                self.conn.execute("DELETE FROM strap_stretch WHERE inst = ? AND seq = ?",
                                  (s["inst"], s["seq"]))
                self.conn.execute("UPDATE strap SET base_rect = NULL WHERE id = ?", (row_id,))
            self.conn.execute(f"UPDATE {table} SET rect = ? WHERE id = ?", (rect, row_id))

    def delete_wires(self, items):
        """Remove route shapes [(table, row id)] (delete_wire)."""
        with self.conn:
            for table, row_id in items:
                assert table in ("net_wire", "strap", "pin_wire")
                if table == "strap":     # its stretches go with it
                    s = self.conn.execute("SELECT inst, seq FROM strap WHERE id = ?",
                                          (row_id,)).fetchone()
                    if s is not None:
                        self.conn.execute("DELETE FROM strap_stretch WHERE inst = ? AND "
                                          "seq = ?", (s["inst"], s["seq"]))
                self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    def restore_wires(self, rows):
        """Put route shapes [(table, row as a dict)] back as they were, row
        ids included, so they keep their place in the table's order
        (delete_wire -undo)."""
        with self.conn:
            for table, row in rows:
                assert table in ("net_wire", "strap", "pin_wire")
                self.conn.execute(f"INSERT INTO {table} ({', '.join(row)}) "
                                  f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))

    def wire_id_used(self, table: str, row_id: int) -> bool:
        assert table in ("net_wire", "strap", "pin_wire")
        return self.conn.execute(f"SELECT 1 FROM {table} WHERE id = ?",
                                 (row_id,)).fetchone() is not None

    def set_wire_fixed(self, row_id: int, fixed: bool):
        """Fix one net wire (set_db net_wire .route_status), or free it."""
        with self.conn:
            self.conn.execute("UPDATE net_wire SET status = ? WHERE id = ?",
                              ("fixed" if fixed else None, row_id))

    def fixed_wire_rows(self, net: str):
        return self.conn.execute("SELECT * FROM net_wire WHERE net = ? AND status = 'fixed' "
                                 "ORDER BY id", (net,)).fetchall()

    def net_wire_row(self, net: str, seq: int):
        return self.conn.execute("SELECT * FROM net_wire WHERE net = ? AND seq = ?",
                                 (net, seq)).fetchone()

    def route_nets(self):
        """The nets with a route shape on them: of straps, pin wires and net
        wires, and the nets of shields and stubs (shield_net; a stub's rows
        are under <net>_stub, not a net)."""
        return [r[0] for r in self.conn.execute(
            "SELECT net FROM strap UNION SELECT net FROM pin_wire UNION "
            "SELECT net FROM net_wire WHERE kind NOT LIKE 'stub%' UNION "
            "SELECT shield_net FROM net_wire ORDER BY 1")
            if r[0]]

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

    def stretch_rows(self, owner=None, inst=None):
        """The strap stretches (strap_stretch) of an owner net, or of an
        instance's straps, or all."""
        if owner is not None:
            return self.conn.execute("SELECT * FROM strap_stretch WHERE owner = ? ORDER BY id",
                                     (owner,)).fetchall()
        if inst is not None:
            return self.conn.execute("SELECT * FROM strap_stretch WHERE inst = ? ORDER BY id",
                                     (inst,)).fetchall()
        return self.conn.execute("SELECT * FROM strap_stretch ORDER BY id").fetchall()

    def stretch_pieces(self, owner, kinds=STRETCH_KINDS):
        """[(layer, (x1, y1, x2, y2))]: the stretches of owner (of kinds) as
        the pieces of metal they add to their straps."""
        found = []
        for r in self.conn.execute("SELECT t.kind, t.x1, t.x2, s.layer, s.rect FROM "
                                   "strap_stretch t JOIN strap s ON s.inst = t.inst AND "
                                   "s.seq = t.seq WHERE t.owner = ? ORDER BY t.id", (owner,)):
            if r["kind"] in kinds:
                _, y1, _, y2 = _floats(r["rect"])
                found.append((r["layer"], (r["x1"], y1, r["x2"], y2)))
        return found

    def unstretch(self, owners, kinds=None):
        """Take back the strap stretches of owners (of kinds, else all)."""
        with self.conn:
            return _unstretch(self.conn, owners, kinds)

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
        """Replace the in-memory database with the file at path. Returns the
        schema version of the file (20 to 23: upgraded here; the tables and
        columns it did not have are empty)."""
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            try:
                row = src.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            except sqlite3.DatabaseError as exc:
                raise SchemaMismatch(f"not an htree database ({exc})")
            found = row[0] if row else "none"
            if found not in (str(SCHEMA_VERSION), "25", "24", "23", "22", "21", "20"):
                raise SchemaMismatch(f"schema version {found}, expected {SCHEMA_VERSION}")
            conn = self._new_memory()
            src.backup(conn)
        finally:
            src.close()
        with conn:          # the same data, with the tables and columns it did not have
            if found == "20":
                conn.executescript(VIA_SCHEMA)
            if found in ("20", "21"):
                conn.executescript(CONNECTION_SCHEMA)
            # also a version 24 file written before these columns came
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'net_route_status'"
                            ).fetchone() is None:
                conn.executescript(ROUTE_STATUS_SCHEMA)
            columns = [r[1] for r in conn.execute("PRAGMA table_info(net_wire)")]
            if "via_def" not in columns:
                conn.execute("ALTER TABLE net_wire ADD COLUMN via_def TEXT")
            if "status" not in columns:
                conn.execute("ALTER TABLE net_wire ADD COLUMN status TEXT")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'strap_stretch'"
                            ).fetchone() is None:
                conn.executescript(STRETCH_SCHEMA)
            if "base_rect" not in [r[1] for r in conn.execute("PRAGMA table_info(strap)")]:
                conn.execute("ALTER TABLE strap ADD COLUMN base_rect TEXT")
            if "root_net" not in [r[1] for r in conn.execute("PRAGMA table_info(spine)")]:
                conn.execute("ALTER TABLE spine ADD COLUMN root_net TEXT")
            cells = [r[1] for r in conn.execute("PRAGMA table_info(spine_cell)")]
            for column in ("track_in", "track_out"):
                if column not in cells:
                    conn.execute(f"ALTER TABLE spine_cell ADD COLUMN {column} INTEGER")
            _stubs_apart(conn)
            _pieces_to_stretches(conn)
            conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'",
                         (str(SCHEMA_VERSION),))
        self.conn.close()
        self.conn = conn
        self.deleted_wires.clear()            # wires of the old database
        self.redrawn = []
        self.show_only.clear()                # ... and its display filter
        self.highlights.clear()               # ... and its colours
        self.drc = None                       # ... and its check_drc run
        self.via_stamp = None
        self.netlist = None
        return found


STUB = "_stub"
CARRIED = ("stub", "stub_cross")   # their shield_net is the signal net they carry, not power


def stub_owner(net):
    """The name a stub's wires are stored under: <its leaf's net>_stub."""
    return net + STUB


def _stubs_apart(conn):
    """Stub rows of a file written before stubs had their own name (under
    their leaf's net) go under <net>_stub, with the auto vias on them; a
    stub wire and crossing carries its leaf's net in shield_net."""
    old = conn.execute("SELECT id, net, seq, kind FROM net_wire WHERE kind LIKE 'stub%' "
                       "AND substr(net, -5) != '_stub'").fetchall()
    for row_id, net, seq, kind in old:
        conn.execute("UPDATE net_wire SET net = 'auto_via:net_wire:' || ? || '/' || ? "
                     "WHERE net = 'auto_via:net_wire:' || ? || '/' || ?",
                     (stub_owner(net), seq, net, seq))
        conn.execute("UPDATE net_wire SET net = ?, shield_net = CASE WHEN kind IN "
                     "('stub', 'stub_cross') THEN COALESCE(shield_net, ?) ELSE shield_net "
                     "END WHERE id = ?", (stub_owner(net), net, row_id))


def _via_prefixes(insts):
    """Owner-net prefixes of the auto vias (stretch_wire) on the route_pin
    and optimize_pg_connection shapes of instances."""
    return [p for n in insts for p in (f"auto_via:strap:{n}/", f"auto_via:pin_wire:{n}/",
                                       f"auto_via:net_wire:pg:{n}/")]


def _floats(rect):
    return tuple(float(c) for c in rect.split()) if isinstance(rect, str) else tuple(rect)


def base_rect(strap):
    """(x1, y1, x2, y2) of a strap row as route_pin made it, without the
    stretches routes added: what its max_extension is measured from."""
    return _floats(strap["base_rect"] or strap["rect"])


def _stretch(conn, owner, kind, layer, rect, net):
    """Lengthen the strap a route's piece (kind extension, shield_ext or
    pg_ext) on layer lies along: the strap of net (the piece's: the signal
    net of an extension, the power net of the others) on that layer the
    piece touches end on, over most of its height. Its rect gets the
    piece's x range; its y range stays. False when no strap is there (the
    piece is kept as a wire)."""
    x1, y1, x2, y2 = _floats(rect)
    own = owner[3:] if owner.startswith("pg:") else None     # optimize_pg_connection's cell
    best, rank = None, None
    for s in conn.execute("SELECT * FROM strap WHERE layer = ? AND net = ?", (layer, net)):
        bx1, by1, bx2, by2 = _floats(s["base_rect"] or s["rect"])
        sx1, _, sx2, _ = _floats(s["rect"])
        o = min(y2, by2) - max(y1, by1)
        if o <= (by2 - by1) / 2 or x1 > sx2 + 1e-6 or x2 < sx1 - 1e-6:
            continue
        # straps of two cells side by side can overlap on one track: the piece is the
        # one whose route_pin end it starts from (of the cell it is for)
        end = abs(x2 - bx1) < 1e-6 or abs(x1 - bx2) < 1e-6
        r = (own is None or s["inst"] == own, end, round(o, 9))
        if rank is None or r > rank:
            best, rank = s, r
    if best is None:
        return False
    conn.execute("INSERT INTO strap_stretch (inst, seq, owner, kind, x1, x2) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (best["inst"], best["seq"], owner, kind, x1, x2))
    _restretch(conn, best["inst"], best["seq"])
    return True


def _restretch(conn, inst, seq):
    """A strap's rect from its base_rect and its stretches."""
    s = conn.execute("SELECT * FROM strap WHERE inst = ? AND seq = ?", (inst, seq)).fetchone()
    if s is None:
        return
    base = s["base_rect"] or s["rect"]
    bx1, by1, bx2, by2 = _floats(base)
    rows = conn.execute("SELECT x1, x2 FROM strap_stretch WHERE inst = ? AND seq = ?",
                        (inst, seq)).fetchall()
    if not rows:
        conn.execute("UPDATE strap SET rect = ?, base_rect = NULL WHERE id = ?", (base, s["id"]))
        return
    x1 = min([bx1] + [r["x1"] for r in rows])
    x2 = max([bx2] + [r["x2"] for r in rows])
    rect = " ".join(_num(round(v, 6)) for v in (x1, by1, x2, by2))
    conn.execute("UPDATE strap SET rect = ?, base_rect = ? WHERE id = ?", (rect, base, s["id"]))


def _unstretch(conn, owners, kinds=None):
    """Take back the stretches the owners made (of kinds, else all).
    Returns how many."""
    touched, n = set(), 0
    for owner in owners:
        for r in conn.execute("SELECT * FROM strap_stretch WHERE owner = ?", (owner,)).fetchall():
            if kinds is None or r["kind"] in kinds:
                conn.execute("DELETE FROM strap_stretch WHERE id = ?", (r["id"],))
                touched.add((r["inst"], r["seq"]))
                n += 1
    for inst, seq in touched:
        _restretch(conn, inst, seq)
    return n


def _pieces_to_stretches(conn):
    """The extension pieces of a file written before straps were stretched
    (net_wire kinds extension, shield_ext, pg_ext) lengthen their straps
    instead. A crossing box of the same net on the piece moves onto the
    strap's y range with it (a strap rebuilt after the route left the piece
    and its box off the strap)."""
    for r in conn.execute("SELECT * FROM net_wire WHERE kind IN ('extension', 'shield_ext', "
                          "'pg_ext') ORDER BY id").fetchall():
        if _stretch(conn, r["net"], r["kind"], r["layer"], r["rect"],
                    r["shield_net"] or r["net"]):
            conn.execute("DELETE FROM net_wire WHERE id = ?", (r["id"],))
    _boxes_onto_straps(conn)


def _boxes_onto_straps(conn):
    """A crossing box on a strap of its net (cross, pg_cross, stub_cross:
    the net it carries) whose y range is a little off the strap's (less than
    half its height: the strap made again after the route) goes onto it."""
    straps = {}
    for s in conn.execute("SELECT net, layer, rect FROM strap"):
        straps.setdefault((s["net"], s["layer"]), []).append(_floats(s["rect"]))
    for c in conn.execute("SELECT id, net, layer, rect, shield_net FROM net_wire WHERE kind IN "
                          "('cross', 'pg_cross', 'stub_cross')").fetchall():
        cx1, cy1, cx2, cy2 = _floats(c["rect"])
        for layer in c["layer"].split("/"):
            for sx1, sy1, sx2, sy2 in straps.get((c["shield_net"] or c["net"], layer), ()):
                h = sy2 - sy1
                if cx2 <= sx1 + 1e-6 or cx1 >= sx2 - 1e-6 or \
                        min(cy2, sy2) - max(cy1, sy1) <= h / 2:
                    continue
                if abs(cy1 - sy1) > 1e-6 and abs(cy2 - cy1 - h) < 1e-6:     # off, as tall
                    conn.execute("UPDATE net_wire SET rect = ? WHERE id = ?",
                                 (" ".join(_num(round(v, 6)) for v in (cx1, sy1, cx2, sy2)),
                                  c["id"]))
                break
