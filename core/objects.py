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
    inst:<name>                       a placed instance of a lib cell (create_inst)
    pin:<inst>/<pin>                  a pin of an instance; .net is the net it is on
                                      (a spine_net, else a net: core/netlist.py)
    net:<net>                         a net that is no spine's: a port's (the root net of
                                      a spine), or one connect_pin made
    route_rule:<rule>                 a named route rule (create_route_rule); route_rule:default
                                      is built in (tech minimum width on every routing layer)
    route_rule_layer:<rule>/<layer>   its wire width and spacing on one layer
    spine:<name>                      a spine built by create_spine -build
    stub:<spine>/<stub>               one of its final stubs (also a net: get_db nets)
    spine_net:<spine>/<net>           one of its nets
    strap:<inst>/<n>                  the n-th strap route_pin made over an instance (1 = top)
    pin_wire:<inst>/<pin>             route_pin's vertical wire from a pin to its strap
    net_wire:<net>/<n>                route_net's n-th wire or crossing box of a net
    via_def:<name>                    a via definition (tech LEF VIA, DEF VIAS)
    via:<net>/<n>                     the n-th via of a net: one cut layer at one point
                                      (core/vias.py; numbered anew when the routing changes)

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
              "min_layer", "max_layer", "removed_layers", "layer", "layers", "extra"]
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
                    "max_drive_length", "count_stub_in_drive", "origin_x", "origin",
                    "level_pitch", "deviation", "orientation", "span", "stub_count", "stub_gap", "stub_tap",
                    "stub_order",
                    "spine_levels", "file", "extra", "yaml_text"]
SPINE_LEVEL_ATTRS = ["obj_type", "name", "spine_cells", "spine_spec"]
SPINE_CELL_ATTRS = ["obj_type", "name", "input", "output", "location", "track_input",
                    "track_output", "extra", "spine_level"]
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
INST_ATTRS = ["obj_type", "name", "ref_name", "lib_cell", "location", "orient", "bbox",
              "status", "place_status", "pins", "straps", "pin_wires"]
STRAP_ATTRS = ["obj_type", "name", "net", "layer", "rect", "width", "length", "max_extension",
               "inst"]
PIN_WIRE_ATTRS = ["obj_type", "name", "net", "layer", "rect", "width", "length", "strap",
                  "pin", "inst"]
NET_WIRE_ATTRS = ["obj_type", "name", "kind", "layer", "rect", "width", "length",
                  "shield_net", "net", "route_status"]
PIN_ATTRS = ["obj_type", "name", "inst", "lib_pin", "direction", "use", "net", "layers",
             "rect"]
SPINE_ATTRS = ["obj_type", "name", "spine_spec", "orientation", "build_direction", "location",
               "origin", "mirror", "ref_cell", "level_pitch", "deviation", "max_drive_length", "stub_length",
               "path", "insts", "stubs", "spine_nets", "spine_input", "spine_output", "root_net"]
STUB_ATTRS = ["obj_type", "name", "driver", "points", "length", "tap", "orientation", "net",
              "route_rule", "route_status", "net_wires", "vias", "spine"]
SPINE_NET_ATTRS = ["obj_type", "name", "driver", "loads", "pins", "group", "length", "detour",
                   "route", "route_rule", "route_status", "net_wires", "vias", "spine"]
NET_ATTRS = ["obj_type", "name", "driver", "pins", "ports", "route_rule", "route_status",
             "net_wires", "vias"]
VIA_DEF_ATTRS = ["obj_type", "name", "source", "default", "via_rule", "bottom_layer",
                 "cut_layer", "top_layer", "layers", "cuts", "rect", "shapes", "extra", "text"]
VIA_ATTRS = ["obj_type", "name", "net", "kind", "via_def", "bottom_layer", "cut_layer",
             "top_layer", "location", "rect", "box", "shapes", "source"]
ROUTE_RULE_ATTRS = ["obj_type", "name", "layers", "route_rule_layers"]
ROUTE_RULE_LAYER_ATTRS = ["obj_type", "name", "layer", "width", "spacing", "spacing_given",
                          "pitch", "tech_min_width", "tech_spacing", "route_rule"]
ATTRS = {"tech": TECH_ATTRS, "layer": LAYER_ATTRS,
         "library_physical": LIBRARY_PHYSICAL_ATTRS, "lib_cell": LIB_CELL_ATTRS,
         "lib_pin": LIB_PIN_ATTRS, "lib_port": LIB_PORT_ATTRS,
         "layer_shape": LAYER_SHAPE_ATTRS, "spine_spec": SPINE_SPEC_ATTRS,
         "spine_level": SPINE_LEVEL_ATTRS, "spine_cell": SPINE_CELL_ATTRS,
         "design": DESIGN_ATTRS, "port": PORT_ATTRS, "port_shape": PORT_SHAPE_ATTRS,
         "track_pattern": TRACK_PATTERN_ATTRS, "track_assignment": TRACK_ASSIGNMENT_ATTRS,
         "inst": INST_ATTRS, "pin": PIN_ATTRS, "route_rule": ROUTE_RULE_ATTRS,
         "route_rule_layer": ROUTE_RULE_LAYER_ATTRS,
         "spine": SPINE_ATTRS, "stub": STUB_ATTRS, "spine_net": SPINE_NET_ATTRS,
         "net": NET_ATTRS,
         "strap": STRAP_ATTRS, "pin_wire": PIN_WIRE_ATTRS, "net_wire": NET_WIRE_ATTRS,
         "via_def": VIA_DEF_ATTRS, "via": VIA_ATTRS}
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
             ("track_pattern", "design"): "design",
             ("inst", "lib_cell"): "lib_cell", ("inst", "pins"): "pin",
             ("inst", "straps"): "strap", ("strap", "inst"): "inst",
             ("inst", "pin_wires"): "pin_wire", ("pin_wire", "inst"): "inst",
             ("pin_wire", "strap"): "strap", ("pin_wire", "pin"): "pin",
             ("spine_net", "net_wires"): "net_wire", ("net_wire", "net"): "spine_net",
             ("pin", "inst"): "inst", ("pin", "lib_pin"): "lib_pin",
             # a pin's net is a spine_net, or a net (no spine's): netlist.net_handle
             ("pin", "net"): "spine_net", ("spine_net", "pins"): "pin",
             ("net", "pins"): "pin", ("net", "ports"): "port",
             ("net", "net_wires"): "net_wire", ("net", "vias"): "via",
             ("net", "route_rule"): "route_rule",
             ("spine", "spine_spec"): "spine_spec", ("spine", "insts"): "inst",
             ("spine", "spine_input"): "pin", ("spine", "spine_output"): "pin",
             ("spine", "root_net"): "net",
             ("spine", "stubs"): "stub", ("spine", "spine_nets"): "spine_net",
             ("stub", "driver"): "inst", ("stub", "spine"): "spine",
             ("stub", "net"): "spine_net", ("stub", "net_wires"): "net_wire",
             ("stub", "route_rule"): "route_rule",
             ("spine_net", "driver"): "inst", ("spine_net", "spine"): "spine",
             ("spine_net", "route_rule"): "route_rule",
             ("spine_net", "vias"): "via", ("stub", "vias"): "via",
             ("via", "via_def"): "via_def",
             ("route_rule", "layers"): "layer",
             ("route_rule", "route_rule_layers"): "route_rule_layer",
             ("route_rule_layer", "layer"): "layer",
             ("route_rule_layer", "route_rule"): "route_rule"}
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
    nested = (kind in _PARTS or kind in _SPINE_PARTS or kind in _DESIGN_PARTS
              or kind in ("stub", "spine_net", "route_rule_layer", "strap",
                                  "pin_wire", "net_wire", "via"))
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
    if kind == "inst" and db.inst_row(handle.partition(":")[2]):
        return
    if kind in ("route_rule", "route_rule_layer") and _route_rule_row(db, handle) is not None:
        return
    if kind in ("spine", "stub", "spine_net") and _built_spine_row(db, handle) is not None:
        return
    if kind == "pin" and _pin_rows(db, handle) is not None:
        return
    if kind == "net" and _net_ends(db, handle):
        return
    if kind == "strap" and _strap_row(db, handle) is not None:
        return
    if kind == "pin_wire" and _pin_wire_row(db, handle) is not None:
        return
    if kind == "net_wire" and _net_wire_row(db, handle) is not None:
        return
    if kind == "via_def" and db.via_def_row(handle.partition(":")[2]) is not None:
        return
    if kind == "via" and _via_row(db, handle) is not None:
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
        if attr in ("min_layer", "max_layer"):       # the range of read_tech, if any
            return db.tech_layer_range()[attr == "max_layer"]
        if attr == "removed_layers":                 # remove_layer, not added back
            return db.removed_layers()
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
    if kind == "inst":
        return _inst_attr(db, handle, attr)
    if kind == "pin":
        return _pin_attr(db, handle, attr)
    if kind == "net":
        return _net_attr(db, handle, attr)
    if kind in ("route_rule", "route_rule_layer"):
        return _route_rule_attr(db, handle, kind, attr)
    if kind in ("spine", "stub", "spine_net"):
        return _built_spine_attr(db, handle, kind, attr)
    if kind == "strap":
        return _strap_attr(db, handle, attr)
    if kind == "pin_wire":
        return _pin_wire_attr(db, handle, attr)
    if kind == "net_wire":
        return _net_wire_attr(db, handle, attr)
    if kind == "via_def":
        return _via_def_attr(db, handle, attr)
    if kind == "via":
        return _via_attr(db, handle, attr)
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
    if attr in ("track_input", "track_output"):
        return row["track_in" if attr == "track_input" else "track_out"]
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


def inst_bbox(db, row):
    """Placed bbox of an inst row, or None if its cell has no SIZE."""
    from core.placement import placed_bbox
    cell = db.lib_cell_row(row["ref_cell"])
    if cell is None or cell["size_x"] is None:
        return None
    return placed_bbox(cell["size_x"], cell["size_y"], row["orient"], row["x"], row["y"])


def _inst_attr(db, handle, attr):
    name = handle.partition(":")[2]
    row = db.inst_row(name)
    if row is None:
        raise _missing(handle)
    if attr == "name":
        return name
    if attr == "ref_name":
        return row["ref_cell"]
    if attr == "lib_cell":
        return f"lib_cell:{row['ref_cell']}"
    if attr == "location":
        return f"{_num(row['x'])} {_num(row['y'])}"
    if attr == "bbox":
        box = inst_bbox(db, row)
        return None if box is None else " ".join(_num(v) for v in box)
    if attr == "pins":
        cell = db.lib_cell_row(row["ref_cell"])
        return [] if cell is None else [f"pin:{name}/{p}" for p in db.lib_pin_names(cell["id"])]
    if attr == "straps":
        return [f"strap:{name}/{r['seq']}" for r in db.strap_rows(name)]
    if attr == "pin_wires":
        return [f"pin_wire:{name}/{r['pin']}" for r in db.pin_wire_rows(name)]
    if attr == "place_status":             # the Innovus name of status
        return row["status"]
    return row[attr]                       # orient, status


def _strap_row(db, handle):
    inst, _, seq = handle.partition(":")[2].rpartition("/")
    return db.strap_row(inst, _index(seq)) if inst and _index(seq) else None


def _strap_attr(db, handle, attr):
    row = _strap_row(db, handle)
    if row is None:
        raise _missing(handle)
    x1, y1, x2, y2 = (float(v) for v in row["rect"].split())
    if attr == "name":
        return str(row["seq"])
    if attr == "inst":
        return f"inst:{row['inst']}"
    if attr == "width":                    # across the strap (y for a horizontal strap)
        return round(y2 - y1, 6)
    if attr == "length":
        return round(x2 - x1, 6)
    return row[attr]                       # net, layer, rect


def _pin_wire_row(db, handle):
    inst, _, pin = handle.partition(":")[2].rpartition("/")
    return db.pin_wire_row(inst, pin) if inst and pin else None


def _pin_wire_attr(db, handle, attr):
    row = _pin_wire_row(db, handle)
    if row is None:
        raise _missing(handle)
    x1, y1, x2, y2 = (float(v) for v in row["rect"].split())
    if attr == "name":
        return row["pin"]
    if attr == "inst":
        return f"inst:{row['inst']}"
    if attr == "pin":
        return f"pin:{row['inst']}/{row['pin']}"
    if attr == "strap":
        return f"strap:{row['inst']}/{row['strap']}"
    if attr == "width":                    # across the wire (x for a vertical wire)
        return round(x2 - x1, 6)
    if attr == "length":
        return round(y2 - y1, 6)
    return row[attr]                       # net, layer, rect


# Route shapes move_wire and stretch_wire edit: handle type -> table.
WIRE_TABLES = {"net_wire": "net_wire", "strap": "strap", "pin_wire": "pin_wire"}


def wire_row(db, handle):
    """The row of a route shape (net_wire, strap or pin_wire handle), or None."""
    kind = obj_type(handle)
    lookup = {"net_wire": _net_wire_row, "strap": _strap_row, "pin_wire": _pin_wire_row}
    return lookup[kind](db, handle) if kind in lookup else None


def _net_wire_row(db, handle):
    net, _, seq = handle.partition(":")[2].rpartition("/")
    return db.net_wire_row(net, _index(seq)) if net and _index(seq) else None


def _net_wire_attr(db, handle, attr):
    row = _net_wire_row(db, handle)
    if row is None:
        raise _missing(handle)
    x1, y1, x2, y2 = (float(v) for v in row["rect"].split())
    if attr == "name":
        return str(row["seq"])
    if attr == "net":                     # a spine's, or a net of no spine with pins
        from core import netlist
        from core.db import STUB
        name = row["net"]                 # a stub's rows (<leaf net>_stub): the leaf's net
        if row["kind"].startswith("stub") and name.endswith(STUB):
            name = name[:-len(STUB)]
        net = netlist.net_handle(db, name)
        return net if net.startswith("spine_net:") or netlist.ends(db, name) else None
    if attr in ("width", "length"):        # across and along a wire; a box: x and y
        dx, dy = round(x2 - x1, 6), round(y2 - y1, 6)
        if row["kind"] == "cross":
            return dx if attr == "width" else dy
        return min(dx, dy) if attr == "width" else max(dx, dy)
    if attr == "route_status":            # fixed alone, or with its net or stub
        from core import route_status
        held = route_status.fixed_shapes(db, [(handle, "net_wire", row)])
        return route_status.FIXED if held else "routed"
    return row[attr]                       # kind, layer, rect


def _shape_texts(shapes):
    """'layer x1 y1 x2 y2' (a polygon: every point) per shape."""
    return [f"{layer} " + " ".join(_num(c) for c in pts) for layer, _, pts in shapes]


def _rect_text(box):
    return None if box is None else " ".join(_num(round(c, 6)) for c in box)


def _via_def_attr(db, handle, attr):
    from core import vias
    name = handle.partition(":")[2]
    row = db.via_def_row(name)
    if row is None:
        raise _missing(handle)
    if attr == "default":
        return row["is_default"]
    if attr == "extra":
        return [line for line in (row["extra"] or "").split("\n") if line]
    if attr in ("name", "source", "via_rule", "text"):
        return row[attr]
    shapes = vias.definition_shapes(db, name)
    if attr == "shapes":
        return _shape_texts(shapes)
    if attr == "layers":                  # in the order of the definition
        return list(dict.fromkeys(layer for layer, _, _ in shapes))
    if attr == "rect":                    # about the via's origin
        return _rect_text(vias.bbox(shapes))
    bottom, cut, top = vias.definition_layers(db).get(name, vias.UNKNOWN)
    if attr == "cuts":
        return None if cut is None else sum(1 for layer, _, _ in shapes if layer == cut)
    return {"bottom_layer": bottom, "cut_layer": cut, "top_layer": top}[attr]


def _via_row(db, handle):
    from core import vias
    net, _, seq = handle.partition(":")[2].rpartition("/")
    return vias.row(db, net, _index(seq)) if net and _index(seq) else None


def _via_attr(db, handle, attr):
    from core import vias
    row = _via_row(db, handle)
    if row is None:
        raise _missing(handle)
    if attr == "name":
        return str(row["seq"])
    if attr == "via_def":
        return None if row["via_def"] is None else f"via_def:{row['via_def']}"
    if attr in ("bottom_layer", "cut_layer", "top_layer"):
        return row[attr.partition("_")[0]]
    if attr == "location":
        return f"{_num(row['x'])} {_num(row['y'])}"
    if attr == "box":                     # what the two shapes it joins share
        return row["rect"]
    if attr == "rect":                    # what it covers: its definition's shapes, else the box
        return _rect_text(vias.extent(db, row))
    if attr == "shapes":
        return _shape_texts(vias.placed_shapes(db, row))
    return row[attr]                      # net, kind, source


def _pin_rows(db, handle):
    """(inst row, lib cell row, lib pin row) for pin:<inst>/<pin>, or None."""
    inst, _, pin = handle.partition(":")[2].partition("/")
    row = db.inst_row(inst) if inst and pin else None
    cell = db.lib_cell_row(row["ref_cell"]) if row is not None else None
    lpin = db.lib_pin_row(cell["name"], pin) if cell is not None else None
    return None if lpin is None else (row, cell, lpin)


def pin_shapes(db, handle):
    """(layer, type, placed points) of an instance pin's shapes."""
    from core.placement import placed_points, placer
    rows = _pin_rows(db, handle)
    if rows is None:
        raise _missing(handle)
    inst, cell, lpin = rows
    place = placer(cell["size_x"], cell["size_y"], inst["orient"], inst["x"], inst["y"])
    return [(layer, kind, placed_points([float(v) for v in pts.split()], place))
            for p, layer, kind, pts in db.lib_cell_shapes(cell["name"]) if p == lpin["name"]]


def pin_centre(db, inst, pin):
    """The centre of the shapes of an instance pin; of the instance when the
    pin has no shapes."""
    shapes = pin_shapes(db, f"pin:{inst}/{pin}") if pin else []
    xs = [v for _, _, pts in shapes for v in pts[0::2]]
    ys = [v for _, _, pts in shapes for v in pts[1::2]]
    if not xs:
        box = inst_bbox(db, db.inst_row(inst))
        xs, ys = box[0::2], box[1::2]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def port_centre(db, port):
    """The centre of the shapes of a port of the design; where it is placed
    when it has no shapes; None when it has neither."""
    row = db.port_row(port) if db.has_design() else None
    if row is None:
        return None
    v = [float(c) for s in db.port_shape_rows(row["id"]) for c in s["points"].split()]
    if not v:
        return None if row["x"] is None else (row["x"], row["y"])
    return (min(v[0::2]) + max(v[0::2])) / 2, (min(v[1::2]) + max(v[1::2])) / 2


def _pin_attr(db, handle, attr):
    rows = _pin_rows(db, handle)
    if rows is None:
        raise _missing(handle)
    inst, cell, lpin = rows
    if attr == "name":
        return lpin["name"]
    if attr == "inst":
        return f"inst:{inst['name']}"
    if attr == "lib_pin":
        return f"lib_pin:{cell['name']}/{lpin['name']}"
    if attr in ("direction", "use"):
        return lpin[attr]
    if attr == "net":                     # a spine's, a port's or connect_pin's
        from core import netlist
        net = netlist.pin_net(db, inst["name"], lpin["name"])
        return None if net is None else netlist.net_handle(db, net)
    shapes = pin_shapes(db, handle)
    if attr == "layers":
        return list(dict.fromkeys(layer for layer, _, _ in shapes))
    xs = [c for _, _, pts in shapes for c in pts[0::2]]       # rect: placed bbox
    ys = [c for _, _, pts in shapes for c in pts[1::2]]
    return None if not xs else " ".join(_num(v) for v in (min(xs), min(ys), max(xs), max(ys)))


def _net_ends(db, handle):
    """The ends (netlist.End) of net:<net>: its instance pins and its port.
    Empty when there is no such net, or it is a spine's (spine_net:)."""
    from core import netlist
    name = handle.partition(":")[2]
    if netlist.net_handle(db, name) != handle:
        return []
    return netlist.ends(db, name)


def _net_attr(db, handle, attr):
    ends = _net_ends(db, handle)
    if not ends:
        raise _missing(handle)
    if attr == "name":
        return handle.partition(":")[2]
    if attr == "driver":                  # an output pin, or an input port of the design
        return next((e.handle for e in ends if e.drives), None)
    name = handle.partition(":")[2]
    if attr == "net_wires":               # what route_net made
        return [f"net_wire:{name}/{r['seq']}" for r in db.net_wire_rows(name)]
    if attr == "vias":
        from core import vias
        return [vias.handle(r) for r in vias.rows(db, name)]
    if attr == "route_rule":              # no rule set: the built-in default
        return f"route_rule:{db.net_route_rule(name) or 'default'}"
    if attr == "route_status":            # fixed | routed | unrouted
        return _route_status(db, name, name, stub=False)
    return [e.handle for e in ends if e.kind == attr[:-1]]    # pins, ports


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


def _route_rule_row(db, handle):
    """The rule's layer names (route_rule) or its row for one layer
    (route_rule_layer), or None if there is no such object."""
    from core.commands.create_route_rule import DEFAULT, default_layer_rule, default_layers
    name, _, layer = handle.partition(":")[2].partition("/")
    if obj_type(handle) == "route_rule":
        if layer:
            return None
        return default_layers(db) if name == DEFAULT else (db.route_rule_layers(name) or None)
    if not layer:
        return None
    if name == DEFAULT:
        return default_layer_rule(db, layer)
    return db.route_rule_layer_row(name, layer)


def _route_rule_attr(db, handle, kind, attr):
    row = _route_rule_row(db, handle)
    if row is None:
        raise _missing(handle)
    name = handle.partition(":")[2].partition("/")[0]
    if kind == "route_rule":
        if attr == "name":
            return name
        if attr == "layers":
            return [f"layer:{l}" for l in row]
        return [f"route_rule_layer:{name}/{l}" for l in row]       # route_rule_layers
    layer = row["layer"]
    if attr == "name":
        return layer
    if attr == "layer":
        return f"layer:{layer}"
    if attr == "route_rule":
        return f"route_rule:{name}"
    if attr == "pitch":                   # centre to centre with a parallel wire of this rule
        if row["width"] is None or row["spacing"] is None:
            return None
        return round(row["width"] + row["spacing"], 6)
    if attr in ("tech_min_width", "tech_spacing"):
        from core.commands.create_route_rule import tech_min_width, tech_spacing
        lrow = db.layer_row(layer) if db.has_tech() else None
        if lrow is None:
            return None
        if attr == "tech_min_width":
            return tech_min_width(lrow)
        return tech_spacing(db, lrow, row["width"])[0]
    return row[attr]                      # width, spacing, spacing_given


def _built_spine_row(db, handle):
    """(spine row, stub or net row or None) of a built spine object, or None."""
    kind = obj_type(handle)
    name, _, part = handle.partition(":")[2].partition("/")
    spine = db.spine_row(name)
    if spine is None or (kind == "spine") == bool(part):
        return None
    if kind == "spine":
        return spine, None
    rows = db.spine_stub_rows(spine["id"]) if kind == "stub" else \
        db.spine_net_rows(spine["id"])
    row = next((r for r in rows if r["name"] == part), None)
    return None if row is None else (spine, row)


def _spine_ends(db, spine, output):
    """The pins where a built spine starts and ends: the signal input of each
    root cell (L1_inv1; with -mirror the mirrored one's too), or the signal
    output of each leaf cell (the cells that drive the stubs)."""
    from core import netlist
    if output:
        stubs = {s["name"] for s in db.spine_stub_rows(spine["id"])}
        cells = [r["driver"] for r in db.spine_net_rows(spine["id"])
                 if stubs & set(r["loads"].split())]
    else:
        cells = [m["inst"] for m in db.spine_members(spine["id"]) if not m["driver"]]
    pins = [(inst, netlist.signal_pin(db, inst, "out" if output else "in"))
            for inst in dict.fromkeys(cells)]
    return [f"pin:{inst}/{pin}" for inst, pin in pins if pin is not None]


def _route_status(db, key, net, stub):
    """fixed (set_db .route_status), routed (it has wires: route_net's, or a
    stub's route_final_stub wire) or unrouted."""
    from core import route_status
    rows = (db.stub_wire_rows(net) if stub else db.net_wire_rows(net)) if net else []
    return route_status.status(db, key, any(r["kind"].startswith("stub") == stub for r in rows))


def stub_key(spine, stub):
    """The name a stub's route rule is kept under (stub names repeat across
    spines, net names do not)."""
    return f"stub:{spine}/{stub}"


def _built_spine_attr(db, handle, kind, attr):
    found = _built_spine_row(db, handle)
    if found is None:
        raise _missing(handle)
    spine, row = found
    if kind == "spine":
        if attr == "name":
            return spine["name"]
        if attr == "spine_spec":
            return f"spine_spec:{spine['spec']}"
        if attr == "location":
            return f"{_num(spine['x'])} {_num(spine['y'])}"
        if attr == "max_drive_length":
            return spine["max_drive"]
        if attr == "path":                # the stub line, bottom / left end first
            from core.spine_snake import Snake
            return " ".join(_num(c) for p in Snake(db, spine["name"], limits=False).body()
                            for c in p)
        if attr == "mirror":
            return "true" if spine["mirror"] else "false"
        if attr == "insts":
            return [f"inst:{m['inst']}" for m in db.spine_members(spine["id"])]
        if attr == "stubs":
            return [f"stub:{spine['name']}/{r['name']}"
                    for r in db.spine_stub_rows(spine["id"])]
        if attr == "spine_nets":
            return [f"spine_net:{spine['name']}/{r['name']}"
                    for r in db.spine_net_rows(spine["id"])]
        if attr in ("spine_input", "spine_output"):
            return _spine_ends(db, spine, attr == "spine_output")
        if attr == "root_net":            # the net on the root's input (netlist.root_net)
            from core import netlist
            return f"net:{netlist.root_net(db, spine)}"
        return spine[attr]
    if attr == "name":
        return row["name"]
    if attr == "spine":
        return f"spine:{spine['name']}"
    if attr == "driver":
        return f"inst:{row['driver']}"
    if kind == "stub" and attr in ("orientation", "net", "net_wires", "vias", "route_rule",
                                   "route_status"):
        leaf = next((r["name"] for r in db.spine_net_rows(spine["id"])
                     if r["loads"] == row["name"]), None)
        if attr == "orientation":
            return spine["orientation"]
        if attr == "net":                  # the leaf's net, which drives the stub
            return None if leaf is None else f"spine_net:{spine['name']}/{leaf}"
        if attr == "net_wires":            # its route_final_stub wire, crossings, shields
            return [f"net_wire:{r['net']}/{r['seq']}" for r in db.stub_wire_rows(leaf)] \
                if leaf else []
        if attr == "vias":                 # the vias of its net that land on its wire
            from core import vias
            return [vias.handle(r) for r in vias.on_wires(
                db, leaf, [r for r in db.stub_wire_rows(leaf) if r["kind"] == "stub"])] \
                if leaf else []
        if attr == "route_status":
            return _route_status(db, stub_key(spine["name"], row["name"]), leaf, stub=True)
        return f"route_rule:{db.net_route_rule(stub_key(spine['name'], row['name'])) or 'default'}"
    if kind == "spine_net" and attr == "route_status":
        return _route_status(db, row["name"], row["name"], stub=False)
    if kind == "spine_net" and attr == "pins":    # the instance pins on it (not a stub)
        from core import netlist
        return [f"pin:{inst}/{pin}" for inst, pin in netlist.by_net(db).get(row["name"], [])]
    if attr == "net_wires":
        return [f"net_wire:{r['net']}/{r['seq']}"          # its stub's wires too
                for r in db.net_wire_rows(row["name"]) + db.stub_wire_rows(row["name"])]
    if attr == "vias":                    # every via that carries the net, pin stacks too
        from core import vias
        return [vias.handle(r) for r in vias.rows(db, row["name"])]
    if attr == "route_rule":              # no rule set: the built-in default
        return f"route_rule:{db.net_route_rule(row['name']) or 'default'}"
    if kind == "stub":
        from core.spine_snake import stub_middle, stub_points
        pts = stub_points(row["points"])  # two; more on a bent spine
        if attr == "length":
            return round(sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
                             for a, b in zip(pts, pts[1:])), 6)
        if attr == "tap":                 # half way along the stub
            x, y = stub_middle(pts)
            return f"{_num(round(x, 6))} {_num(round(y, 6))}"
        return row["points"]
    if attr == "loads":
        return row["loads"].split()
    if attr == "group":
        return row["grp"]
    if attr == "route":                   # one "x1 y1 x2 y2" per segment
        return [seg for seg in row["route"].split(";") if seg]
    return row[attr]                      # length, detour


def format_value(value) -> str:
    """Shortest round-trip text, empty string for None."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)
