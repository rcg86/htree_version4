"""write_logical -output <file> [-overwrite]: write the logical changes htree4
made to the design as an Innovus (Stylus) script to source, in the form
htree version 3 dumped them:

    create_net -name <net>
    create_inst -cell <cell> -name <inst>
    place_inst <inst> <x> <y> <orientation>
    connect <inst>/<pin> -net <net>

Step 1 creates every spine net (the output net of each spine cell). Then, level
by level from the root, each cell is created, placed (lower-left corner,
microns) and its input and output pins connected. A spine's root takes the
spec's root_net, which must already exist in the design. Instances that belong
to no spine (create_inst) are created and placed, not connected.
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
    from core.commands.write_def import _pin
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
            lines.append(f"create_net -name {r['name']}")
        lines.append("")

    in_net = {}                      # inst -> the net on its input
    out_net = {r["driver"]: r["name"] for r in nets}
    for r in nets:
        for load in r["loads"].split():
            in_net[load] = r["name"]
    members = {}                     # inst -> (spine, level)
    roots = {}
    for s in spines:
        spec = db.spine_spec_row(s["spec"])
        root = (spec["root_net"] if spec is not None else None) or "net"
        for m in db.spine_members(s["id"]):
            members[m["inst"]] = (s["name"], m["level"])
            if not m["driver"]:
                roots[m["inst"]] = root

    levels = []                      # (spine, level) in build order, root level first
    for inst, key in members.items():
        if key not in levels:
            levels.append(key)
    count = 0
    for step, (spine, level) in enumerate(levels, start=2):
        sep(f"Step {step}: Place and connect spine {spine} level {level}")
        for inst in [i for i, k in members.items() if k == (spine, level)]:
            count += 1
            lines += _inst_lines(db, inst)
            pin_in, pin_out = _pin(db, inst, "in"), _pin(db, inst, "out")
            net = roots.get(inst) or in_net.get(inst)
            if pin_in and net:
                lines.append(f"connect {inst}/{pin_in} -net {net}")
            if pin_out and inst in out_net:
                lines.append(f"connect {inst}/{pin_out} -net {out_net[inst]}")
            lines.append("")
    others = [r["name"] for r in db.inst_rows() if r["name"] not in members]
    if others:
        sep(f"Step {len(levels) + 2}: Other instances (create_inst), not connected")
        for inst in others:
            count += 1
            lines += _inst_lines(db, inst) + [""]
    return "\n".join(lines) + "\n", len(nets), count


def _inst_lines(db, inst):
    r = db.inst_row(inst)
    lines = [f"# {inst}  lower-left ({_num(r['x'])}, {_num(r['y'])}) um, {r['orient'] or 'N'}",
             f"create_inst -cell {r['ref_cell']} -name {inst}",
             f"place_inst {inst} {_num(r['x'])} {_num(r['y'])} "
             f"{ORIENT.get(r['orient'] or 'N', 'R0')}"]
    status = (r["status"] or "placed").lower()
    if status != "placed":       # set_db .place_status fixed (or cover)
        lines.append(f"set_db inst:{inst} .place_status {status}")
    return lines
