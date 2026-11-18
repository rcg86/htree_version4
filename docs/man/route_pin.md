NAME
    route_pin - add horizontal straps over an instance, one per net, and a
    vertical wire from each pin to a strap of its net

SYNOPSIS
    route_pin -inst <insts> [-spec <yaml>] [-layer <layer>]
              [-nets {net ...}] [-width <width>] [-spacing <spacing>]
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
        are not routed (warning).
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
        Pin routing spec file (a 'pin_routing:' section). Default: the
        built-in spec above.
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
    HT4-166  WARN: a pin is missing from the cell, has no shape on the
             pin layer, or its net has no strap in the stack; more signal
             pins than SIGNAL straps; a pin shape not under its wire
    HT4-167  the -spec file cannot be read, is not valid YAML, has no
             'pin_routing:' section, or has an unknown key or a bad value;
             the -dump file cannot be written
    HT4-168  the -dump file exists (use -overwrite)
    HT4-286  WARN: an instance with straps or pin wires on a fixed
             net is not routed again (set_db .route_status fixed)
    HT4-297  WARN: vias that no definition of their layer pair fits

SEE ALSO
    create_inst, create_route_rule, assign_track_for_route, get_db,
    gui_show, assign_via_for_route
