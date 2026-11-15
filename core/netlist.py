"""The logical connections: the net of every instance pin.

A net is known by its driver, an output pin of an instance or an input port
of the design, and has a name the driver gives it:

    a port                      the net of the port (DEF PINS, + NET)
    the output of a spine cell  its spine net (<inst>_Y)
    another output pin          <inst>_<pin>

Where the net of a pin comes from, the last that applies:

    1. the root of a built spine: the spine spec's root_net on its input
    2. the built spines: the driver of a spine net (the cell's first signal
       output pin) and its loads (their first signal input pin), as route_net
       takes them
    3. the connection table: a load connected by hand (connect_pin), with
       its driver, or a pin disconnected by hand (net NULL); and an output
       pin that drives an output port of the design (connect_spine), on the
       net of the port, with itself as the driver

connect_pin and disconnect_pin change 3 and the loads of 2: a load that goes
onto a spine net by its first input pin becomes a load of the spine net, so
every command that reads the net (route_net, write_def, check_drc, get_db)
has it. A leaf's net keeps its stub as its only load there: more loads on it,
and loads on a pin that is not the cell's first input, are rows of 3.
"""

from collections import namedtuple

from core import objects
from core.messages import HtreeError

BAD_DIRECTION = 251
NET_NAME = 252
PORT = "port:"


class End(namedtuple("End", "kind inst pin direction")):
    """A pin of an instance (kind pin) or a port of the design (kind port:
    inst is the design, pin the port). direction as the database has it: in,
    out, inout, feedthru or empty."""

    @property
    def drives(self):
        """An output pin of an instance, or an input port of the design."""
        return self.direction == ("in" if self.kind == "port" else "out")

    @property
    def is_load(self):
        """An input pin of an instance."""
        return self.kind == "pin" and self.direction == "in"

    @property
    def what(self):
        """'an input pin', 'an output port', 'a pin without a direction'."""
        if not self.direction:
            return f"a {self.kind} without a direction"
        word = {"in": "input", "out": "output"}.get(self.direction, self.direction)
        return f"{'an' if word[0] in 'aeiou' else 'a'} {word} {self.kind}"

    @property
    def text(self):
        return f"{self.inst}/{self.pin}" if self.kind == "pin" else f"port {self.pin}"

    @property
    def handle(self):
        return f"{self.kind}:{self.inst}/{self.pin}"

    @property
    def key(self):
        """As the connection table names a driver."""
        return f"{self.inst}/{self.pin}" if self.kind == "pin" else PORT + self.pin


def resolve(db, word, cmd):
    """The End of a pin or port given as pin:<inst>/<pin>, <inst>/<pin>,
    port:<design>/<port> or <port>."""
    kind = objects.obj_type(word) if objects.is_handle(word) else None
    if kind == "pin" or (kind is None and "/" in word):
        rows = objects._pin_rows(db, word if kind else f"pin:{word}")
        if rows is not None:
            inst, _, lpin = rows
            return End("pin", inst["name"], lpin["name"], (lpin["direction"] or "").lower())
    if kind == "port":
        objects.check_exists(db, word)
        word = word.partition(":")[2].partition("/")[2]
    if kind in (None, "port") and db.has_design():
        row = db.port_row(word)
        if row is not None:
            return End("port", db.design_row()["name"], row["name"],
                       (row["direction"] or "").lower())
    if kind not in (None, "pin", "port"):
        raise HtreeError(objects.UNKNOWN_OBJECT, f"{cmd}: '{word}' is a {kind}: give a pin "
                         f"(pin:<inst>/<pin> or <inst>/<pin>) or a port of the design")
    raise HtreeError(objects.UNKNOWN_OBJECT, f"{cmd}: no pin or port '{word}' (get_db "
                     f"inst:<inst> .pins and get_db ports list them)")


def signal_pin(db, inst, direction):
    """The pin of inst a spine net goes to: the first signal input ('in') or
    output ('out') pin of its cell; None when it has none, or is no instance
    (a stub)."""
    from core.commands.write_def import _pin
    return _pin(db, inst, direction)


def _spines(db):
    """(spine row, root net, {stub names}, [spine_net rows]) of every built spine."""
    found = []
    for name in db.spine_names():
        spine = db.spine_row(name)
        spec = db.spine_spec_row(spine["spec"])
        root = (spec["root_net"] if spec is not None else None) or "net"
        found.append((spine, root, {s["name"] for s in db.spine_stub_rows(spine["id"])},
                      db.spine_net_rows(spine["id"])))
    return found


def roots(db):
    """{root instance of a built spine: the root net of its spec}."""
    return {m["inst"]: root for spine, root, _, _ in _spines(db)
            for m in db.spine_members(spine["id"]) if not m["driver"]}


def spine_nets(db):
    """{net name: (spine_net row, True when a leaf's: its load is a stub)}."""
    return {r["name"]: (r, bool(stubs & set(r["loads"].split())))
            for _, _, stubs, rows in _spines(db) for r in rows}


def pins(db):
    """{inst: {pin: net}} of every connected instance pin. Kept until the
    database changes: do not change the result."""
    stamp = (id(db.conn), db.conn.total_changes)
    if db.netlist is not None and db.netlist[0] == stamp:
        return db.netlist[1]
    found, terminal = {}, {}

    def put(inst, direction, net, pin=None):
        if pin is None:
            if (inst, direction) not in terminal:
                terminal[inst, direction] = signal_pin(db, inst, direction)
            pin = terminal[inst, direction]
        if pin:
            found.setdefault(inst, {})[pin] = net

    for inst, root in roots(db).items():
        put(inst, "in", root)
    for _, _, stubs, rows in _spines(db):
        for r in rows:
            put(r["driver"], "out", r["name"])
            for load in r["loads"].split():
                if load not in stubs:
                    put(load, "in", r["name"])
    for r in db.connection_rows():
        if r["net"] is None:
            found.get(r["inst"], {}).pop(r["pin"], None)
            continue
        put(r["inst"], None, r["net"], r["pin"])
        if r["driver"] and not r["driver"].startswith(PORT):
            inst, _, pin = r["driver"].partition("/")
            put(inst, None, r["net"], pin)
    found = {inst: mine for inst, mine in found.items() if mine}
    db.netlist = (stamp, found)
    return found


def pin_net(db, inst, pin):
    """The net of an instance pin, or None."""
    return pins(db).get(inst, {}).get(pin)


def by_net(db):
    """{net: [(inst, pin)]} of every connected instance pin. Kept as pins()
    is: do not change the result."""
    pins(db)
    if len(db.netlist) == 2:
        nets = {}
        for inst, mine in db.netlist[1].items():
            for pin, net in mine.items():
                nets.setdefault(net, []).append((inst, pin))
        owner = {r["name"]: spine["name"] for spine, _, _, rows in _spines(db) for r in rows}
        db.netlist += (nets, owner)
    return db.netlist[2]


def net_handle(db, net):
    """The object of a net: spine_net:<spine>/<net> for a net of a built
    spine, net:<net> for any other (a port's, connect_pin's)."""
    by_net(db)
    spine = db.netlist[3].get(net)
    return f"net:{net}" if spine is None else f"spine_net:{spine}/{net}"


def ends(db, net):
    """[End] of what is on net: its instance pins, and the port of the
    design whose net it is. Empty when there is no such net."""
    found = []
    for inst, pin in by_net(db).get(net, []):
        rows = objects._pin_rows(db, f"pin:{inst}/{pin}")
        if rows is not None:
            found.append(End("pin", inst, pin, (rows[2]["direction"] or "").lower()))
    port = db.port_of_net(net) if db.has_design() else None
    if port is not None:
        found.append(End("port", db.design_row()["name"], port["name"],
                         (port["direction"] or "").lower()))
    return found


def port_net(db, port):
    """The net of a port of the design: its DEF net, else its own name."""
    row = db.port_row(port)
    return row["net"] or row["name"]


def driver_net(db, end, cmd):
    """(the net an output pin or port drives, True when it is a new net:
    nothing is on it yet, and it is no net of the design or of a spine)."""
    if end.kind == "port":
        return port_net(db, end.pin), False
    net = pin_net(db, end.inst, end.pin)
    if net is not None:
        return net, False
    net = f"{end.inst}_{end.pin}"
    taken = set(spine_nets(db)) | set(roots(db).values())
    taken |= {r["net"] for r in db.connection_rows() if r["net"]}
    if net in taken or (db.has_design() and db.port_of_net(net) is not None):
        raise HtreeError(NET_NAME, f"{cmd}: the net of {end.text} would be '{net}', the name "
                         f"of another net (of a port, a spine or connect_pin)")
    return net, True


def loads(db, net, driver=None):
    """[(inst, pin)] on net, the driver's pin (an End) left out."""
    mine = (driver.inst, driver.pin) if driver is not None and driver.kind == "pin" else None
    return [(inst, pin) for inst, of in pins(db).items() for pin, n in of.items()
            if n == net and (inst, pin) != mine]


def stubs(db, net):
    """The spine_stub rows a leaf's net drives; none for any other net."""
    for spine, _, names, rows in _spines(db):
        for r in rows:
            if r["name"] == net:
                mine = names & set(r["loads"].split())
                return [s for s in db.spine_stub_rows(spine["id"]) if s["name"] in mine]
    return []


def new_nets(db):
    """The nets connect_pin made that the design does not have: driven by an
    instance pin, not a spine net and not the net of a port. In the order
    they were made."""
    spine = spine_nets(db)
    port = set(port_nets(db))
    return list(dict.fromkeys(r["net"] for r in db.connection_rows()
                              if r["net"] and r["net"] not in spine and r["net"] not in port
                              and not (r["driver"] or PORT).startswith(PORT)))


def port_nets(db):
    """{net: port} of the port nets with a pin on them: the loads connect_pin
    put on the net of an input port, the pin that drives an output port."""
    found = {}
    for r in db.connection_rows():
        if r["net"] and (r["driver"] or "").startswith(PORT):
            found[r["net"]] = r["driver"][len(PORT):]
        elif r["net"] and r["net"] not in found and db.has_design():
            port = db.port_of_net(r["net"])
            if port is not None:
                found[r["net"]] = port["name"]
    return found


def port_driver(db, port):
    """The output pin (an End) that drives the net of a port of the design,
    or None."""
    return next((e for e in ends(db, port_net(db, port)) if e.kind == "pin" and e.drives),
                None)


def drives_port(db, inst, pin):
    """The name of the port an output pin was put on the net of
    (connect_port), or None."""
    row = db.conn.execute("SELECT net FROM connection WHERE inst = ? AND pin = ? AND "
                          "driver = ?", (inst, pin, f"{inst}/{pin}")).fetchone()
    port = db.port_of_net(row["net"]) if row is not None and db.has_design() else None
    return None if port is None else port["name"]


def routed(db, net):
    """The number of route_net / route_final_stub wires of net."""
    return len(db.net_wire_rows(net))


def plain_nets(db):
    """The names of the nets of no spine (net:<name>) with a pin on them: a
    port's, connect_pin's, add_buffer_on_net's."""
    spine = spine_nets(db)
    return [n for n in by_net(db) if n not in spine]


def signal_nets(db):
    """The names of the nets that carry a signal: those of the built spines
    and the nets of no spine. A strap or pin wire named after one of them is
    part of its route (route_net); any other name is a power net."""
    return set(spine_nets(db)) | set(by_net(db))


# -- changes: no commit here, the command's transaction (with db.conn) ------------

def disconnect_load(db, inst, pin):
    """Take a load pin off its net; it is on no net afterwards."""
    ex = db.conn.execute
    ex("DELETE FROM connection WHERE inst = ? AND pin = ?", (inst, pin))
    if pin == signal_pin(db, inst, "in"):
        for _, _, stubs, rows in _spines(db):
            for r in rows:
                names = r["loads"].split()
                if inst in names and inst not in stubs:
                    ex("UPDATE spine_net SET loads = ? WHERE id = ?",
                       (" ".join(n for n in names if n != inst), r["id"]))
        if inst in roots(db):                 # else the root net of its spec comes back
            ex("INSERT INTO connection (inst, pin, net, driver) VALUES (?, ?, NULL, NULL)",
               (inst, pin))


def connect_port(db, inst, pin, port):
    """Put an output pin, on no net, onto the net of an output port of the
    design: it drives the port."""
    db.conn.execute("DELETE FROM connection WHERE inst = ? AND pin = ?", (inst, pin))
    db.conn.execute("INSERT INTO connection (inst, pin, net, driver) VALUES (?, ?, ?, ?)",
                    (inst, pin, port_net(db, port), f"{inst}/{pin}"))


def disconnect_port(db, inst, pin):
    """Take an output pin off the net of the port it drives (connect_port)."""
    db.conn.execute("DELETE FROM connection WHERE inst = ? AND pin = ? AND driver = ?",
                    (inst, pin, f"{inst}/{pin}"))


def connect_load(db, inst, pin, net, driver):
    """Put a load pin, on no net (disconnect_load), onto the net of driver (an
    End). Returns True when it became a load of a spine net: route_net routes
    to it."""
    ex = db.conn.execute
    ex("DELETE FROM connection WHERE inst = ? AND pin = ?", (inst, pin))
    row, leaf = spine_nets(db).get(net, (None, False))
    if row is not None and not leaf and pin == signal_pin(db, inst, "in") and \
            driver.key == f"{row['driver']}/{signal_pin(db, row['driver'], 'out')}":
        ex("UPDATE spine_net SET loads = ? WHERE id = ?",
           (" ".join(row["loads"].split() + [inst]), row["id"]))
        return True
    ex("INSERT INTO connection (inst, pin, net, driver) VALUES (?, ?, ?, ?)",
       (inst, pin, net, driver.key))
    return False
