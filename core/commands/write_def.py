"""write_def -output <file> [-sections {components specialnets nets}] [-overwrite]:
write what htree4 added to the design as DEF 5.8, for defIn (incremental).

    write_def -output htree.def
    write_def -output comps.def -sections components

COMPONENTS: the instances (create_inst, create_spine -build), PLACED.
SPECIALNETS: route_pin straps and pin wires of power nets (not a signal net),
as stripes. NETS: the spine nets with their pin connections, and every shape
shorted to them: route_net wires and strap extensions, and the straps and pin
wires route_net connected (renamed to the net). Each shape is written as a
RECT, exactly as stored. Crossing boxes are overlaps of wires already written,
so they are not repeated. Straps still named SIGNAL are connected to no net
and are left out (counted in the report).
"""

import os

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
SECTIONS = ["components", "specialnets", "nets"]
STATUS = {"placed": "PLACED", "fixed": "FIXED", "cover": "COVER"}   # .place_status
SIGNAL = "SIGNAL"                # route_pin's placeholder net for signal straps
ORIENT = {"N": "N", "S": "S", "E": "E", "W": "W", "FN": "FN", "FS": "FS", "FE": "FE",
          "FW": "FW", "R0": "N", "R180": "S", "MX": "FS", "MY": "FN"}


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-output" not in opts:
        raise HtreeError(USAGE, "write_def: -output is required. Usage: write_def -output "
                         "<file> [-sections {components specialnets nets}] [-overwrite]")
    sections = [w.lower() for w in session.split_list(opts.get("-sections",
                                                               " ".join(SECTIONS)))]
    bad = [w for w in sections if w not in SECTIONS]
    if bad or not sections:
        raise HtreeError(USAGE, f"write_def: -sections takes {' '.join(SECTIONS)}; got "
                         f"'{' '.join(bad) or opts['-sections']}'")
    path = opts["-output"]
    if os.path.exists(path) and not opts["-overwrite"]:
        raise HtreeError(EXISTS, f"write_def: '{path}' exists; use -overwrite to replace it")
    db = session.db
    text, counts, left = def_text(db, [s for s in SECTIONS if s in sections])
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
    return path


def def_text(db, sections):
    """(DEF text, {section: item count}, shapes left out)."""
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
    signal_nets = set(_spine_nets(db))
    if "specialnets" in sections:
        power = {}                   # net -> [(layer, rect, kind)], [(inst, pin)]
        for r in db.strap_rows():
            if r["net"] != SIGNAL and r["net"] not in signal_nets:
                power.setdefault(r["net"], ([], []))[0].append((r["layer"], r["rect"]))
        for r in db.pin_wire_rows():
            if r["net"] != SIGNAL and r["net"] not in signal_nets:
                shapes, pins = power.setdefault(r["net"], ([], []))
                shapes.append((r["layer"], r["rect"]))
                pins.append((r["inst"], r["pin"]))
        shields = {}             # power net -> [(signal net, layer, rect)]
        for r in db.net_wire_rows():
            if r["kind"] in ("shield", "stub_shield"):
                shields.setdefault(r["shield_net"], []).append((r["net"], r["layer"], r["rect"]))
                power.setdefault(r["shield_net"], ([], []))
            elif r["kind"] in ("shield_ext", "pg_ext"):   # power straps lengthened
                power.setdefault(r["shield_net"], ([], []))[0].append((r["layer"], r["rect"]))
        counts["specialnets"] = len(power)
        lines.append(f"SPECIALNETS {len(power)} ;")
        for net, (shapes, pins) in power.items():
            lines.append(f"  - {net}" + "".join(f" ( {i} {p} )" for i, p in pins))
            for k, (layer, rect) in enumerate(shapes):
                w, a, b = _path(rect, dbu)
                lines.append(f"    {'+ ROUTED' if k == 0 else 'NEW'} {layer} {w} + SHAPE STRIPE "
                             f"( {a[0]} {a[1]} ) ( {b[0]} {b[1]} )")
            for signal, layer, rect in shields.get(net, []):   # route_net -shield
                w, a, b = _path(rect, dbu)
                lines.append(f"    + SHIELD {signal} {layer} {w} ( {a[0]} {a[1]} ) "
                             f"( {b[0]} {b[1]} )")
            lines.append("  ;")
        lines += ["END SPECIALNETS", ""]
    if "nets" in sections:
        nets = _spine_nets(db)
        counts["nets"] = len(nets)
        lines.append(f"NETS {len(nets)} ;")
        straps = {}
        for r in db.strap_rows():
            straps.setdefault(r["net"], []).append((r["layer"], r["rect"]))
        for r in db.pin_wire_rows():
            straps.setdefault(r["net"], []).append((r["layer"], r["rect"]))
        for name, row in nets.items():
            conns = [(row["driver"], _pin(db, row["driver"], "out"))]
            conns += [(load, _pin(db, load, "in")) for load in row["loads"].split()
                      if db.inst_row(load) is not None]
            rows = db.net_wire_rows(name)
            shield_nets = dict.fromkeys(r["shield_net"] for r in rows if r["kind"] == "shield")
            lines.append(f"  - {name}" + "".join(f" ( {i} {p} )" for i, p in conns if p)
                         + "".join(f" + SHIELDNET {n}" for n in shield_nets) + " + USE CLOCK")
            shapes = [(r["layer"], r["rect"]) for r in rows
                      if r["kind"] in ("wire", "extension", "stub")] + straps.get(name, [])
            for k, (layer, rect) in enumerate(shapes):
                x1, y1, x2, y2 = (dbu(v) for v in rect.split())
                lines.append(f"    {'+ ROUTED' if k == 0 else 'NEW'} {layer} ( {x1} {y1} ) "
                             f"RECT ( 0 0 {x2 - x1} {y2 - y1} )")
            lines.append("  ;")
        lines += ["END NETS", ""]
    left = len(straps_on(db, SIGNAL))
    lines.append("END DESIGN")
    return "\n".join(lines) + "\n", counts, left


def _path(rect, dbu):
    """(width, start, end) of a rect as a wire along its long side."""
    x1, y1, x2, y2 = (dbu(v) for v in rect.split())
    if x2 - x1 >= y2 - y1:
        return y2 - y1, (x1, (y1 + y2) // 2), (x2, (y1 + y2) // 2)
    return x2 - x1, ((x1 + x2) // 2, y1), ((x1 + x2) // 2, y2)


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
    cell = db.lib_cell_row(row["ref_cell"]) if row is not None else None
    if cell is None:
        return None
    for p in db.lib_pin_names(cell["id"]):
        lp = db.lib_pin_row(cell["name"], p)
        if (lp["direction"] or "").lower().startswith(direction) and \
                (lp["use"] or "signal").lower() == "signal":
            return p
    return None
