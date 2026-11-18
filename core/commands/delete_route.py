"""delete_route -nets <nets>: remove the physical routing of nets; the nets
themselves (instances, connections, route rules) stay.

    delete_route -nets [get_db stubs]
    delete_route -nets {temp_L1_inv1_Y temp_L2*}

A stub loses its route_final_stub wire and crossing boxes. A spine net, or a
net of no spine (net:<name>: a port's, connect_pin's, add_buffer_on_net's),
loses what route_net made: wires, strap extensions, crossing boxes, shields
and shield extensions; the route_pin straps and pin wires it had named after
the net go back to SIGNAL, as they connect to nothing now. A leaf net keeps its
stub's wire, and a stub keeps its leaf net's route: each is deleted on its own.
"""

import fnmatch

from core import netlist, route_status
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "delete_route"
SUMMARY = "Remove the physical routing of nets (the nets stay)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-nets": "value"}

USAGE = 1
NO_NET = 195
NOTHING = 196
SIGNAL = "SIGNAL"


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-nets" not in opts:
        raise HtreeError(USAGE, "delete_route: -nets is required. Usage: delete_route -nets "
                         "<nets>  (names, patterns, spine_net:, net: or stub: handles)")
    db = session.db
    nets, stubs = _targets(session, opts["-nets"])
    out = session.out
    fixed = db.fixed_nets()
    held = [f"spine_net:{spine}/{name}" if spine else f"net:{name}"
            for spine, name in nets if name in fixed]
    held += [f"stub:{spine}/{stub}" for spine, stub, _ in stubs
             if route_status.stub_key(spine, stub) in fixed]
    route_status.skip(NAME, "fixed net(s)", held, out)
    nets = [(spine, name) for spine, name in nets if name not in fixed]
    stubs = [e for e in stubs if route_status.stub_key(e[0], e[1]) not in fixed]
    done = []
    for spine, name in nets:
        wires = db.set_net_wires(name, [], stub=False)
        kept = db.fixed_wire_rows(name)
        if kept:
            route_status.skip(NAME, f"fixed wire(s) of {name}",
                              [f"net_wire:{name}/{r['seq']}" for r in kept], out)
        pins = 0 if kept else db.unname_pins(name, SIGNAL)
        info(f"  {name}: {wires} wire(s), extension(s), crossing box(es) and shield(s) "
             f"removed" + (f"; {pins} strap(s) and pin wire(s) back on {SIGNAL}"
                           if pins else ""), out)
        if wires or pins:
            done.append(f"spine_net:{spine}/{name}" if spine else f"net:{name}")
    for spine, stub, leaf in stubs:
        wires = db.set_net_wires(leaf, [], stub=True) if leaf else 0
        info(f"  stub {spine}/{stub}: {wires} wire(s) and crossing box(es) removed"
             f"{f' (from net {leaf})' if leaf else ''}", out)
        if wires:
            done.append(f"stub:{spine}/{stub}")
    if not done and not held:
        warn(NOTHING, "delete_route: the nets given have no routing; nothing removed", out)
    given = len(nets) + len(stubs) + len(held)
    info(f"delete_route: routing removed from {len(done)} of {given} net(s); the nets stay",
         out)
    return tuple(done)


def _targets(session, text):
    """([(spine, net name)], [(spine, stub name, leaf net)]) from names, glob
    patterns, spine_net:, net: and stub: handles; each word must match one.
    A net of no spine (net:<name>) has spine None."""
    db = session.db
    nets, stubs = [], []
    for s in db.spine_names():
        spine = db.spine_row(s)
        rows = db.spine_net_rows(spine["id"])
        nets += [(s, r["name"]) for r in rows]
        leaf = {r["loads"]: r["name"] for r in rows}
        stubs += [(s, r["name"], leaf.get(r["name"])) for r in db.spine_stub_rows(spine["id"])]
    mine = {name for _, name in nets}
    # the nets of no spine: with a pin on them, or still holding a route
    plain = [n for n in dict.fromkeys(netlist.plain_nets(db) + [
        r["net"] for r in db.net_wire_rows() if r["kind"] == "wire"]) if n not in mine]
    found_nets, found_stubs = [], []
    for word in session.split_list(text):
        kind, _, rest = word.partition(":") if ":" in word else ("", "", word)
        spine, _, name = rest.partition("/") if kind else ("", "", rest)
        hit_nets = [n for n in nets if kind in ("", "spine_net")
                    and (n == (spine, name) if kind else fnmatch.fnmatchcase(n[1], name))]
        hit_nets += [(None, n) for n in plain if kind in ("", "net")
                     and (n == rest if kind else fnmatch.fnmatchcase(n, rest))]
        hit_stubs = [t for t in stubs if kind in ("", "stub")
                     and ((t[0], t[1]) == (spine, name) if kind
                          else fnmatch.fnmatchcase(t[1], name))]
        if not hit_nets and not hit_stubs:
            raise HtreeError(NO_NET, f"delete_route: no net or stub '{word}' (get_db nets "
                             f"lists them)")
        found_nets += [n for n in hit_nets if n not in found_nets]
        found_stubs += [t for t in hit_stubs if t not in found_stubs]
    return found_nets, found_stubs
