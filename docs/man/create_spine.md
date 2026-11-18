NAME
    create_spine - validate (and show) or build a spine from a spine spec

SYNOPSIS
    create_spine -name <spine> -spec_name <spine_spec> -location {x y}
                 [-build_direction +x|-x|+y|-y] [-mirror]
                 (-validate [-show] [-ref_cell <cell>] | -build -ref_cell <cell>)

DESCRIPTION
    Places the inverter tree and stubs of a spine spec (read_spine_spec)
    as the spine -name. One spec can be placed many times under different
    spine names.
    -validate computes the placement and reports every warning without
    changing the design; -build creates it, ignoring the warnings.

    Root net. The root's input is on the spine's root net: the spec's
    root_net, or <spine>_primary_input when that is the placeholder
    'net' (or not given), so a script write_logical writes does not
    connect to a net 'net' the design does not have. get_db
    spine:<name> .root_net gives it; rename_obj -from [get_db
    spine:<name> .root_net] -to <name> renames it.

    Layout. The root cell (the one whose input is the root net, L1_inv1)
    sits placement.origin (default 0) from -location along the spine:
    above it for a vertical spine, right of it for a horizontal one
    (its centre). Each level of the spec is a column:
    L1 at the root, L2 one level_pitch further toward
    -build_direction, and so on; the stubs are one level_pitch beyond the
    last level. A vertical spine steps its columns along x (+x or -x,
    default +x) and runs its stubs up from the root; a horizontal
    spine steps along y (+y or -y, default +y) and runs right. The stubs
    lie end to end in one line with stubs.gap between them and share
    spine.span equally:
        stub length = (span - (stubs - 1) x gap) / stubs
    (6000 um, 6 stubs, gap 10: 991.667 um). When leaves have a location
    the leaves give the stubs instead (Leaf locations, below).

    Mirror. -mirror adds the same spine reflected across -location: a
    vertical spine is mirrored below it (its root placement.origin below
    -location, its stubs running down), a horizontal one left of it (root
    placement.origin to the left, stubs running left). The columns stay
    on the -build_direction side. With origin 10 the two roots are 20 um
    apart. Both halves are fed by the root net and have the same placement
    and net lengths. The mirror's instances are named
    <spine>_mirror_<level>_<cell>, its nets <spine>_mirror_<level>_<cell>_Y
    and its stubs <stub>_mirror; -build places them flipped (FS for a
    vertical spine, FN for a horizontal one) and stores them in the same
    spine. Cells of the two halves closer than the cell size (a small
    origin) are reported as overlaps.

    Placement. Fixed: the root, every cell with a location key, and
    every other leaf (a cell with an output stub) at the middle of its
    stub. A
    cell's location is its distance from its driver along the spine, in
    um, centre to centre: + is up (vertical) or right (horizontal), - is
    down or left, whatever the build direction:
        inv2: {input: L1/inv1/Y, location: 1000}    # 1000 um above L1/inv1
        inv2: {input: L1/inv3/Y, location: -500}    # 500 um below L1/inv3
    When the driver moves, the cell moves with it. A location may put a
    cell outside the span; the root cannot have one. Limits and balance
    are still checked, so a location that makes a net too long shows as
    a warning.

    Leaf locations. A leaf with a location is placed by it too, at its
    driver's position + location. The leaves then decide the stubs, not
    the span: every stub is centred on its leaf (half below or left of
    it, half above or right) and all stubs have one length, the longest
    that leaves stubs.gap between the stubs of the two closest leaves:
        stub length = distance of the two closest leaves - stubs.gap
    (leaves 22.5 apart, gap 2: 20.5 um, 10.25 on each side). The stubs
    of the closest leaves are stubs.gap apart, the others further, and a
    stub may leave the span. A leaf's net is level_pitch plus this
    length, so it is checked against max_drive_length. A leaf without a
    location sits at the middle of a place the span gives it and its
    stub is centred on it too. With one stub the span gives the length.
    Leaves closer than stubs.gap have no room for stubs (HT4-151). The
    mirror is not looked at for the length: see the table.

    Stub spacing. -validate and -build print the table to judge the
    stubs by: the stub length and where it comes from, then the room
    between each stub and the next in their order along the spine
    (bottom to top, or left to right; with -mirror the stubs of both
    halves in one table), from the end of one stub to the start of the
    next, with the distance of their leaves:
        Stub spacing (um, bottom to top; stubs.gap 2):
          stub length   : 20.5 (10.25 on each side of its leaf) = 22.5
                          between the closest leaves (stub2, stub1) -
                          stubs.gap 2; 19 by the span
          stub2 - stub1 : 2  leaves 22.5 apart
    (the stub length is printed on one line). Without leaf locations the
    length is "by the span" and every row is stubs.gap. A room larger
    than stubs.gap is not a warning: the table is there to decide by. A
    negative room is two stubs over each other (two stub nets on one
    line): the row is marked OVERLAP and it is a warning (HT4-278). The
    stubs of one spine never overlap; those of a spine and its mirror do
    when a leaf's stub reaches past -location, and a larger
    placement.origin moves the two apart.

    Every other cell keeps its column and moves
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

    Net length is the wire drawn once: one trunk along the spine, from
    the lowest to the highest of the driver and its loads, whatever
    their columns, plus level_pitch for each column crossed between the
    trunk and the driver or a load, plus detour. Loads in two columns
    share the trunk: a driver with one load 1200 um up in its own column
    and one 1200 um up in the next column has a net of 1200 + 2.88, not
    1200 in each column. The trunk is drawn in the column that needs the
    fewest crossings. A leaf's net is level_pitch plus its whole stub.
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
      stubs of the spine and its mirror that overlap (leaf locations);
      cells or stubs outside the design boundary (read_def).
    With -mirror, -validate reports both halves, the spine first; -show
    draws the spine only.

    -build creates one instance per cell, named <spine>_<level>_<cell>
    (clk_a_L1_inv1 for -name clk_a), of -ref_cell, orientation N, centred on
    its position (lower-left snapped to the manufacturing grid). The
    stubs and the net centre lines are stored with the spine and drawn in
    the GUI layout tab (Spine checkbox); no routing layer is assigned yet.
    write_db saves the built spine.

    Spec keys used: spine.orientation, spine.span, placement.level_pitch
    (level_pitch_x / level_pitch_y are read as level_pitch),
    placement.deviation (default 0), placement.origin (default 0, not
    negative), constraints.max_drive_length,
    stubs.gap, stubs.tap (center only), stubs.count (if given, must match
    the stubs named), root_net, levels. placement.origin_x is not used:
    -location and placement.origin place the root.

OPTIONS
    -name <spine>
        Name of the spine (spine:<spine>) and the prefix of its instance
        names: <spine>_L1_inv1, ... No '/', spaces or braces. Required.
    -spec_name <spine_spec>
        Spine spec to place (name or spine_spec: handle). Required.
    -location {x y}
        Where the spine starts, microns: the root cell (L1_inv1) is
        centred placement.origin from it along the spine (on it when
        origin is 0). With -mirror, the point the spine is mirrored
        across. Required.
    -build_direction +x|-x|+y|-y
        Side the columns step to: +x or -x for a vertical spine (default
        +x), +y or -y for a horizontal one (default +y).
    -mirror
        Also place the spine mirrored across -location: below it for a
        vertical spine, left of it for a horizontal one.
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
        obj_type, name, spine_spec, orientation, build_direction, location
        (-location), origin, mirror (true/false), ref_cell, level_pitch, deviation, max_drive_length, stub_length,
        path (the line of its stubs, "x y x y ...", bottom or left end
        first: two points as built, more once move_spine_to_boundary has
        bent it), insts, stubs, spine_nets (handles), spine_input (pin
        handles: the signal input of the root cell, and with -mirror of
        the mirrored root too: where the spine is driven), spine_output
        (pin handles: the signal output of every leaf cell, the cells
        that drive the stubs: where the spine ends), root_net (net handle:
        the net on spine_input. <spine>_primary_input when the spec's
        root_net is the placeholder 'net' or none, else the spec's
        root_net; rename_obj renames it)
    stub:<spine>/<stub>
        a final stub (the class is stub; get_db stubs lists them, get_db
        nets lists them with the nets): obj_type, name, driver (inst),
        points (x1 y1 x2 y2; more points when the stub lies over a bend
        of its spine), length, tap (half way along it), orientation (the
        spine's), net
        (the leaf's spine_net, which drives it), route_rule (set_db; kept
        per stub), net_wires (its route_final_stub wire and crossings),
        vias (the vias of its leaf net on its wire), spine
    spine_net:<spine>/<net>
        obj_type, name (<driver inst>_Y), driver (inst), loads (inst names
        or the stub), group (L1-L2, ...), length, detour, route (one
        "x1 y1 x2 y2" per centre-line segment), route_rule (the rule
        the net is routed with; route_rule:default until set_db sets
        another), spine
    get_db spines lists the built spines; get_db nets lists the nets of
    all of them.

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
    htree> create_spine -name clk_v -spec_name custom_spine_v6 -location {5622.772 10066.7} -mirror -build -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04
    Built spine:clk_v: 34 instances of INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04, 12 stubs of 991.667 um, 34 nets (with its mirror clk_v_mirror_*)
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
             location on the root, a negative placement.origin, leaves
             with a location closer than stubs.gap
    HT4-152  -ref_cell not in the library, or it has no SIZE
    HT4-153  the spine is already built, or its instance names are taken
    HT4-154  WARN: a net over max_drive_length + deviation
    HT4-155  WARN: a level's nets differ by more than deviation
    HT4-156  WARN: stubs behind different numbers of inverters
    HT4-157  WARN: overlapping cells (also between a spine and its
             mirror)
    HT4-158  WARN: a cell that drives nothing
    HT4-159  WARN: cells or stubs outside the design boundary
    HT4-278  WARN: stubs of the spine and its mirror overlap (leaf
             locations)

SEE ALSO
    read_spine_spec, create_inst, gui_show, get_db
