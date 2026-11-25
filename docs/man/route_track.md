NAME
    route_track - route nets as route_net does and report the signal
    tracks they use; -compact packs the nets on the fewest tracks

SYNOPSIS
    route_track -net <nets> -rule <route_rule> [-compact]
                [-via_weight <um>] [-shield]
                [-shield_nets {<left/above> <right/below>}]
                [-min_routing_distance <um> [-max_routing_distance <um>]]

DESCRIPTION
    Routes the nets with the router of route_net (man route_net: the two
    layers of the rule, the signal tracks, the pin routes, the design
    boundary, -shield), then prints the table of the signal tracks the
    nets lie on. Without -compact the wires are exactly route_net's; the
    table is what the command adds.

    The table. The tracks are listed in bands: used tracks next to each
    other, with at most 2 empty tracks between two of them. Only a band
    with 25 um of wire or more on one of its tracks is listed (the short
    hops between a pin and its track are not a band). For each band: the
    layer, the tracks from the first to the last, the span of the wires
    along the tracks, the number of signal tracks and how many of them
    are empty. For each track of the band: the wire on it in um, how much
    of the band's length that fills, and the nets. An empty track is a
    signal track of the band that carries no wire of these nets: the
    track to win back. "(stub)" marks a net whose wire on the track is a
    final stub (route_final_stub), "(stub, kept free)" a stub that is not
    routed yet and has the track kept for it (-compact).

    -compact is for a design short of horizontal and vertical tracks. It
    changes the router in three ways:

      - Stub tracks first. The tracks route_final_stub gives the stubs
        of the nets' spines are worked out before any net is routed and
        kept free: no net may lie on them where the stubs will. So the
        stubs take the track next to the cells and no net track is lost
        between them and the cells. A stub routed before on another
        track than the one kept for it has its wires, crossing boxes and
        shields removed (HT4-279); run route_final_stub again. A stub
        already on its track is kept.

      - A net keeps to the tracks of its pins. A wire on a track beyond
        the tracks of the net's pins costs 0.25 of its length more for
        every track further out, on both layers. A net leaves its track
        only to pass what blocks it, takes the nearest free track, and
        comes back. Of tracks that cost the same, the net takes the one
        nearest a stub track of its spine, so the nets lie against the
        stubs and the tracks left empty are the outer ones.

      - Both sides of the driver. A branch of a net may leave the
        driver's strap on any signal track the extended strap covers,
        not only where the first branch left it. Another place on the
        strap costs one layer change (-via_weight), so it is taken only
        when it saves wire.

    Limits of -compact:
      - The nets are routed one after another, in the order of -net; a
        net does not move for a later one. Another order can give
        another result.
      - A net that passes a blocked piece of its track changes layer
        twice more for each one: -compact gives more layer changes than
        route_net for the tracks it saves.
      - The table reports what was used; it is not a proof that fewer
        tracks are impossible.

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

OPTIONS
    -net <nets>
        Net names, glob patterns (sp_L3*), or spine_net: and net:
        handles, as a Tcl list: [get_db nets], [get_db nets .name] and
        {sp_L1_inv1_Y sp_L2*} all work. Every word must match a net. The
        final stubs in the list are left to route_final_stub, as in
        route_net. Required.
    -rule <route_rule>
        A rule from create_route_rule with at least one horizontal and one
        vertical layer. Not 'default'. Required.
    -compact
        Pack the nets on the fewest signal tracks: the stub tracks are
        kept free for route_final_stub, a net keeps to the tracks
        nearest its pins and the stubs of its spine, and a branch may
        leave the driver's strap on either side of the cell (man
        route_track). Default: route as route_net.
    -via_weight <um>
        Cost of one layer change, in um of wire. Default 5; 0 counts wire
        length only.
    -shield
        Add one power shield on each side of every wire of the net (its
        track's net), and join the cells' power straps to them.
    -shield_nets {<left/above> <right/below>}
        Shield nets for a layer with no track assignment (implies
        -shield). Default {VDD_SOC VSS}.
    -min_routing_distance <um>
        The least length of the wire from each net's driver to its
        nearest load, along the route (the drops from the tracks to the
        strap centres not counted). A shorter route goes out and back:
        see route_net, "Route length".
    -max_routing_distance <um>
        The most that length may be; with -min_routing_distance. Default
        -min_routing_distance + 10. A wider window (e.g. 2600 .. 2700)
        leaves the router more ways to make it.
    -force
        Route the fixed nets given too (see route_net;
        without it they are left, HT4-286), keeping every shape they have:
        their wires, their stubs' wires, shields, vias and lengthened
        straps. Only the pins not on the route yet (an input pin
        connect_pin or connect_spine put on the net, a strap still on
        SIGNAL) are routed, from the nearest point of the existing wires;
        only those new wires, their crossing boxes, shields and power links
        are added. The net stays fixed.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the nets that were routed (spine_net:<spine>/<net>,
    net:<name>), as route_net.

EXAMPLES
    htree> route_track -net [get_db nets .name] -rule r
    route_track: signal tracks of the 8 net(s) (bands of tracks next to each other with 25 um of wire or more on one; Filled: of the band's length)
      IB x 70.92 .. 79.56 (y 67.7 .. 132.3): 4 signal track(s), 1 empty
        Track x         Wire um  Filled  Nets
        70.92             16.46     25%  sp_L1_inv1_Y sp_mirror_L1_inv1_Y
        73.8              43.44     67%  sp_L2_inv1_Y sp_mirror_L2_inv1_Y
        76.68                 0      0%  (empty)
        79.56             10.96     17%  sp_mirror_L3_inv2_Y sp_L3_inv2_Y sp_mirror_L3_inv1_Y sp_L3_inv1_Y
    htree> route_track -net [get_db nets .name] -rule r -compact
      compact: every net on the tracks nearest its pins (a wire on a track beyond them costs 0.25 of its length more for every track further out); of equal tracks, the one nearest the stubs of its spine
      compact: tracks kept free for the stubs (route_final_stub): IB x 79.56 (4 stub(s))
    route_track: signal tracks of the 8 net(s) (bands of tracks next to each other with 25 um of wire or more on one; Filled: of the band's length)
      IB x 73.8 .. 79.56 (y 60 .. 140): 3 signal track(s), 0 empty
        Track x         Wire um  Filled  Nets
        73.8              16.46     21%  sp_L1_inv1_Y sp_mirror_L1_inv1_Y
        76.68             43.44     54%  sp_L2_inv1_Y sp_mirror_L2_inv1_Y
        79.56             75.64     95%  sp_mirror_L3_inv2_Y (stub, kept free) sp_L3_inv2_Y (stub, kept free) sp_mirror_L3_inv1_Y (stub, kept free) sp_L3_inv1_Y (stub, kept free)
    htree> route_final_stub -spine sp -rule r
    htree> route_track -net [get_db nets .name] -rule r -shield -compact
    htree> route_track -net {sp_L1_inv1_Y sp_L2*} -rule r -compact -via_weight 10

ERRORS
    The errors and warnings of route_net (man route_net: HT4-001,
    HT4-025, HT4-170 to HT4-179, HT4-265, HT4-266), named route_track,
    and:
    HT4-279  WARN: -compact removed the wires of stubs routed before on
             another track than the one kept free for them;
             route_final_stub routes them again
    HT4-286  WARN: a fixed net is not routed again, and a fixed
             stub keeps its wires (set_db .route_status fixed)
    HT4-297  WARN: vias that no definition of their layer pair fits

SEE ALSO
    route_net, route_final_stub, delete_route, assign_track_for_route,
    create_route_rule, check_drc, assign_via_for_route
