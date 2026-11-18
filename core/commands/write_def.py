"""write_def -output <file> [-sections {components specialnets nets}] [-overwrite]:
write what htree4 added to the design as DEF 5.8, for read_def (incremental),
in the form Innovus writes routed clock and power nets.

    write_def -output htree.def
    write_def -output comps.def -sections components

COMPONENTS: the instances (create_inst, create_spine -build), PLACED.
SPECIALNETS (default): the routing, as special wiring.
  - Each routed signal net (the spine nets, and the nets of no spine with a
    pin on them): its route_net wires and strap extensions, its stub's
    wires, and the route_pin straps and pin wires route_net connected
    (renamed to the net), each as + FIXED + RECT <layer> ( x1 y1 ) ( x2 y2 );
    then its vias as one + FIXED <bottom layer> 0 ( x y ) <via> with a NEW
    line per via. No pins and no USE: write_logical's script made the net
    and its connections.
  - Each power net with shapes of htree4 (VSS, VDD_SOC): route_pin straps
    and pin wires on it (its pins listed on the net line), the shields
    route_net -shield made, shield extensions and power links, each as
    + ROUTED + RECT; its vias as + ROUTED <layer> 0 ( x y ) <via>; then
    + USE as the design's port of the net has it (POWER, GROUND), else as
    its pins' library pin, else POWER.
  A shield is a shape of its power net, not a + SHIELD route: Innovus
  checks a + SHIELD against the signal net's + SHIELDNET (IMPDF-168).
  Crossing boxes are overlaps of wires already written and are not
  repeated. A via with no definition for its layers (assign_via_for_route)
  cannot be written and is counted. Straps still named SIGNAL are
  connected to no net and are left out (counted in the report).
NETS (only when asked for): the connections of the signal nets, with no
routing: ( <inst> <pin> ), a port as ( PIN <port> ), + USE CLOCK. For a
design whose nets were not made by write_logical's script.
"""

import os

from core import netlist, vias
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "write_def"
SUMMARY = "Write the instances, straps and routed nets as DEF (for defIn)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-output": "value", "-sections": "value", "-overwrite": "flag"}

USAGE = 1
EXISTS = 180
WRITE_FAILED = 181
LEFT_OUT = 182
NO_VIA_DEF = 183
SECTIONS = ["components", "specialnets", "nets"]
DEFAULT = ["components", "specialnets"]     # nets: the routing is in specialnets
STATUS = {"placed": "PLACED", "fixed": "FIXED", "cover": "COVER"}   # .place_status
SIGNAL = "SIGNAL"                # route_pin's placeholder net for signal straps
ORIENT = {"N": "N", "S": "S", "E": "E", "W": "W", "FN": "FN", "FS": "FS", "FE": "FE",
          "FW": "FW", "R0": "N", "R180": "S", "MX": "FS", "MY": "FN"}
# The net_wire kinds written: a signal net's own shapes, and those on a power net.
SIGNAL_KINDS = ("wire", "extension", "stub")
POWER_KINDS = ("shield", "stub_shield", "shield_ext", "pg_ext")


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-output" not in opts:
        raise HtreeError(USAGE, "write_def: -output is required. Usage: write_def -output "
                         "<file> [-sections {components specialnets nets}] [-overwrite]")
    sections = [w.lower() for w in session.split_list(opts.get("-sections",
                                                               " ".join(DEFAULT)))]
    bad = [w for w in sections if w not in SECTIONS]
    if bad or not sections:
        raise HtreeError(USAGE, f"write_def: -sections takes {' '.join(SECTIONS)}; got "
                         f"'{' '.join(bad) or opts['-sections']}'")
    path = opts["-output"]
    if os.path.exists(path) and not opts["-overwrite"]:
        raise HtreeError(EXISTS, f"write_def: '{path}' exists; use -overwrite to replace it")
    db = session.db
    text, counts, left, undefined = def_text(db, [s for s in SECTIONS if s in sections])
    try:
        with open(path, "w") as f:
            f.write(text)
    except OSError as exc:
        raise HtreeError(WRITE_FAILED, f"write_def: cannot write '{path}': {exc.strerror}")
    out = session.out
    info(f"DEF written to '{os.path.abspath(path)}': "
         + ", ".join(f"{s.upper()} {counts[s]}" for s in counts), out)
    if left:
        warn(LEFT_OUT, f"{left} route_pin strap(s) or pin wire(s) still on net {SIGNAL} (no "
             f"routed net connected them) are not written", out)
    if undefined:
        warn(NO_VIA_DEF, f"{undefined} via(s) with no via definition for their layers are "
             f"not written (assign_via_for_route gives them one)", out)
    return path


def def_text(db, sections):
    """(DEF text, {section: item count}, shapes left out, vias left out)."""
    design = db.design_row() if db.has_design() else None
    units = int(design["units"]) if design and design["units"] else 1000
    dbu = lambda v: int(round(float(v) * units))
    lines = ["VERSION 5.8 ;", 'DIVIDERCHAR "/" ;', 'BUSBITCHARS "[]" ;',
             f"DESIGN {design['name'] if design else 'htree4'} ;",
             f"UNITS DISTANCE MICRONS {units} ;", ""]
    if design and design["boundary"]:
        pts = design["boundary"].split()
        lines.insert(-1, "DIEAREA " + " ".join(f"( {dbu(pts[k])} {dbu(pts[k + 1])} )"
                                                for k in range(0, len(pts), 2)) + " ;")
    counts = {}
    if "components" in sections:
        rows = db.inst_rows()
        counts["components"] = len(rows)
        lines.append(f"COMPONENTS {len(rows)} ;")
        for r in rows:
            status = STATUS.get((r["status"] or "placed").lower(), "PLACED")
            lines.append(f"  - {r['name']} {r['ref_cell']} + {status} ( {dbu(r['x'])} "
                         f"{dbu(r['y'])} ) {ORIENT.get(r['orient'] or 'N', 'N')} ;")
        lines += ["END COMPONENTS", ""]
    undefined = 0
    if "specialnets" in sections:
        nets, undefined = special_nets(db)
        counts["specialnets"] = len(nets)
        lines.append(f"SPECIALNETS {len(nets)} ;")
        for net in nets:
            lines += _special_lines(net, dbu)
        lines += ["END SPECIALNETS", ""]
    if "nets" in sections:
        conns = net_connections(db)
        counts["nets"] = len(conns)
        lines.append(f"NETS {len(conns)} ;")
        for name, pins in conns.items():
            lines.append(f"- {name}" + "".join(f" ( {i} {p} )" for i, p in pins if p)
                         + " + USE CLOCK ;")
        lines += ["END NETS", ""]
    left = len(straps_on(db, SIGNAL))
    lines.append("END DESIGN")
    return "\n".join(lines) + "\n", counts, left, undefined


class SpecialNet:
    """A net of SPECIALNETS: its pins [(inst, pin)], shapes [(layer, rect)],
    vias [(bottom layer, x, y, definition)] (microns), status (FIXED for a
    signal net, ROUTED for a power net) and use (POWER / GROUND, None for a
    signal net)."""

    def __init__(self, name, status, use=None):
        self.name, self.status, self.use = name, status, use
        self.pins, self.shapes, self.vias = [], [], []


def special_nets(db):
    """([SpecialNet] with a shape or a via, signal nets first; the number of
    vias left out for want of a definition)."""
    spine = _spine_nets(db)
    signal = list(spine) + [n for n in netlist.plain_nets(db) if n not in spine]
    found = {n: SpecialNet(n, "FIXED") for n in signal}
    power = {}

    def power_net(net):
        if net not in power:
            power[net] = SpecialNet(net, "ROUTED")
        return power[net]

    for name in signal:                  # its wires and its stub's, then the straps
        rows = db.net_wire_rows(name) + db.stub_wire_rows(name)
        found[name].shapes += [(r["layer"], r["rect"]) for r in rows
                               if r["kind"] in SIGNAL_KINDS]
    for r in db.strap_rows():
        if r["net"] in found:
            found[r["net"]].shapes.append((r["layer"], r["rect"]))
        elif r["net"] != SIGNAL:
            power_net(r["net"]).shapes.append((r["layer"], r["rect"]))
    for r in db.pin_wire_rows():
        if r["net"] in found:
            found[r["net"]].shapes.append((r["layer"], r["rect"]))
        elif r["net"] != SIGNAL:
            p = power_net(r["net"])
            p.shapes.append((r["layer"], r["rect"]))
            p.pins.append((r["inst"], r["pin"]))
    for r in db.net_wire_rows():
        if r["kind"] in POWER_KINDS and r["shield_net"]:
            power_net(r["shield_net"]).shapes.append((r["layer"], r["rect"]))
    undefined = 0
    for v in vias.rows(db):
        if v["net"] == SIGNAL:
            continue                     # on a strap no routed net connected
        net = found.get(v["net"]) or power_net(v["net"])
        if not v["via_def"]:
            undefined += 1
            continue
        net.vias.append((v["bottom"], v["x"], v["y"], v["via_def"]))
    for net in power.values():
        net.use = _use(db, net)
    nets = [n for n in list(found.values()) + list(power.values()) if n.shapes or n.vias]
    return nets, undefined


def _use(db, net):
    """POWER or GROUND: as the design's port of the net, else its pins'
    library pin, else POWER."""
    for r in db.conn.execute("SELECT use FROM port WHERE COALESCE(NULLIF(net, ''), name) = ?",
                             (net.name,)):
        if r["use"] and r["use"].upper() in ("POWER", "GROUND"):
            return r["use"].upper()
    for inst, pin in net.pins:
        row = db.inst_row(inst)
        lp = db.lib_pin_row(row["ref_cell"], pin) if row is not None else None
        if lp is not None and (lp["use"] or "").upper() in ("POWER", "GROUND"):
            return lp["use"].upper()
    return "POWER"


def _special_lines(net, dbu):
    """The lines of a SpecialNet: one + <status> + RECT per shape, the vias
    as one + <status> <layer> 0 ( x y ) <via> and a NEW line each, + USE."""
    lines = [f"- {net.name}" + "".join(f" ( {i} {p} )" for i, p in net.pins)]
    for layer, rect in net.shapes:
        x1, y1, x2, y2 = (dbu(v) for v in rect.split())
        lines.append(f"  + {net.status} + RECT {layer} ( {x1} {y1} ) ( {x2} {y2} )")
    for k, (layer, x, y, via) in enumerate(net.vias):
        lines.append(f"  + {net.status} {layer} 0 ( {dbu(x)} {dbu(y)} ) {via}" if k == 0
                     else f"    NEW {layer} 0 ( {dbu(x)} {dbu(y)} ) {via}")
    if net.use:
        lines.append(f"  + USE {net.use}")
    lines.append(" ;")
    return lines


def net_connections(db):
    """{signal net: [(inst or PIN, pin)]}: the spine nets with their driver,
    loads and connect_pin loads, then the nets of no spine with their ends."""
    nets = _spine_nets(db)
    by_hand = {}                 # connect_pin loads that are not in a net's loads
    for r in db.connection_rows():
        if r["net"] in nets:
            by_hand.setdefault(r["net"], []).append((r["inst"], r["pin"]))
    conns_of = {}
    for name, row in nets.items():
        conns = [(row["driver"], _pin(db, row["driver"], "out"))]
        conns += [(load, _pin(db, load, "in")) for load in row["loads"].split()
                  if db.inst_row(load) is not None]
        conns_of[name] = conns + by_hand.get(name, [])
    for name in netlist.plain_nets(db):          # a port is ( PIN <port> )
        conns_of[name] = [("PIN", e.pin) if e.kind == "port" else (e.inst, e.pin)
                          for e in netlist.ends(db, name)]
    return conns_of


def straps_on(db, net):
    return [r for r in db.strap_rows() if r["net"] == net] + \
        [r for r in db.pin_wire_rows() if r["net"] == net]


def _spine_nets(db):
    """{net name: spine_net row} of every built spine."""
    return {r["name"]: r for s in db.spine_names()
            for r in db.spine_net_rows(db.spine_row(s)["id"])}


def _pin(db, inst, direction):
    """The signal input ('in') or output ('out') pin of an instance's cell."""
    row = db.inst_row(inst)
    return cell_pin(db, row["ref_cell"], direction) if row is not None else None


def cell_pin(db, ref_cell, direction):
    """The first signal input ('in') or output ('out') pin of a library cell."""
    cell = db.lib_cell_row(ref_cell)
    if cell is None:
        return None
    for p in db.lib_pin_names(cell["id"]):
        lp = db.lib_pin_row(cell["name"], p)
        if (lp["direction"] or "").lower().startswith(direction) and \
                (lp["use"] or "signal").lower() == "signal":
            return p
    return None
