"""all_fanout -from <port or pin> [-to <port or pin>]: the paths of the
netlist from a port (or an output pin) forward, through every cell, with
the buffers and inverters on each.

    all_fanout -from [get_db ports clk] -to [get_db ports q]
    all_fanout -from [get_db ports clk]

A path goes from net to net through each cell on it, from the input pin a
net reaches to every signal output pin of the cell (core/netlist.py: the
spines, connect_pin and the buffers of add_buffer_on_net, connect_spine and
create_buffer_tree). It ends at -to (a port or an input pin), or without
-to at each end: an output port, an input pin of a cell whose outputs
drive nothing, a stub of a spine (a leaf's net ends at its stubs: stub
<spine>/<stub>), or the pin that drives a net with nothing more on it.
A cell is an inverter or a buffer as create_buffer_tree was told
(-inverter_ref, -buffer_ref), else by its name (INV, BUF in the cell's
name, ignoring case); others are counted apart. A loop is not followed
round again.

Returns a list with an element per path: {{<end>} <buffers> <inverters>}, so
lindex [lindex $r 0] 2 is the inverters of the first path.
"""

from core import netlist
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "all_fanout"
SUMMARY = "The paths from a port forward, with the buffers and inverters on each"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-to": "value"}
USAGE = "all_fanout -from <port or output pin> [-to <port or input pin>]"

NO_PATH = 305
MOST = 10000             # paths followed at most


def kind_of(ref, kinds=None):
    """inverter, buffer or other: as create_buffer_tree was told (kinds:
    db.cell_kinds()), else by the cell name."""
    if kinds and ref in kinds:
        return kinds[ref]
    name = ref.upper()
    return "inverter" if "INV" in name else "buffer" if "BUF" in name else "other"


def count(db, path, kinds=None):
    """(the instances on path, buffers, inverters, others): each cell whose
    input pin the path passes, not the input pin it ends at."""
    kinds = db.cell_kinds() if kinds is None else kinds
    insts = [e.inst for e in path[1:-1] if e.kind == "pin" and e.direction == "in"]
    found = [kind_of(db.inst_row(i)["ref_cell"], kinds) for i in insts]
    return insts, found.count("buffer"), found.count("inverter"), found.count("other")


def _one(session, text, option):
    words = session.split_list(text)
    if len(words) != 1:
        raise HtreeError(1, f"{NAME}: {option} takes one port or pin, got '{text}'. "
                         f"Usage: {USAGE}")
    return netlist.resolve(session.db, words[0], NAME)


class Stub:
    """The end of a path at a stub of a spine (a leaf's net)."""

    kind = "stub"

    def __init__(self, spine, name):
        self.text = f"stub {spine}/{name}"


def paths(db, start, end=None):
    """[[End...]]: every path from start (a port or an output pin) to end
    (an End), or to each end of the fanout without one. A path lists the
    pins it passes (each cell: its input then its output) and its end."""
    net = netlist.port_net(db, start.pin) if start.kind == "port" else \
        netlist.pin_net(db, start.inst, start.pin)
    if net is None:
        return []
    by_net, found = netlist.by_net(db), []
    spine_of = {r["name"]: (s, r) for s in db.spine_names()
                for r in db.spine_net_rows(db.spine_row(s)["id"])}

    def ref(inst):
        return db.inst_row(inst)["ref_cell"]

    def outs(inst):
        row = db.inst_row(inst)
        cell = db.lib_cell_row(row["ref_cell"]) if row is not None else None
        if cell is None:
            return []
        return [p for p in db.lib_pin_names(cell["id"])
                if (db.lib_pin_row(cell["name"], p)["direction"] or "").lower().startswith("out")
                and (db.lib_pin_row(cell["name"], p)["use"] or "signal").lower() == "signal"]

    def walk(net, trail, seen):
        if len(found) >= MOST:
            return
        before = len(found)
        if end is None and net in spine_of:      # a leaf's net: its stubs are ends
            spine, row = spine_of[net]
            stubs = {r["name"] for r in db.spine_stub_rows(db.spine_row(spine)["id"])}
            found.extend(trail + [Stub(spine, w)] for w in row["loads"].split() if w in stubs)
        port = db.port_of_net(net) if db.has_design() else None
        if port is not None and (port["direction"] or "").lower() == "out":
            e = netlist.End("port", db.design_row()["name"], port["name"], "out")
            if end is None or (end.kind == "port" and end.pin == port["name"]):
                found.append(trail + [e])
        for inst, pin in by_net.get(net, []):
            e = netlist.resolve(db, f"{inst}/{pin}", NAME)
            if not e.is_load:
                continue
            if end is not None and end.kind == "pin" and (inst, pin) == (end.inst, end.pin):
                found.append(trail + [e])
                continue
            nexts = [(o, netlist.pin_net(db, inst, o)) for o in outs(inst)]
            nexts = [(o, n) for o, n in nexts if n is not None]
            if not nexts:                # drives nothing: the path ends at its input
                if end is None:
                    found.append(trail + [e])
                continue
            if inst in seen:
                continue                 # round a loop: not again
            for o, n in nexts:
                walk(n, trail + [e, netlist.End("pin", inst, o, "out")], seen | {inst})
        if end is None and len(found) == before and len(trail) > 1:
            found.append(trail)          # a net nothing more is on: ends at its driver
    walk(net, [start], frozenset())
    return found


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-from" not in opts:
        raise HtreeError(1, f"{NAME}: -from is required. Usage: {USAGE}")
    start = _one(session, opts["-from"], "-from")
    if not start.drives:
        raise HtreeError(1, f"{NAME}: -from {start.text} drives nothing: give an input port "
                         f"or an output pin")
    end = _one(session, opts["-to"], "-to") if "-to" in opts else None
    found = paths(db, start, end)
    if not found:
        raise HtreeError(NO_PATH, f"{NAME}: no path from {start.text}"
                         + (f" to {end.text}" if end else "") + " in the netlist")
    totals, kinds = [], db.cell_kinds()
    for k, path in enumerate(found, start=1):
        insts, *counts = count(db, path, kinds)
        totals.append(tuple(counts))
        info(f"path {k}: {start.text} -> " + " -> ".join(
            f"{i} ({db.inst_row(i)['ref_cell']})" for i in insts)
            + (" -> " if insts else "") + path[-1].text, out)
        info(f"  number of buffers: {totals[-1][0]}  number of inverters: {totals[-1][1]}"
             + (f"  other cells: {totals[-1][2]}" if totals[-1][2] else "")
             + ("  (polarity inverted)" if totals[-1][1] % 2 else ""), out)
    if len(found) > 1:
        info(f"{len(found)} path(s); buffers {min(t[0] for t in totals)} .. "
             f"{max(t[0] for t in totals)}, inverters {min(t[1] for t in totals)} .. "
             f"{max(t[1] for t in totals)}", out)
    if len(found) >= MOST:
        info(f"  (the first {MOST} paths only)", out)
    # per path: its end, its buffers, its inverters
    return tuple(f"{{{path[-1].text}}} {b} {i}" for path, (b, i, _) in zip(found, totals))
