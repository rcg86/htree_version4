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

Attribute values are Python scalars, None (empty), or lists. Attributes that
refer to other objects return handles, so get_db can keep walking.
"""

from core.messages import HtreeError

UNKNOWN_OBJECT = 22
UNKNOWN_ATTR = 23
NO_TECH = 25
NO_LIBRARY = 26
NO_SPINE_SPEC = 27

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
ATTRS = {"tech": TECH_ATTRS, "layer": LAYER_ATTRS,
         "library_physical": LIBRARY_PHYSICAL_ATTRS, "lib_cell": LIB_CELL_ATTRS,
         "lib_pin": LIB_PIN_ATTRS, "lib_port": LIB_PORT_ATTRS,
         "layer_shape": LAYER_SHAPE_ATTRS, "spine_spec": SPINE_SPEC_ATTRS,
         "spine_level": SPINE_LEVEL_ATTRS, "spine_cell": SPINE_CELL_ATTRS}
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
             ("spine_cell", "spine_level"): "spine_level"}
# Objects with exactly one instance; the handle is the type name.
SINGLETONS = ("tech", "library_physical")
# Number of '/'-separated parts in the name of each library object.
_PARTS = {"lib_cell": 1, "lib_pin": 2, "lib_port": 3, "layer_shape": 4}
_SPINE_PARTS = {"spine_spec": 1, "spine_level": 2, "spine_cell": 3}


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
    return name.rsplit("/", 1)[-1] if kind in _PARTS or kind in _SPINE_PARTS else name


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
    if kind == "layer" and db.layer_row(handle.partition(":")[2]) is not None:
        return
    raise _missing(handle)


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


def format_value(value) -> str:
    """Shortest round-trip text, empty string for None."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)
