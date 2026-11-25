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
    .net); a pin on no net gets none. The report counts the pin
    crossings ("On pins"). Pin shapes on -top_layer and the ports of the
    design are not looked at.

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

    Via definitions, per pair of layers of the way from -bottom_layer to
    -top_layer, the first of:
      1. the one -via_ref names for the pair;
      2. a via generated to fill the crossing, when the tech has a
         VIARULE ... GENERATE for the pair (DH_VIAGEN for D12/H1,
         N1_VIAGEN for H1/H2 ...): of all the arrays of the rule's cuts,
         the one with the most cuts whose cuts lie inside the crossing
         box and whose pad lies inside the wire on that layer (on a layer
         inside a stack, which has no wire: inside the box), centred on
         the box. The cuts are as far apart as the rule's SPACING (centre
         to centre), at least the cut's own width apart (N1_VIAGEN's
         SPACING 0.064 equals its cut). Each layer's two ENCLOSURE values
         are tried either way round. The definition is made once, named
         <rule>_<rows>x<columns>_<enclosures in nm> (DH_VIAGEN_4x3_18_18_
         0_26: 4 rows of 3 cuts, D12 enclosure 0.018 0.018, H1 0 0.026),
         get_db via_defs lists it, and write_def writes it in VIAS;
      3. the definition assign_via_for_route names for those layers and
         that net, if any; else the via has no definition and its shape
         is the crossing box (the GUI draws a box with a cross).
    The definitions belong to the vias inserted by this command only, and
    stay theirs when the assignments change. Not checked for a generated
    array: the cut layer's LEF58 rules beyond the cut width and spacing
    (adjacent cuts, array spacing), and the spacing of its pads to other
    nets; check_drc reports these.

    Run again. Each run first removes the vias insert_vias made before,
    of the nets given (-nets; else every net), joining layers from
    -bottom_layer to -top_layer (both ends in that range) and, with
    -area, inside the area; then it inserts at every crossing again. The
    report says how many were removed. Vias on wires of fixed nets stay.

    The vias of the router and of route_pin. An inserted via takes the
    place of a via the routing has at the same crossing (a crossing box
    of route_net, a pin wire on its pin or strap): the net keeps one via
    per layer change there, the inserted one. When the inserted vias are
    deleted, the routing's come back.

    Not inserted:
      - a crossing where a wire of another net lies on a layer between
        the two, over the crossing box: the stack would short the two
        nets. Each one is reported (HT4-277).
      - a crossing where no via definition of the layers (-via_ref's,
        when given; else not even one cut of the VIARULE) fits on the two
        wires: placed at the middle of the crossing box, its pad on each
        of the two layers must lie inside that layer's wire, and its cut
        inside both. Where a wire only just
        overlaps the end of a strap, the box is narrower than any pad, and
        the pad would stick out of the metal towards other nets (HT4-311).
        The layers inside a stack, which have no wire, are not looked at.

    Not checked: the spacing of the pads to other nets' shapes (a pad
    inside its wire keeps the wire's spacing). check_drc reports the
    shorts and spacing of via pads, and the opens the vias close.

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
        Default: a via generated from the tech's VIARULE for the pair,
        else the definition of assign_via_for_route, or none.
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
    insert_vias: IA to IB in {0 0 20 40}: 1 crossing(s) of wires of one net
      Inserted      : 1 via(s) at 1 crossing(s) (cut layers C6)
      Nets          : n(1)
      Definitions   : GEN_IA_IB_2x2_50_20_20_50(1)
    via:n/1
    htree> insert_vias -bottom_layer IA -top_layer IB -area {0 0 20 40}
    insert_vias: IA to IB in {0 0 20 40}: 1 crossing(s) of wires of one net
      Removed       : the vias insert_vias made before at 1 crossing(s) here, made again
      Inserted      : 1 via(s) at 1 crossing(s) (cut layers C6)
      ...
    htree> insert_vias -bottom_layer D12 -top_layer H2 -nets u1_Y
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
    HT4-311  (warning) a crossing got no via: no via definition of the
             layers fits on the two wires there
    HT4-286  (warning) no via on a wire of a fixed net (set_db
             .route_status fixed)

SEE ALSO
    assign_via_for_route, get_obj_in_area, delete_wire, stretch_wire,
    check_drc, get_db
