NAME
    move_spine_to_boundary - bend a built spine along a path of head moves

SYNOPSIS
    move_spine_to_boundary -spine <spine> -moves <moves>
                           [-clearance {<left> <right> <top> <bottom>}]

DESCRIPTION
    Moves a built spine (create_spine -build) like the snake of the game.
    The spine, its mirror included, is one body lying on a path: the line
    of its stubs, from its bottom end to its top end (left to right for a
    horizontal spine). A move pulls one end, the head, and the body
    follows along the path the head has drawn.

    Every cell, stub and net centre line keeps its distance along the
    spine and its distance from the stub line, so the stub lengths, the
    stub gaps, the spacing of the cells and the drive lengths stay as
    built. A stub that lies over a corner of the path is L-shaped. The
    columns of cells keep their side as seen along the path: cells right
    of the stubs on a stretch running up are below them on a stretch
    running right. Cells on a horizontal stretch of a vertical spine are
    side by side, not above each other.

    Moves (-moves), a Tcl list of pairs, made in order:
      head <end>          the end that moves from here on: bottom or top
                          for a vertical spine, left or right for a
                          horizontal one. Before the first one the head is
                          the bottom (left) end.
      <direction> <um>    pull the head up, down, left or right:
        - the way the head points (out of the body): the path grows
          straight on
        - to a side: the path turns a corner where the head is
        - into the body: the spine backs up along its own path, as far as
          its next corner; a move back along the next stretch takes it
          round the corner. The other end goes back out the way it came,
          or straight on where it has not been.

    Tracks. The head lands on a signal track ('-' of assign_track_for_route)
    of the layer whose tracks it crosses: the horizontal layer for up and
    down, the vertical one for left and right (the first layer assigned in
    each direction). It takes the track nearest the distance asked, at
    least one track on, so the corners of the path are on signal tracks
    and the distance moved can differ from the one asked by up to half a
    track step; the report gives the distance moved. Without assigned
    tracks, with no track ahead of it, or outside the track area and not
    reaching it, the head moves the distance asked on the manufacturing
    grid. The first stretch stays where create_spine put the stub line; a
    turn made before the head has moved along it starts from a point that
    need not be on a track.

    Hard stops, for the head only:
      - Clearance (-clearance): the head keeps at least this distance
        from the design boundary (DEF DIEAREA) on each side: from the edge
        ahead of the move, and from the edges beside the move wherever it
        keeps that distance when the move starts. A move that would come
        closer stops on the last signal track before the limit (HT4-232).
        With 17 um of room and a clearance of 10 the limit is 7 um; with
        signal tracks every 2.88 the head moves 5.76. A head outside the
        boundary is not stopped.
      - Its own body: a move that would lay the spine over itself, taking
        it as wide as its columns of cells, is refused (HT4-233): the
        command stops and nothing is changed.
    What ends up outside the boundary behind the head (cells by their
    centre, stubs by any point) is reported (HT4-234), not stopped.

    When all moves are made:
      1. The spine is stored on its path: instances (lower-left corner on
         the manufacturing grid), stub points (two for a straight stub,
         more for one over a corner), net centre lines, and the spine's
         location and path.
      2. Its routing is removed, as it no longer fits: the route_pin
         straps and pin wires of its instances, their
         optimize_pg_connection wires, the route_net wires and shields of
         its nets and the route_final_stub wires of its stubs. Run
         route_pin, route_net and route_final_stub again.
      3. Its cells are put on legal sites: legalize_placement -inst on the
         spine's instances, which also resolves cells that overlap on the
         inside of a bend. From then on legalize_placement moves a cell of
         this spine apart from another along its own stretch of the path:
         in y on a vertical stretch, in x on a horizontal one. Without
         DEF rows this step is skipped (HT4-235).

    The command can be run again on a bent spine: the moves start from
    the path it has. move_obj moves a bent spine whole, as any other.

OPTIONS
    -spine <spine>
        The built spine: its name or handle (temp, spine:temp). Required.
    -moves <moves>
        The moves, a Tcl list of 'head <end>' and '<direction> <um>'
        pairs (see above). At least one move. Required.
    -clearance {<left> <right> <top> <bottom>}
        Least distance of the head from the design boundary on each side,
        microns, 0 or more. Default {0 0 0 0}: the head may reach the
        boundary.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The spine's handle.

EXAMPLES
    htree> move_spine_to_boundary -spine temp -clearance {10 10 10 10} \
               -moves {head bottom down 700 left 200 down 2000}
    **WARN: (HT4-232): down 700: moved 665.14, stopped by the bottom clearance 10 to the boundary at y 3378.96; head bottom at 5676.84 3391.56
    **WARN: (HT4-232): left 200: moved 139.68, stopped by the left clearance 10 to the boundary at x 5526.72; head bottom at 5537.16 3391.56
      down 2000: moved 1998.72 to the signal track; head bottom at 5537.16 1392.84
    Moved spine:temp onto a path with 2 corner(s): 34 instances, 12 stubs, 34 nets. Removed its routing: 0 strap(s), 0 pin wire(s), 0 net wire(s); run route_pin, route_net and route_final_stub again
    legalize_placement: 34 instance(s) moved onto sites (up to 0.24825 um), 0 already legal, 0 fixed (not moved)
    legalize_placement: 4 pair(s) closer than set_place_constraint; 8 instance(s) moved apart (up to 2.54 um), 0 pair(s) left
    spine:temp
    htree> get_db spine:temp .path
    5537.16 1392.84 5537.16 3391.56 5676.84 3391.56 5676.84 13273.16

    The same path again, from the distances it moved:
    htree> move_spine_to_boundary -spine temp -clearance {10 10 10 10} \
               -moves {head bottom down 665.14 left 139.68 down 1998.72}

ERRORS
    HT4-001  missing -spine or -moves, or a -clearance that is not four
             distances of 0 or more
    HT4-230  no built spine of that name, or one built before the spine
             path was stored (build it again)
    HT4-231  -moves is not a list of 'head <end>' and '<direction> <um>'
             pairs, names an end the spine does not have, or has no move
    HT4-232  WARN: a move stopped short of the distance asked (clearance
             to the boundary, or the next corner when backing up)
    HT4-233  a move would run the spine into its own body; nothing changed
    HT4-234  WARN: cells or stubs of the spine are outside the boundary
    HT4-235  WARN: no DEF rows; the cells are not on sites

SEE ALSO
    create_spine, move_obj, legalize_placement, route_pin, route_net,
    route_final_stub, assign_track_for_route
