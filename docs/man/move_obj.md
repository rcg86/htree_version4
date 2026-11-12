NAME
    move_obj - move spines (with everything they own) or instances

SYNOPSIS
    move_obj -direction <up|down|left|right> -distance <um> [-legal]
             <objects>

DESCRIPTION
    Moves the objects given by -distance microns toward -direction (up and
    down move in y, left and right in x; +x -x +y -y also work).

    Objects are spine names or handles ([get_db spines .name], spine:temp)
    and instance names or handles ([get_db insts .name], inst:u1), as Tcl
    lists; glob patterns work. A name is taken as a spine first. An
    instance of a spine that is moved too moves with its spine.

      - A spine moves whole: its location, its instances, their route_pin
        straps and pin wires, its stubs, its nets' centre lines, and every
        routed shape of its nets and stubs: wires, strap extensions,
        crossing boxes, shields, shield extensions, stub wires and stub
        shields. Everything keeps its place relative to the rest.
      - An instance moves alone. Its pin routes, its spine's geometry and
        the routes to it stay where they were; a warning (HT4-202) says to
        route_pin and route_net it again, or to move the whole spine.

    -legal: nets snap to tracks, instances snap to sites.
      - A spine first moves by -distance rounded to the nearest legal step,
        at least one: the least common multiple of the track-pattern
        periods of the layers its routes use whose tracks run across the
        move (track pitch x assign_track_for_route pattern length; the
        pitch with no assignment). With 0.72 tracks and an 8-track pattern
        the step is 5.76. Every wire stays on its track: signal wires on
        signal tracks, shields on their power tracks. Then each of its
        instances snaps, with its pin routes, to the nearest placement
        site of its orientation (below). An instance that moves off its
        net's route this way is reported (HT4-206) with the route_net
        command that reconnects its nets.
      - An instance moves by -distance, then snaps to the nearest site:
        a DEF ROW (read_def) of the instance's orientation (N cells in N
        rows, FS cells in FS rows) that the cell fits in, at a whole
        number of the row's site steps from the row origin. With no DEF
        rows it snaps to the manufacturing grid (warning HT4-205).
    Without -legal everything moves by exactly -distance; when that takes
    a spine's routes off their tracks a warning (HT4-201) says so.

    Moved instances outside the design boundary (HT4-203) or overlapping an
    instance that did not move (HT4-204) are reported.

OPTIONS
    -direction <up|down|left|right>
        Direction of the move. Required.
    -distance <um>
        Distance, microns, positive. Required.
    -legal
        Snap: nets to tracks, instances to sites (see above).
    <objects>
        Spines and instances to move. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the spines and instances moved.

EXAMPLES
    htree> move_obj -direction down -distance 2000 -legal [get_db spine .name]
      -legal: distance 2000 rounded to 1998.72 (the spine step is 5.76)
    Moved spine:temp 1998.72 down: 34 instances, 34 nets with their routing, stubs and pin routes
    htree> move_obj -direction right -distance 1 [get_db insts temp_L7_inv1]

ERRORS
    HT4-001  missing -direction, -distance or objects, a bad direction, or
             a distance that is not a positive number
    HT4-200  no spine or instance matches an object word
    HT4-201  WARN: a spine's routes are off their tracks after the move
    HT4-202  WARN: instances moved alone; their pin routes and routes stay
    HT4-203  WARN: moved instances outside the design boundary
    HT4-204  WARN: a moved instance overlaps one that did not move
    HT4-205  WARN: no DEF rows (snapped to the grid), or no row of an
             instance's orientation fits it
    HT4-206  WARN: spine instances snapped to sites moved off their nets'
             routes; route them again

SEE ALSO
    create_spine, create_inst, route_pin, route_net, assign_track_for_route
