"""Database objects as Cadence-style handles and their attributes.

    tech                              tech data (read_tech)
    layer:<layer>                     a tech layer
    library_physical                  the cell library (read_lef)
    lib_cell:<cell>                   a MACRO
    lib_pin:<cell>/<pin>              a PIN of a cell
    lib_port:<cell>/<pin>/<n>         the n-th PORT of a pin (1-based)
    layer_shape:<cell>/<pin>/<n>/<k>  the k-th RECT or POLYGON of a port
    spine_spec:<spec>                 a spine spec (read_spine_spec)
    spine_level:<spec>/<level>        a level of a spine spec (L1, L2, ...)
    spine_cell:<spec>/<level>/<cell>  a cell of a level
    design:<design>                   the design read by read_def
    port:<design>/<pin>               a top-level pin (DEF PINS)
    port_shape:<design>/<pin>/<k>     the k-th shape of a port
    track_pattern:<design>/<k>        the k-th TRACKS statement of the DEF
    track_assignment:<layer>          a layer's net pattern (assign_track_for_route)

Attribute values are Python scalars, None (empty), or lists. Attributes that
refer to other objects return handles, so get_db can keep walking.
"""

from core.messages import HtreeError

UNKNOWN_OBJECT = 22
UNKNOWN_ATTR = 23
NO_TECH = 25
NO_LIBRARY = 26
NO_SPINE_SPEC = 27
NO_DESIGN = 28

# Ordered attribute names per object type. Relation attrs return handles.
TECH_ATTRS = ["obj_type", "file", "lef_version", "db_units", "manufacturing_grid",
              "layer", "layers", "extra"]
LAYER_ATTRS = ["obj_type", "name", "type", "direction", "pitch_x", "pitch_y",
               "offset_x", "offset_y", "width", "min_width", "max_width", "area",
               "min_enclosed_area", "min_step", "min_step_max_edges", "min_spacing",
               "extra", "lef_text", "tech"]
LIBRARY_PHYSICAL_ATTRS = ["obj_type", "files", "lib_cells", "extra"]
LIB_CELL_ATTRS = ["obj_type", "name", "ref_name", "class", "size_x", "size_y", "site",
                  "lib_pins", "file", "extra", "lef_text", "library_physical"]
LIB_PIN_ATTRS = ["obj_type", "name", "direction", "use", "lib_ports", "layers",
                 "tech_layers", "extra", "lib_cell"]
LIB_PORT_ATTRS = ["obj_type", "name", "layer_shapes", "layers", "extra", "lib_pin"]
LAYER_SHAPE_ATTRS = ["obj_type", "name", "layer", "type", "rect", "points", "mask",
                     "in_tech", "lib_port"]
SPINE_SPEC_ATTRS = ["obj_type", "name", "type", "units", "point", "root_net",
                    "max_drive_length", "count_stub_in_drive", "origin_x", "level_pitch_x",
                    "orientation", "span", "stub_count", "stub_gap", "stub_tap", "stub_order",
                    "spine_levels", "file", "extra", "yaml_text"]
SPINE_LEVEL_ATTRS = ["obj_type", "name", "spine_cells", "spine_spec"]
SPINE_CELL_ATTRS = ["obj_type", "name", "input", "output", "extra", "spine_level"]
DESIGN_ATTRS = ["obj_type", "name", "file", "def_version", "units", "boundary", "bbox",
                "area", "ports", "track_patterns"]
TRACK_PATTERN_ATTRS = ["obj_type", "name", "direction", "start", "num_tracks", "step", "end",
                       "mask", "same_mask", "layers", "design"]
PORT_ATTRS = ["obj_type", "name", "net", "direction", "use", "special", "status",
              "location", "orient", "layers", "rect", "port_shapes", "extra", "design"]
PORT_SHAPE_ATTRS = ["obj_type", "name", "layer", "type", "rect", "points", "mask",
                    "in_tech", "port"]
TRACK_ASSIGNMENT_ATTRS = ["obj_type", "name", "layer", "direction", "pattern", "period",
                          "num_tracks", "counts", "tracks"]
ATTRS = {"tech": TECH_ATTRS, "layer": LAYER_ATTRS,
         "library_physical": LIBRARY_PHYSICAL_ATTRS, "lib_cell": LIB_CELL_ATTRS,
         "lib_pin": LIB_PIN_ATTRS, "lib_port": LIB_PORT_ATTRS,
         "layer_shape": LAYER_SHAPE_ATTRS, "spine_spec": SPINE_SPEC_ATTRS,
         "spine_level": SPINE_LEVEL_ATTRS, "spine_cell": SPINE_CELL_ATTRS,
         "design": DESIGN_ATTRS, "port": PORT_ATTRS, "port_shape": PORT_SHAPE_ATTRS,
         "track_pattern": TRACK_PATTERN_ATTRS, "track_assignment": TRACK_ASSIGNMENT_ATTRS}
# (object type, attr) -> object type of the handles the attr returns.
RELATIONS = {("tech", "layer"): "layer", ("tech", "layers"): "layer",
             ("layer", "tech"): "tech",
             ("library_physical", "lib_cells"): "lib_cell",
             ("lib_cell", "library_physical"): "library_physical",
             ("lib_cell", "lib_pins"): "lib_pin", ("lib_pin", "lib_cell"): "lib_cell",
             ("lib_pin", "lib_ports"): "lib_port", ("lib_port", "lib_pin"): "lib_pin",
             ("lib_port", "layer_shapes"): "layer_shape",
             ("layer_shape", "lib_port"): "lib_port",
             ("spine_spec", "spine_levels"): "spine_level",
             ("spine_level", "spine_spec"): "spine_spec",
             ("spine_level", "spine_cells"): "spine_cell",
             ("spine_cell", "spine_level"): "spine_level",
             ("design", "ports"): "port", ("port", "design"): "design",
             ("port", "port_shapes"): "port_shape", ("port_shape", "port"): "port",
             ("design", "track_patterns"): "track_pattern",
             ("track_pattern", "design"): "design"}
# Objects with exactly one instance; the handle is the type name.
SINGLETONS = ("tech", "library_physical")
# Number of '/'-separated parts in the name of each library object.
_PARTS = {"lib_cell": 1, "lib_pin": 2, "lib_port": 3, "layer_shape": 4}
_SPINE_PARTS = {"spine_spec": 1, "spine_level": 2, "spine_cell": 3}
_DESIGN_PARTS = {"design": 1, "port": 2, "port_shape": 3, "track_pattern": 2}


def is_handle(word: str) -> bool:
    if word in SINGLETONS:
        return True
    kind, sep, name = word.partition(":")
    return bool(sep and kind and name)


def obj_type(handle: str) -> str:
    return handle if handle in SINGLETONS else handle.partition(":")[0]


def name_of(handle: str) -> str:
    """The object's own name: 'A' for lib_pin:INV/A, '2' for lib_port:INV/A/2."""
    if handle in SINGLETONS:
        return handle
    name = handle.partition(":")[2]
    kind = obj_type(handle)
    nested = kind in _PARTS or kind in _SPINE_PARTS or kind in _DESIGN_PARTS
    return name.rsplit("/", 1)[-1] if nested else name


def require_tech(db):
    if not db.has_tech():
        raise HtreeError(NO_TECH, "no tech data in the database; run read_tech first")


def require_library(db):
    if not db.has_library():
        raise HtreeError(NO_LIBRARY, "no physical library in the database; run read_lef first")


def require_spine_specs(db):
    if not db.has_spine_specs():
        raise HtreeError(NO_SPINE_SPEC, "no spine spec in the database; "
                         "run read_spine_spec first")


def require_design(db):
    if not db.has_design():
        raise HtreeError(NO_DESIGN, "no design in the database; run read_def first")


def _missing(handle):
    return HtreeError(UNKNOWN_OBJECT, f"object '{handle}' does not exist")


def _lib_row(db, handle: str):
    """DB row of a library object, or raise. Cell and pin names hold no '/'
    (LEF DIVIDERCHAR), so the name splits cleanly from the right."""
    kind = obj_type(handle)
    name = handle.partition(":")[2]
    parts = name.split("/") if kind != "lib_cell" else [name]
    if len(parts) != _PARTS[kind]:
        raise _missing(handle)
    if kind == "lib_cell":
        row = db.lib_cell_row(name)
    else:
        row = db.lib_pin_row(parts[0], parts[1])
        if row is not None and kind in ("lib_port", "layer_shape"):
            row = db.lib_port_row(row["id"], _index(parts[2])) if _index(parts[2]) else None
        if row is not None and kind == "layer_shape":
            k = _index(parts[3])
            shapes = db.shape_rows(row["id"])
            row = shapes[k - 1] if k and k <= len(shapes) else None
    if row is None:
        raise _missing(handle)
    return row


def _index(text: str):
    return int(text) if text.isdigit() and int(text) > 0 else None


def check_exists(db, handle: str):
    kind = obj_type(handle)
    if kind == "tech":
        require_tech(db)
        return
    if kind == "library_physical":
        require_library(db)
        return
    if kind in _PARTS:
        _lib_row(db, handle)
        return
    if kind in _SPINE_PARTS:
        _spine_row(db, handle)
        return
    if kind in _DESIGN_PARTS:
        _design_row(db, handle)
        return
    if kind == "track_assignment" and db.track_assignment_row(handle.partition(":")[2]):
        return
    if kind == "layer" and db.layer_row(handle.partition(":")[2]) is not None:
        return
    raise _missing(handle)


def exists(db, handle: str) -> bool:
    try:
        check_exists(db, handle)
        return True
    except HtreeError:
        return False


def selected(db):
    """Selected handles that still exist (a new DEF can make old ones stale)."""
    db.selection[:] = [h for h in db.selection if exists(db, h)]
    return list(db.selection)


def attr_names(handle: str):
    return ATTRS.get(obj_type(handle), [])


def is_relation(handle: str, attr: str) -> bool:
    return (obj_type(handle), attr) in RELATIONS


def get_attr(db, handle: str, attr: str):
    kind = obj_type(handle)
    if attr not in attr_names(handle):
        raise HtreeError(UNKNOWN_ATTR, f"'{attr}' is not an attribute of {kind} objects. "
                         f"Valid: {' '.join(attr_names(handle))}")
    if attr == "obj_type":
        return kind
    if kind == "tech":
        require_tech(db)
        if attr in ("layer", "layers"):
            return [f"layer:{n}" for n in db.layer_names()]
        if attr == "extra":
            return [r["text"] for r in db.tech_extra()]
        return db.tech_row()[attr]
    if kind == "library_physical":
        require_library(db)
        if attr == "files":
            return db.lef_files()
        if attr == "lib_cells":
            return [f"lib_cell:{n}" for n in db.lib_cell_names()]
        return [r["text"] for r in db.lef_extra()]          # extra
    if kind in _PARTS:
        return _lib_attr(db, handle, kind, attr)
    if kind in _SPINE_PARTS:
        return _spine_attr(db, handle, kind, attr)
    if kind in _DESIGN_PARTS:
        return _design_attr(db, handle, kind, attr)
    if kind == "track_assignment":
        return _track_assignment_attr(db, handle, attr)
    row = db.layer_row(handle.partition(":")[2])
    if row is None:
        raise _missing(handle)
    if attr == "tech":
        return "tech"
    if attr == "extra":
        return db.layer_extra(row["id"])
    return row[attr]


def _lib_attr(db, handle, kind, attr):
    row = _lib_row(db, handle)
    name = handle.partition(":")[2]
    parent = name.rsplit("/", 1)[0]
    if attr == "name":
        return name_of(handle)
    if kind == "lib_cell":
        if attr == "ref_name":          # the MACRO name
            return row["name"]
        if attr == "lib_pins":
            return [f"lib_pin:{name}/{p}" for p in db.lib_pin_names(row["id"])]
        if attr == "library_physical":
            return "library_physical"
        if attr == "extra":
            return db.lib_extra("lib_cell", row["id"])
        return row[attr]
    if kind == "lib_pin":
        if attr == "lib_ports":
            return [f"lib_port:{name}/{n}" for n in db.lib_port_seqs(row["id"])]
        if attr == "layers":
            return db.pin_layers(row["id"])
        if attr == "tech_layers":
            tech = set(db.layer_names())
            return [l for l in db.pin_layers(row["id"]) if l in tech]
        if attr == "lib_cell":
            return f"lib_cell:{parent}"
        if attr == "extra":
            return db.lib_extra("lib_pin", row["id"])
        return row[attr]
    if kind == "lib_port":
        shapes = db.shape_rows(row["id"])
        if attr == "layer_shapes":
            return [f"layer_shape:{name}/{s['seq']}" for s in shapes]
        if attr == "layers":
            return list(dict.fromkeys(s["layer"] for s in shapes))
        if attr == "lib_pin":
            return f"lib_pin:{parent}"
        return db.lib_extra("lib_port", row["id"])          # extra
    # layer_shape
    if attr == "rect":                  # bounding box; the rect itself for a RECT
        words = row["points"].split()     # keep the stored text: '0', not '0.0'
        xs, ys = words[0::2], words[1::2]
        return " ".join((min(xs, key=float), min(ys, key=float),
                         max(xs, key=float), max(ys, key=float)))
    if attr == "in_tech":
        return "true" if db.layer_row(row["layer"]) is not None else "false"
    if attr == "lib_port":
        return f"lib_port:{parent}"
    return row[attr]


def _spine_row(db, handle: str):
    kind = obj_type(handle)
    parts = handle.partition(":")[2].split("/")
    if len(parts) != _SPINE_PARTS[kind]:
        raise _missing(handle)
    if kind == "spine_spec":
        row = db.spine_spec_row(parts[0])
    else:
        row = db.spine_level_row(parts[0], parts[1])
        if row is not None and kind == "spine_cell":
            row = db.spine_cell_row(row["id"], parts[2])
    if row is None:
        raise _missing(handle)
    return row


def _spine_attr(db, handle, kind, attr):
    row = _spine_row(db, handle)
    name = handle.partition(":")[2]
    parent = name.rsplit("/", 1)[0]
    if attr == "name":
        return name_of(handle)
    if kind == "spine_spec":
        if attr == "spine_levels":
            return [f"spine_level:{name}/{l}" for l in db.spine_level_names(row["id"])]
        if attr == "extra":
            return db.spine_extra("spine_spec", row["id"])
        return row[attr]          # stub_order is stored as Tcl list text
    if kind == "spine_level":
        if attr == "spine_cells":
            return [f"spine_cell:{name}/{c}" for c in db.spine_cell_names(row["id"])]
        return f"spine_spec:{parent}"                   # spine_spec
    if attr == "extra":
        return db.spine_extra("spine_cell", row["id"])
    if attr == "spine_level":
        return f"spine_level:{parent}"
    return row[attr]


def _design_row(db, handle: str):
    """Row of a design object. Pin names hold no '/' (DEF DIVIDERCHAR), so the
    port name is everything between the design name and the shape index."""
    kind = obj_type(handle)
    name = handle.partition(":")[2]
    design = db.design_row()
    if design is None:
        require_design(db)
    dname, _, rest = name.partition("/")
    if dname != design["name"]:
        raise _missing(handle)
    if kind == "design":
        if rest:
            raise _missing(handle)
        return design
    if kind == "port":
        row = db.port_row(rest) if rest else None
    elif kind == "track_pattern":
        row = db.track_pattern_row(_index(rest)) if _index(rest) else None
    else:
        pin, _, k = rest.rpartition("/")
        row = db.port_row(pin) if pin else None
        if row is not None:
            shapes = db.port_shape_rows(row["id"])
            k = _index(k)
            row = shapes[k - 1] if k and k <= len(shapes) else None
    if row is None:
        raise _missing(handle)
    return row


def _bbox(point_lists):
    xs, ys = [], []
    for points in point_lists:
        words = points.split()       # keep the stored text: '0', not '0.0'
        xs += words[0::2]
        ys += words[1::2]
    if not xs:
        return None
    return " ".join((min(xs, key=float), min(ys, key=float),
                     max(xs, key=float), max(ys, key=float)))


def _design_attr(db, handle, kind, attr):
    row = _design_row(db, handle)
    name = handle.partition(":")[2]
    parent = name.rsplit("/", 1)[0]
    if attr == "name":
        return name_of(handle) if kind != "port" else name.partition("/")[2]
    if kind == "design":
        if attr == "ports":
            return [f"port:{name}/{p}" for p in db.port_names()]
        if attr == "track_patterns":
            return [f"track_pattern:{name}/{k}" for k in db.track_pattern_ids()]
        if attr == "bbox":
            return _bbox([row["boundary"]])
        if attr == "area":
            from core.def_parser import polygon_area
            return round(polygon_area([float(v) for v in row["boundary"].split()]), 6)
        return row[attr]
    if kind == "track_pattern":
        if attr == "end":               # the last track
            return round(row["start"] + (row["num_tracks"] - 1) * row["step"], 6)
        if attr == "layers":
            return row["layers"].split()
        if attr == "design":
            return f"design:{parent}"
        return row[attr]
    if kind == "port":
        shapes = db.port_shape_rows(row["id"])
        if attr == "port_shapes":
            return [f"port_shape:{name}/{s['seq']}" for s in shapes]
        if attr == "layers":
            return list(dict.fromkeys(s["layer"] for s in shapes))
        if attr == "rect":
            return _bbox([s["points"] for s in shapes])
        if attr == "location":
            return None if row["x"] is None else f"{_num(row['x'])} {_num(row['y'])}"
        if attr == "extra":
            return db.port_extra(row["id"])
        if attr == "design":
            return f"design:{name.partition('/')[0]}"
        return row[attr]
    # port_shape
    if attr == "rect":
        return _bbox([row["points"]])
    if attr == "in_tech":
        return "true" if db.layer_row(row["layer"]) is not None else "false"
    if attr == "port":
        return f"port:{parent}"
    return row[attr]


def _num(value: float) -> str:
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


def _track_assignment_attr(db, handle, attr):
    layer = handle.partition(":")[2]
    row = db.track_assignment_row(layer)
    if row is None:
        raise _missing(handle)
    pattern = row["pattern"].split()
    if attr in ("name", "layer"):
        return layer
    if attr in ("direction",):
        return row["direction"]
    if attr == "pattern":
        return pattern
    if attr == "period":
        return len(pattern)
    positions = db.track_positions(layer, row["direction"]) if db.has_design() else []
    if attr == "num_tracks":
        return len(positions)
    if attr == "counts":                  # net count net count ...; '-' = signal
        from core.commands.assign_track_for_route import summarize
        return [w for net, n, _ in summarize(pattern, positions) for w in (net, str(n))]
    # tracks: {coordinate net} per track, lowest first
    return [f"{_num(c)} {pattern[i % len(pattern)]}" for i, c in enumerate(positions)]


def format_value(value) -> str:
    """Shortest round-trip text, empty string for None."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)
