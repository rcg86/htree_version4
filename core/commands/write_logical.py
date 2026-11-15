"""write_logical -output <file> [-overwrite]: write the logical changes htree4
made to the design as an Innovus (Stylus) script to source, in the form
htree version 3 dumped them:

    create_net -name <net>
    create_inst -cell <cell> -name <inst>
    place_inst <inst> <x> <y> <orientation>
    connect <inst>/<pin> -net <net>

Step 1 creates every spine net (the output net of each spine cell) and the
nets connect_pin made. Then, level by level from the root, each cell is
created, placed (lower-left corner, microns) and its pins connected as the
netlist has them (core/netlist.py: the spine, then connect_pin and
disconnect_pin). A spine's root takes the spec's root_net, which must already
exist in the design, as the net of a port must. Instances that belong to no
spine (create_inst) are created and placed last, with the connections
connect_pin gave them.
"""

import os

from core.db import _num
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "write_logical"
SUMMARY = "Write the new nets, instances and connections as an Innovus script"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-output": "value", "-overwrite": "flag"}

USAGE = 1
EXISTS = 185
WRITE_FAILED = 186
# DEF orientation -> Innovus orientation
ORIENT = {"N": "R0", "S": "R180", "W": "R90", "E": "R270", "FN": "MY", "FS": "MX",
          "FW": "MX90", "FE": "MY90"}


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-output" not in opts:
        raise HtreeError(USAGE, "write_logical: -output is required. Usage: write_logical "
                         "-output <file> [-overwrite]")
    path = opts["-output"]
    if os.path.exists(path) and not opts["-overwrite"]:
        raise HtreeError(EXISTS, f"write_logical: '{path}' exists; use -overwrite to replace "
                         f"it")
    text, nets, insts = logical_text(session.db)
    try:
        with open(path, "w") as f:
            f.write(text)
    except OSError as exc:
        raise HtreeError(WRITE_FAILED, f"write_logical: cannot write '{path}': "
                         f"{exc.strerror}")
    info(f"Logical changes written to '{os.path.abspath(path)}': {nets} nets, {insts} "
         f"instances", session.out)
    return path


def logical_text(db):
    """(script text, nets created, instances created)."""
    from core import netlist
    lines = ["# htree4 logical changes: Innovus script, source it to reproduce them.", ""]

    def sep(title):
        lines.extend(["# " + "=" * 60, f"# {title}", "# " + "=" * 60, ""])

    spines = [db.spine_row(s) for s in db.spine_names()]
    nets = [r for s in spines for r in db.spine_net_rows(s["id"])]
    sep("Step 1: Create all nets")
    for s in spines:
        spec = db.spine_spec_row(s["spec"])
        root = (spec["root_net"] if spec is not None else None) or "net"
        lines.append(f"# spine {s['name']}: root net {root} must exist in the design")
        for r in db.spine_net_rows(s["id"]):
            lines.append(f"create_net -name {_word(r['name'])}")
        lines.append("")
    made = netlist.new_nets(db)
    ports = netlist.port_nets(db)
    if made or ports:
        for net, port in ports.items():
            lines.append(f"# connect_pin: net {net} of port {port} must exist in the design")
        lines += [f"create_net -name {_word(net)}" for net in made] + [""]

    pins = netlist.pins(db)          # inst -> {pin: net}
    members = {}                     # inst -> (spine, level)
    for s in spines:
        for m in db.spine_members(s["id"]):
            members[m["inst"]] = (s["name"], m["level"])

    levels = []                      # (spine, level) in build order, root level first
    for inst, key in members.items():
        if key not in levels:
            levels.append(key)
    count = 0
    for step, (spine, level) in enumerate(levels, start=2):
        sep(f"Step {step}: Place and connect spine {spine} level {level}")
        for inst in [i for i, k in members.items() if k == (spine, level)]:
            count += 1
            lines += _inst_lines(db, inst) + _connect_lines(db, inst, pins) + [""]
    others = [r["name"] for r in db.inst_rows() if r["name"] not in members]
    if others:
        sep(f"Step {len(levels) + 2}: Other instances (create_inst)"
            + ("" if any(i in pins for i in others) else ", not connected"))
        for inst in others:
            count += 1
            lines += _inst_lines(db, inst) + _connect_lines(db, inst, pins) + [""]
    return "\n".join(lines) + "\n", len(nets) + len(made), count


def _connect_lines(db, inst, pins):
    """The connect lines of an instance: its input, its output, then the rest."""
    from core.commands.write_def import _pin
    mine = pins.get(inst, {})
    first = [p for p in (_pin(db, inst, "in"), _pin(db, inst, "out")) if p in mine]
    return [f"connect {_word(f'{inst}/{p}')} -net {_word(mine[p])}"
            for p in first + [p for p in mine if p not in first]]


def _word(name):
    """name as one Tcl word of the script: in braces when it has a character
    Tcl reads (the net d[3] of a bus port)."""
    return "{" + name + "}" if set(name) & set('[]$;"\\ ') else name


def _inst_lines(db, inst):
    r = db.inst_row(inst)
    lines = [f"# {inst}  lower-left ({_num(r['x'])}, {_num(r['y'])}) um, {r['orient'] or 'N'}",
             f"create_inst -cell {r['ref_cell']} -name {_word(inst)}",
             f"place_inst {_word(inst)} {_num(r['x'])} {_num(r['y'])} "
             f"{ORIENT.get(r['orient'] or 'N', 'R0')}"]
    status = (r["status"] or "placed").lower()
    if status != "placed":       # set_db .place_status fixed (or cover)
        lines.append(f"set_db {_word(f'inst:{inst}')} .place_status {status}")
    return lines
