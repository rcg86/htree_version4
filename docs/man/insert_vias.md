NAME
    insert_vias - insert vias where wires of one net cross on two layers

SYNOPSIS
    insert_vias -top_layer <layer> -bottom_layer <layer>
                [-area {x1 y1 x2 y2}] [-via_ref <via_defs>] [-nets <nets>]

DESCRIPTION
    Finds the crossings of the two layers and puts a via at each one: in
    the whole design, every net, or with -area in that rectangle only.

    A crossing is where a wire on -bottom_layer and a wire on -top_layer
    of the same net overlap. The wires are the route shapes: route_pin
    straps and pin wires, and net wires (wires, extensions, stubs,
    shields). The net is the one the wire carries: a shield and a power
    strap are on their power net (VSS, VDD_SOC), so shields are tied to
    the straps and pin wires of their net. Wires of two different nets
    get no via (it would short them), and the straps of pins that are not
    routed yet (net SIGNAL) get none.

    Instance pins. A rectangle of an instance pin on -bottom_layer is a
    shape of the pin's net: where a wire of that net on -top_layer lies
    over it, that is a crossing and gets a via. Every rectangle of the
    pin is taken by itself, so a pin of two rectangles under one wire
    gets two vias (two stacks), one on each. The net of a pin is the net
    its pin wire carries (route_pin, route_net: so a power pin is on
    VDD_SOC or VSS), else its net of the netlist (get_db pin:<inst>/<pin>
    .net); a pin on no net gets none. The rectangles under a pin's own
    pin wire have their vias from route_pin: "Already there". The report
    counts the pin crossings ("On pins"). Pin shapes on -top_layer and
    the ports of the design are not looked at.

    The crossing box is the overlap of the two wires, whatever its shape:
    two wires that run along each other give one box and one via at its
    centre. With -area, only a crossing whose whole box lies inside the
    area gets a via (an edge on the area's edge is inside); the crossings
    partly inside are counted in the report.

    Each crossing gets one via when one cut layer lies between the two
    layers, and else a stack: one via per cut layer at the same point,
    lowest first (H2 to IA: H2/G1, G1/G2, G2/IA). The cut layers between
    two layers come from the via definitions (man assign_via_for_route).
    When no definitions join the two layers the crossing gets one via
    with no cut layer.

    Via definitions. -via_ref names the definitions to use, one for each
    pair of layers of the way from -bottom_layer to -top_layer, or for
    some of them. A pair without one uses the definition
    assign_via_for_route names for those layers and that net, if any;
    else the via has no definition and its shape is the crossing box (the
    GUI draws a box with a cross). The -via_ref definitions belong to the
    vias inserted by this command only, and stay theirs when the
    assignments change.

    Not inserted:
      - a crossing where the net already has its vias (a crossing box of
        the router, a route_pin via, an auto via, or an insert_vias via
        of before): "Already there". When some of the vias of a stack
        are there, only the missing ones are added. So the command can be
        run again; run again with another -via_ref it changes the
        definitions of the vias it inserted before, and adds none.
      - a crossing where a wire of another net lies on a layer between
        the two, over the crossing box: the stack would short the two
        nets. Each one is reported (HT4-277).

    Not checked: that the pads of a definition fit the wires (width,
    enclosure) and keep their spacing to other nets. check_drc reports
    the shorts and spacing of via pads, and the opens the vias close.

    An inserted via is a via object of kind insert on its net (get_db
    vias; .source is its crossing box). The box is stored as a net_wire of
    kind insert_via under the wire on -top_layer (net auto_via:<wire
    handle>, layer <bottom>/<top>, .shield_net its net), as the auto vias
    of stretch_wire are, and follows that wire the same way: it is
    removed when the wire is moved (move_wire), deleted (delete_wire),
    stretched off the crossing, or rebuilt (route_pin, route_net), and it
    moves with the wire's instance or spine. It does not follow the wire
    on -bottom_layer: when that one is moved or deleted the via stays
    until it is deleted. To delete inserted vias:
        delete_wire -wires [get_db <vias> .source]
    write_def does not write vias yet.

OPTIONS
    -top_layer <layer>
        The upper of the two layers: a routing layer of the tech.
        Required.
    -bottom_layer <layer>
        The lower of the two layers: a routing layer below -top_layer in
        the tech. Required.
    -area {x1 y1 x2 y2}
        The rectangle to look in, in microns (any two opposite corners).
        Default: the whole design, every crossing of the two layers.
    -via_ref <via_defs>
        The via definitions to use, as a Tcl list of names or via_def:
        handles (get_db via_defs). Each must join two layers of the way
        from -bottom_layer to -top_layer, and no two the same pair.
        Default: the definitions of assign_via_for_route, or none.
    -nets <nets>
        Insert vias only on these nets: names, glob patterns (clk_*), or
        net objects (net:, spine_net:, stub: for the net of the stub), as
        a Tcl list. Power nets are given by name. Default: every net.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the vias inserted (via:<net>/<n>), one per cut layer
    of each crossing; empty when none was inserted.

EXAMPLES
    htree> insert_vias -bottom_layer IA -top_layer IB -area {0 0 20 40}
    insert_vias: IA to IB in {0 0 20 40}: 19 crossing(s) of wires of one net
      Inserted      : 1 via(s) at 1 crossing(s) (cut layers C6)
      Nets          : VSS(1)
      Definitions   : none; 1 via(s) have none (-via_ref, assign_via_for_route)
      Already there : 18 crossing(s)
    via:VSS/21
    htree> insert_vias -bottom_layer IA -top_layer IB
    htree> insert_vias -bottom_layer D12 -top_layer H2 -nets u1_Y
    insert_vias: D12 to H2 in the design: 3 crossing(s) of wires of one net
      On pins       : 3 of them a wire over a pin rectangle on D12
      Inserted      : 6 via(s) at 3 crossing(s) (cut layers C1 C2)
      Nets          : u1_Y(3)
      Definitions   : none; 6 via(s) have none (-via_ref, assign_via_for_route)
    via:u1_Y/1 via:u1_Y/2 via:u1_Y/3 via:u1_Y/4 via:u1_Y/5 via:u1_Y/6
    htree> insert_vias -bottom_layer H2 -top_layer IA -area {0 0 20 40} \
               -nets {VSS VDD_SOC} -via_ref {V_H2_G1 V_G1_G2 V_G2_IA}
    htree> insert_vias -bottom_layer IA -top_layer IB -area {0 0 20 40} \
               -nets {sp_L3_* spine_net:sp/sp_L1_inv1_Y} -via_ref V_IA_IB_2
    htree> set made [get_db vias -if {.kind == insert}]
    htree> delete_wire -wires [get_db $made .source]

ERRORS
    HT4-001  -top_layer or -bottom_layer missing, -via_ref or -nets empty,
             or an unknown option
    HT4-245  -area is not four numbers
    HT4-272  a layer is not a routing layer of the tech, or -bottom_layer
             is not below -top_layer
    HT4-273  -via_ref: no such via definition
    HT4-274  -via_ref: the definition does not join two layers of the way
             from -bottom_layer to -top_layer
    HT4-275  -via_ref: two definitions for the same pair of layers
    HT4-276  -nets: no net of that name with route wires
    HT4-277  (warning) a crossing got no via: a wire of another net lies
             on a layer in between
    HT4-286  (warning) no via on a wire of a fixed net (set_db
             .route_status fixed)

SEE ALSO
    assign_via_for_route, get_obj_in_area, delete_wire, stretch_wire,
    check_drc, get_db
