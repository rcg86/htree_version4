NAME
    read_pin_spec - read named pin routing specs into the database, for
    route_pin -spec_name

SYNOPSIS
    read_pin_spec -file <yaml>

DESCRIPTION
    Reads the pin routing specs of a YAML file, by name, into the database.
    route_pin -spec_name <name> (and add_buffer_on_net -spec_name) then uses
    one by its name, without the file. The specs are saved by write_db and
    come back with read_db; the file is not read again.

    The file holds the specs under 'pin_routing', each a mapping of the keys
    of a route_pin spec (cell_pattern, routing_direction, width, spacing,
    max_strap_extension,
    nets, pins); a missing key keeps route_pin's built-in value, an unknown
    key is an error:

        pin_routing:
          vertical_routing:
            width: 0.36
            spacing: 0.36
            nets: [VSS, VDD_SOC, SIGNAL, VSS, SIGNAL, VDD_SOC]
            pins: {layer: D12, horizontal_layer: IA, vertical_layer: H2,
                   nets: {VDD: VDD_SOC, VSS: VSS, A: SIGNAL, Y: SIGNAL}}
          horizontal_routing:
            ...

    A spec name is one word. A spec of a name read before is replaced
    (HT4-314). A file whose pin_routing holds the keys of one spec, not
    named, is for route_pin -spec only (HT4-313).

    The report gives, per spec, its cells (cell_pattern), its straps, width,
    spacing and layers.

    get_db pin_route_spec prints every spec read, with all its values;
    get_db pin_route_specs lists them (pin_route_spec:<name>), and
    get_db pin_route_spec:<name> .<attr> gives one value: file,
    cell_pattern, routing_direction, width, spacing, max_strap_extension,
    nets, pin_layer, horizontal_layer (none: no straps), vertical_layer,
    pin_nets ("<pin> <net>"), insts (the instances route_pin routed with it).

OPTIONS
    -file <yaml>
        The YAML file. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The names of the specs read.

EXAMPLES
    htree> read_pin_spec -file pin_routing_spec.yaml
    read_pin_spec: 2 pin routing spec(s) from 'pin_routing_spec.yaml':
      vertical_routing: cells *, 6 straps (VSS VDD_SOC SIGNAL VSS SIGNAL VDD_SOC), width 0.36, spacing 0.36, on IA from H2
      horizontal_routing: cells *, 6 straps (VSS VDD_SOC SIGNAL VSS SIGNAL VDD_SOC), width 0.36, spacing 0.36, on IA from H2
      route_pin -inst <insts> -spec_name <name>
    vertical_routing horizontal_routing
    htree> route_pin -inst [get_db [get_db insts mgt_clk_main*] .name] -spec_name vertical_routing

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-167  the file cannot be read, is not valid YAML, has no
             'pin_routing:' section, a spec name that is not one word, or
             an unknown key or a bad value in a spec
    HT4-313  the spec under pin_routing has no name (use route_pin -spec)
    HT4-314  WARN: a spec of a name read before is replaced

SEE ALSO
    route_pin, add_buffer_on_net, legalize_placement, read_spine_spec,
    write_db
