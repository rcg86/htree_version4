"""connect_pin -from <pin | port> -to <pins | ports> [-disconnect] [-ref_cell
<lib_cell> [-distance <um>] [-name <prefix>]]: connect input pins of
instances, and output ports of the design, to a driver, an output pin of an
instance or an input port of the design.

    connect_pin -from sp_L2_inv1/Y -to dummy1/A
    connect_pin -from port:top/clk -to {buf1/A buf2/A}
    connect_pin -from buf1/Y -to sp_L1_inv1/A -disconnect
    connect_pin -from [get_db ports clk_in] -to [get_db ports clk_out] -ref_cell INV_RP

An output port of -to is driven through a buffer, always (a net does not
join two ports): an instance of -ref_cell, its output pin -distance um
(default 10) from the port on the way to the driver, x + y; its input goes on
the net of the driver, its output drives the port. The buffer is named
<prefix>_<port> (-name, default buf). A port driven already is an error;
with -disconnect its driver is taken off it first.

The pins go onto the net of the driver: the net of the port, the spine net of
a spine cell's output, else a new net <inst>_<pin>. A pin that is on another
net already is an error; with -disconnect it is taken off that net first.
Only the netlist changes (get_db pin:<inst>/<pin> .net, write_logical), not
the routing.
"""

import re

from core import netlist, objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "connect_pin"
SUMMARY = "Connect input pins to an output pin or an input port (the netlist)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-to": "value", "-disconnect": "flag", "-ref_cell": "value",
           "-distance": "value", "-name": "value"}

USAGE = 1
BAD_DIRECTION = netlist.BAD_DIRECTION
CONNECTED = 253
ROUTED = 254
PORT_DRIVEN = 308            # an output port of -to is driven already, or on the driver's net
DISTANCE = 10.0              # um from the port to the output pin of its buffer, by default


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-from" not in opts or "-to" not in opts:
        raise HtreeError(USAGE, "connect_pin: -from and -to are required. Usage: connect_pin "
                         "-from <pin | port> -to <pins | ports> [-disconnect] [-ref_cell "
                         "<lib_cell> [-distance <um>] [-name <prefix>]]")
    drivers = session.split_list(opts["-from"])
    words = list(dict.fromkeys(session.split_list(opts["-to"])))
    if not words:
        raise HtreeError(USAGE, f"connect_pin: -to is empty: no pin or port to connect (a "
                         f"get_db that matched nothing?), -from '{opts['-from']}'")
    if len(drivers) != 1:
        raise HtreeError(USAGE, f"connect_pin: -from takes one pin or port (one driver; -to "
                         f"takes many), got -from '{opts['-from']}'")
    driver = netlist.resolve(db, drivers[0], NAME)
    if not driver.drives:
        raise HtreeError(BAD_DIRECTION, f"connect_pin: -from {driver.text} is "
                         f"{driver.what}: the driver must be an output pin of an instance "
                         f"or an input port of the design")
    ends = list(dict.fromkeys(netlist.resolve(db, w, NAME) for w in words))
    ports = [e for e in ends if e.kind == "port" and e.direction == "out"]
    wrong = [f"{e.text} ({e.what})" for e in ends if not e.is_load and e not in ports]
    if wrong:
        raise HtreeError(BAD_DIRECTION, f"connect_pin: -to takes input pins of instances and "
                         f"output ports of the design; not one: {', '.join(wrong)}")
    net, new = netlist.driver_net(db, driver, NAME)
    bufs = _port_buffers(session, opts, driver, net, ports)   # checked before any change
    ends = [e for e in ends if e not in ports]
    now = {e: netlist.pin_net(db, e.inst, e.pin) for e in ends}
    same = [e for e in ends if now[e] == net]
    taken = [e for e in ends if now[e] not in (None, net)]
    if taken and not opts["-disconnect"]:
        raise HtreeError(CONNECTED, "connect_pin: already connected: "
                         + ", ".join(f"{e.text} (net {now[e]})" for e in taken)
                         + "; -disconnect takes a pin off its net first")
    todo = [e for e in ends if e not in same]
    if bufs:
        db.add_net_buffers([(b["name"], b["ref"], b["x"], b["y"], "N") for b in bufs],
                           [], [], [], [])
    with db.conn:
        for e in taken:
            netlist.disconnect_load(db, e.inst, e.pin)
        spine = [e for e in todo if netlist.connect_load(db, e.inst, e.pin, net, driver)]
        for b in bufs:           # the buffer between the driver and the port
            if b["old"] is not None:
                netlist.disconnect_port(db, b["old"].inst, b["old"].pin)
            spine += [netlist.End("pin", b["name"], b["pin_in"], "in")] if netlist.connect_load(
                db, b["name"], b["pin_in"], net, driver) else []
            netlist.connect_port(db, b["name"], b["pin_out"], b["port"].pin)
    legal = _legalize(session, [b["name"] for b in bufs])

    into = [e.text for e in todo] + [f"{b['name']}/{b['pin_in']}" for b in bufs]
    info(f"connect_pin: net {net}{' (new)' if new and into else ''}: {driver.text} -> "
         f"{' '.join(into) or 'no new pin'}", out)
    if bufs:
        _report_buffers(db, bufs, out)
        from core.commands.add_buffer_on_net import _check_place
        _check_place(db, [b["name"] for b in bufs], out, NAME)
        info("  Next: " + ("" if legal else "legalize_placement, ") + "route_pin -inst {"
             + " ".join(b["name"] for b in bufs) + "}, then route_net -net {" + " ".join(
                 [net] + [netlist.port_net(db, b["port"].pin) for b in bufs]) + "}", out)
    if taken:
        info("  disconnected first: " + ", ".join(f"{e.text} from net {now[e]}"
                                                 for e in taken), out)
    if same:
        info(f"  on the net already: {' '.join(e.text for e in same)}", out)
    other = [e for e in todo if e not in spine]
    if other and net in netlist.spine_nets(db):
        info(f"  netlist only, no wire yet; route_net routes the net to "
             f"{'them' if len(other) > 1 else 'it'} too (-force on a fixed net: to these "
             f"only, its wires kept): {' '.join(e.text for e in other)}", out)
    elif other:
        info(f"  a net of no spine: route_net -net net:{net} -rule <rule> routes it", out)
    stale = {net: [e.text for e in spine]} if spine else {}
    for e in taken:
        stale.setdefault(now[e], []).append(e.text)
    warn_routed(db, stale, NAME, out)
    # the pins of -to, and for each port of it its buffer
    return tuple(e.handle for e in ends) + tuple(f"inst:{b['name']}" for b in bufs)


def _port_buffers(session, opts, driver, net, ports):
    """The buffers to make for the output ports of -to: {name, ref, x, y,
    pin_in, pin_out, port, old (the End that drives the port now, taken off
    it: -disconnect)}. Every check is made here, before anything changes."""
    if not ports:
        return []
    from core.commands.connect_spine import _cell, _snap, _ways
    from core.commands.add_buffer_on_net import _pin_offset
    from core.placement import placed_bbox, point_in_polygon, rect_in_polygon
    db = session.db
    if "-ref_cell" not in opts:
        raise HtreeError(USAGE, f"connect_pin: -to {ports[0].text}: an output port is driven "
                         f"through a buffer, always: give -ref_cell <lib_cell> (and -distance "
                         f"<um>, default {_num(DISTANCE)}, -name <prefix>)")
    try:
        dist = float(opts.get("-distance", DISTANCE))
    except ValueError:
        dist = -1.0
    if not dist > 0 or dist == float("inf"):
        raise HtreeError(USAGE, f"connect_pin: -distance must be a distance in um above 0, "
                         f"got '{opts['-distance']}'")
    prefix = opts.get("-name", "buf")
    if not prefix or "/" in prefix or any(c.isspace() for c in prefix):
        raise HtreeError(USAGE, f"connect_pin: -name '{prefix}' must not be empty or contain "
                         f"'/' or spaces")
    try:
        ref, cell, pin_in, pin_out = _cell(db, opts["-ref_cell"])
    except HtreeError as exc:            # its text names connect_spine
        raise HtreeError(exc.msg_id, str(exc.text).replace("connect_spine:", f"{NAME}:"))
    at = objects.port_centre(db, driver.pin) if driver.kind == "port" else \
        objects.pin_centre(db, driver.inst, driver.pin)
    snap = _snap(db)
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()]
    w, h = cell["size_x"], cell["size_y"]
    off = _pin_offset(db, cell, pin_out, "N")
    taken = set(db.inst_names())
    made = []
    for e in ports:
        if netlist.port_net(db, e.pin) == net:
            raise HtreeError(PORT_DRIVEN, f"connect_pin: {e.text} is on net {net}, the net of "
                             f"{driver.text}: a buffer between them needs two nets")
        old = netlist.port_driver(db, e.pin)
        if old is not None and not opts["-disconnect"]:
            raise HtreeError(PORT_DRIVEN, f"connect_pin: {e.text} is driven already, by "
                             f"{old.text}; -disconnect takes it off first")
        spot = objects.port_centre(db, e.pin)
        if spot is None or at is None:
            raise HtreeError(PORT_DRIVEN, f"connect_pin: "
                             f"{e.text if spot is None else driver.text} has no shapes and "
                             f"no location: where its buffer goes is not known")
        base = f"{prefix}_" + re.sub(r"\W+", "_", e.pin).strip("_")
        name, k = base, 1
        while name in taken:
            k += 1
            name = f"{base}_{k}"
        taken.add(name)
        spots = []                       # inside the boundary first, as connect_spine
        for px, py in _ways(spot, at, dist):
            x, y = snap(px - off[0] - w / 2), snap(py - off[1] - h / 2)
            cell_in = not boundary or rect_in_polygon(placed_bbox(w, h, "N", x, y), boundary)
            spots.append((not cell_in, not (boundary and point_in_polygon(px, py, boundary)),
                          len(spots), x, y))
        x, y = min(spots)[3:]
        made.append({"name": name, "ref": ref, "x": x, "y": y, "pin_in": pin_in,
                     "pin_out": pin_out, "port": e, "old": old})
    return made


def _legalize(session, names):
    """Put the buffers on placement sites; False when they are not."""
    from core.commands.add_buffer_on_net import NOT_LEGAL
    if not names:
        return True
    if not session.db.has_site_rows():
        warn(NOT_LEGAL, "connect_pin: no placement rows (read_def a DEF with ROW statements), "
             "so the buffers are on the manufacturing grid, not on sites: run "
             "legalize_placement on them once the rows are read", session.out)
        return False
    from core.commands import legalize_placement
    try:
        legalize_placement.run(session, ["-inst", " ".join(names)])
    except HtreeError as exc:
        warn(NOT_LEGAL, f"connect_pin: the buffers are made, but not put on sites: {exc}",
             session.out)
        return False
    return True


def _report_buffers(db, bufs, out):
    info("  output ports, each driven through a buffer (its output pin from the port, x + y; "
         "as placed):", out)
    for b in bufs:
        box = objects.inst_bbox(db, db.inst_row(b["name"]))
        px, py = objects.pin_centre(db, b["name"], b["pin_out"])
        ax, ay = objects.port_centre(db, b["port"].pin)
        info(f"    {b['port'].text}: {b['name']} ({b['ref']}) at {{{_num(round((box[0] + box[2]) / 2, 3))} "
             f"{_num(round((box[1] + box[3]) / 2, 3))}}}, {_num(round(abs(px - ax) + abs(py - ay), 3))} "
             f"um; {b['name']}/{b['pin_out']} -> net {netlist.port_net(db, b['port'].pin)}"
             + (f" (taken off {b['old'].text})" if b["old"] is not None else ""), out)


def warn_routed(db, nets, cmd, out):
    """Say which of nets {net: [pins that came or went]} have routing: it is
    as it was."""
    for net, pins in nets.items():
        count = netlist.routed(db, net)
        if count:
            warn(ROUTED, f"{cmd}: net {net} is routed ({count} wires and crossing boxes), and "
                 f"its routing is not changed for {' '.join(pins)}: route it again (route_net "
                 f"-net {net} -rule <rule>)", out)
