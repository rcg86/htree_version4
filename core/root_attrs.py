"""Root attributes: settings that change how the commands work.

    get_db ignore_shield_less_than_routing_length
    set_db ignore_shield_less_than_routing_length 20
    set_db ignore_shield_less_than_routing_length default
    set_db route_auto_via_insertion_during_stretch 3
    get_db root_attributes

A value is kept in the database (the meta table, under attr:<name>), so
write_db and read_db carry it. An attribute never set, or set back to
default, takes its default, which may come from the loaded data (a spec).
"""

from dataclasses import dataclass
from typing import Callable

from core.messages import HtreeError

BAD_VALUE = 141              # as set_db
DEVIATION = 10.0             # spine spec placement.deviation when no spec says


def _spec_deviation(db):
    """placement.deviation of the built spines, else of the spine specs read,
    else DEVIATION: the length tolerance of the nets."""
    for table in ("spine", "spine_spec"):
        row = db.conn.execute(f"SELECT deviation FROM {table} WHERE deviation IS NOT NULL "
                              f"ORDER BY id").fetchone()
        if row is not None:
            return float(row[0])
    return DEVIATION


@dataclass
class Attr:
    kind: str                    # num (>= 0) | int (>= 0)
    default: Callable            # db -> value
    default_text: str            # where the default comes from, for get_db root_attributes
    help: str


ATTRS = {
    "ignore_shield_less_than_routing_length": Attr(
        "num", _spec_deviation, "the spine spec's placement.deviation, else 10",
        "route_net / route_final_stub -shield: a signal wire piece shorter than this "
        "(um) gets no shields"),
    "route_auto_via_insertion_during_stretch": Attr(
        "int", lambda db: 1, "1",
        "Tools > Stretch / stretch_wire: a via is added where the stretched wire newly "
        "crosses a wire of its net up to this many routing layers away (1: the next "
        "layer, IA-IB; 3: H2-IA over G1 and G2; 0: none)"),
}


def names():
    return list(ATTRS)


def _key(name):
    return f"attr:{name}"


def get(db, name):
    """The value of root attribute name: as set, else its default."""
    attr = ATTRS[name]
    row = db.conn.execute("SELECT value FROM meta WHERE key = ?", (_key(name),)).fetchone()
    if row is None:
        return attr.default(db)
    return {"num": float, "int": int}.get(attr.kind, str)(row[0])


def is_set(db, name):
    return db.conn.execute("SELECT 1 FROM meta WHERE key = ?", (_key(name),)).fetchone() \
        is not None


def set_value(db, name, text):
    """Set root attribute name from text; 'default' goes back to the default.
    Returns the value now in effect."""
    attr = ATTRS[name]
    with db.conn:
        if text.lower() == "default":
            db.conn.execute("DELETE FROM meta WHERE key = ?", (_key(name),))
            return get(db, name)
        if attr.kind == "num":
            try:
                value = float(text)
            except ValueError:
                value = -1.0
            if value < 0:
                raise HtreeError(BAD_VALUE, f"set_db: {name} must be a number of microns "
                                 f">= 0 (or default), got '{text}'")
            text = repr(value)
        elif attr.kind == "int":
            try:
                value = int(text)
            except ValueError:
                value = -1
            if value < 0:
                raise HtreeError(BAD_VALUE, f"set_db: {name} must be a whole number >= 0 "
                                 f"(or default), got '{text}'")
            text = str(value)
        db.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (_key(name), text))
    return get(db, name)
