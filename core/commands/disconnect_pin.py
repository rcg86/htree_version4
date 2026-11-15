"""disconnect_pin -pin <pins | ports>: take pins off their nets.

    disconnect_pin -pin sp_L3_inv2/A
    disconnect_pin -pin port:top/clk

An input pin of an instance is taken off its net. A driver (an output pin of
an instance or an input port of the design) loses every load: all the pins on
its net are taken off it. An output pin that drives an output port (the
buffer connect_spine made) is taken off the net of the port, with any loads.
Only the netlist changes (get_db pin:<inst>/<pin> .net, write_logical), not
the routing.
"""

from core import netlist
from core.commands.connect_pin import USAGE, warn_routed
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "disconnect_pin"
SUMMARY = "Take pins off their nets (the netlist)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-pin": "value"}

NOT_CONNECTED = 255


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    words = list(dict.fromkeys(session.split_list(opts.get("-pin", ""))))
    if not words:
        raise HtreeError(USAGE, "disconnect_pin: -pin is required. Usage: disconnect_pin "
                         "-pin <pins | ports>")
    ends = list(dict.fromkeys(netlist.resolve(db, w, NAME) for w in words))
    done, stale, idle = [], {}, []
    with db.conn:
        for e in ends:
            driver, net, off, port = e.drives, None, [], None
            if driver:
                net = netlist.port_net(db, e.pin) if e.kind == "port" else \
                    netlist.pin_net(db, e.inst, e.pin)
                off = netlist.loads(db, net, e) if net is not None else []
                port = netlist.drives_port(db, e.inst, e.pin) if e.kind == "pin" else None
            elif e.is_load:
                net = netlist.pin_net(db, e.inst, e.pin)
                off = [(e.inst, e.pin)] if net is not None else []
            if port is not None:              # an output pin that drives a port
                for inst, pin in off:
                    netlist.disconnect_load(db, inst, pin)
                netlist.disconnect_port(db, e.inst, e.pin)
                names = [f"{inst}/{pin}" for inst, pin in off]
                done += [e.handle] + [f"pin:{n}" for n in names]
                stale.setdefault(net, []).extend([e.text] + names)
                info(f"disconnect_pin: net {net}: {e.text} taken off, it drove port {port}"
                     + (f" and {len(off)} load(s), taken off as well: {' '.join(names)}"
                        if off else ""), out)
                continue
            if not off:
                idle.append(e)
                continue
            for inst, pin in off:
                netlist.disconnect_load(db, inst, pin)
            names = [f"{inst}/{pin}" for inst, pin in off]
            done += [f"pin:{n}" for n in names]
            stale.setdefault(net, []).extend(names)
            info(f"disconnect_pin: net {net}: {e.text} drives it, {len(off)} load(s) taken "
                 f"off: {' '.join(names)}" if driver else
                 f"disconnect_pin: net {net}: {e.text} taken off", out)
    if idle:
        warn(NOT_CONNECTED, f"disconnect_pin: nothing to disconnect on "
             f"{', '.join(e.text for e in idle)}: "
             + ("it is" if len(idle) == 1 else "they are") + " on no net, or "
             "drive" + ("s" if len(idle) == 1 else "") + " a net without a load pin", out)
    warn_routed(db, stale, NAME, out)
    return tuple(done)
