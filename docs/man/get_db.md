NAME
    get_db - query objects and attributes in the design database

SYNOPSIS
    get_db tech
    get_db library_physical
    get_db <path> [<name_pattern>] [-if {<expr>}]
    get_db <objects> .<attr>[.<attr>...] [-if {<expr>}]
    get_db <objects> .*

DESCRIPTION
    get_db is the command that reads the design database. It follows the
    Cadence Stylus Common UI get_db conventions.

    Objects are named by handles: 'tech' for the tech data,
    'layer:<name>' for a layer (layer:IA), 'library_physical' for the
    cell library read by read_lef, 'lib_cell:<cell>' for one of its
    cells, 'lib_pin:<cell>/<pin>' for a pin, 'lib_port:<cell>/<pin>/<n>'
    for a pin's n-th PORT and 'layer_shape:<cell>/<pin>/<n>/<k>' for a
    shape in it. Handles are plain
    strings, so they can be stored in Tcl variables and passed back to
    get_db.

    get_db tech
        Prints all tech data (file, LEF version, DB units, manufacturing
        grid, and every layer with its attributes and any unmodeled
        statements). Returns 'tech'. Use '.lef_text' on a layer to see its
        original LEF text.

    get_db library_physical
        Prints the cell LEF files read, the number of cells, each cell's
        class, size, site and pins, and unmodeled top-level statements. Returns
        'library_physical'.

    get_db <path>
        A path starts at a root and follows attributes separated by dots.
        Roots: tech, head (same as tech), layers, layer, library_physical,
        lib_cells, lib_cell (both same as library_physical.lib_cells). A leading dot is
        optional: get_db .tech.layer is the same as get_db tech.layer, and
        get_db .tech is the same as get_db tech.
            get_db tech.layer      -> layer:H1 layer:H2 ... (LEF order)
            get_db layers          -> same
            get_db head.layers     -> same
            get_db layers.name     -> H1 H2 ...
        An optional second word filters objects by name (glob):
            get_db layers G*       -> layer:G1 layer:G2

    get_db <objects> .<attr>
        Returns the attribute for each object. One object returns a single
        value; several return a Tcl list in input order. Empty attributes
        return an empty string. Attributes that refer to objects return
        handles, and can be chained: get_db layer:IA .tech.lef_version

    get_db <objects> .*
        Prints every attribute of each object.

    -if {<expr>}
        Keeps only objects for which <expr> is true, applied before the
        attribute is taken. Operators: == != < > <= >= && || ! and
        parentheses. == and != do glob matching when the right side has
        * ? or [. Comparison is numeric when both sides are numbers,
        string otherwise. A bare attribute is true when non-empty.
        The Cadence form uses braces: -if {.name == IA}. The parenthesized
        form -if (.name == IA) is also accepted.

OBJECT ATTRIBUTES
    tech
        obj_type, file, lef_version, db_units, manufacturing_grid,
        layer (handles), layers (same), extra (unmodeled top-level LEF text)
    layer
        obj_type, name, type, direction, pitch_x, pitch_y, offset_x,
        offset_y, width, min_width, max_width, area, min_enclosed_area,
        min_step, min_step_max_edges, min_spacing, extra (unmodeled layer
        statements), lef_text (original LAYER block), tech (handle)
    library_physical, lib_cell, lib_pin, lib_port, layer_shape
        See 'man read_lef'.
    Distances are microns. type and direction are lowercase.

TAB COMPLETION
    At the interactive prompt, <tab> lists what can come next. Matching
    choices are listed on the first <tab>; a unique match is filled in.
        get_db .<tab>                 tech library_physical
        get_db .tech.<tab>            db_units extra file layer layers ...
        get_db .tech.layer.<tab>      area direction ... width
        get_db layer:<tab>            layer:G1 layer:G2 ... (needs read_tech)
        get_db layer:IA .<tab>        .* and every layer attribute
        get_db layers -if {.<tab>     attributes usable in the expression
    Lists show only the last path segment. The aliases head, layers and
    layer are completed once their first letter is typed. After a nested
    command (get_db [get_db layers] .<tab>) the object type cannot be
    known, so attributes of every object type are offered.

RETURN VALUE
    A handle list, a value, or a list of values, as described above.

EXAMPLES
    htree> get_db tech.layer
    layer:H1 layer:H2 layer:G1 layer:G2 layer:IA layer:IB
    htree> get_db [get_db tech.layer -if (.name == IA)] .min_width
    0.36
    htree> get_db layer:IA .name
    IA
    htree> get_db layers .name -if {.direction == vertical && .pitch_x > 0.2}
    G2 IB
    htree> foreach l [get_db layers] { puts "[get_db $l .name] [get_db $l .pitch_x]" }

ERRORS
    HT4-020  usage error (missing argument, bad -if placement)
    HT4-021  unknown path root
    HT4-022  object does not exist
    HT4-023  unknown attribute (message lists valid ones)
    HT4-024  -if expression cannot be parsed
    HT4-025  no tech data loaded; run read_tech first
    HT4-026  no physical library loaded; run read_lef first

SEE ALSO
    read_tech, read_lef, write_db, read_db
