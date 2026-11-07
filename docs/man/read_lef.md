NAME
    read_lef - read a cell LEF file into the physical library

SYNOPSIS
    read_lef -file <lef_file>

DESCRIPTION
    Parses a cell (standard cell or macro) LEF file and adds its cells to
    the physical library in the in-memory design database. read_lef can be
    run several times; each file adds to the library. tech data is not
    needed to read a cell LEF.

    Modeled data:
      lib_cell     MACRO: name (.name, .ref_name), CLASS (lowercase, with
                   any subclass: "core", "pad inout"), SIZE x BY y
                   (.size_x, .size_y), SITE
      lib_pin      PIN: DIRECTION (base direction, lowercase: input,
                   output, inout, feedthru), USE (signal, power, ground,
                   clock, ...)
      lib_port     each PORT block of a pin, numbered from 1
      layer_shape  each RECT and POLYGON in a port, numbered from 1, with
                   its LAYER, MASK and points

    Pin shapes are read on every layer. Only shapes on layers defined in
    the tech data are used in calculations; the others are kept and can be
    queried. read_lef reports the pin layers it found, which of them are in
    the tech data, and warns (HT4-064) about the rest. layer_shape .in_tech
    is evaluated when queried, so it is correct whether read_tech runs
    before or after read_lef.

    Nothing is dropped:
      - The full original text of every MACRO block, comments included,
        is kept in the cell's .lef_text attribute. OBS and DENSITY are kept
        there only.
      - Unmodeled cell, pin and port statements (ORIGIN, FOREIGN, SYMMETRY,
        ANTENNA*, PROPERTY, SHAPE, LAYER ... SPACING, DIRECTION OUTPUT
        TRISTATE, ...) are kept verbatim in that object's .extra.
      - Top-level statements and blocks other than MACRO (SITE,
        PROPERTYDEFINITIONS, BUSBITCHARS, ...) are kept verbatim in
        library_physical .extra, with one warning per kind.

    If a MACRO name is already in the library (from this file or an
    earlier one), the first definition is kept and a warning is printed.
    A parse error leaves the database unchanged.

OPTIONS
    -file <lef_file>
        Cell LEF file to read. Required.

OBJECTS AND ATTRIBUTES
    library_physical
        obj_type, files, lib_cells (handles), extra
    lib_cell:<cell>
        obj_type, name, ref_name (the MACRO name), class, size_x, size_y,
        site, lib_pins (handles), file, extra, lef_text, library_physical
    lib_pin:<cell>/<pin>
        obj_type, name, direction, use, lib_ports (handles), layers (all
        shape layers), tech_layers (only those in tech), extra, lib_cell
    lib_port:<cell>/<pin>/<n>
        obj_type, name (n), layer_shapes (handles), layers, extra, lib_pin
    layer_shape:<cell>/<pin>/<n>/<k>
        obj_type, name (k), layer, type (rect or polygon), rect (bounding
        box "x1 y1 x2 y2", lower left first), points (as written in the
        LEF), mask, in_tech (true or false), lib_port

QUERIES
    get_db .lib_cell                                  all lib_cell handles
    get_db library_physical                           summary per cell
    get_db lib_cell:<cell> .lib_pins                  pins of a cell
    get_db lib_cells.lib_pins -if {.use == signal} .name
    get_db [get_db lib_pin:<cell>/Y .lib_ports.layer_shapes] \
        -if {.in_tech == true} .rect                  Y pin rects on tech layers

RETURN VALUE
    None. Prints the file, LEF version, counts of cells, pins, ports and
    shapes, and the pin layers.

EXAMPLES
    htree> read_tech -file tech.lef
    htree> read_lef -file ln04lpp_sc_s7p94t_cdk12m3mx2fx7dx_slvt_c60l04.lef
    Reading cell LEF '/path/to/ln04lpp_sc_s7p94t_cdk12m3mx2fx7dx_slvt_c60l04.lef'
      LEF version : 5.8
      Cells       : 6 added
      Pins        : 36, ports 294, shapes 294
      Pin layers  : S11(192) D12(42) M1(12) NW(24) PSUB(24)
      In tech     : D12
    **WARN: (HT4-064): 252 pin shape(s) on layers not in tech: S11 M1 NW PSUB. They are kept but ignored in calculations

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-060  file not found
    HT4-061  parse error (message gives file and line)
    HT4-062  WARN: duplicate MACRO name, first definition kept
    HT4-063  WARN: top-level statements not modeled, kept verbatim
    HT4-064  WARN: pin shapes on layers not in tech (kept, ignored in
             calculations)
    HT4-065  WARN: no tech data loaded, pin layers not checked
    HT4-026  (get_db) no physical library loaded; run read_lef first

SEE ALSO
    get_db, read_tech, write_db, read_db
