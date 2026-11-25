"""connect_spine -from <spine | stubs> -to <spines | pins | ports> [-ref_cell
<lib_cell> -distance <um> [-name <prefix>]] [-source_spine_stub_distance <um>]
[-sink_spine_distance <um>]: connect the inputs of spines, input pins of
instances and output ports of the design to the nearest stub of a built
spine.

    connect_spine -from sp -to sp2
    connect_spine -from spine:sp -to {sp2 sp3 buf1/A}
    connect_spine -from sp -to q -ref_cell INV_RP -distance 10 -name out
    connect_spine -from sp -to sp2 -source_spine_stub_distance 5 \
        -sink_spine_distance 10 -ref_cell INV_RP

A -to spine with -source_spine_stub_distance and/or -sink_spine_distance
(and -ref_cell) is driven through buffers on the way from its stub to its
root input: stub -> source buffer (its input pin -source_spine_stub_distance
from the stub) -> sink buffer (its output pin -sink_spine_distance from the
root input) -> root input(s). Each buffer drives a net of its own,
<buffer>_<output pin>; the link is kept in spine_link. Returns then two
names per -to spine: the source buffer and the sink buffer, "" for one not
made. Else the pins of -to.

Each -to spine takes the stub of -from nearest to it, by the Manhattan
distance from the input pin of its root (the middle of the two of a mirrored
spine) to the stub; its root input pins go onto the net of that stub, the net
of the leaf that drives it. A pin of -to takes the stub nearest to itself. A
stub may get more than one. A pin that is on another net is taken off it
first. A port of -to gets a buffer, -distance from the port towards its
nearest stub: the stub's net goes to the input of the buffer, and its output
drives the port. Only the netlist changes (get_db pin:<inst>/<pin> .net,
write_logical), not the routing.
"""

import math
import re

from core import netlist, objects
from core.commands.add_buffer_on_net import BAD_CELL, NOT_LEGAL, _check_place, _pin_offset
from core.commands.connect_pin import warn_routed
from core.commands.write_def import cell_pin
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import placed_bbox, point_in_polygon, rect_in_polygon

NAME = "connect_spine"
SUMMARY = "Connect the inputs of spines, input pins and ports to the nearest stub of a spine"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-to": "value", "-ref_cell": "value",
           "-distance": "value", "-name": "value", "-sink_spine_distance": "value",
           "-source_spine_stub_distance": "value"}

USAGE = 1
BAD_DIRECTION = netlist.BAD_DIRECTION
NO_STUB = 267
LOOP = 268
PORT = 269
OLD_BUFFER = 299             # WARN: a buffer of an earlier link is left on the stub's net


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-from" not in opts or "-to" not in opts:
        raise HtreeError(USAGE, "connect_spine: -from and -to are required. Usage: "
                         "connect_spine -from <spine> -to <spines | pins | ports> "
                         "[-ref_cell <lib_cell> -distance <um> [-name <prefix>]] "
                         "[-sink_spine_distance <um>] [-source_spine_stub_distance <um>]")
    sources = list(dict.fromkeys(session.split_list(opts["-from"])))
    words = list(dict.fromkeys(session.split_list(opts["-to"])))
    if not sources or not words:
        raise HtreeError(USAGE, f"connect_spine: -from takes one spine, or stubs of one spine, "
                         f"and -to one or more spines, pins or ports, got -from "
                         f"'{opts['-from']}' -to '{opts['-to']}'")
    spine, stubs = _sources(db, sources)
    targets = list({t.text: t for t in (_target(db, w, spine) for w in words)}.values())
    if "-distance" in opts and not any(t.port for t in targets):
        raise HtreeError(USAGE, "connect_spine: -distance is where the buffer of an output "
                         "port goes, and -to has no port. For a spine: "
                         "-source_spine_stub_distance <um> (a buffer that far from the "
                         "stub), -sink_spine_distance <um> (a buffer that far from its "
                         "input)")
    inside = {m["inst"] for m in db.spine_members(spine["id"])}
    above = _upstream(db, inside)
    picks = []                           # (target, stub, distance)
    for t in targets:
        loop = sorted({e.inst for e in t.ends} & above)
        if loop:
            raise HtreeError(LOOP, f"connect_spine: {t.text} is in spine {spine['name']} or "
                             f"drives it ({' '.join(loop)}): its stub cannot drive it")
        picks.append((t,) + min(((s, _distance(t.at, s.points)) for s in stubs),
                                key=lambda pick: pick[1]))
    # the ports: each gets a buffer, planned before anything is stored
    bufs = _buffers(session, opts, [(t, s) for t, s, _ in picks if t.port])
    links = _links(session, opts, [(t, s, d) for t, s, d in picks if t.spine],
                   ports=any(t.port for t, _, _ in picks))

    ends = list(dict.fromkeys(e for t, _, _ in picks for e in t.ends))
    feed = {e: (s.net, s.driver) for t, s, _ in picks for e in t.ends}   # (net, driver)
    made = [b for k in links if k.new for b in k.buffers()]
    for k in links:              # behind its buffers: the last one's net
        _, _, net, driver = k.chain()[-1]
        for e in k.target.ends:
            feed[e] = (net, driver)
    now = {e: netlist.pin_net(db, e.inst, e.pin) for e in ends}
    same = [e for e in ends if now[e] == feed[e][0]]
    taken = [e for e in ends if now[e] not in (None, feed[e][0])]
    todo = [e for e in ends if e not in same]
    if bufs or made:
        db.add_net_buffers([(b.name, b.ref, b.x, b.y, b.orient) for b in bufs]
                           + [(b.name, b.ref, b.x, b.y, b.orient) for b in made],
                           [], [], [], [])
    with db.conn:
        for b in bufs:
            netlist.connect_port(db, b.name, b.pin_out, b.port)
        for k in links:
            if k.new:            # each buffer's input on the net before it
                for inst, pin, net, driver in k.chain()[:len(k.buffers())]:
                    netlist.connect_load(db, inst, pin, net, driver)
        for e in taken:
            netlist.disconnect_load(db, e.inst, e.pin)
        for e in todo:
            netlist.connect_load(db, e.inst, e.pin, *feed[e])
    for k in links:
        db.set_spine_link(spine["name"], k.stub.name, k.target.spine,
                          k.src.name if k.src else None, k.src_d,
                          k.sink.name if k.sink else None, k.sink_d)
    legal = _legalize(session, bufs + made)

    info(f"connect_spine: spine {spine['name']} ({len(stubs)} stub(s)) -> "
         f"{len(targets)} of -to, {len(todo)} pin(s) connected"
         + (f", {len(bufs)} buffer(s) made" if bufs else ""), out)
    rows = [(t.text, s.name, s.net, _num(round(d, 3)), " ".join(e.text for e in t.ends))
            for t, s, d in picks]
    heads = ("To", "Stub", "Net", "Distance", "Pins")
    wide = [max(len(h), *(len(r[k]) for r in rows)) for k, h in enumerate(heads)]
    for r in [heads] + rows:
        info("  " + "  ".join(c.rjust(w) if k == 3 else c.ljust(w)
                              for k, (c, w) in enumerate(zip(r, wide))).rstrip(), out)
    if taken:
        info("  disconnected first: " + ", ".join(f"{e.text} from net {now[e]}"
                                                 for e in taken), out)
    if same:
        info(f"  on the net already: {' '.join(e.text for e in same)}", out)
    if bufs:
        _report_buffers(db, bufs, opts, out)
    if links:
        _report_links(db, links, out)
    if todo:
        info("  netlist only: no wire is made; route_net routes the stub's net to these pins "
             "(route_net -force on a fixed net: to them only, its wires kept)"
             + ("; it does not route the net of an output port" if bufs else ""), out)
    placed = [b.name for b in bufs] + [b.name for b in made]
    if placed:
        _check_place(db, placed, out, NAME)
        info("  Next: " + ("" if legal else "legalize_placement, ") + "route_pin -inst {"
             + " ".join(placed) + "}", out)
    # The wires of a net a pin was taken off still go to the pin. Not so those
    # of a leaf's net, the stub's too: they go to the stub only.
    leaf = {net for net, (_, is_leaf) in netlist.spine_nets(db).items() if is_leaf}
    stale = {}
    for e in taken:
        if now[e] not in leaf:
            stale.setdefault(now[e], []).append(e.text)
    warn_routed(db, stale, NAME, out)
    if links:                    # per -to spine: {source buffer, sink buffer}; "" for none
        return tuple(n for k in links for n in (k.src.name if k.src else "",
                                                 k.sink.name if k.sink else ""))
    return tuple(e.handle for e in ends)


class Stub:
    """A stub of the -from spine: its name, the net and the output pin (an
    End) of the leaf that drives it, and its centre line [(x, y)]."""

    def __init__(self, name, net, driver, points):
        self.name, self.net, self.driver, self.points = name, net, driver, points


class Target:
    """What -to names: a spine (its root input pins), a pin, or a port of the
    design (port: its name). ends: the input pins to connect, of a port the
    input of its buffer, once that is known; at: the point its distance to a
    stub is from."""

    def __init__(self, db, text, ends, port=None, spine=None):
        self.text, self.ends, self.port, self.spine = text, ends, port, spine
        if port is not None:
            self.at = objects.port_centre(db, port)
            return
        spots = [objects.pin_centre(db, e.inst, e.pin) for e in ends]
        xs, ys = [x for x, _ in spots], [y for _, y in spots]
        self.at = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


class Buffer:
    """The buffer of a port: its instance (name, ref, lower-left x y, orient),
    the pins of its cell, and how far the port is from its stub when that is
    nearer than -distance (near, else None)."""

    def __init__(self, port, name, ref, x, y, orient, pin_in, pin_out, near):
        self.port, self.name, self.ref, self.x, self.y = port, name, ref, x, y
        self.orient, self.pin_in, self.pin_out, self.near = orient, pin_in, pin_out, near


def _spine(db, word, option):
    name = word.removeprefix("spine:")
    row = db.spine_row(name)
    if row is None:
        raise HtreeError(objects.UNKNOWN_OBJECT, f"connect_spine: {option}: no built spine "
                         f"'{name}' (get_db spines lists them)")
    return row


def _sources(db, words):
    """(spine row, [Stub]) of -from: one spine (its stubs), or stubs of one
    spine (stub:<spine>/<stub> handles: those stubs only)."""
    if not all(objects.is_handle(w) and objects.obj_type(w) == "stub" for w in words):
        if len(words) != 1:
            raise HtreeError(USAGE, f"connect_spine: -from takes one spine, or stubs of one "
                             f"spine (stub: handles), got '{' '.join(words)}'")
        spine = _spine(db, words[0], "-from")
        return spine, _stubs(db, spine)
    names = {}
    for w in words:
        objects.check_exists(db, w)
        owner, _, stub = w.partition(":")[2].partition("/")
        names.setdefault(owner, []).append(stub)
    if len(names) != 1:
        raise HtreeError(USAGE, f"connect_spine: -from: stubs of one spine, got stubs of "
                         f"{' '.join(names)}")
    (owner, wanted), = names.items()
    spine = _spine(db, owner, "-from")
    stubs = [s for s in _stubs(db, spine) if s.name in wanted]
    if not stubs:
        raise HtreeError(NO_STUB, f"connect_spine: -from: no stub of {' '.join(words)} is "
                         f"driven by a leaf")
    return spine, stubs


def _stubs(db, spine):
    """The stubs of spine that a leaf drives, as Stub."""
    found = []
    for s in db.spine_stub_rows(spine["id"]):
        pin = netlist.signal_pin(db, s["driver"], "out") if s["driver"] else None
        pts = [float(c) for c in (s["points"] or "").split()]
        if not pin or len(pts) < 4:
            continue
        driver = netlist.resolve(db, f"{s['driver']}/{pin}", NAME)
        found.append(Stub(s["name"], netlist.driver_net(db, driver, NAME)[0], driver,
                          list(zip(pts[0::2], pts[1::2]))))
    if not found:
        raise HtreeError(NO_STUB, f"connect_spine: spine {spine['name']} has no stub driven "
                         f"by a leaf (get_db spine:{spine['name']} .stubs)")
    return found


def _target(db, word, source):
    """The Target of a -to word: spine:<name>, a pin (pin:<inst>/<pin> or
    <inst>/<pin>), a port (port:<design>/<port>), or the name of a spine or
    of a port."""
    kind = objects.obj_type(word) if objects.is_handle(word) else None
    if kind == "pin" or (kind is None and "/" in word):
        end = netlist.resolve(db, word, NAME)
        if end.kind == "pin":
            if not end.is_load:
                raise HtreeError(BAD_DIRECTION, f"connect_spine: -to {end.text} is "
                                 f"{end.what}: a stub drives input pins of instances")
            return Target(db, f"pin {end.text}", [end])
    if kind == "spine" or (kind is None and db.spine_row(word) is not None):
        spine = _spine(db, word, "-to")
        if spine["id"] == source["id"]:
            raise HtreeError(LOOP, f"connect_spine: spine {spine['name']} is given with "
                             f"-from and with -to: its stub cannot drive its own input")
        ends = []
        for m in db.spine_members(spine["id"]):
            if m["driver"]:
                continue
            pin = netlist.signal_pin(db, m["inst"], "in")
            if not pin:
                raise HtreeError(BAD_DIRECTION, f"connect_spine: the root {m['inst']} of "
                                 f"spine {spine['name']} has no signal input pin")
            ends.append(netlist.resolve(db, f"{m['inst']}/{pin}", NAME))
        if not ends:
            raise HtreeError(objects.UNKNOWN_OBJECT, f"connect_spine: spine "
                             f"{spine['name']} has no root cell: build it (create_spine "
                             f"-build)")
        return Target(db, f"spine {spine['name']}", ends, spine=spine["name"])
    if kind == "port" or (kind is None and db.has_design() and db.port_row(word) is not None):
        end = netlist.resolve(db, word, NAME)
        if end.direction == "in":
            raise HtreeError(BAD_DIRECTION, f"connect_spine: -to {end.text} is an input port: "
                             f"it drives nets of the design, a stub cannot drive it")
        if objects.port_centre(db, end.pin) is None:
            raise HtreeError(PORT, f"connect_spine: -to {end.text} has no shapes and no "
                             f"location (DEF PINS): its nearest stub is not known")
        return Target(db, end.text, [], end.pin)
    raise HtreeError(objects.UNKNOWN_OBJECT, f"connect_spine: -to: no spine, pin or port "
                     f"'{word}' (get_db spines, get_db inst:<inst> .pins, get_db ports)")


def _buffers(session, opts, ports):
    """The buffers to make for ports [(Target, Stub)], as Buffer; the input
    pin of each becomes the ends of its Target. A port whose net is driven
    from its stub already gets none: its driver's input pin is its ends."""
    if not ports:
        return []
    db = session.db
    ref = opts.get("-ref_cell")
    # where the buffer goes: -distance from the port, else -source_spine_stub_distance from
    # the stub (the way from the stub to the port, as for a -to spine)
    dist, from_stub = _um(opts, "-distance"), _um(opts, "-source_spine_stub_distance")
    if ref is None or (dist is None and from_stub is None):
        raise HtreeError(USAGE, f"connect_spine: -to {ports[0][0].text}: a port is driven "
                         f"through a buffer, give -ref_cell <lib_cell> and -distance <um> "
                         f"(from the port) or -source_spine_stub_distance <um> (from the "
                         f"stub), and -name <prefix>")
    prefix = _prefix(opts)
    ref, cell, pin_in, pin_out = _cell(db, ref)
    snap, boundary = _snap(db), [float(v) for v in (db.design_row()["boundary"] or "").split()]
    w, h = cell["size_x"], cell["size_y"]
    taken = set(db.inst_names())
    made = []
    for t, stub in ports:
        driver = netlist.port_driver(db, t.port)
        if driver is not None:
            pin = netlist.signal_pin(db, driver.inst, "in")
            if not pin or netlist.pin_net(db, driver.inst, pin) != stub.net:
                raise HtreeError(PORT, f"connect_spine: {t.text} is driven already, by "
                                 f"{driver.text}: take that off first (disconnect_pin -pin "
                                 f"{driver.text})")
            t.ends = [netlist.resolve(db, f"{driver.inst}/{pin}", NAME)]
            continue
        # a bit of a bus, d[3]: buf_d_3, a name that needs no escaping
        base = f"{prefix}_" + re.sub(r"\W+", "_", t.port).strip("_")
        name, k = base, 1
        while name in taken:
            k += 1
            name = f"{base}_{k}"
        taken.add(name)
        orient = db.inst_row(stub.driver.inst)["orient"] or "N"
        to = _nearest(t.at, stub.points)
        # the output pin of the buffer goes dist from the port, on the way to
        # the stub (or its input pin from_stub from the stub, on the way to the
        # port): the way that keeps the cell inside the boundary, else the one
        # that keeps the pin inside it (a way along the edge of the die:
        # legalize_placement takes the cell off the edge), else the first
        if dist is not None:
            off, way, d = _pin_offset(db, cell, pin_out, orient), _ways(t.at, to, dist), dist
        else:
            off, way, d = _pin_offset(db, cell, pin_in, orient), _ways(to, t.at, from_stub), \
                from_stub
        spots = []
        for px, py in way:
            x, y = snap(px - off[0] - w / 2), snap(py - off[1] - h / 2)
            cell_in = not boundary or rect_in_polygon(placed_bbox(w, h, orient, x, y), boundary)
            spots.append((not cell_in, not (boundary and point_in_polygon(px, py, boundary)),
                          len(spots), x, y))
        x, y = min(spots)[3:]
        away = abs(to[0] - t.at[0]) + abs(to[1] - t.at[1])
        made.append(Buffer(t.port, name, ref, x, y, orient, pin_in, pin_out,
                           away if away < d else None))
        t.ends = [netlist.End("pin", name, pin_in, "in")]
    return made


def _prefix(opts):
    prefix = opts.get("-name", "buf")
    if not prefix or "/" in prefix or any(c.isspace() for c in prefix):
        raise HtreeError(USAGE, f"connect_spine: -name '{prefix}' must not be empty or "
                         f"contain '/' or spaces")
    return prefix


def _cell(db, ref):
    """(ref, lib cell row, input pin, output pin) of a buffer cell."""
    objects.require_library(db)
    ref = ref.removeprefix("lib_cell:")
    cell = db.lib_cell_row(ref)
    if cell is None:
        raise HtreeError(BAD_CELL, f"connect_spine: lib cell '{ref}' is not in the library "
                         f"(read_lef); cells: {' '.join(db.lib_cell_names())}")
    pin_in, pin_out = cell_pin(db, ref, "in"), cell_pin(db, ref, "out")
    if cell["size_x"] is None or not pin_in or not pin_out:
        raise HtreeError(BAD_CELL, f"connect_spine: lib cell {ref} needs a SIZE, a signal "
                         f"input pin and a signal output pin in its LEF")
    return ref, cell, pin_in, pin_out


def _snap(db):
    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    return (lambda v: round(round(v / grid) * grid, 6)) if grid else (lambda v: round(v, 6))


def _um(opts, option):
    """The value of a distance option, um above 0; None when not given."""
    if option not in opts:
        return None
    try:
        v = float(opts[option])
    except ValueError:
        v = None
    if v is None or not math.isfinite(v) or v <= 0:
        raise HtreeError(USAGE, f"connect_spine: {option} must be a distance in um above 0, "
                         f"got '{opts[option]}'")
    return v


class Link:
    """A -to spine with -source_spine_stub_distance or -sink_spine_distance:
    its Target, Stub, the straight way from the stub to its root input (x +
    y), the two distances (None: not given) and its two buffers (Buffer or
    None): the source buffer next to the stub, the sink buffer next to the
    spine. new False: the buffers of the link before, kept; old: the names
    of the ones of before that are left."""

    def __init__(self, target, stub, straight, src_d, sink_d):
        self.target, self.stub, self.straight = target, stub, straight
        self.src_d, self.sink_d = src_d, sink_d
        self.src = self.sink = None
        self.new, self.old = True, []

    def buffers(self):
        return [b for b in (self.src, self.sink) if b is not None]

    def net_of(self, b):
        return f"{b.name}_{b.pin_out}"

    def chain(self):
        """[(inst, pin, net, driver End)]: each buffer input and the root
        inputs, on the net that drives them: stub, source, sink, roots."""
        net, driver, found = self.stub.net, self.stub.driver, []
        for b in self.buffers():
            found.append((b.name, b.pin_in, net, driver))
            net, driver = self.net_of(b), netlist.End("pin", b.name, b.pin_out, "out")
        return found + [(e.inst, e.pin, net, driver) for e in self.target.ends]


def _links(session, opts, spines, ports=False):
    """The Links of the -to spines [(Target, Stub, distance)] when
    -source_spine_stub_distance or -sink_spine_distance is given; [] else.
    Each buffer planned on the way between the stub and the root input: the
    source buffer's input pin -source_spine_stub_distance from the stub, the
    sink buffer's output pin -sink_spine_distance from the root input."""
    db, out = session.db, session.out
    src_d = _um(opts, "-source_spine_stub_distance")
    sink_d = _um(opts, "-sink_spine_distance")
    if (src_d is not None and not spines and not ports) or (sink_d is not None and not spines):
        raise HtreeError(USAGE, "connect_spine: -source_spine_stub_distance is for a -to spine "
                         "or port (a buffer that far from the stub) and -sink_spine_distance "
                         "for a -to spine (a buffer that far from its root input)")
    if not spines or (src_d is None and sink_d is None):
        return []
    links = [Link(t, s, d, src_d, sink_d) for t, s, d in spines]
    for k in links:
        need = (src_d or 0.0) + (sink_d or 0.0)
        if need >= k.straight - 1e-6:
            raise HtreeError(USAGE, f"connect_spine: {k.target.text}: the buffers would not "
                             f"fit: -source_spine_stub_distance + -sink_spine_distance "
                             f"({_num(round(need, 3))}) is not less than the way from stub "
                             f"{k.stub.name} to its root input ({_num(round(k.straight, 3))} "
                             f"um)")
    ref = opts.get("-ref_cell")
    if ref is None:
        raise HtreeError(USAGE, "connect_spine: -source_spine_stub_distance and "
                         "-sink_spine_distance need -ref_cell <lib_cell>: the cell of the "
                         "buffers (and -name <prefix>)")
    prefix = _prefix(opts)
    ref, cell, pin_in, pin_out = _cell(db, ref)
    snap, boundary = _snap(db), [float(v) for v in (db.design_row()["boundary"] or "").split()]
    w, h = cell["size_x"], cell["size_y"]
    taken = set(db.inst_names())
    nets = {r["net"] for r in db.connection_rows() if r["net"]} | set(netlist.spine_nets(db))
    old = {r["to_spine"]: r for r in db.spine_link_rows()}

    def place(orient, pin, frm, to, d):
        """Lower-left corner with the pin d (x + y) from frm on the way to to:
        the way that keeps the cell inside the boundary, else the pin."""
        off = _pin_offset(db, cell, pin, orient)
        spots = []
        for px, py in _ways(frm, to, d):
            x, y = snap(px - off[0] - w / 2), snap(py - off[1] - h / 2)
            cell_in = not boundary or rect_in_polygon(placed_bbox(w, h, orient, x, y), boundary)
            spots.append((not cell_in, not (boundary and point_in_polygon(px, py, boundary)),
                          len(spots), x, y))
        return min(spots)[3:]

    def name_for(base):
        name, n = base, 1
        while name in taken or f"{name}_{pin_out}" in nets:
            n += 1
            name = f"{base}_{n}"
        taken.add(name)
        return name

    for k in links:
        if _keep(db, k, old.get(k.target.spine)):
            continue
        base = f"{prefix}_" + re.sub(r"\W+", "_", k.target.spine).strip("_")
        orient = db.inst_row(k.stub.driver.inst)["orient"] or "N"
        start = _nearest(k.target.at, k.stub.points)
        if src_d is not None:    # its input pin src_d from the stub, towards the root input
            x, y = place(orient, pin_in, start, k.target.at, src_d)
            k.src = Buffer(None, name_for(base), ref, x, y, orient, pin_in, pin_out, None)
        if sink_d is not None:   # its output pin sink_d from the root input, towards the stub
            x, y = place(orient, pin_out, k.target.at, start, sink_d)
            k.sink = Buffer(None, name_for(f"{base}_sink"), ref, x, y, orient, pin_in,
                            pin_out, None)
    return links


def _keep(db, k, was):
    """Keep the buffers of the link before when this run asks for the same
    (the same stub, a source and a sink buffer as before) and they are still
    in the chain from the stub to the root input: True. Else the old ones
    still there are named in k.old (left on their nets), False."""
    if was is None:
        return False
    names = [n for n in (was["buffer"], was["sink_buffer"]) if n]
    there = [n for n in names if db.inst_row(n) is not None]
    want = (k.src_d is not None, k.sink_d is not None)
    if was["stub"] == k.stub.name and there == names and names and \
            (bool(was["buffer"]), bool(was["sink_buffer"])) == want:
        for which, n in (("src", was["buffer"]), ("sink", was["sink_buffer"])):
            if n:
                setattr(k, which, Buffer(None, n, db.inst_row(n)["ref_cell"], 0, 0, "N",
                                         netlist.signal_pin(db, n, "in"),
                                         netlist.signal_pin(db, n, "out"), None))
        if all(netlist.pin_net(db, inst, pin) == net for inst, pin, net, _ in k.chain()):
            k.new = False
            return True
        k.src = k.sink = None
    k.old = there
    return False


def _report_links(db, links, out):
    info("  links (stub -> source buffer -> sink buffer -> root input):", out)
    rows = []
    for k in links:
        cells = []
        for b, d, pin, frm in ((k.src, k.src_d, "pin_in", "stub"),
                               (k.sink, k.sink_d, "pin_out", "input")):
            if b is None:
                cells.append("-")
                continue
            px, py = objects.pin_centre(db, b.name, getattr(b, pin))
            if frm == "stub":
                sx, sy = _nearest((px, py), k.stub.points)
            else:
                sx, sy = k.target.at
            cells.append(f"{b.name} ({'as before, ' if not k.new else ''}"
                         f"{_num(round(abs(px - sx) + abs(py - sy), 3))} um from the {frm})")
        rows.append((k.target.text, k.stub.name, _num(round(k.straight, 3))) + tuple(cells))
    heads = ("To", "Stub", "Straight", "Source buffer", "Sink buffer")
    wide = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(heads)]
    for r in [heads] + rows:
        info("    " + "  ".join(c.ljust(w) for c, w in zip(r, wide)).rstrip(), out)
    for k in links:
        if k.old:
            warn(OLD_BUFFER, f"connect_spine: {k.target.text}: the buffer(s) "
                 f"{' '.join(k.old)} of its link before are left, on their nets "
                 f"(disconnect_pin takes their pins off)", out)


def _legalize(session, bufs):
    """Put the new buffers on placement sites; False when they are not."""
    if not bufs:
        return True
    out = session.out
    if not session.db.has_site_rows():
        warn(NOT_LEGAL, "connect_spine: no placement rows (read_def a DEF with ROW "
             "statements), so the buffers are on the manufacturing grid, not on sites: run "
             "legalize_placement on them once the rows are read", out)
        return False
    from core.commands import legalize_placement
    try:
        legalize_placement.run(session, ["-inst", " ".join(b.name for b in bufs)])
    except HtreeError as exc:
        warn(NOT_LEGAL, f"connect_spine: the buffers are made, but not put on sites: {exc}",
             out)
        return False
    return True


def _report_buffers(db, bufs, opts, out):
    where = f"the output pin {_num(float(opts['-distance']))} um from the port" \
        if "-distance" in opts else \
        f"the input pin {_num(float(opts['-source_spine_stub_distance']))} um from the stub"
    info(f"  buffers ({bufs[0].ref}, {where}, x + y; as placed):", out)
    rows = []
    for b in bufs:
        box = objects.inst_bbox(db, db.inst_row(b.name))
        px, py = objects.pin_centre(db, b.name, b.pin_out)
        ax, ay = objects.port_centre(db, b.port)
        rows.append((b.port, b.name, f"{b.name}/{b.pin_out} -> net {netlist.port_net(db, b.port)}",
                     "{" + f"{_num(round((box[0] + box[2]) / 2, 3))} "
                     f"{_num(round((box[1] + box[3]) / 2, 3))}" + "}",
                     _num(round(abs(px - ax) + abs(py - ay), 3))
                     + (f"  (its stub is {_num(round(b.near, 3))} um from the port: at the stub)"
                        if b.near is not None else "")))
    heads = ("Port", "Buffer", "Drives", "Centre", "From port")
    wide = [max(len(h), *(len(r[k]) for r in rows)) for k, h in enumerate(heads)]
    for r in [heads] + rows:
        info("    " + "  ".join(c.ljust(w) for c, w in zip(r, wide)).rstrip(), out)


def _nearest(at, points):
    """The point of the line through points, whose pieces run along x or y,
    nearest to at (x + y); the first of two as near."""
    x, y = at
    spots = [(min(max(x, min(x1, x2)), max(x1, x2)), min(max(y, min(y1, y2)), max(y1, y2)))
             for (x1, y1), (x2, y2) in zip(points, points[1:])]
    return min(spots, key=lambda p: abs(x - p[0]) + abs(y - p[1]))


def _distance(at, points):
    """The Manhattan distance from at to the nearest point of the line through
    points, whose pieces run along x or y."""
    px, py = _nearest(at, points)
    return abs(at[0] - px) + abs(at[1] - py)


def _ways(at, to, dist):
    """The points dist (x + y) from at on the two ways to `to` that run along
    x and along y: the longer leg first, then the shorter leg first. `to`
    itself when it is nearer than dist."""
    dx, dy = to[0] - at[0], to[1] - at[1]

    def walk(x_first):
        left, (x, y) = min(dist, abs(dx) + abs(dy)), at
        for along_x in (x_first, not x_first):
            step = min(left, abs(dx if along_x else dy))
            if along_x:
                x += math.copysign(step, dx)
            else:
                y += math.copysign(step, dy)
            left -= step
        return x, y

    x_first = abs(dx) >= abs(dy)
    return walk(x_first), walk(not x_first)


def _upstream(db, insts):
    """insts and every instance that drives one of them, through any number
    of cells (a cell is taken to pass each input to each output)."""
    direction = {}

    def is_out(inst, pin):
        if (inst, pin) not in direction:
            rows = objects._pin_rows(db, f"pin:{inst}/{pin}")
            direction[inst, pin] = rows is not None and \
                (rows[2]["direction"] or "").lower() == "out"
        return direction[inst, pin]

    pins = netlist.pins(db)
    driver = {net: inst for inst, mine in pins.items() for pin, net in mine.items()
              if is_out(inst, pin)}
    found, todo = set(insts), list(insts)
    while todo:
        inst = todo.pop()
        for pin, net in pins.get(inst, {}).items():
            up = driver.get(net)
            if up is not None and not is_out(inst, pin) and up not in found:
                found.add(up)
                todo.append(up)
    return found
