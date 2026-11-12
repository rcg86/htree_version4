NAME
    route_final_stub - route the final stubs of the built spines as straight
    wires on signal tracks

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
        (every DEF track of the layer when it has no assignment). The
        track nearest the stub's centre line is used when the wire there
        keeps the rule spacing to the shapes of other nets on that layer
        (route_pin straps and pin wires, other nets' wires and shields)
        over the whole stub; otherwise the next tracks out on either side
        are tried, up to 20 each way. The report gives how far the wire
        is from the centre line.
      - Net: the stub wire belongs to its leaf's net (the net that drives
        the stub, e.g. temp_L7_inv1_Y) and is stored with it as kind stub.
        route_net and route_final_stub each replace only their own wires of
        the net, so either can be run again without losing the other's.
      - Join: where the leaf's route (route_net) overlaps the stub wire on
        the other layer a crossing box is stored (kind stub_cross) for the
        via to come. When the leaf's route does not reach the stub wire
        (not routed yet, or on another track), a warning says so (HT4-192).

    Shields (-shield), as route_net -shield does for the main route: the
    stub wire, when at least ignore_shield_less_than_routing_length long
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
    touch it. The report gives each shield net's length and how much was
    cut. Stub shields are stored with the stub (kind stub_shield,
    .shield_net), so delete_route and routing the stub again remove them
    with it; write_def writes them as + SHIELD <net> wiring.

    write_def writes the stub wires under their net in NETS. The GUI draws
    them with the other route wires (Routes checkbox).

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
        every stub of every built spine.
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
    htree> route_final_stub -rule rule1 -stub [get_db stubs .name] -shield

ERRORS
    HT4-001  missing -rule, or -shield_nets not two nets
    HT4-025  no tech data loaded (read_tech)
    HT4-171  no such rule, 'default', or a rule without a horizontal and a
             vertical layer
    HT4-175  a rule layer has no DEF tracks, or no signal track
    HT4-176  WARN: the stub is beyond the signal tracks (not routed), or
             runs past the last track across it (partly outside the die)
    HT4-190  no built spine stubs, or no stub matches a -stub word
    HT4-191  WARN: no signal track near the stub keeps the spacing; not
             routed
    HT4-177  WARN: no shield beside a stub whose next track is not a power
             track
    HT4-192  WARN: the leaf's route does not reach the stub wire
    HT4-193  WARN: the stub runs over a bend of its spine
             (move_spine_to_boundary); bent stubs are not routed yet

SEE ALSO
    route_net, create_spine, assign_track_for_route, create_route_rule,
    write_def
