NAME
    assign_via_for_route - name the via definition the routes use between
    two layers

SYNOPSIS
    assign_via_for_route -via <via_defs> [-nets <nets>]
    assign_via_for_route -reset [-nets <nets>]
    assign_via_for_route

DESCRIPTION
    Vias. A via is where a route changes layer: one cut layer at one
    point. The database has a via object for every layer change of the
    routing:
      cross       a crossing box of route_net
      stub_cross  a crossing box of route_final_stub
      pg_cross    a crossing box of optimize_pg_connection
      auto        a via stretch_wire added
      pin         a route_pin pin wire over the pin shape it starts from
      strap       a route_pin pin wire under the strap it reaches
    The via objects are derived from the routing each time it changes:
    the routers still write a layer change as a crossing box (a net_wire
    whose layer is <layer>/<layer>), and the via's .source names the box
    or pin wire it stands for. Two boxes of one net on the same layers at
    the same place (a stub that joins its leaf net where the route already
    changes layer) are one via.

    Stacks. Layers more than one cut apart are joined by a stack: one via
    per cut layer at the same point, lowest first. Which cut layers lie
    between two layers comes from the via definitions (the bottom, cut and
    top layer of each), not from the order of the layers in the tech LEF.
    When no chain of definitions joins the two layers, the change is one
    via with no cut layer.

    Via definitions (via_def) are the VIA blocks of the tech LEF
    (read_tech) and the entries of the DEF VIAS section (read_def). A DEF
    via replaces a LEF via of the same name.

    This command names the definition the vias use. A via between two
    layers has no definition until one is assigned for those layers: its
    .rect is then the box where the two wires overlap. With a definition,
    its shapes are the definition's, centred on the box.

    -via names one definition per pair of layers; each is used for every
    via between its bottom and top layer. Without -nets the assignment is
    for every net that has none of its own; with -nets, for those nets
    only. A new assignment for the same layers and net replaces the old
    one (HT4-243). Assignments are kept in the database (write_db), and
    apply to vias made later: route the nets before or after.

    Without options the assignments are printed, with the number of vias
    that use each, and the vias that have no definition by layer pair.

    Not checked: that the definition's pads fit the wires they land on
    (width, spacing, enclosure). write_def does not write vias yet.

    The GUI draws the vias (Vias checkbox, and a via_<bottom>_<top> row
    of Layers between the two layers, with S P G boxes for the vias of
    signal, power and ground nets): a via without a definition as its
    box with a cross, one with a definition as the definition's cuts and
    pads at its place. See 'man gui_show'.

OPTIONS
    -via <via_defs>
        Via definition names or via_def: handles as a Tcl list, at most
        one per pair of layers.
    -nets <nets>
        Net names, spine_net: or stub: handles (a stub: its leaf net), as
        a Tcl list. A power net is named as its shields and pin wires
        are (VSS, VDD_SOC). With -via: assign for these nets only. With
        -reset: remove the assignments of these nets only.
    -reset
        Remove the assignments: the vias have no definition again. Not
        with -via.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    via_def:<name>
        a via definition: obj_type, name, source (lef | def), default
        (true: VIA ... DEFAULT), via_rule (the VIARULE it is generated
        from), bottom_layer, cut_layer, top_layer (empty when its shapes
        are not on one cut layer between two layers of the tech), layers
        (as written), cuts (number of cut shapes), rect (bounding box
        about its origin), shapes ("layer x1 y1 x2 y2" each; a polygon:
        every point), extra (statements not modeled), text (as written)
    via:<net>/<n>
        the n-th via of a net: obj_type, name (n), net (the electrical
        net: a shield's via is on its power net; the vias of pin wires
        route_net has not named yet are on SIGNAL), kind (above), via_def
        (handle; empty when none is assigned), bottom_layer, cut_layer
        (empty: no definitions join the two layers), top_layer, location
        ("x y", its centre), rect (what it covers: the definition's shapes
        at its location, else the box), box (where the two shapes it
        joins overlap), shapes (the definition's, placed; empty without
        one), source (the net_wire or pin_wire it stands for)
    get_db via_defs and get_db vias list all. spine_net:<spine>/<net>
    .vias lists a net's vias; stub:<spine>/<stub> .vias those of its leaf
    net that land on the stub's wire. The numbers of a net's vias follow
    its routing: they change when the net is routed again or edited.

RETURN VALUE
    None. Prints the assignments.

EXAMPLES
    htree> get_db via_defs -if {.bottom_layer == IA} .name
    VIA_IA_IB VIA_IA_IB_WIDE
    htree> assign_via_for_route -via {VIA_IA_IB VIA_G2_IA}
    Via assignments (layers, cut layer, net, via definition, vias using it):
      IA/IB      C6     (every net)      VIA_IA_IB  11
      G2/IA      C5     (every net)      VIA_G2_IA  16
    Vias: 91, with a definition 27, without: D12/H1(16) H1/H2(16) H2/G1(16) G1/G2(16)
    htree> assign_via_for_route -via VIA_IA_IB_WIDE -nets [get_db nets *L1*]
    htree> get_db [get_db nets *L1*] .vias
    via:sp_L1_inv1_Y/1 via:sp_L1_inv1_Y/2 ...
    htree> get_db via:sp_L1_inv1_Y/1 .via_def
    via_def:VIA_IA_IB_WIDE
    htree> assign_via_for_route -reset -nets [get_db nets *L1*]

ERRORS
    HT4-001  -via with -reset, -nets without -via or -reset, an empty list,
             or an unknown option
    HT4-022  a spine_net: or stub: handle of -nets does not exist
    HT4-240  no via definition of that name
    HT4-241  the definition's shapes are not on one cut layer between two
             layers of the tech
    HT4-242  two definitions of -via join the same two layers
    HT4-243  WARN: an assignment was replaced
    HT4-244  WARN: a net of -nets has no via now (the assignment is kept)

SEE ALSO
    get_db, get_obj_in_area, read_tech, read_def, route_net, route_pin,
    route_final_stub, stretch_wire
