"""Flylines: straight lines from the selected pins to what their nets
connect them to (View panel, Objects > Flyline).

A selected pin (pin:<inst>/<pin>), each connected pin of a selected instance
(inst:<name>) and a selected port of the design (port:<design>/<pin>) is
taken with its net (core/netlist.py):

    a driver (an output pin, an input port)   a line to every other pin and
                                              port on the net, and to the
                                              stub of a leaf's net
    any other pin or port                     a line to the driver of the
                                              net; to everything else on it
                                              when it has no driver

A line runs between the centres of the shapes of the pins (the centre of the
instance when the pin has none); a port is taken at the centre of its
shapes, a stub at the point of its line nearest to the pin. Power and ground
pins are on no net of the netlist, so they have no flylines.
"""

from core import netlist, objects


def flylines(db, handles):
    """[((x1, y1), (x2, y2))], model coordinates, for the selected handles:
    from the selected end to the other. A line between two selected ends
    comes once."""
    starts = []
    for handle in handles:
        kind = objects.obj_type(handle)
        name = handle.partition(":")[2]
        if kind == "inst":
            starts += [("pin", name, pin) for pin in netlist.pins(db).get(name, {})]
        elif kind in ("pin", "port"):
            starts.append((kind,) + tuple(name.partition("/")[::2]))
    lines, seen, at = [], set(), {}

    def point(end):
        if end not in at:
            at[end] = _point(db, end)
        return at[end]

    for start in dict.fromkeys(starts):
        kind, inst, pin = start
        net = netlist.pin_net(db, inst, pin) if kind == "pin" else _port_net(db, pin)
        here = point(start)
        if net is None or here is None:
            continue
        ends = netlist.ends(db, net)
        me = next((e for e in ends if tuple(e[:3]) == start), None)
        if me is None:
            continue
        if me.drives:
            others = [e for e in ends if e is not me]
        else:
            others = [e for e in ends if e.drives] or [e for e in ends if e is not me]
        for e in others:
            there, pair = point(tuple(e[:3])), frozenset((start, tuple(e[:3])))
            if there is not None and pair not in seen:
                seen.add(pair)
                lines.append((here, there))
        if me.drives:
            for s in netlist.stubs(db, net):
                v = [float(c) for c in s["points"].split()]
                lines.append((here, _nearest(here, list(zip(v[0::2], v[1::2])))))
    return lines


def _port_net(db, port):
    return netlist.port_net(db, port) if db.has_design() and db.port_row(port) else None


def _point(db, end):
    """Where a flyline meets (kind, inst or design, pin): the centre of its
    shapes; None for a port that is nowhere or a pin that is not there."""
    kind, inst, pin = end
    if kind == "pin":
        if objects._pin_rows(db, f"pin:{inst}/{pin}") is None:
            return None
        return objects.pin_centre(db, inst, pin)
    return objects.port_centre(db, pin)


def _nearest(p, pts):
    """The point of the line through pts nearest to p."""
    best = None
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        t = ((p[0] - x1) * dx + (p[1] - y1) * dy) / ((dx * dx + dy * dy) or 1.0)
        t = min(1.0, max(0.0, t))
        q = (x1 + t * dx, y1 + t * dy)
        d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
        if best is None or d < best[0]:
            best = d, q
    return best[1] if best else pts[0]
