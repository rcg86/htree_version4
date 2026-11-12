NAME
    read_spine_spec - read spine specs from a YAML file

SYNOPSIS
    read_spine_spec -file <yaml_file>

DESCRIPTION
    Reads one or more spine specs from a YAML file into the design
    database. A spine spec describes how a clock spine is built: the root
    net, drive-length constraints, placement, spine span, stubs, and the
    buffer levels with their cells and connections. tech data and the
    physical library are not needed to read it.

    File layout. Each spec is a mapping under 'spine_spec:'. Several specs
    go in one file either as YAML documents separated by '---':

        spine_spec:
          name: custom_spine_5000
          ...
        ---
        spine_spec:
          name: custom_spine_5001
          ...

    or as a list:

        spine_spec:
          - name: custom_spine_5000
            ...
          - name: custom_spine_5001
            ...

    Duplicate keys are an error. Two specs written one after the other
    under a single 'spine_spec:' without '---' are duplicate keys; most
    YAML readers silently keep only the last one, so read_spine_spec
    rejects the file and names the line.

    Modeled keys (YAML key -> spine_spec attribute):
        name                          name (required; no '/' or spaces)
        type, units, point, root_net  same names
        constraints.max_drive_length  max_drive_length (number)
        constraints.count_stub_in_drive  count_stub_in_drive (true/false)
        placement.origin_x            origin_x (number; not used)
        placement.origin              origin (number); um along the spine
                                      from create_spine -location to the
                                      root cell (and, with -mirror, to the
                                      mirrored root the other way)
        placement.level_pitch         level_pitch (number); the column step,
                                      along x for a vertical spine and y
                                      for a horizontal one. level_pitch_x
                                      and level_pitch_y are read as
                                      level_pitch (give only one)
        placement.deviation           deviation (number): how much a net
                                      may exceed max_drive_length, and
                                      how far apart a level's nets may be
        spine.orientation             orientation
        spine.span                    span (number)
        stubs.count                   stub_count (integer)
        stubs.gap                     stub_gap (number)
        stubs.tap                     stub_tap
        stubs.order                   stub_order (list of names)
        levels.<L>.cells.<cell>       a spine_level and spine_cell object;
                                      the cell's input, output and
                                      location keys (location: a number,
                                      um from the cell's driver along the
                                      spine; see create_spine)
    Values are stored as written; nothing is derived or checked against
    other specs, tech or the library here (create_spine does that).

    Nothing is dropped: keys that are not modeled are kept verbatim as
    'path: value' in the spec's .extra (or the cell's .extra for keys in a
    cell mapping), and the spec's source lines are kept in .yaml_text.

    Reading a spec whose name is already loaded replaces it, with a
    warning. A parse error leaves the database unchanged.

OPTIONS
    -file <yaml_file>
        YAML file to read. Required.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    spine_spec:<spec>
        obj_type, name, type, units, point, root_net, max_drive_length,
        count_stub_in_drive, origin_x, origin, level_pitch, deviation, orientation, span,
        stub_count, stub_gap, stub_tap, stub_order, spine_levels (handles),
        file, extra, yaml_text
    spine_level:<spec>/<level>
        obj_type, name, spine_cells (handles), spine_spec
    spine_cell:<spec>/<level>/<cell>
        obj_type, name, input, output, location, extra, spine_level

QUERIES
    get_db spine_spec                           print every spec (all attributes,
                                                levels and cells), return handles
    get_db spine_specs                          all spine_spec handles, no printing
                                                (use this in scripts and loops)
    get_db spine_spec .name                     their names
    get_db spine_spec:<spec> .stub_order
    get_db spine_spec:<spec> .spine_levels.spine_cells.name -if {.output == stub3}
    get_db spine_cell:<spec>/L2/inv1 .input

RETURN VALUE
    None. Prints each spec with its line, levels and cell counts.

EXAMPLES
    htree> read_spine_spec -file runs/custom_spine.yaml
    Reading spine spec '/path/to/runs/custom_spine.yaml'
      custom_spine_5000       : line 3, levels L1(3) L2(2) L3(3) L4(6), 14 cells
      custom_spine_5001       : line 57, levels L1(3) L2(2) L3(3) L4(6), 14 cells
    htree> get_db spine_spec
    spine_spec:custom_spine_5000 spine_spec:custom_spine_5001

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-080  file not found
    HT4-081  parse error: YAML syntax, duplicate key, missing name, wrong
             value type (message gives file and line)
    HT4-082  WARN: a spec with the same name was replaced
    HT4-083  WARN: a top-level key other than spine_spec was ignored
    HT4-027  (get_db) no spine spec loaded; run read_spine_spec first

SEE ALSO
    get_db, read_lef, read_tech
