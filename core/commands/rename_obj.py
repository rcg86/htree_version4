"""rename_obj -from <net or instance> -to <new name>: rename a net or an
instance everywhere htree4 names it.

    rename_obj -from [get_db spine:sp .root_net] -to clk_root
    rename_obj -from sp_L1_inv1_Y -to sp_root_out
    rename_obj -from [get_db inst:sp_L1_inv1 .name] -to sp_root_buf

A net: a spine net, a spine's root net, or a net connect_pin made, with its
wires, its stub's wires (<net>_stub), straps, pin wires, route rule, route
status and via assignments (db.rename_net). The net of a port is the
design's and is not renamed, nor a power net. An instance: everything that
names it (db.rename_inst); the nets it drives keep their names. The
selection, show_only and highlight follow the new name.
"""

import re

from core import netlist, objects
from core.commands.show_only import net_handles
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "rename_obj"
SUMMARY = "Rename a net or an instance"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-to": "value"}
USAGE = "rename_obj -from <net or instance> -to <new name>"

NO_OBJECT = 292
AMBIGUOUS = 293
TAKEN = 294
NOT_RENAMABLE = 295
BAD_NAME = 296
NAME_OK = re.compile(r"[^\s/:{}\[\]\"\\$;]+")    # one Tcl word, no handle separators


def _target(session, word):
    """(kind, name) of -from: inst or net, by handle or by name."""
    db = session.db
    if objects.is_handle(word):
        kind = objects.obj_type(word)
        if kind not in ("inst", "net", "spine_net"):
            raise HtreeError(NOT_RENAMABLE, f"rename_obj: '{word}' is not a net or an "
                             f"instance; only those are renamed")
        objects.check_exists(db, word)
        name = word.partition(":")[2]
        return ("inst", name) if kind == "inst" else ("net", name.rpartition("/")[2])
    is_inst = db.inst_row(word) is not None
    is_net = word in net_handles(db)
    if is_inst and is_net:
        raise HtreeError(AMBIGUOUS, f"rename_obj: '{word}' is both an instance and a net: "
                         f"give inst:{word} or {net_handles(db)[word]}")
    if is_inst:
        return "inst", word
    if is_net:
        return "net", word
    raise HtreeError(NO_OBJECT, f"rename_obj: no net or instance '{word}' (get_db nets, "
                     f"get_db insts list them)")


def _check_net(db, old, new):
    ports = db.port_net_names()
    if old in ports:
        raise HtreeError(NOT_RENAMABLE, f"rename_obj: '{old}' is the net of a port: it is the "
                         f"design's and keeps its name")
    spine_nets = netlist.spine_nets(db)
    if old not in spine_nets and old not in netlist.by_net(db):
        raise HtreeError(NOT_RENAMABLE, f"rename_obj: '{old}' is on no pin (a power net, or "
                         f"route shapes only); only a signal net is renamed")
    taken = set(net_handles(db)) | set(ports) | \
        {r[0] for r in db.conn.execute("SELECT DISTINCT net FROM net_wire")}
    if new in taken or new.endswith("_stub"):
        raise HtreeError(TAKEN, f"rename_obj: a net '{new}' is there already" if new in taken
                         else f"rename_obj: '{new}' ends in _stub, the name of a stub's wires")


def _follow(handle, kind, old, new):
    """handle after the rename, for the selection, show_only and highlight."""
    k, _, rest = handle.partition(":")
    if kind == "inst":
        if k == "inst" and rest == old:
            return f"inst:{new}"
        if k in ("pin", "strap", "pin_wire") and rest.startswith(old + "/"):
            return f"{k}:{new}/{rest[len(old) + 1:]}"
        return handle
    if k == "net" and rest == old:
        return f"net:{new}"
    if k == "spine_net" and rest.rpartition("/")[2] == old:
        return f"spine_net:{rest.rpartition('/')[0]}/{new}"
    if k == "net_wire":
        owner, _, seq = rest.rpartition("/")
        if owner in (old, old + "_stub"):
            return f"net_wire:{new}{owner[len(old):]}/{seq}"
    return handle


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db = session.db
    if "-from" not in opts or "-to" not in opts:
        raise HtreeError(1, f"rename_obj: give -from and -to. Usage: {USAGE}")
    words = session.split_list(opts["-from"])
    if len(words) != 1:
        raise HtreeError(1, f"rename_obj: -from takes one net or instance, not "
                         f"{len(words)}. Usage: {USAGE}")
    new = opts["-to"]
    if not NAME_OK.fullmatch(new):
        raise HtreeError(BAD_NAME, f"rename_obj: '{new}' is not a name: no blanks, '/', ':', "
                         f"braces, brackets, quotes, '$' or ';'")
    kind, old = _target(session, words[0])
    if new == old:
        raise HtreeError(TAKEN, f"rename_obj: '{old}' has that name already")
    if kind == "inst":
        if db.inst_row(new) is not None:
            raise HtreeError(TAKEN, f"rename_obj: an instance '{new}' is there already")
        db.rename_inst(old, new)
        info(f"rename_obj: instance {old} renamed {new} (the nets it drives keep their names)",
             session.out)
        result = f"inst:{new}"
    else:
        _check_net(db, old, new)
        roots = [s for s in db.spine_names() if netlist.root_net(db, db.spine_row(s)) == old]
        wires = db.rename_net(old, new, roots)
        what = f"root net of spine {', '.join(roots)}" if roots else "net"
        info(f"rename_obj: {what} {old} renamed {new} ({wires} wire(s))", session.out)
        result = netlist.net_handle(db, new)
    for state in (db.selection, db.show_only):
        state[:] = [_follow(h, kind, old, new) for h in state]
    db.highlights[:] = [(_follow(h, kind, old, new), c) for h, c in db.highlights]
    return result
