"""delete_wire -wires <wires>: remove route shapes by hand; delete_wire -undo
puts the ones removed last back.

    delete_wire -wires [get_db selected]
    delete_wire -wires {net_wire:temp_L2_inv1_Y/3 strap:temp_L2_inv1/2}
    delete_wire -undo

The wires are the route shapes of move_wire: route_net / route_final_stub /
optimize_pg_connection wires, shields and crossing boxes (net_wire:),
route_pin straps (strap:) and pin wires (pin_wire:). Only the wires given go,
and what cannot stay without them: the pin wires that end on a deleted strap,
and the wires' auto vias (stretch_wire). Nothing else follows: the crossing
boxes on a deleted wire and the shapes it connected to stay, the net is left
open. The GUI's Tools > Delete runs this command on the selected wires.

The wires of each delete_wire are kept, in this session only, so -undo can put
them back as they were (same handles); again for the delete before it.
"""

from core import auto_via, objects, route_status
from core.commands.move_wire import USAGE, wire_rows
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "delete_wire"
SUMMARY = "Delete route wires (net wires, straps, pin wires); -undo puts them back"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-wires": "value", "-undo": "flag"}

NOTHING = 223
TAKEN = 224
ORDER = {"strap": 0, "pin_wire": 1, "net_wire": 2}     # a pin wire needs its strap first


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if opts["-undo"] == ("-wires" in opts):
        raise HtreeError(USAGE, "delete_wire: give -wires or -undo. Usage: delete_wire "
                         "-wires <wires>  |  delete_wire -undo")
    if opts["-undo"]:
        return _undo(session)
    db = session.db
    given = wire_rows(session, opts["-wires"], NAME)
    held = route_status.fixed_shapes(db, given)
    route_status.skip(NAME, "wire(s) of fixed nets", [h for h, _, _ in held], session.out)
    given = [item for item in given if item not in held]
    if not given:
        return ()
    rows = targets(db, given)
    db.delete_wires([(table, row["id"]) for _, table, row in rows])
    db.deleted_wires.append([(handle, table, dict(row)) for handle, table, row in rows])
    info(f"delete_wire: deleted {len(given)} wire(s)", session.out)
    also = [h for h, _, _ in rows[len(given):]]
    if also:
        info(f"  and {len(also)} that cannot stay without them (pin wires on a deleted "
             f"strap, auto vias): {' '.join(also)}", session.out)
    info("  delete_wire -undo puts them back", session.out)
    return tuple(h for h, _, _ in rows)


def targets(db, rows):
    """rows [(handle, table, row)], then what cannot stay without them: the
    pin wires that end on a strap among them, and the auto vias (stretch_wire)
    of every one."""
    found = {handle: (handle, table, row) for handle, table, row in rows}
    for _, table, row in rows:
        if table == "strap":
            for w in db.pin_wire_rows(row["inst"]):
                if w["strap"] == row["seq"]:
                    handle = f"pin_wire:{w['inst']}/{w['pin']}"
                    found.setdefault(handle, (handle, "pin_wire", w))
    for owner in list(found):
        for r in db.net_wire_rows(auto_via.owner(owner)):
            handle = f"net_wire:{r['net']}/{r['seq']}"
            found.setdefault(handle, (handle, "net_wire", r))
    return list(found.values())


def last_deleted(db):
    """The handles -undo would put back now."""
    return [handle for handle, _, _ in db.deleted_wires[-1]] if db.deleted_wires else []


def _undo(session):
    db = session.db
    if not db.deleted_wires:
        raise HtreeError(NOTHING, "delete_wire: -undo: no deleted wires to put back")
    back, taken = [], []
    for handle, table, row in sorted(db.deleted_wires.pop(), key=lambda t: ORDER[t[1]]):
        if _taken(db, handle, table, row):
            taken.append(handle)
        else:
            db.restore_wires([(table, row)])
            back.append(handle)
    info(f"delete_wire: put back {len(back)} wire(s)" + (f": {' '.join(back)}" if back else ""),
         session.out)
    if taken:
        warn(TAKEN, f"delete_wire: not put back, their place in the database is taken or "
             f"gone (routed again, or the instance changed, since they were deleted): "
             f"{' '.join(taken)}", session.out)
    return tuple(back)


def _taken(db, handle, table, row):
    """True when a deleted wire cannot go back as it was: a wire made since
    has its handle or its row, its instance is gone, or (a pin wire) its strap
    is."""
    if objects.wire_row(db, handle) is not None or db.wire_id_used(table, row["id"]):
        return True
    if table == "net_wire":
        return False
    if db.inst_row(row["inst"]) is None:
        return True
    return table == "pin_wire" and db.strap_row(row["inst"], row["strap"]) is None
