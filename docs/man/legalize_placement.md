NAME
    legalize_placement - put instances on the free legal sites of their cells

SYNOPSIS
    legalize_placement -inst <insts>

DESCRIPTION
    Moves each instance to the nearest free legal site of its cell:
      - a DEF ROW (read_def) whose site is the cell's LEF SITE (the SITE
        line in its MACRO; rows of other sites at the same place, such as
        _2x or _pg sites, are not used; a cell with no SITE, or a SITE no
        row has, takes rows of any site);
      - of the instance's orientation: N cells in N rows, FS cells in FS
        rows;
      - with the cell inside the row, at a whole number of the row's site
        steps from its origin;
      - overlapping no other instance (abutting is fine).
    The nearest is by x + y distance, at most one cell width + height from
    where the instance is: a legalization, not a re-placement. An instance
    with no free site within that stays where it is (warning HT4-212), for
    example one outside the die.

    Instances already on a legal, free site do not move. Fixed or cover
    instances (set_db .place_status fixed) never move, and the others keep
    clear of them. Instances are legalized in the order given; each one
    takes its site before the next looks.

    An instance's route_pin straps and pin wires move with it. Routes of
    its nets (route_net) do not: the routed nets whose cells moved are
    listed (HT4-213) with the route_net command to route them again.

    Spacing (set_place_constraint). After the instances are on sites, two
    instances closer than their constraint (gap less than space_x in x and
    less than space_y in y) are moved apart, each along its spine: a cell
    of a vertical spine moves in y (to a row of its site and orientation
    above or below), a cell of a horizontal spine in x (along its row); a
    cell of a spine bent by move_spine_to_boundary the way its own stretch
    of the path runs (y on a vertical stretch, x on a horizontal one); a
    cell in no spine the way that needs the shorter move. It goes to the
    nearest free site far enough away, too close to no third instance.
      - fixed (or cover) and placed: only the placed one moves, the whole
        distance; an instance not in -inst is treated as fixed
      - two placed: each moves about half the distance, away from the other
      - two fixed: neither moves; the pair is reported
    The report gives the pairs found, the instances moved and how far;
    pairs still too close are listed with their gaps and why (HT4-214).
    With no constraints set nothing of this runs.

OPTIONS
    -inst <insts>
        Instance names, glob patterns or inst: handles, as a Tcl list:
        [get_db insts], [get_db inst .name], *temp_* all work. Every word
        must match an instance. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the instances moved.

EXAMPLES
    htree> legalize_placement -inst [get_db inst]
    legalize_placement: 33 instance(s) moved onto sites (up to 0.259 um), 0 already legal, 0 fixed (not moved)
    **WARN: (HT4-212): no free site of the cell's site and orientation within one cell width + height of temp_mirror_L7_inv6; left where they are

ERRORS
    HT4-001  missing -inst
    HT4-210  no instance matches a -inst word
    HT4-211  no placement rows (read_def a DEF with ROW statements)
    HT4-212  WARN: no free site near an instance; it stays
    HT4-213  WARN: routed nets whose cells moved; route them again
    HT4-214  WARN: instances still closer than set_place_constraint (both
             fixed, or no free site far enough away)

SEE ALSO
    set_place_constraint, move_obj, move_spine_to_boundary, read_def,
    read_lef, create_inst, route_net, set_db
