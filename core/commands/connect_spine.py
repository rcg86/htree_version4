"""connect_spine -from <spine> -to <spines | pins | ports> [-ref_name
<lib_cell> -distance <um> [-name <prefix>]]: connect the inputs of spines,
input pins of instances and output ports of the design to the nearest stub
of a built spine.

    connect_spine -from sp -to sp2
    connect_spine -from spine:sp -to {sp2 sp3 buf1/A}
    connect_spine -from sp -to q -ref_name INV_RP -distance 10 -name out

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
# -ref_cell: -ref_name, as the other commands call it.
OPTIONS = {"-from": "value", "-to": "value", "-ref_name": "value", "-ref_cell": "value",
           "-distance": "value", "-name": "value"}

USAGE = 1
BAD_DIRECTION = netlist.BAD_DIRECTION
NO_STUB = 267
LOOP = 268
PORT = 269


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-from" not in opts or "-to" not in opts:
        raise HtreeError(USAGE, "connect_spine: -from and -to are required. Usage: "
                         "connect_spine -from <spine> -to <spines | pins | ports> "
                         "[-ref_name <lib_cell> -distance <um> [-name <prefix>]]")
    sources = session.split_list(opts["-from"])
    words = list(dict.fromkeys(session.split_list(opts["-to"])))
    if len(sources) != 1 or not words:
        raise HtreeError(USAGE, f"connect_spine: -from takes one spine and -to one or more "
                         f"spines, pins or ports, got -from '{opts['-from']}' -to "
                         f"'{opts['-to']}'")
    spine = _spine(db, sources[0], "-from")
    stubs = _stubs(db, spine)
    targets = list({t.text: t for t in (_target(db, w, spine) for w in words)}.values())
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

    ends = list(dict.fromkeys(e for t, _, _ in picks for e in t.ends))
    stub_of = {e: s for t, s, _ in picks for e in t.ends}
    now = {e: netlist.pin_net(db, e.inst, e.pin) for e in ends}
    same = [e for e in ends if now[e] == stub_of[e].net]
    taken = [e for e in ends if now[e] not in (None, stub_of[e].net)]
    todo = [e for e in ends if e not in same]
    if bufs:
        db.add_net_buffers([(b.name, b.ref, b.x, b.y, b.orient) for b in bufs], [], [], [], [])
    with db.conn:
        for b in bufs:
            netlist.connect_port(db, b.name, b.pin_out, b.port)
        for e in taken:
            netlist.disconnect_load(db, e.inst, e.pin)
        for e in todo:
            netlist.connect_load(db, e.inst, e.pin, stub_of[e].net, stub_of[e].driver)
    legal = _legalize(session, bufs)

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
    if todo:
        info("  netlist only: no wire is made, and route_net does not route a leaf's net "
             "to these pins" + (", nor the net of an output port" if bufs else ""), out)
    if bufs:
        _check_place(db, [b.name for b in bufs], out, NAME)
        info("  Next: " + ("" if legal else "legalize_placement, ") + "route_pin -inst {"
             + " ".join(b.name for b in bufs) + "}", out)
    # The wires of a net a pin was taken off still go to the pin. Not so those
    # of a leaf's net, the stub's too: they go to the stub only.
    leaf = {net for net, (_, is_leaf) in netlist.spine_nets(db).items() if is_leaf}
    stale = {}
    for e in taken:
        if now[e] not in leaf:
            stale.setdefault(now[e], []).append(e.text)
    warn_routed(db, stale, NAME, out)
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

    def __init__(self, db, text, ends, port=None):
        self.text, self.ends, self.port = text, ends, port
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
        return Target(db, f"spine {spine['name']}", ends)
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
    ref = opts.get("-ref_name", opts.get("-ref_cell"))
    if ref is None or "-distance" not in opts:
        raise HtreeError(USAGE, f"connect_spine: -to {ports[0][0].text}: a port is driven "
                         f"through a buffer, give -ref_name <lib_cell> and -distance <um> "
                         f"(and -name <prefix>)")
    if "-ref_name" in opts and "-ref_cell" in opts:
        raise HtreeError(USAGE, "connect_spine: give -ref_name or -ref_cell, not both")
    try:
        dist = float(opts["-distance"])
    except ValueError:
        dist = None
    if dist is None or not math.isfinite(dist) or dist <= 0:
        raise HtreeError(USAGE, f"connect_spine: -distance must be a distance in um above 0, "
                         f"got '{opts['-distance']}'")
    prefix = opts.get("-name", "buf")
    if not prefix or "/" in prefix or any(c.isspace() for c in prefix):
        raise HtreeError(USAGE, f"connect_spine: -name '{prefix}' must not be empty or "
                         f"contain '/' or spaces")
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

    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    snap = (lambda v: round(round(v / grid) * grid, 6)) if grid else (lambda v: round(v, 6))
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()]
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
        off = _pin_offset(db, cell, pin_out, orient)
        to = _nearest(t.at, stub.points)
        # the output pin of the buffer goes dist from the port, on the way to
        # the stub: the way that keeps the cell inside the boundary, else the
        # one that keeps the pin inside it (a way along the edge of the die:
        # legalize_placement takes the cell off the edge), else the first
        spots = []
        for px, py in _ways(t.at, to, dist):
            x, y = snap(px - off[0] - w / 2), snap(py - off[1] - h / 2)
            cell_in = not boundary or rect_in_polygon(placed_bbox(w, h, orient, x, y), boundary)
            spots.append((not cell_in, not (boundary and point_in_polygon(px, py, boundary)),
                          len(spots), x, y))
        x, y = min(spots)[3:]
        away = abs(to[0] - t.at[0]) + abs(to[1] - t.at[1])
        made.append(Buffer(t.port, name, ref, x, y, orient, pin_in, pin_out,
                           away if away < dist else None))
        t.ends = [netlist.End("pin", name, pin_in, "in")]
    return made


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
    info(f"  buffers ({bufs[0].ref}, the output pin {_num(float(opts['-distance']))} um from "
         f"the port, x + y; as placed):", out)
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
