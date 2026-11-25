"""read_pin_spec -file <yaml>: read named pin routing specs into the database,
for route_pin -spec_name (and add_buffer_on_net -spec_name).

    read_pin_spec -file pin_routing_spec.yaml
    route_pin -inst [get_db insts mgt_clk_main*] -spec_name vertical_routing

The file holds, under 'pin_routing', specs by name, each with the keys of a
route_pin -spec file (cell_pattern, width, spacing, max_strap_extension,
nets, pins); a missing key keeps the built-in value:

    pin_routing:
      vertical_routing:
        width: 0.36
        ...
      horizontal_routing:
        ...

A spec of a name read before is replaced. The specs are kept in the
database (write_db, read_db); the file is not read again.
"""

import os

from core.commands import route_pin
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "read_pin_spec"
SUMMARY = "Read named pin routing specs from a YAML file (route_pin -spec_name)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-file": "value"}

USAGE = 1
NOT_NAMED = 313
REPLACED = 314


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    path = opts.get("-file")
    if not path:
        raise HtreeError(USAGE, f"{NAME}: -file is required. Usage: {NAME} -file <yaml>")
    try:
        specs = route_pin.load_specs(path)
    except HtreeError as exc:
        raise HtreeError(exc.msg_id, exc.text.replace("route_pin:", f"{NAME}:")
                         .replace("-spec '", "-file '"))
    if None in specs:
        raise HtreeError(NOT_NAMED, f"{NAME}: {path}: the spec under pin_routing has no name: "
                         f"put it under one (pin_routing: {{vertical_routing: {{width: ..."
                         f"}}}}), or give the file to route_pin -spec")
    db = session.db
    replaced = db.set_pin_spec_defs(specs, os.path.abspath(path))
    out = session.out
    info(f"{NAME}: {len(specs)} pin routing spec(s) from '{path}':", out)
    for name, spec in specs.items():
        info(f"  {name}: cells {' '.join(spec['cell_pattern'])}, {len(spec['nets'])} straps "
             f"({' '.join(spec['nets'])}), width {spec['width']:g}, spacing "
             f"{spec['spacing']:g}, on {spec['pins']['horizontal_layer']} from "
             f"{spec['pins']['vertical_layer']}" if spec["pins"]["horizontal_layer"] else
             f"  {name}: cells {' '.join(spec['cell_pattern'])}, no straps: "
             f"{spec['pins']['vertical_layer']} pin wires only (pins.horizontal_layer none)",
             out)
    if replaced:
        warn(REPLACED, f"{NAME}: replaced the spec(s) of the same name read before: "
             f"{' '.join(replaced)}", out)
    info(f"  route_pin -inst <insts> -spec_name <name>", out)
    return tuple(specs)
