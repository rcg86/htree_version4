"""Fixed routes: set_db <nets> .route_status fixed.

A fixed net's routes are left as they are by every command that makes, edits
or removes route shapes: route_net, route_track, route_final_stub,
delete_route, delete_wire, move_wire, stretch_wire, insert_vias, route_pin,
add_buffer_on_net, connect_spine and move_spine_to_boundary. Those commands
skip what is fixed and say so (HT4-286). A stub is a net of its own here, keyed
stub:<spine>/<stub> as its route rule is: fixing a spine net does not fix the
stub of its leaf, nor the other way round.

The routes of a net are the shapes route_net and route_pin make for it: its
wires, strap extensions, crossing boxes and shields (net_wire rows under its
name, not of kind stub*), the straps and pin wires named after it, and the
auto vias on any of these. A stub's are the stub* rows under its leaf's net.
Power straps, SIGNAL straps and optimize_pg_connection wires (pg:<inst>) belong
to no net here and are never fixed.

A wire can also be fixed alone (set_db <net_wire> .route_status fixed, a wire of
kind wire): the commands above leave it, and route_net keeps it and joins the
rest of its net to it (the shields round it are made again).
"""

from core import netlist
from core.messages import warn

FIXED = "fixed"
SKIPPED = 286


def stub_key(spine, stub):
    from core.objects import stub_key as key
    return key(spine, stub)


def fixed_keys(db):
    return db.fixed_nets()


def is_fixed(db, key):
    return key in db.fixed_nets()


def status(db, key, routed):
    """fixed, routed or unrouted."""
    return FIXED if is_fixed(db, key) else "routed" if routed else "unrouted"


def _stubs_of_leaves(db):
    """{leaf net: stub key} of every built spine."""
    found = {}
    for spine in db.spine_names():
        row = db.spine_row(spine)
        stubs = {s["name"] for s in db.spine_stub_rows(row["id"])}
        for n in db.spine_net_rows(row["id"]):
            hit = [w for w in n["loads"].split() if w in stubs]
            if hit:
                found[n["name"]] = stub_key(spine, hit[0])
    return found


def shape_key(db, table, row, leaves=None):
    """The key of the net or stub a route shape belongs to (see the module
    docstring), or None for a shape of no net (power, SIGNAL, pg:)."""
    if table in ("strap", "pin_wire"):
        return row["net"] if row["net"] in netlist.signal_nets(db) else None
    net = row["net"]
    if net.startswith("pg:"):
        return None
    if net.startswith("auto_via:"):                 # the shape it sits on
        kind, _, rest = net[len("auto_via:"):].partition(":")
        owner, _, part = rest.rpartition("/")
        if kind == "net_wire":
            r = db.conn.execute("SELECT * FROM net_wire WHERE net = ? AND seq = ?",
                                (owner, part)).fetchone()
        else:
            column = "seq" if kind == "strap" else "pin"
            r = db.conn.execute(f"SELECT * FROM {kind} WHERE inst = ? AND {column} = ?",
                                (owner, part)).fetchone()
        return None if r is None else shape_key(db, kind, r, leaves)
    if (row["kind"] or "").startswith("stub"):
        from core.db import STUB
        leaf = net[:-len(STUB)] if net.endswith(STUB) else net     # under <leaf net>_stub
        leaves = _stubs_of_leaves(db) if leaves is None else leaves
        return leaves.get(leaf, leaf)
    return net


def wire_fixed(row):
    """True for a net_wire row fixed alone."""
    try:
        return row["status"] == FIXED
    except (IndexError, KeyError):
        return False


def fixed_shapes(db, items):
    """The (handle, table, row) items whose net or stub is fixed, or that
    are fixed wires themselves."""
    keys = db.fixed_nets()
    leaves = _stubs_of_leaves(db) if keys else {}
    return [item for item in items
            if (item[1] == "net_wire" and wire_fixed(item[2]))
            or (keys and shape_key(db, item[1], item[2], leaves) in keys)]


def skip(cmd, what, names, out):
    """Warn that the fixed names were left as they are."""
    if names:
        more = f" and {len(names) - 10} more" if len(names) > 10 else ""
        warn(SKIPPED, f"{cmd}: {len(names)} {what} left as they are, route_status fixed "
             f"(set_db .route_status routed frees them): {' '.join(names[:10])}{more}", out)
