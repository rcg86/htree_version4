NAME
    move_wire - move route wires (net wires, straps, pin wires) by a
    distance, or to the next track

SYNOPSIS
    move_wire -wires <wires> -delta {<dx> <dy>}
    move_wire -wires <wires> -delta {{<dx> <dy>} {<dx> <dy>} ...}
    move_wire -wires <wires> -next_track up|down|left|right

DESCRIPTION
    Moves each wire by dx in x and dy in y (microns), or (-next_track)
    onto the next track of its own net in a direction. A wire keeps its
    size, net and layer; only its place changes. Wires are route shapes:
      net_wire:<net>/<n>   route_net, route_final_stub and
                           optimize_pg_connection wires, extensions,
                           shields, shield extensions and crossing boxes
      strap:<inst>/<n>     route_pin straps
      pin_wire:<inst>/<pin> route_pin pin wires
    Every handle is checked before anything moves.

    Nothing else follows a moved wire: the crossing boxes on it and the
    shapes it connected to stay where they are. A wire whose centre line
    is then off its layer's tracks (a horizontal wire: DEF TRACKS Y, a
    vertical one: TRACKS X) is reported (HT4-222). route_net, route_pin
    and route_final_stub replace hand edits when they run again. The
    auto vias stretch_wire added to a moved wire are removed.

    Next track (-next_track). Each wire moves across its length only: a
    horizontal wire up or down, a vertical one left or right (a wire that
    runs along the direction given stays). Its centre line goes onto the
    next track of its layer on that side that carries its net:
      - a power wire onto the next track of its net in the layer's track
        assignment (assign_track_for_route): a shield, shield extension or
        stub shield (.shield_net) and a strap or pin wire whose net a
        track assignment names, VDD_SOC onto the next VDD_SOC track, VSS
        onto the next VSS track;
      - every other wire (signal wires, stub wires, strap extensions,
        SIGNAL and routed straps and pin wires) onto the next signal ('-')
        track. NA tracks are never used;
      - on a layer with no track assignment in that direction, onto the
        next DEF track.
    A wire that is off the tracks goes onto the next proper track on that
    side. Running it twice moves two tracks.

    A signal wire and its shields move together as a group. The shields
    of a route_net wire or a route_final_stub stub wire are the net's
    shield (stub shield) wires that run beside it on its layer; they go
    with it also when only the signal wire is given. The signal goes
    onto the next signal track that has, beside it, a track of each
    shield's net as far away as the shield is now; each shield goes onto
    that track of its own net, on whichever side of the signal it is.
    With the pattern {VDD_SOC NA - NA VSS NA - NA} the signal moves 4
    tracks and the VDD_SOC and VSS tracks beside it change sides: the
    shield the signal moves toward stays where it is and the other one
    moves 8 tracks, to the far side. On a layer with no track assignment
    the group moves one DEF track, each shield on its side. A group with
    no such signal track on that side stays whole (HT4-226). A shield
    given without its signal wire moves alone, onto the next track of
    its net. Shield extensions, the shields' crossing boxes and the
    power wires that join a shield to a cell are not part of the group:
    they stay unless given, each by its own rule.

    A crossing box (two layers) has no track of its own: it moves with the
    wires given with it when they all move the same distance (a group:
    its signal wire's distance), and stays otherwise. A wire with no such
    track on that side (the last track, a
    layer without tracks, a net with no track on the layer) is not moved
    and reported (HT4-226); the others still move.
    Only the tracks are looked at: the spacing to other shapes and the
    design boundary are not checked.

    The GUI's Tools > Move runs this command when a wire is dragged
    (several when the dragged wire is selected with others), and with
    -next_track when Shift+arrow is pressed in that mode (the selected
    wires); Tools > Undo Edit moves them back.

OPTIONS
    -wires <wires>
        Wire handles as a Tcl list, e.g. [get_db selected]. Required.
    -delta {<dx> <dy>}
        How far to move, in microns. A list of pairs, one for each wire
        in the order of -wires, moves each wire by its own distance.
    -next_track up|down|left|right
        Move each wire onto the next track of its net on that side, a
        signal wire together with its shields.
        One of -delta and -next_track is required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the wires moved (-next_track: without those that
    stayed, with the shields that moved with a signal wire).

EXAMPLES
    htree> move_wire -wires net_wire:temp_L2_inv1_Y/3 -delta {0 1.44}
    move_wire: moved 1 wire(s) by 0 1.44
    htree> move_wire -wires [get_db selected] -delta {-0.72 0}
    htree> move_wire -wires {strap:u1/1 strap:u1/3} -next_track down
    move_wire: moved 2 wire(s) to the next track down
      strap:u1/1 (VSS): IA y 5.209 -> 5.04
      strap:u1/3 (signal): IA y 2.329 -> 0.72
    htree> move_wire -wires net_wire:n1/1 -next_track down
    move_wire: moved 2 wire(s) to the next track down
      net_wire:n1/2 (VDD_SOC shield of net_wire:n1/1): IA y 7.92 -> 2.16
      net_wire:n1/1 (signal): IA y 6.48 -> 3.6; net_wire:n1/3 (VSS shield) stays on y 5.04
    htree> move_wire -wires {strap:u1/1 strap:u1/3} -delta {{0 0.169} {0 1.609}}
    move_wire: moved 2 wire(s) strap:u1/1 by 0 0.169, strap:u1/3 by 0 1.609

ERRORS
    HT4-001  missing -wires, neither or both of -delta and -next_track,
             -delta not two numbers or not one pair for each wire, or
             a -next_track that is not up, down, left or right
    HT4-220  no wires, or a handle that is not a route wire
    HT4-222  WARN: a wire is off the tracks of its layer (-delta)
    HT4-226  WARN: wires -next_track did not move (they run along the
             direction, have no track of their net on that side, or
             no signal track there has room for the shields)

SEE ALSO
    stretch_wire, delete_wire, assign_track_for_route, route_net,
    route_pin, gui_show
