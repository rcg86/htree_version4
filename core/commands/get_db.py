"""get_db: the one command that reads the design database.

    get_db tech                                   print all tech data
    get_db library_physical                       print the physical library summary
    get_db .tech.layer                            leading dot is optional on paths
    get_db <path> [<name_pattern>] [-if {expr}]   objects on a path (tech.layer, layers)
    get_db <objects> .<attr>[.<attr>] [-if {expr}]
    get_db <objects> .*
"""

import os
from fnmatch import fnmatchcase

from core import objects
from core.expr import Expr
from core.messages import HtreeError, info

NAME = "get_db"
SUMMARY = "Query objects and attributes in the design database"

USAGE = 20
UNKNOWN_PATH = 21

# Path roots: name -> function(db) returning handles.
ROOTS = {
    "tech": lambda db: _singleton(db, "tech"),
    "head": lambda db: _singleton(db, "tech"),      # Innovus alias
    "layers": lambda db: objects.get_attr(db, "tech", "layers"),
    "layer": lambda db: objects.get_attr(db, "tech", "layer"),
    "library_physical": lambda db: _singleton(db, "library_physical"),
    "lib_cells": lambda db: objects.get_attr(db, "library_physical", "lib_cells"),
    "lib_cell": lambda db: objects.get_attr(db, "library_physical", "lib_cells"),
    "spine_specs": lambda db: _spine_specs(db),
    "spine_spec": lambda db: _spine_specs(db),
}


def _spine_specs(db):
    objects.require_spine_specs(db)
    return [f"spine_spec:{n}" for n in db.spine_spec_names()]


def _singleton(db, handle):
    objects.check_exists(db, handle)
    return [handle]


def run(session, argv):
    db = session.db
    words, if_text = _split_if(list(argv))
    if not words:
        raise HtreeError(USAGE, "get_db: missing object or path. "
                         "Usage: get_db <path|objects> [.attr] [-if {expr}]")
    if len(words) > 2:
        raise HtreeError(USAGE, f"get_db: unexpected argument '{words[2]}'")
    expr = Expr(if_text) if if_text is not None else None
    target = words[0]
    if target.startswith(".") and target != ".*":
        target = target[1:]                       # '.tech.layer' == 'tech.layer'
    second = words[1] if len(words) == 2 else None

    if target == "tech" and second is None and expr is None:
        objects.require_tech(db)
        _dump_tech(db, session.out)
        return "tech"
    if target == "library_physical" and second is None and expr is None:
        objects.require_library(db)
        _dump_library(db, session.out)
        return "library_physical"

    items = list(session.split_list(target))
    if items and all(objects.is_handle(i) for i in items):
        for handle in items:
            objects.check_exists(db, handle)
        handles, tail = items, []
    else:
        if len(items) != 1:
            raise HtreeError(UNKNOWN_PATH, f"get_db: '{target}' is neither a path nor a list of objects")
        handles, tail = _walk_path(db, items[0])

    if second is not None and not second.startswith("."):
        if tail:
            raise HtreeError(USAGE, f"get_db: name pattern '{second}' cannot follow an attribute path")
        handles = [h for h in handles if fnmatchcase(_name(h), second)]
        second = None

    if second is not None and second != ".*":
        tail = tail + _attr_chain(second)
    handles, attr = _walk_chain(db, handles, tail)

    # Like Cadence, -if filters the objects at the end of the chain: the
    # returned objects (.lib_pins), or the owners of a returned value (.name).
    if expr is not None:
        handles = [h for h in handles if expr.evaluate(lambda a, h=h: _as_text(db, h, a))]

    if second == ".*":
        for handle in handles:
            _print_all(db, handle, session.out)
        return ""
    return _values(db, handles, attr)


def _split_if(argv):
    """Remove '-if <expr>' from argv. The (…) form arrives as several words."""
    if "-if" not in argv:
        return argv, None
    i = argv.index("-if")
    if i + 1 >= len(argv):
        raise HtreeError(USAGE, "get_db: -if needs an expression")
    first = argv[i + 1]
    if not first.startswith("("):
        return argv[:i] + argv[i + 2:], first
    depth, j, parts = 0, i + 1, []
    while j < len(argv):
        parts.append(argv[j])
        depth += argv[j].count("(") - argv[j].count(")")
        j += 1
        if depth <= 0:
            break
    if depth > 0:
        raise HtreeError(USAGE, f"get_db: -if expression has no closing ')': {' '.join(parts)}")
    return argv[:i] + argv[j:], " ".join(parts)


def _attr_chain(word: str):
    chain = word[1:].split(".")
    if not all(chain):
        raise HtreeError(USAGE, f"get_db: bad attribute '{word}'")
    return chain


def _walk_path(db, path: str):
    """Resolve 'tech.layer' style paths. Returns (handles, remaining value attrs)."""
    segs = path.split(".")
    if segs[0] not in ROOTS or not all(segs):
        raise HtreeError(UNKNOWN_PATH, f"get_db: unknown path '{path}'. "
                         f"Paths start with: {' '.join(ROOTS)}")
    handles = ROOTS[segs[0]](db)
    rest = segs[1:]
    while rest and handles and objects.is_relation(handles[0], rest[0]):
        handles = _follow(db, handles, rest[0])
        rest = rest[1:]
    if rest and handles:
        objects.get_attr(db, handles[0], rest[0])  # raises for unknown attrs
    return handles, rest


def _follow(db, handles, attr):
    out = []
    for handle in handles:
        value = objects.get_attr(db, handle, attr)
        for h in (value if isinstance(value, list) else [value]):
            if h not in out:
                out.append(h)
    return out


def _walk_chain(db, handles, chain):
    """Follow the object attrs in chain. Returns (objects, value attr or None)."""
    while chain and handles and objects.is_relation(handles[0], chain[0]):
        handles = _follow(db, handles, chain[0])
        chain = chain[1:]
    if not chain or not handles:
        return handles, (chain[-1] if chain else None)
    if len(chain) > 1:
        objects.get_attr(db, handles[0], chain[0])  # raises for unknown attrs
        raise HtreeError(USAGE, f"get_db: '.{chain[0]}' is a value, not an object; "
                         f"it cannot be followed by '.{chain[1]}'")
    return handles, chain[0]


def _values(db, handles, attr):
    if attr is None:
        return tuple(handles)
    values, listed = [], False
    for handle in handles:
        value = objects.get_attr(db, handle, attr)
        if isinstance(value, list):
            listed = True
            values.extend(objects.format_value(v) for v in value)
        else:
            values.append(objects.format_value(value))
    if len(handles) == 1 and not listed:
        return values[0]
    return tuple(values)


def _name(handle: str) -> str:
    return objects.name_of(handle)


def _as_text(db, handle, attr):
    value = objects.get_attr(db, handle, attr)
    if isinstance(value, list):
        return " ".join(objects.format_value(v) for v in value)
    return objects.format_value(value)


def _print_all(db, handle, out):
    info(f"Object: {handle}", out)
    for attr in objects.attr_names(handle):
        value = objects.get_attr(db, handle, attr)
        if isinstance(value, list):
            text = " ".join(value) if attr != "extra" else "; ".join(value)
        else:
            text = objects.format_value(value)
        if "\n" in text:
            text = "\n    " + text.replace("\n", "\n    ")
        info(f"  {attr}: {text}", out)


def _dump_tech(db, out):
    tech = db.tech_row()
    layers = db.layer_names()
    info("tech", out)
    for attr in ("file", "lef_version", "db_units", "manufacturing_grid"):
        info(f"  {attr:<20}: {objects.format_value(tech[attr])}", out)
    info(f"  {'layers':<20}: {len(layers)}", out)
    skip = {"obj_type", "name", "lef_text", "tech", "extra"}
    for name in layers:
        handle = f"layer:{name}"
        info(handle, out)
        for attr in objects.LAYER_ATTRS:
            if attr in skip:
                continue
            info(f"  {attr:<20}: {objects.format_value(objects.get_attr(db, handle, attr))}", out)
        for stmt in objects.get_attr(db, handle, "extra"):
            info(f"  {'extra':<20}: {stmt}", out)
    extras = db.tech_extra()
    if extras:
        info("tech extra (not modeled, kept verbatim)", out)
        for row in extras:
            first = row["text"].splitlines()[0] if row["text"] else ""
            info(f"  line {row['line']:<6} {row['kind']:<20}: {first}", out)


def _dump_library(db, out):
    names = db.lib_cell_names()
    info("library_physical", out)
    for path in db.lef_files():
        info(f"  {'file':<20}: {path}", out)
    info(f"  {'lib_cells':<20}: {len(names)}", out)
    for name in names:
        row = db.lib_cell_row(name)
        size = "" if row["size_x"] is None else \
            f"{objects.format_value(row['size_x'])} x {objects.format_value(row['size_y'])}"
        info(f"lib_cell:{name}", out)
        info(f"  {'class':<20}: {objects.format_value(row['class'])}", out)
        info(f"  {'size':<20}: {size}", out)
        info(f"  {'site':<20}: {objects.format_value(row['site'])}", out)
        info(f"  {'pins':<20}: {' '.join(db.lib_pin_names(row['id']))}", out)
    extras = db.lef_extra()
    if extras:
        info("library_physical extra (not modeled, kept verbatim)", out)
        for row in extras:
            first = row["text"].splitlines()[0] if row["text"] else ""
            info(f"  {os.path.basename(row['file'])}:{row['line']:<6} {row['kind']:<20}: {first}", out)
