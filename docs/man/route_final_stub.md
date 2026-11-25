NAME
    route_final_stub - route the final stubs of the built spines as straight
    wires on signal tracks, a wire a straight piece of a bent stub

SYNOPSIS
    route_final_stub -rule <route_rule> [-stub <stubs>] [-shield]
                     [-shield_nets {<left/above> <right/below>}]

DESCRIPTION
    Routes the stubs of the spines built by create_spine -build: the final
    spines of the tree. Each stub becomes one straight wire, exactly as
    long and where create_spine placed it from the spec (spine.span shared
    by the stubs, stubs.gap between them: 6 stubs over 6000 um with gap 10
    are 991.667 um each).

      - Direction: the spine's orientation (.orientation of the stub). A
        stub of a vertical spine is routed vertically on the rule's
        vertical layer (IB), one of a horizontal spine horizontally on its
        horizontal layer (IA), as wide as the rule width there.
      - Track: signal tracks only, the '-' tracks of assign_track_for_route
        (every DEF track of the layer when it has no assignment).
      - One track for the stubs of a centre line. The stubs of a spine
        that lie on one centre line (create_spine puts the stubs of a
        straight spine on one line) share one track: all of them are on
        it, none on the track beside it. A straight spine so has one stub
        track. A spine with bends (move_spine_to_boundary) has one for
        each straight stretch stubs lie on: with two bends three, the
        track of the stretch before the bends, the one of the stretch
        between them and the one of the stretch after. The stubs of two
        spines do not share.
      - Which track: the one nearest the centre line on which the wire of
        every stub of the line keeps the rule spacing to the shapes of
        other nets on that layer (route_pin straps and pin wires, other
        nets' wires and shields) over the whole stub. A track the leaves'
        pin wires with no strap reach already (route_pin -spec_name
        horizontal_routing takes a leaf's output to its stub's track) is
        tried first, the more leaves on it the sooner: the stub then lies
        on the pin wire's end. A leaf's own straps and pin wires do not
        keep its stub off a track (they are on its net). When it is blocked
        for one stub, the next tracks out on either side are tried, up to
        20 each way, for all the stubs of the line: they move together.
        The report gives the tracks of the spine, the number of stubs on
        each and how far it is from the centre line.
      - The whole spine counts, also with -stub. The tracks are chosen
        for every stub of the spine, so a stub routed on its own takes
        the track the others would get with it. Stub wires of the spine
        from an earlier run are no obstacle. Those that -stub leaves out
        stay as they are: when they are not on the tracks chosen now
        (another track, or other ends) a warning names them (HT4-193).
        Route them again, so the spine is on its tracks.
      - A stub that cannot share. When no track holds every stub of the
        spine, the stubs are taken in the order of the spine and a stub
        that does not fit with the ones before it is left out: it is not
        routed (HT4-191), and is never put on a track of its own.
      - Stubs that meet end to end. The two stubs at the middle of a
        mirrored spine (create_spine -mirror) end at the same point, and
        other stubs may be closer than the rule spacing of the layer. On
        one track their wires would touch, so each of the two ends is
        drawn back by half of what the spacing needs, up to the
        manufacturing grid: 0.18 um each for stubs that touch and a
        spacing of 0.36. The report names the stub and the length left
        off. Only an end of a stub is drawn back, not a bend.
      - Design boundary: a hard limit, as in route_net. A track on which
        the stub wire would not lie inside the boundary (DEF DIEAREA; on
        the boundary line counts as inside) is not taken, so a stub next
        to a notch of the boundary moves to the nearest track that keeps
        it inside. A stub that fits inside on none of the tracks tried
        (it runs out of the die) is not routed (HT4-178): move the spine.
      - Net: the stub wire carries its leaf's net (the net that drives
        the stub, e.g. sp_L3_inv1_Y: its .net and .shield_net) and is
        stored under the stub's own name, <leaf net>_stub, as kind stub:
        net_wire:sp_L3_inv1_Y_stub/<n>, as are its crossing boxes and
        shields, apart from the leaf's own wires (route_net's). A
        database written before stubs had their own name is read into
        these names.
        route_net and route_final_stub each replace only their own wires of
        the net, so either can be run again without losing the other's.
      - Join: where the leaf's route (route_net) overlaps the stub wire on
        the other layer a crossing box is stored (kind stub_cross) for the
        via to come. When the leaf's route does not reach the stub wire
        (not routed yet, or on another track), a warning says so (HT4-192).
        route_net ends a leaf's route on the track its stub gets here
        (the shared one), before the stub is routed as well as after, so
        route_net first and route_final_stub after it meet. A leaf route
        made before a stub moved to another track ends short of it:
        route_net the leaf net again, then route_final_stub the stub
        again (it stores the crossing box).

    A bent stub. A stub that lies over a bend of its spine
    (move_spine_to_boundary) is L-shaped, or has more bends; a stub on a
    horizontal stretch of a vertical spine lies flat. It is routed as one
    wire a straight piece:
      - Each piece the way it runs: a vertical piece on the rule's vertical
        layer (IB), a horizontal one on its horizontal layer (IA), each on
        the track of its centre line, shared with the other stubs on that
        line, as above. The tracks of all the lines of the spine are
        chosen together.
      - Bend: the pieces meet where their tracks cross. Each wire runs on
        to cover the whole crossing, a box of (vertical width) x
        (horizontal width), stored as a crossing box (kind stub_cross,
        layer IA/IB) for the via to come, as route_net does at a layer
        change.
      - Length: a piece on a track off its centre line moves the end of
        the piece it meets, so the routed length can differ from the
        stub's. The report gives the length and the difference.
      - An end piece no longer than half the width of the wire it joins
        lies inside that wire and gets no wire of its own (the report says
        so).
      - Shields (-shield): each piece gets its own, as below.
      - The join with the leaf's route is looked for on every piece.
    On a horizontal stretch the cells' IA straps (route_pin) are close to
    the flat piece of the stub: when they are within the rule spacing of
    its centre track the piece takes the next free track. route_net aims
    at that track (it works out the tracks of the spine's stubs the same
    way), so either order works: route_pin, route_net, route_final_stub;
    or route_pin, route_final_stub, route_net, then route_final_stub again
    for the crossing boxes at the leaf routes. Routing the stubs first
    keeps their tracks free of the other nets: route_net does not keep a
    track free for a stub that is not routed yet. (The pin route
    extensions of route_net keep only the strap layer's tech spacing to a
    stub wire, so a later route_final_stub can still move the stubs of a
    line a track; a leaf route that then ends short gets HT4-192.)

    Shields (-shield), as route_net -shield does for the main route: the
    stub wire (each piece of a bent stub), when at least
    ignore_shield_less_than_routing_length long
    (root attribute, set_db), gets one power shield on each side, on the same layer and
    span, as wide as the rule width, on the nearest track whose centre is
    at least width + spacing from the stub's. The shield takes its track's
    net when the layer has a track assignment (VDD_SOC on a VDD_SOC track,
    VSS on a VSS track; none beside a signal or blank track, warning
    HT4-177); with no assignment, -shield_nets (default VDD_SOC left of /
    above, VSS right of / below). A shield is cut where it would come
    closer than the rule spacing to a shape of another net on its layer:
    signal wires, straps and shields of the other power net. Shapes of its
    own power net (another net's VSS shield beside a VSS stub shield) may
    touch it. A shield is also cut where it would leave the design
    boundary. The report gives each shield net's length and how much was
    cut, for either reason. Stub shields are stored with the stub (kind
    stub_shield, .shield_net), so delete_route and routing the stub again
    remove them with it; write_def writes them as + SHIELD <net> wiring.

    write_def writes the stub wires under their net in NETS. The GUI draws
    them with the other route wires (Routes checkbox).

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
    -rule <route_rule>
        A rule from create_route_rule with a horizontal and a vertical
        layer. Required.
    -shield
        Add one power shield on each side of every stub wire.
    -shield_nets {<left/above> <right/below>}
        Shield nets for a layer with no track assignment (implies
        -shield). Default {VDD_SOC VSS}.
    -stub <stubs>
        Stub names, glob patterns (stub*) or stub: handles, as a Tcl
        list: [get_db stubs .name] and [get_db stubs] both work. Default:
        every stub of every built spine. The tracks are those of the
        whole spine of each stub (see 'The whole spine counts' above).
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the stubs routed.

EXAMPLES
    htree> route_final_stub -rule rule1
    route_final_stub: rule rule1: vertical stubs on IB (width 0.72), horizontal ones on IA (width 0.72), on signal tracks
      stub temp/stub1 (temp_L7_inv1_Y): IB x 5643.72 (0.788 from its centre line), 10076.7 .. 11068.366667 (length 991.666667); meets its leaf route (2 overlap(s))
      ...
    route_final_stub: 6 of 6 stubs routed
    htree> route_final_stub -rule rule1 -stub {stub1 stub2}

    A stub over two bends of its spine, after move_spine_to_boundary:
    htree> route_final_stub -rule rule1 -stub stub6_mirror -shield
      stub temp/stub6_mirror (temp_mirror_L7_inv6_Y): 3 pieces round 2 bend(s) (length 993.106667, 1.44 more than the stub's 991.666667); meets its leaf route (1 overlap(s))
        IB x 5537.16, 2971.08 .. 3394.44 (length 423.36)
        IA y 3394.44 (2.88 from its centre line), 5537.16 .. 5678.28 (length 141.12)
        IB x 5678.28 (1.44 from its centre line), 3394.44 .. 3823.066667 (length 428.626667)
        shield VDD_SOC: 3 wire(s), 994.547 um
        shield VSS: 3 wire(s), 994.547 um
    htree> route_final_stub -rule rule1 -stub [get_db stubs .name] -shield

    A mirrored spine: its four stubs on one track, the two that meet at
    the middle of the spine each 0.18 um short:
    htree> route_final_stub -rule r
    route_final_stub: rule r: vertical stubs on IB (width 0.36), horizontal ones on IA (width 0.36), on signal tracks
      spine sp: 4 of 4 stub(s) on 1 track(s), the stubs on one centre line on one track: IB x 79.56 (4 stub(s), 0.92 from their centre line)
      stub sp/stub1 (sp_L3_inv1_Y): IB x 79.56 (0.92 from its centre line), 100.18 .. 119 (length 18.82)
        its first 0.18 um are left off: stub stub1_mirror is on the same track there (IB spacing 0.36)
      stub sp/stub2 (sp_L3_inv2_Y): IB x 79.56 (0.92 from its centre line), 121 .. 140 (length 19)
      ...
    route_final_stub: 4 of 4 stubs routed

    One stub routed again after the track of the spine changed:
    htree> route_final_stub -rule r -stub stub1
      spine sp: 4 of 4 stub(s) on 1 track(s), the stubs on one centre line on one track: IB x 79.56 (4 stub(s), 0.92 from their centre line)
      ...
    **WARN: (HT4-193): spine sp: the wires of stub(s) stub2 stub1_mirror stub2_mirror, of an earlier route_final_stub, are not on the tracks its stubs share now: route them again (route_final_stub -stub {stub2 stub1_mirror stub2_mirror}), or remove them (delete_route -nets {stub:sp/stub2 stub:sp/stub1_mirror stub:sp/stub2_mirror})

ERRORS
    HT4-001  missing -rule, or -shield_nets not two nets
    HT4-025  no tech data loaded (read_tech)
    HT4-171  no such rule, 'default', or a rule without a horizontal and a
             vertical layer
    HT4-175  a rule layer has no DEF tracks, or no signal track
    HT4-176  WARN: the stub is beyond the signal tracks (not routed), or
             runs past the last track across it (partly outside the die)
    HT4-178  WARN: the stub's wire would not lie inside the design
             boundary on any track tried; not routed
    HT4-179  the design boundary has a slanted edge: routes are kept
             inside a rectilinear boundary only
    HT4-190  no built spine stubs, or no stub matches a -stub word
    HT4-191  WARN: no signal track near the stub keeps the spacing, none
             that it can share with the other stubs of its spine does,
             or on the shared track it would come closer than the
             spacing to another stub of the spine; not routed
    HT4-177  WARN: no shield beside a stub whose next track is not a power
             track
    HT4-192  WARN: the leaf's route does not reach the stub wire (not
             routed yet, or it ended on another track: route_net the leaf
             net again, then route_final_stub the stub again)
    HT4-193  WARN: stubs of the spine that are not routed now have wires
             of an earlier run that are not on the tracks the stubs of
             the spine share now; route them again
    HT4-286  WARN: a fixed stub (set_db .route_status fixed) is
             not routed again
    HT4-297  WARN: vias that no definition of their layer pair fits

SEE ALSO
    route_net, create_spine, move_spine_to_boundary,
    assign_track_for_route, create_route_rule, delete_route, write_def, assign_via_for_route
