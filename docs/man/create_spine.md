NAME
    create_spine - validate (and show) or build a spine from a spine spec

SYNOPSIS
    create_spine -name <spine> -spec_name <spine_spec> -location {x y}
                 [-build_direction +x|-x|+y|-y]
                 (-validate [-show] [-ref_cell <cell>] | -build -ref_cell <cell>)

DESCRIPTION
    Places the inverter tree and stubs of a spine spec (read_spine_spec)
    as the spine -name. One spec can be placed many times under different
    spine names.
    -validate computes the placement and reports every warning without
    changing the design; -build creates it, ignoring the warnings.

    Layout. The root cell (the one whose input is root_net, L1_inv1)
    sits at -location (its centre). Each level of the spec is a column:
    L1 at the location, L2 one level_pitch further toward
    -build_direction, and so on; the stubs are one level_pitch beyond the
    last level. A vertical spine steps its columns along x (+x or -x,
    default +x) and runs its stubs up from the location; a horizontal
    spine steps along y (+y or -y, default +y) and runs right. The stubs
    lie end to end in one line with stubs.gap between them and share
    spine.span equally:
        stub length = (span - (stubs - 1) x gap) / stubs
    (6000 um, 6 stubs, gap 10: 991.667 um).

    Placement. Fixed: the root, every leaf (a cell with an output stub)
    at the middle of its stub, and every cell with a location key. A
    cell's location is its distance from its driver along the spine, in
    um, centre to centre: + is up (vertical) or right (horizontal), - is
    down or left, whatever the build direction:
        inv2: {input: L1/inv1/Y, location: 1000}    # 1000 um above L1/inv1
        inv2: {input: L1/inv3/Y, location: -500}    # 500 um below L1/inv3
    When the driver moves, the cell moves with it. A location may put a
    cell outside the span; the root and leaves cannot have one. Limits
    and balance are still checked, so a location that makes a net too
    long shows as a warning. Every other cell keeps its column and moves
    only along the spine. A linear program places them, using
    the least wire, so that every net is at most max_drive_length +
    deviation and the nets of each level are within deviation of each
    other; detour (snaked) wire may lengthen a short net to balance its
    level. Which stub goes where is chosen by the tool, keeping each
    cell's stubs next to each other so nets do not cross (stubs.order is
    not used). A cell with no loads and no stub (a dummy) sits at its
    driver's position, or at its location if it has one. With -ref_cell,
    a cell driven from its own column (and with no location) is kept one
    cell length further along than its driver.

    Net length is the wire drawn once: level_pitch for each column the
    net crosses, plus, for each column its loads are in, one trunk from
    the driver's position to its farthest load there (shared wire counted
    once), plus detour. A leaf's net is level_pitch plus its whole stub.
    Nets are grouped by the level of their driver: L1-L2, L2-L3, L3-L4,
    L4-stubs.

    Warnings (-validate prints them; -build ignores them and prints how
    many there were):
      a net longer than max_drive_length + deviation;
      a level whose longest and shortest nets differ by more than
      deviation;
      stubs reached through different numbers of inverters (different
      delay; opposite clock polarity for odd and even counts);
      cells overlapping (same column closer than a cell length, or
      neighbouring columns when level_pitch is under the cell width;
      without -ref_cell only cells at the same position);
      a cell that drives nothing;
      cells or stubs outside the design boundary (read_def).

    -build creates one instance per cell, named <spine>_<level>_<cell>
    (clk_a_L1_inv1 for -name clk_a), of -ref_cell, orientation N, centred on
    its position (lower-left snapped to the manufacturing grid). The
    stubs and the net centre lines are stored with the spine and drawn in
    the GUI layout tab (Spine checkbox); no routing layer is assigned yet.
    write_db saves the built spine.

    Spec keys used: spine.orientation, spine.span, placement.level_pitch
    (level_pitch_x / level_pitch_y are read as level_pitch),
    placement.deviation (default 0), constraints.max_drive_length,
    stubs.gap, stubs.tap (center only), stubs.count (if given, must match
    the stubs named), root_net, levels. placement.origin_x is not used:
    -location places the root.

OPTIONS
    -name <spine>
        Name of the spine (spine:<spine>) and the prefix of its instance
        names: <spine>_L1_inv1, ... No '/', spaces or braces. Required.
    -spec_name <spine_spec>
        Spine spec to place (name or spine_spec: handle). Required.
    -location {x y}
        Centre of the root cell (L1_inv1), microns. Required.
    -build_direction +x|-x|+y|-y
        Side the columns step to: +x or -x for a vertical spine (default
        +x), +y or -y for a horizontal one (default +y).
    -validate
        Compute and report only; the design is not changed. Give exactly
        one of -validate and -build.
    -show
        With -validate: draw the spine in a Schematic tab next to the
        Layout tab of the GUI (opens the GUI if needed).
    -build
        Create the spine in the design, ignoring warnings.
    -ref_cell <cell>
        Inverter cell to place (lib_cell name or handle). Required with
        -build; with -validate it gives the cell size for the overlap
        check.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    spine:<name>
        obj_type, name, spine_spec, orientation, build_direction, location,
        ref_cell, level_pitch, deviation, max_drive_length, stub_length,
        insts, spine_stubs, spine_nets (handles)
    spine_stub:<spine>/<stub>
        obj_type, name, driver (inst), points (x1 y1 x2 y2), length, tap,
        spine
    spine_net:<spine>/<net>
        obj_type, name (<driver inst>_Y), driver (inst), loads (inst names
        or the stub), group (L1-L2, ...), length, detour, route (one
        "x1 y1 x2 y2" per centre-line segment), spine
    get_db spines lists the built spines.

RETURN VALUE
    -validate: the number of warnings. -build: spine:<name>.

EXAMPLES
    htree> create_spine -name clk_a -spec_name custom_spine_5000 -location {5622.772 10066.7} -validate -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04
    Spine clk_a (spec custom_spine_5000): vertical, built toward +x from {5622.772 10066.7}
      Columns : L1 L2 L3 L4 and the stubs, level_pitch 2.88
      Stubs   : 6 x 991.667 um, gap 10, from {5634.292 10066.7} to {5634.292 16066.7}
      Limits  : net <= max_drive_length 1020 + deviation 10 = 1030; nets of a level within 10 of each other
    ...
    **WARN: (HT4-154): net clk_a_L2_inv1_Y (L2-L3) is 3454.585 um, over max_drive_length 1020 + deviation 10 = 1030 by 2424.585 um
    htree> create_spine -name clk_a -spec_name custom_spine_5000 -location {5622.772 10066.7} -validate -show
    htree> create_spine -name clk_a -spec_name custom_spine_5000 -location {5622.772 10066.7} -build -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04
    Built spine:clk_a: 14 instances of INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04, 6 stubs of 991.667 um, 13 nets
      5 warning(s) ignored; run create_spine with -validate to see them

ERRORS
    HT4-001  missing -name, -spec_name or -location, a bad -name (with
             '/', spaces or braces), a bad location, not exactly one
             of -validate and -build, -show without -validate, -build
             without -ref_cell
    HT4-027  no spine spec loaded (read_spine_spec)
    HT4-100  -show: PySide6 is not available
    HT4-101  -show: no display
    HT4-150  no spine spec with that name
    HT4-151  the spec cannot be placed: bad orientation or build
             direction, missing span / level_pitch / max_drive_length,
             stubs that do not fit, a missing or unknown input, more or
             fewer than one root, a loop, a stub driven twice, a leaf
             that also drives cells, stubs.count not matching, a
             location on the root or on a leaf
    HT4-152  -ref_cell not in the library, or it has no SIZE
    HT4-153  the spine is already built, or its instance names are taken
    HT4-154  WARN: a net over max_drive_length + deviation
    HT4-155  WARN: a level's nets differ by more than deviation
    HT4-156  WARN: stubs behind different numbers of inverters
    HT4-157  WARN: overlapping cells
    HT4-158  WARN: a cell that drives nothing
    HT4-159  WARN: cells or stubs outside the design boundary

SEE ALSO
    read_spine_spec, create_inst, gui_show, get_db
