NAME
    route_pin - add horizontal straps over an instance, one per net, and a
    vertical wire from each pin to a strap of its net

SYNOPSIS
    route_pin -inst <insts> [-spec_name <name> | -spec <yaml> [-spec_name <name>]]
              [-layer <layer>] [-nets {net ...}] [-width <width>]
              [-spacing <spacing>]
    route_pin -dump <yaml> [-overwrite] [-spec <yaml>] [-layer <layer>]
              [-nets {net ...}] [-width <width>] [-spacing <spacing>]

DESCRIPTION
    Adds a stack of horizontal straps over a placed instance, one strap
    per net in -nets, listed top to bottom. Every strap is -width tall and
    the straps are -spacing apart (edge to edge), so the pitch is width +
    spacing. Each strap is exactly as long as the instance is wide (its
    bbox x1 .. x2). The stack is centred on the instance in y.

    Then each connected pin gets one vertical wire on the vertical layer
    (pin wire):
      - width: the pin's width on the pin layer; a pin with several
        shapes (VDD, VSS in two pieces) takes its widest shape, and the
        wire runs at that shape's x span;
      - length: over the whole strap stack, top strap to bottom strap,
        and over all the pin's shapes (so the pieces are joined); every
        wire crosses every strap, and vias will pick the connections;
      - strap: the strap of its net the wire is to connect to. Power nets
        (VDD_SOC, VSS) take the nearest strap of their net. SIGNAL straps
        are placeholders for signal nets: A and Y are different nets, so
        each signal pin gets a SIGNAL strap of its own, by where the pins
        lie in the placed cell: the higher pin (the centre of its shapes)
        the higher SIGNAL strap; of pins as high, the input first. Turning
        the cell about the x axis (N to FS) so swaps their straps;
        legalize_placement turns a cell so its input faces the net coming
        in. With fewer SIGNAL straps than signal pins, the pins left over
        are not routed (warning). The netlist knows each pin's net, so a
        signal pin wire and the SIGNAL strap it lands on are put on that net
        at once ("on their nets (netlist)"): their vias (pin to pin wire,
        pin wire to strap) are the net's and get their definitions now, and
        route_net, delete_route and check_drc see them as the net's. A pin
        on no net stays SIGNAL.
    Vias. A pin wire has a via to its strap and one to every rectangle
    of its pin under it: a pin of two rectangles is connected at both.
    The rectangles are the pin's shapes on the highest tech layer below
    the pin wire's layer. They are via objects (get_db vias, kinds strap
    and pin; man assign_via_for_route), derived from the pin wire: a
    stack of one via per cut layer.

    The defaults are the pin_connect spec (runs/pin_connect.rpt):
        nets     VSS VDD_SOC SIGNAL VSS SIGNAL VDD_SOC VDD_SOC
        width    0.72
        spacing  0.72 (pitch 1.44)
        pins     shapes on D12; straps on IA (horizontal_layer), pin
                 wires on H2 (vertical_layer); VDD -> VDD_SOC,
                 VSS -> VSS, A -> SIGNAL, Y -> SIGNAL (VNW, VPW not
                 connected)
    which gives a stack 9.36 um tall edge to edge (10.08 um tileable).

    The spec can be kept in a YAML file and given with -spec;
    runs/pin_routing_spec.yaml holds the defaults above, to edit:

        pin_routing:
          cell_pattern: '*'
          width: 0.72
          spacing: 0.72
          max_strap_extension: 3
          nets: [VSS, VDD_SOC, SIGNAL, VSS, SIGNAL, VDD_SOC, VDD_SOC]
          pins:
            layer: D12
            horizontal_layer: IA
            vertical_layer: H2
            nets: {VDD: VDD_SOC, VSS: VSS, A: SIGNAL, Y: SIGNAL}

    Every key is optional (a missing one keeps its default); an unknown
    key is an error. Values come from the defaults, then the -spec file,
    then -layer, -nets, -width and -spacing on the command line. The file
    is read each time; it is not stored in the database.

    route_pin -dump <yaml> writes the spec in force (the defaults, then
    -spec, -layer, -nets, -width and -spacing) to a file in this layout,
    with comments, to edit and give back with -spec. It needs no -inst
    and routes nothing. Comments of a -spec file are not carried over.

    cell_pattern (default *: every cell) says which cells the spec is
    for: a glob on the library cell name (* any text, ? one character,
    [..] one of), or a list of them, case sensitive. An instance whose
    cell matches none is not routed: the report lists it with its cell,
    and HT4-306 warns when no instance is left to route. For example
        cell_pattern: INV12M3Mx2Fx7Dx_D*_N_S7P94TSL_C60L04
        cell_pattern: [INV12M3*, 'BUF_?P']
    (quote a pattern with ? or [ in a [..] list.)

    routing_direction (default null: either way) says how the nets come to
    the cells of the spec, and route_net keeps to it: vertical, from above
    or below (onto a strap along the vertical layer; no side pins are made
    for such a cell); horizontal, from the left or the right (onto a side
    pin along the horizontal layer, or onto a strap from the horizontal
    layer). A net that cannot reach a pin that way is not routed to it
    (HT4-174 says "in the routing direction of its pin specs").

    pins.horizontal_layer none (a net reached from the left or the right:
    horizontal_routing): no straps at all. Each pin of pins.nets gets its
    pin wire on vertical_layer alone. A signal pin whose net has a wire on
    the horizontal signal layer already across the pin's column within
    reach (its route, or the stub wire of a leaf's net under the cell) has
    its pin wire go on to that wire: joined there (route_pin's pin vias),
    nothing left to route. A leaf's output whose stub is not routed yet
    goes on to the track route_final_stub would lay the stub on as things
    are (its stub plan; the signal track nearest the stub's line when no
    route rule is made yet), when that line runs across the pin's
    column within reach; that track is kept for the stub: no other pin of
    a cell the stub crosses lands on it. These targets are taken first,
    the other pins' tracks are looked for after. A signal pin's wire goes on to the
    nearest signal track of the horizontal signal layer (the track
    assignment's) free across the cell and out past its edge on the side
    its net comes from, as a side pin's, and route_net brings the net in
    along that track onto it. A power pin's wire goes on to the nearest
    track the track assignment gives its net on that layer (VDD_SOC, VSS):
    insert_pg_grid -layer IA lays the power wire there, and insert_vias
    -bottom_layer H2 -top_layer IA joins the pin wire to it (until then
    check_drc reports it as a power open; route_net -shield does not join
    a pin with no strap). Both extensions keep clear of other nets' shapes
    on the pin wire layer; with no track near (two cell heights + 10 um) a
    wire covers its pin only. nets and width do not apply; a key left out
    still means the built-in IA, so write none.

    max_strap_extension (default 3, microns, >= 0) is how far route_net
    may extend a strap past each instance edge to meet the vertical wire of
    the net's route (see route_net). It is stored with each strap
    (.max_extension); the strap itself keeps the instance width.

    Running route_pin again on an instance replaces its straps and pin
    wires.

    To show whether the spec works, route_pin reports:
      - the tech checks: width against the layer minimum width, spacing
        against the tech spacing for a wire of this width, and, for two
        adjacent straps of one net, the width and tech spacing they would
        have merged into one strap (they are kept as two);
      - strap edges off the manufacturing grid;
      - whether each strap centre is on a DEF TRACKS Y track of the
        layer, and the shift that would put the whole stack on tracks;
      - each pin wire: its strap, x span and width, y span and length;
        a pin shape not under the wire (it takes the widest shape's x
        span); a wire narrower than the vertical layer's minimum width;
        two wires side by side closer than the vertical layer's tech
        spacing; a vertical layer that is not vertical in tech.

    Straps and pin wires are shown in the GUI in their layer colour,
    see-through, under the "Routes (route_pin, route_net)" checkbox and the layer
    checkboxes; Label writes each strap's net and each pin wire's pin on
    it. They can be selected (click, Shift+drag, right drag) or with
    select_obj. write_db saves them. The vias of a pin wire, over each
    rectangle of its pin and under its strap, are drawn under the Vias
    checkbox, each with its via_<bottom>_<top> row of the layer list.

    Via definitions. At the end, every via of the routing that has no
    via definition gets one: for each net and layer pair with no
    assignment of assign_via_for_route (neither the net's own nor one for
    every net), the definition of those layers that fits the most of the
    net's vias, each pad inside the net's own metal on its layer (wires,
    straps, pin wires, pin shapes) and each cut inside both. A DEFAULT via
    of the tech LEF comes before another (a power via the DEF generated),
    then, of those that fit every via, the one with the most cuts, then
    pads that run the way their layers do, then the smallest pads. The
    choice is stored as the net's assignment (assign_via_for_route lists
    it and can change it), so write_def writes every via. Printed: the
    definitions given, per layer pair, with the number of nets and vias;
    HT4-297 when no definition of a pair fits some of the vias.
    Before the definitions are chosen, every crossing box is made the
    full crossing of its net's two wires: the vertical wire's width by the
    horizontal wire's width, so each via sits in the middle of the
    crossing. A routed wire that stops short of the other wire's far edge
    is lengthened to it (no further than the box is long); straps, pin
    wires and pins are not. Fixed nets are left. Printed: how many boxes
    moved and wires lengthened.
    A via of a crossing box that its net's definition does not fit (its
    pads past the metal there) while another of the same layers does gets
    that one as its own, kept on the box as insert_vias -via_ref keeps one
    (of those that fit, the first in the order above); the net's
    assignment stays. Every net's vias are looked at, not only the nets
    routed. Printed: how many vias, per layer pair.

    A piece of each layer between the pin layer and the pin wire layer
    (pins.layer and pins.vertical_layer: H1, between D12 and H2) under
    every pin wire: as wide as the pin wire, from the bottom of the cell
    to its top, on the pin's net (power or signal). The vias from the pin
    up to its pin wire then land on metal of every layer they join, as
    Innovus draws a clock pin's H1. It is a net_wire of kind pin_layer
    under pg:<inst> (as optimize_pg_connection's
    pieces are kept), so it moves with the instance, goes when route_pin
    routes the instance again (made again with the new pin wires), and
    optimize_pg_connection keeps it. write_def writes it on the pin's net.
    It is not a crossing for stretch_wire's auto vias or insert_vias: the
    pin's via stack goes through it already.

    Pins reached from the side. A signal pin whose net comes from the
    left or the right gets no strap. Where the net comes from: for an
    input pin the nearest of its driver, the stubs its driver drives and
    the net's routed wires; for an output pin the nearest of its loads and
    the stubs it drives. From the side when that point is farther from
    the pin along x than along y. Its pin wire (H2) is extended to the
    nearest signal track of the strap layer (IA) within the strap stack's
    height of the stack, clear of the cell's other straps by the route
    rule's width and spacing (at least the straps' own), and with a free
    way out on that track to the first vertical signal track past the
    cell's edge on that side (other cells' straps and side pins, other
    nets' wires). route_net brings its wire along the track onto the pin
    wire, with an H2/IA crossing box for the via, and keeps that way free
    of other nets' strap extensions. With no such track the pin keeps its
    strap, and the report says so. The other straps are numbered on, top
    first. A pin whose net comes from above or below keeps its strap.

    Pin vias. After the instances are routed, route_pin runs insert_vias
    from the pin wire layer to the strap layer (H2 to IA by default) over
    each of them (the box of its straps and pin wires), so a pin wire is
    joined to every strap of its net it crosses: a signal pin wire to its
    strap, a power pin wire to both straps of its net. One line reports
    how many vias were inserted and how many crossings had theirs
    already; the vias then get their definitions with the rest
    (Via definitions). An instance left as it is (on a fixed net) gets
    none.

OPTIONS
    -inst <insts>
        Instance names, glob patterns (*temp_*) or inst: handles, as a Tcl
        list: [get_db insts], [get_db insts .name] and {u1 temp_L7*} all
        work. Every word must match an instance; all are checked before
        any is routed, and each is routed as one route_pin -inst would.
        Required unless -dump.
    -dump <yaml>
        Write the spec in force to this file and stop (nothing is routed).
    -overwrite
        With -dump, replace the file if it exists.
    -spec <yaml>
        Pin routing spec file (a 'pin_routing:' section). Default (no
        -spec, no -spec_name): each instance its own spec, the one set_db
        inst:<name> .pin_spec gave it or the one it was last routed with,
        else the built-in spec above; its old pin routes and pin vias are
        removed and made again with it. A file of named specs (pin_routing:
        {vertical_routing: {...}, horizontal_routing: {...}}) needs
        -spec_name when it names more than one.
    -spec_name <name>
        A named spec: one read_pin_spec read into the database (no -spec),
        or one of the -spec file. The instance keeps the name (get_db
        inst:<name> .pin_spec) and the spec's values, so legalize_placement
        can make its pin routes again.
        auto: each instance the named spec (of -spec's file, else of those
        read_pin_spec read) whose routing_direction is the way its nets
        run there: from the middle of the cell to every other pin and port
        on the nets of its pins (the cell before it and the cells after
        it), the x distances summed against the y ones; horizontal when x
        is more, else vertical (also a cell on no net). The first spec of
        each direction is taken. On a comb-shaped die the cells of a
        buffer tree down the spine get the vertical spec, those along the
        arms the horizontal one. The report lists which spec each got. An
        error when no named spec has the direction an instance needs.
    -layer <layer>
        Tech layer of the straps (overrides pins.horizontal_layer).
        Default IA. A warning is given if the
        layer's tech direction is not horizontal.
    -nets {net ...}
        Net of each strap, top to bottom. Default the spec stack above.
        A net may repeat.
    -width <width>
        Strap width (its height in y), microns. Default 0.72.
    -spacing <spacing>
        Edge-to-edge gap between straps, microns. Default 0.72.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    strap:<inst>/<n>
        the n-th strap over an instance, 1 = top: obj_type, name (n), net,
        layer, rect ("x1 y1 x2 y2"), width (in y), length (in x),
        max_extension, inst (handle)
    pin_wire:<inst>/<pin>
        the vertical wire from a pin to its strap: obj_type, name (pin),
        net, layer, rect ("x1 y1 x2 y2"), width (in x), length (in y),
        strap (handle), pin (handle), inst (handle)
    get_db straps and get_db pin_wires list them all; get_db
    inst:<name> .straps and .pin_wires those of one instance.

RETURN VALUE
    The new strap handles, top first, then the pin wire handles. With
    -dump, the file name.

EXAMPLES
    htree> route_pin -inst inst_1
    Straps over inst:inst_1 (INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04) on IA: 7 nets, width 0.72, spacing 0.72, pitch 1.44
      length 3.12 (instance width, x 5622.772 .. 5625.892); height 9.36 edge to edge, 10.08 tileable; centred on the instance (y 10066.7 .. 10068.478)
      ...
    htree> route_pin -inst inst_1 -spec pin_routing_spec.yaml
    htree> route_pin -inst [get_db insts .name] -spec pin_routing_spec.yaml
    htree> route_pin -inst *temp_*
    htree> route_pin -dump my_spec.yaml -width 0.36
    htree> route_pin -inst inst_1 -nets {VSS VDD_SOC SIGNAL VSS SIGNAL VDD_SOC} -width 0.36

ERRORS
    HT4-001  missing -inst, an empty -nets, or a width or spacing that
             is not a positive number
    HT4-025  no tech data loaded (read_tech)
    HT4-160  no instance matches a -inst word, or a cell has no SIZE
    HT4-161  the strap or pin wire layer is not in tech
    HT4-162  WARN: the instance's old straps and pin wires were replaced;
             also when routes had lengthened the old straps: those
             stretches are dropped with them and the nets named, to be
             routed again (route_net)
    HT4-163  WARN: width or spacing below the tech rule (straps or pin
             wires), or a layer not in its direction in tech
    HT4-164  WARN: strap or pin wire edges off the manufacturing grid
    HT4-165  WARN: strap centres not on the layer's tracks
    HT4-301  WARN: insert_vias failed over the instances (its message
             follows); the pin routes are made
    HT4-166  WARN: a pin is missing from the cell, has no shape on the
             pin layer, or its net has no strap in the stack; more signal
             pins than 