"""show_only -object <objects> | -show_all: draw only some nets, instances or
spines in the GUI, for debugging; -show_all draws everything again.

    show_only -object sp_L3_inv1_Y
    show_only -object {spine:sp u1}
    show_only -object [get_db selected]
    show_only -show_all

A filter on the display, over the boxes of the View panel: the other
instances and the routing of the other nets are not drawn (and cannot be
picked). The database does not change. What is shown of each object:

    instance  its outline, pins, route_pin straps and pin wires, the power
              connections optimize_pg_connection made for it, and their vias
    net       its wires with their shields, crossing boxes and vias, every
              other route shape on the net (a power net: straps, shields),
              its centre line, and the pins on it with their pin wires and
              the straps those reach
    stub      its bar, its route_final_stub wires and the vias on them
    spine     its instances, nets and stubs, each as above
"""

import fnmatch

from core import netlist, objects
from core.commands.route_pin import SIGNAL
from core.db import STUB
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "show_only"
SUMMARY = "Show only some nets, instances or spines in the GUI (-show_all: all again)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-object": "value", "-show_all": "flag"}
USAGE = "show_only -object <nets, instances or spines> | -show_all"

NO_OBJ = 270
NOT_SHOWABLE = 271
KINDS = ("spine", "inst", "spine_net", "net", "stub")      # what a filter is made of
PG = "pg:"               # the net_wire net of an instance's optimize_pg_connection wires
LISTED = 10              # names printed of each kind


class Scope:
    """What a show_only filter leaves on the display. The GUI asks shows()
    for each instance and route shape it draws."""

    def __init__(self):
        self.insts = set()               # instance names
        self.nets = set()                # net names
        self.pins = set()                # <inst>/<pin> of the pins on the nets
        self.lines = set()               # stub: and spine_net: handles (centre lines)
        # More shapes by handle: the wires and vias of the stubs shown alone, the
        # straps the pin wires of the nets reach.
        self.shapes = set()

    def shows(self, handle, net=None, source=None):
        """Is the shape of this handle drawn. net: the net a route shape is
        on; source: the wire a via is derived from (core/vias.py)."""
        if net in self.nets or handle in self.shapes:
            return True
        kind, _, name = handle.partition(":")
        if kind == "via":
            return bool(source) and self.shows(source)
        owner = name.rpartition("/")[0]
        if kind == "inst":
            return name in self.insts
        if kind in ("pin", "pin_wire"):
            return owner in self.insts or name in self.pins
        if kind == "strap":
            return owner in self.insts
        if kind == "net_wire":           # a stub's rows (<net>_stub) go with its net
            return owner in self.nets or (owner.startswith(PG) and owner[len(PG):] in self.insts) \
                or (owner.endswith(STUB) and owner[:-len(STUB)] in self.nets)
        if kind in ("stub", "spine_net"):
            return handle in self.lines
        return True                      # not an instance, not net routing: a port


def scope(db):
    """The Scope of the filter show_only set (db.show_only), from what the
    database has now: a net routed again is shown with its new wires. None
    when no filter is set. An object that is gone shows nothing."""
    if not db.show_only:
        return None
    return scope_of(db, db.show_only)


def scope_of(db, handles):
    """The Scope of these handles (KINDS), as show_only -object takes them."""
    sc = Scope()
    for handle in handles:
        kind, name = objects.obj_type(handle), handle.partition(":")[2]
        if kind == "net":                # also a power net, which is no net object
            sc.nets.add(name)
        elif not objects.exists(db, handle):
            continue
        elif kind == "inst":
            sc.insts.add(name)
        elif kind == "spine_net":
            sc.nets.add(name.partition("/")[2])
            sc.lines.add(handle)
        elif kind == "stub":
            sc.lines.add(handle)
            sc.shapes.update(objects.get_attr(db, handle, "net_wires") +
                             objects.get_attr(db, handle, "vias"))
        else:                            # a spine: all of it
            spine = db.spine_row(name)
            sc.insts.update(m["inst"] for m in db.spine_members(spine["id"]))
            sc.nets.update(r["name"] for r in db.spine_net_rows(spine["id"]))
            sc.lines.update(objects.get_attr(db, handle, "spine_nets") +
                            objects.get_attr(db, handle, "stubs"))
    by_net = netlist.by_net(db)
    for inst, pin in (p for net in sc.nets for p in by_net.get(net, [])):
        sc.pins.add(f"{inst}/{pin}")
        wire = db.pin_wire_row(inst, pin)
        if wire is not None and wire["strap"]:        # the strap the net is routed to
            sc.shapes.add(f"strap:{inst}/{wire['strap']}")
    return sc


def net_handles(db):
    """{net name: its handle}: the nets of the built spines, the nets with a
    pin or a port on them, and the nets only route shapes are on (power
    nets: straps, shields)."""
    found = {r["name"]: f"spine_net:{s}/{r['name']}" for s in db.spine_names()
             for r in db.spine_net_rows(db.spine_row(s)["id"])}
    others = list(netlist.by_net(db)) + db.port_net_names() + \
        [n for n in db.route_nets() if n != SIGNAL and not n.startswith(PG)]
    for name in others:
        found.setdefault(name, f"net:{name}")
    return found


def _owner(db, handle):
    """The instance or net a pin, a wire or a via belongs to (what the GUI
    selects on a click), or None for another kind of object."""
    kind, name = objects.obj_type(handle), handle.partition(":")[2]
    if kind in ("pin", "strap", "pin_wire"):
        return f"inst:{name.rpartition('/')[0]}"
    if kind == "net_wire":
        net = name.rpartition("/")[0]
        if net.startswith(PG):
            return f"inst:{net[len(PG):]}"
        if net.endswith(STUB):               # a stub's wire: the stub
            stub = _stub_of(db, net[:-len(STUB)])
            if stub:
                return stub
        return netlist.net_handle(db, net)
    if kind == "via":
        return _owner(db, objects.get_attr(db, handle, "source"))
    return None


def _stub_of(db, leaf):
    """stub:<spine>/<stub> of the stub a leaf net drives, or None."""
    for s in db.spine_names():
        row = db.spine_row(s)
        stubs = {r["name"] for r in db.spine_stub_rows(row["id"])}
        for n in db.spine_net_rows(row["id"]):
            if n["name"] == leaf:
                hit = [w for w in n["loads"].split() if w in stubs]
                return f"stub:{s}/{hit[0]}" if hit else None
    return None


def resolve(session, text):
    """The handles (KINDS) of the words of -object: handles, or names and
    glob patterns, which take every spine, instance, net and stub of the
    name."""
    db = session.db
    nets = net_handles(db)
    stubs = [(s, r["name"]) for s in db.spine_names()
             for r in db.spine_stub_rows(db.spine_row(s)["id"])]
    found = []
    for word in session.split_list(text):
        if word.startswith("net:") and nets.get(word[4:]) == word:
            hits = [word]
        elif objects.is_handle(word):
            objects.check_exists(db, word)
            hits = [word if objects.obj_type(word) in KINDS else _owner(db, word)]
            if hits[0] is None:
                raise HtreeError(NOT_SHOWABLE, f"show_only: '{word}' is not a net, an "
                                 f"instance or a spine (nor a pin, wire or via of one). "
                                 f"The display is not changed")
        else:
            hits = [f"spine:{n}" for n in db.spine_names() if fnmatch.fnmatchcase(n, word)] + \
                [f"inst:{n}" for n in db.inst_names() if fnmatch.fnmatchcase(n, word)] + \
                [h for n, h in nets.items() if fnmatch.fnmatchcase(n, word)] + \
                [f"stub:{s}/{n}" for s, n in stubs if fnmatch.fnmatchcase(n, word)]
            if not hits:
                raise HtreeError(NO_OBJ, f"show_only: no net, instance or spine '{word}' "
                                 f"(get_db nets, get_db insts, get_db spines). The display "
                                 f"is not changed")
        found += [h for h in hits if h not in found]
    return found


def _names(handles, kinds):
    names = [h.partition(":")[2] for h in handles if objects.obj_type(h) in kinds]
    more = f" ... (+{len(names) - LISTED} more)" if len(names) > LISTED else ""
    return len(names), " ".join(names[:LISTED]) + more


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if opts["-show_all"] == ("-object" in opts):
        raise HtreeError(1, f"show_only: give -object or -show_all, one of the two. "
                         f"Usage: {USAGE}")
    if opts["-show_all"]:
        was = len(db.show_only)
        db.show_only = []
        info("show_only: every instance and all net routing are shown again" if was else
             "show_only: nothing was hidden", out)
        return None
    handles = resolve(session, opts["-object"])
    if not handles:
        raise HtreeError(1, f"show_only: -object is empty: nets, instances or spines. "
                         f"Usage: {USAGE}")
    db.show_only = handles
    info(f"show_only: showing only {len(handles)} object(s); the other instances and net "
         f"routing are hidden", out)
    for title, kinds in (("Spines", ("spine",)), ("Instances", ("inst",)),
                         ("Nets", ("spine_net", "net")), ("Stubs", ("stub",))):
        n, text = _names(handles, kinds)
        if n:
            info(f"  {title:<12}: {n} ({text})", out)
    info("  show_only -show_all shows everything again", out)
    return handles
