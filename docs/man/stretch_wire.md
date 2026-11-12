NAME
    stretch_wire - move one edge of a route wire to a coordinate (lengthen
    or shorten it)

SYNOPSIS
    stretch_wire -wire <wire> -edge <left|right|bottom|top> -to <coordinate>

DESCRIPTION
    Moves one edge of a wire to the coordinate (x for the left and right
    edges, y for the bottom and top), keeping the other three, so the
    wire gets longer or shorter. Wires are the route shapes of move_wire:
    net_wire:, strap: and pin_wire: handles. An edge may not reach or pass
    its opposite edge. A wire off its layer's tracks afterwards is
    reported (HT4-222), as by move_wire.

    Auto vias. Where the part the wire gains crosses a wire of the same
    net (its electrical net: VSS for a VSS strap or a VSS shield) on
    another routing layer at most route_auto_via_insertion_during_stretch
    layers away (root attribute, set_db; default 1), a via is added at the
    crossing box. Layers count in tech order of the routing layers: with
    D12 H1 H2 G1 G2 IA IB, 1 joins IA and IB only, 3 joins H2 to IA (over
    G1 and G2), 0 adds none. No via where a crossing box or via is already
    there, and none for straps of unrouted signal pins (net SIGNAL).
    Shortening the wire removes its auto vias it no longer covers;
    move_wire, route_pin and route_net (rebuilding the wire) remove them;
    they move with the wire's instance or spine (legalize_placement,
    move_obj).

    Until vias have their own table, an auto via is stored as a net_wire
    of kind via under net auto_via:<wire handle>, layer <lower>/<upper>
    (e.g. H2/IA), .shield_net its net. The GUI draws it as an outline like
    a crossing box; write_def does not write it yet.

    The GUI's Tools > Stretch runs this command when an edge of a wire is
    dragged; Tools > Undo Edit puts the edge back (and so removes the
    vias the stretch added).

OPTIONS
    -wire <wire>
        One wire handle. Required.
    -edge <left|right|bottom|top>
        The edge to move. Required.
    -to <coordinate>
        Where the edge goes, in microns. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handle of the wire.

EXAMPLES
    htree> stretch_wire -wire net_wire:temp_L2_inv1_Y/3 -edge top -to 10120.5
    stretch_wire: net_wire:temp_L2_inv1_Y/3 top edge 10100.1 -> 10120.5 (longer by 20.4)
    htree> set_db route_auto_via_insertion_during_stretch 3
    htree> stretch_wire -wire strap:temp_L3_inv1/1 -edge right -to 5694.48
    stretch_wire: strap:temp_L3_inv1/1 right edge 5692.8 -> 5694.48 (longer by 1.68)
      auto via IA/IB {5693.76 12130.021 5694.48 12130.381} to net_wire:temp_L2_inv1_Y/9

ERRORS
    HT4-001  a missing option, a bad edge or coordinate, or more than one
             wire
    HT4-220  the handle is not a route wire
    HT4-221  the edge would reach or pass its opposite edge
    HT4-222  WARN: the wire is off the tracks of its layer

SEE ALSO
    move_wire, set_db, route_net, route_pin, gui_show
