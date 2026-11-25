NAME
    check_drc - check the routing for shorts, spacing and width
    violations, opens, and the routing direction of the cells

SYNOPSIS
    check_drc [-check_shorts_only | -check_spacing_only | -check_open_only]
              [-layer_range <bottom>:<top>] [-file <file> [-overwrite]]
              [-direction_jog <um>]

DESCRIPTION
    What is checked. Only what the tool made or placed:
      wires     route_pin straps and pin wires; route_net,
                route_final_stub and optimize_pg_connection wires,
                extensions, shields and stub wires
      via pads  the metal shapes of each via on its two layers, for the
                vias that have a definition (assign_via_for_route); a
                polygon counts as its bounding box
      pins      the pin shapes of the placed cells
    The ports of the design, the power grid and blockages of the DEF and
    the obstructions of the cells are not checked. Crossing boxes are not
    shapes: the vias stand for them.

    Nets. A shape belongs to its power net (shields, power straps and
    their pin wires) or to its net. A strap and pin wire route_net has
    not named yet belong to the net of their pin: a spine net, or a net
    of no spine (a port's, connect_pin's, add_buffer_on_net's). Shapes of one net
    are never compared with each other, and two pins are not compared
    (library geometry).

    Shorts. Two shapes of different nets on one layer that overlap, or
    abut along an edge. The box is the overlap. Shapes that touch at a
    corner only are a spacing violation of 0.

    Spacing. Two shapes of different nets on one layer closer than asked,
    edge to edge (corner to corner on the diagonal). The box is the gap
    between the two. It is checked twice and reported apart:
      tech    the tech LEF: SPACING, and the SPACINGTABLE
              PARALLELRUNLENGTH and TWOWIDTHS value for the widths of
              the two shapes and the length they run side by side. A row
              or column applies when the width or run length is larger
              than its value (not equal). The largest of them counts.
      custom  the route rule: the spacing of the rule of either shape,
              the larger of the two. A rule belongs to the wires drawn
              with it: route_net wires and shields (the net's rule) and
              route_final_stub stub wires and their shields (the stub's
              rule when it has one, else its net's). Straps, pin wires and
              extensions have no rule: they are drawn by the pin routing.
              The default rule is the tech: no custom check.
    A violation of both is listed in both.

    Width. A wire narrower than asked; the box is the wire:
      tech    its smaller side is less than the layer's MINWIDTH (WIDTH
              when the layer has none)
      custom  across the layer's direction it is less than the width of
              its route rule
    Pieces of one net that continue each other (a strap and its
    extension) count as one wire. Via pads and pins are not checked for
    width.

    Opens. A via joins the shapes of its net on its two layers that lie
    over it, and the vias of a stack join each other; shapes on one layer
    join when they overlap or abut; the shapes of a pin are joined in the
    cell.
      signal  a net must be one piece: every part with no path to
              the driver pin is one open (a load pin, a piece of wire).
              On the net of a port, which is not checked itself, every
              part with no path to the largest piece is.
              A stub that route_final_stub has not routed is an open.
      power   the power grid above the routing is not in the database:
              a power net is fed through its shields, as for route_net
              (HT4-177) and optimize_pg_connection. A piece of a power
              net without a strap (a shield tied to no cell) is an open,
              and when the net has shields, a strap with no path to one.
    A net of a pin without a pin wire is not checked.

    -layer_range. Only the shapes on the layers from <bottom> to <top>
    (in the order of the tech LEF, both included) are checked, and the
    vias between two of them. For opens the question is then whether
    each net is connected from bottom to top: of the layers of the range
    the net has shapes on, the lowest and the highest are taken, and a
    piece that has a shape on the lowest and none on the highest is an
    open. So with -layer_range H2:IA a pin wire on H2 that reaches no
    strap on IA is an open; a break higher up is not seen.

    Output. First what was checked, then a table with the count of each
    check per layer, then one line per violation:
      shorts    <layer> {x1 y1 x2 y2}  <shape> (<net>) and <shape> (<net>)
      spacing   <layer> {x1 y1 x2 y2}  <is> < <asked>  the two shapes
                and where the value comes from
      width     <layer> {x1 y1 x2 y2}  <is> < <asked>  the wire
      opens     {x1 y1 x2 y2}  the net and the part that is cut off
    The shapes are named by their handles (net_wire:, strap:, pin_wire:,
    via:, pin:), which get_db, select_obj and move_wire take. With -file
    the lines of the violations go to the file only. A spacing table the
    check does not read (LEF58 properties, other kinds) is named with its
    layer: spacing on that layer is checked against the rest only.

    GUI. With the window open (gui_show), the violations are also listed
    in the DRC Violations table under the layout; a window opened later
    lists the last run. A click on a violation shows only its nets
    (show_only), selects its shapes and zooms to its box, to debug it
    (see 'man gui_show'). Each violation also gets a marker at its box
    on the layout (a white box with a cross), shown while Violation
    markers is ticked in the Objects of the View panel. The table and
    the markers are this run: run check_drc again after a fix.

    Routing direction (the whole design, every check: not with an -only
    option or -layer_range). Each routed signal pin of a cell is reached
    vertically or horizontally: from where the net touches the pin (its
    strap, or its pin wire when it has none), the net's wires are
    followed out, nearest first along the route, and the first one at
    least -direction_jog um long (default 10) gives the way: on a vertical
    layer vertical, on a horizontal one horizontal. Shorter pieces on the
    way (a drop onto a strap, a jog) are passed over; a pin whose net has
    no wire that long is not counted. Two rows: direction mixed, a cell whose pins are reached both ways
    (heterogeneous routing direction: no cell should need both), and
    direction spec, a pin reached against the routing_direction of the
    cell's pin spec (route_pin, read_pin_spec). A pin the route does not
    reach is not counted.

OPTIONS
    -check_shorts_only
        Only the shorts.
    -check_spacing_only
        Only spacing and width, tech and custom.
    -check_open_only
        Only the opens.
        One of the three at most. Default: all checks.
    -layer_range <bottom>:<top>
        The layers to check, as in H2:IA; one layer name checks that
        layer. Default: every layer.
    -file <file>
        Write the report (what was checked, the table and every
        violation) to this file; the table is still printed.
    -overwrite
        Replace the file when it exists.
    -direction_jog <um>
        Wires shorter than this are jogs for the routing direction check:
        passed over. Default 10.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The number of violations.

EXAMPLES
    htree> check_drc
    check_drc: every layer
      Shapes: 68 wires, 0 via pads, 40 pin shapes on M1 D12 H2 IA IB
      Vias  : 107, 107 without a definition (no pads: checked as connections only)
      Nets  : 5 signal nets, 2 power nets
      Check     Rule    Layer   Violations
      --------- ------- ------- ----------
      short     -       IA      6
      spacing   tech    -       0
      width     tech    -       0
      spacing   custom  -       0
      width     custom  -       0
      open      signal  -       0
      open      power   -       0
      Total                     6
    Shorts: 6
      IA {4.2 7.7 4.44 8.42}  strap:sp_L2_inv1/5 (sp_L1_inv1_Y) and strap:sp_L3_inv1/5 (sp_L2_inv1_Y) overlap 0.24 x 0.72
      ...
    **WARN: (HT4-250): check_drc: 6 violation(s)
    htree> check_drc -check_open_only -layer_range H2:IA
    htree> check_drc -check_spacing_only -layer_range IA:IB -file drc.rpt -overwrite
    htree> if {[check_drc -check_shorts_only] > 0} { puts "shorts" }

ERRORS
    HT4-001  more than one -check_..._only option, -overwrite without
             -file, or an unknown option
    HT4-025  no tech data: run read_tech first
    HT4-247  -layer_range is not <bottom>:<top>, or names a layer the
             tech does not have
    HT4-248  the file exists; use -overwrite
    HT4-249  the file cannot be written
    HT4-250  WARN: the number of violations found

SEE ALSO
    route_pin, route_net, route_final_stub, optimize_pg_connection,
    create_route_rule, assign_via_for_route, get_obj_in_area, select_obj,
    show_only, gui_show
