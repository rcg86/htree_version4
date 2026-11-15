"""connect_pin -from <pin | port> -to <pins> [-disconnect]: connect input pins
of instances to a driver, an output pin of an instance or an input port of the
design.

    connect_pin -from sp_L2_inv1/Y -to dummy1/A
    connect_pin -from port:top/clk -to {buf1/A buf2/A}
    connect_pin -from buf1/Y -to sp_L1_inv1/A -disconnect

The pins go onto the net of the driver: the net of the port, the spine net of
a spine cell's output, else a new net <inst>_<pin>. A pin that is on another
net already is an error; with -disconnect it is taken off that net first.
Only the netlist changes (get_db pin:<inst>/<pin> .net, write_logical), not
the routing.
"""

from core import netlist
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "connect_pin"
SUMMARY = "Connect input pins to an output pin or an input port (the netlist)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-to": "value", "-disconnect": "flag"}

USAGE = 1
BAD_DIRECTION = netlist.BAD_DIRECTION
CONNECTED = 253
ROUTED = 254


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-from" not in opts or "-to" not in opts:
        raise HtreeError(USAGE, "connect_pin: -from and -to are required. Usage: connect_pin "
                         "-from <pin | port> -to <pins> [-disconnect]")
    drivers = session.split_list(opts["-from"])
    words = list(dict.fromkeys(session.split_list(opts["-to"])))
    if len(drivers) != 1 or not words:
        raise HtreeError(USAGE, f"connect_pin: -from takes one pin or port and -to one or "
                         f"more pins, got -from '{opts['-from']}' -to '{opts['-to']}'")
    driver = netlist.resolve(db, drivers[0], NAME)
    if not driver.drives:
        raise HtreeError(BAD_DIRECTION, f"connect_pin: -from {driver.text} is "
                         f"{driver.what}: the driver must be an output pin of an instance "
                         f"or an input port of the design")
    ends = list(dict.fromkeys(netlist.resolve(db, w, NAME) for w in words))
    wrong = [f"{e.text} ({e.what})" for e in ends if not e.is_load]
    if wrong:
        raise HtreeError(BAD_DIRECTION, f"connect_pin: -to takes input pins of instances; "
                         f"not one: {', '.join(wrong)}")
    net, new = netlist.driver_net(db, driver, NAME)
    now = {e: netlist.pin_net(db, e.inst, e.pin) for e in ends}
    same = [e for e in ends if now[e] == net]
    taken = [e for e in ends if now[e] not in (None, net)]
    if taken and not opts["-disconnect"]:
        raise HtreeError(CONNECTED, "connect_pin: already connected: "
                         + ", ".join(f"{e.text} (net {now[e]})" for e in taken)
                         + "; -disconnect takes a pin off its net first")
    todo = [e for e in ends if e not in same]
    with db.conn:
        for e in taken:
            netlist.disconnect_load(db, e.inst, e.pin)
        spine = [e for e in todo if netlist.connect_load(db, e.inst, e.pin, net, driver)]

    info(f"connect_pin: net {net}{' (new)' if new and todo else ''}: {driver.text} -> "
         f"{' '.join(e.text for e in todo) or 'no new pin'}", out)
    if taken:
        info("  disconnected first: " + ", ".join(f"{e.text} from net {now[e]}"
                                                 for e in taken), out)
    if same:
        info(f"  on the net already: {' '.join(e.text for e in same)}", out)
    other = [e for e in todo if e not in spine]
    if other and net in netlist.spine_nets(db):
        info(f"  netlist only, route_net does not route to {'them' if len(other) > 1 else 'it'}"
             f" (it routes a spine net, not a leaf's, to the first input pin of each load): "
             f"{' '.join(e.text for e in other)}", out)
    elif other:
        info(f"  a net of no spine: route_net -net net:{net} -rule <rule> routes it", out)
    stale = {net: [e.text for e in spine]} if spine else {}
    for e in taken:
        stale.setdefault(now[e], []).append(e.text)
    warn_routed(db, stale, NAME, out)
    return tuple(e.handle for e in ends)


def warn_routed(db, nets, cmd, out):
    """Say which of nets {net: [pins that came or went]} have routing: it is
    as it was."""
    for net, pins in nets.items():
        count = netlist.routed(db, net)
        if count:
            warn(ROUTED, f"{cmd}: net {net} is routed ({count} wires and crossing boxes), and "
                 f"its routing is not changed for {' '.join(pins)}: route it again (route_net "
                 f"-net {net} -rule <rule>)", out)
