NAME
    read_def - read the boundary, tracks and pins of a DEF file

SYNOPSIS
    read_def -file <def_file>

DESCRIPTION
    Reads the design boundary, the routing tracks and the top-level pins
    from a DEF file into the design database. Only these parts of the DEF
    are read:

      header    VERSION, DESIGN, UNITS DISTANCE MICRONS, DIVIDERCHAR,
                BUSBITCHARS
      DIEAREA   the design boundary: a rectangle (2 points) or a
                rectilinear polygon (4 or more points; '*' repeats the
                previous coordinate)
      TRACKS    every TRACKS statement: X or Y, start, DO count, STEP,
                MASK [SAMEMASK] (before or after the X/Y part) and its
                LAYER names
      PINS      every pin: NET, DIRECTION, USE, SPECIAL, and each PORT's
                LAYER and POLYGON shapes with MASK and placement (FIXED,
                PLACED or COVER, location, orientation)

    Every other section and statement (ROW, GCELLGRID, VIAS,
    COMPONENTS, NETS, SPECIALNETS, BLOCKAGES, PINPROPERTIES, ...) is
    skipped without being stored, and listed with its count in the
    summary. The file is read line by line; '.def.gz' files are read
    directly. A 45 MB floorplan DEF with 110,000 pins reads in about 4
    seconds.

    Coordinates are converted from DEF database units to microns. Pin
    shapes are stored in absolute coordinates: each shape is rotated by
    its port's orientation (N W S E FN FW FS FE) and moved to its
    placement. A pin without placement keeps its shapes as written.

    Pin shapes are read on every layer. Only shapes on layers in the tech
    data are used in calculations; read_def reports the pin layers, which
    are in tech, and warns about the rest (HT4-093). port_shape .in_tech is
    evaluated when queried, so read_tech may run before or after read_def.

    DIRECTION is stored as Cadence reports it: INPUT -> in, OUTPUT -> out,
    INOUT -> inout, FEEDTHRU -> feedthru. Unmodeled pin statements (VIA,
    ANTENNA*, NETEXPR, DIRECTION ... TRISTATE, ...) are kept verbatim in
    the port's .extra.

    The database holds one design. Reading another DEF replaces it, with a
    warning. A parse error leaves the database unchanged.

OPTIONS
    -file <def_file>
        DEF file to read (.def or .def.gz). Required.

OBJECTS AND ATTRIBUTES
    design:<design>
        obj_type, name, file, def_version, units (DEF units per micron),
        boundary ("x y x y ..." microns, as in DIEAREA; a rectangle is
        given as its 4 corners), bbox ("x1 y1 x2 y2"), area (square
        microns), ports (handles)
    port:<design>/<pin>
        obj_type, name, net, direction, use, special (true/false), status
        (fixed, placed, cover, unplaced), location ("x y"), orient, layers,
        rect (bounding box of all shapes), port_shapes (handles), extra,
        design
        status, location and orient come from the pin's first PORT.
    port_shape:<design>/<pin>/<k>
        obj_type, name (k), layer, type (rect or polygon), rect (bounding
        box), points (absolute, microns), mask, in_tech, port
    track_pattern:<design>/<k>
        one per TRACKS statement, k = 1, 2, ... in file order
        obj_type, name (k), direction (x or y, as in DEF: x patterns are
        vertical tracks at x = start + i * step), start, num_tracks, step,
        end (the last track), mask, same_mask (true/false), layers, design
        Distances in microns.
    design .track_patterns returns all patterns.

    Bus pin names hold brackets, so brace the handle in Tcl:
        get_db {port:cf999/data[3]} .rect

QUERIES
    get_db design                               print the design summary
    get_db designs                              design handle, no printing
    get_db design:<d> .boundary                 die polygon
    get_db ports .name -if {.direction == in}
    get_db ports -if {.layers == H2}
    get_db design .ports.port_shapes.rect -if {.in_tech == true}
    get_db track_patterns -if {.layers == D12 && .direction == x}
    get_db track_pattern:<d>/13 .start

    For list attributes (.layers), == compares the whole list text: a
    pattern on "H2 M1" does not match {.layers == H2}. Use a glob such as
    {.layers == *H2*} when a pattern lists several layers.

RETURN VALUE
    None. Prints the design, boundary, pin and shape counts, track
    patterns and their layers (which are in tech, and which tech layers
    have no tracks), skipped sections and pin layers.

EXAMPLES
    htree> read_tech -file tech.lef
    htree> read_def -file cf999.def
    Reading DEF '/path/to/cf999.def'
      Design      : cf999 (DEF 5.8, 4000 units/micron)
      Boundary    : polygon, 26 points, bbox 0 0 5704.56 14144.08
      Pins        : 110728, shapes 110725
      Tracks      : 56 patterns on 19 layers (IB IA G2 G1 H2 H1 D12 D11 ... M1)
      Tracks tech : IB IA G2 G1 H2 H1 D12
      Skipped     : PROPERTYDEFINITIONS ROW(167043) GCELLGRID(6) VIAS PINPROPERTIES BLOCKAGES
      Pin layers  : D6(2084) D8(16404) D12(17251) ...
      In tech     : D12 G1 H1 G2 H2
    **WARN: (HT4-093): 62522 pin shape(s) on layers not in tech: D6 D8 D9 D11 D7 D10. They are kept but ignored in calculations

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-090  file not found
    HT4-091  parse error (message gives file and line), or no DESIGN
    HT4-092  WARN: the existing design was replaced
    HT4-093  WARN: pin shapes on layers not in tech (kept, ignored in
             calculations)
    HT4-094  WARN: no tech data loaded, pin layers not checked
    HT4-095  WARN: no DIEAREA, the design has no boundary
    HT4-028  (get_db) no design loaded; run read_def first

SEE ALSO
    get_db, read_tech, read_lef
