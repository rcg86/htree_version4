NAME
    legalize_placement - put instances on the free legal sites of their cells

SYNOPSIS
    legalize_placement -inst <insts> [-keep_orientation]

DESCRIPTION
    Moves each instance to the nearest free legal site of its cell:
      - a DEF ROW (read_def) whose site is the cell's LEF SITE (the SITE
        line in its MACRO; rows of other sites at the same place, such as
        _2x or _pg sites, are not used; a cell with no SITE, or a SITE no
        row has, takes rows of any site);
      - of the instance's orientation: N and FN cells in N rows, FS and S
        cells in FS rows (FN and S are N and FS mirrored about the y axis:
        the cells of a mirrored spine);
      - with the cell inside the row, at a whole number of the row's site
        steps from its origin;
      - overlapping no other instance (abutting is fine);
      - with the cell inside the design boundary (DEF DIEAREA). A row
        can be lower than the cell (a cell that is several rows tall), so
        a cell in a row at the edge of the die may reach across the
        edge: a free site where it does not is taken before a nearer
        one where it does. With no such site near enough the nearest
        free site is taken.
    The nearest is by x + y distance, at most one cell width + height from
    where the instance is: a legalization, not a re-placement. On a crowded
    spot (another cell on it already: two buffers made at one point) with
    no free site that near, it looks two, four ... up to 32 cell widths +
    heights away, the nearest free site there. An instance with no free
    site within that stays where it is (warning HT4-212), for example one
    outside the die.

    Instances already on a legal, free site do not move. Fixed or cover
    instances (set_db .place_status fixed) never move, and the others keep
    clear of them. Instances are legalized in the order given; each one
    takes its site before the next looks.

    An instance's route_pin straps and pin wires move with it. Routes of
    its nets (route_net) do not: the routed nets whose cells moved are
    listed (HT4-213) with the route_net command to route them again.

    Orientation for pin access (not with -keep_orientation). A cell whose
    signal comes from above or below it (the driver of its input net is
    farther above or below the cell than beside it, by more than the
    cell's height) is put in the
    orientation, N or FS (turned about the x axis), that has its input
    pin on the side the signal comes from: of
    its two signal pins the input the higher one when the signal comes
    from above, the lower when from below. route_pin gives the higher pin
    the higher SIGNAL strap, so the net coming in reaches the input's
    strap first, and route_net takes each from its outer side: the net in
    and the net out pass the cell on one track. A cell whose pins are as
    high in both orientations, whose signal comes from beside it, or with
    no driver, keeps its orientation. A turned
    cell goes on the nearest free site of the new orientation (an FS row
    for FS, one row away); its pin routes would be upside down and are
    removed, and the cells turned are listed with the route_pin command
    to run on them.

    Spine spec tracks. A cell the spine spec gives tracks (track:
    {input, output}, man read_spine_spec, TRACKS) is moved across its
    stretch of the spine, on whole sites of its row and onto no other
    cell, the least distance that puts both its tracks in its straps'
    reach (its max_extension each side, the rule's wire width); the cells
    moved are listed with how far. One that cannot reach them (no free
    site, tracks farther apart than its straps reach, or no such track)
    is reported (HT4-289). Its pin access is checked on those tracks
    only.

    Pin access check. At the end every signal pin (on a net, or routed by
    route_pin) of the instances given is checked: can route_net reach
    it? A pin is reached on its strap from a signal track of the vertical
    layer with a track assignment (IB) that the strap covers or reaches
    by its max_extension, at the horizontal signal track nearest the
    strap or the one on its other side. A track is of no use when
      - it is outside the design there (a notch of the die),
      - a wire of another net on the vertical layer is closer than the
        rule spacing to the wire down to the strap, at both crossings
        ("taken by <net>"), or
      - the strap's extension to it would come closer than the tech
        spacing to another net's strap or wire on its layer (another
        cell's straps).
    Every pin with no track of use is listed (HT4-288) with each track
    in reach and why it is of no use, so the cell can be moved or turned,
    or the net in the way routed elsewhere. The routes of the nets the
    command moved cells off are not counted as in the way (route them
    again). Before route_pin the cell's width stands for its strap,
    reaching as far as other cells' straps do. With no track assignment
    numbered in x the check is not made (said so).

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
    -keep_orientation
        Keep every instance's orientation (no turning for pin access).
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the instances moved.

EXAMPLES
    htree> legalize_placement -inst [get_db inst]
    legalize_placement: 33 instance(s) moved onto sites (up to 0.259 um), 0 already legal, 0 fixed (not moved)
    **WARN: (HT4-212): no free site of the cell's site and orientation within 32 cell widths + heights of temp_mirror_L7_inv6; left where they are

ERRORS
    HT4-001  missing -inst
    HT4-210  no instance matches a -inst word
    HT4-211  no placement rows (read_def a DEF with ROW statements)
    HT4-212  WARN: no free site near an instance; it stays
    HT4-213  WARN: routed nets whose cells moved; route them again
    HT4-288  WARN: signal pins with no track route_net can reach them on,
             each with the tracks in reach and why
    HT4-289  WARN: a cell cannot reach the tracks the spine spec gives it
    HT4-214  WARN: instances still closer than set_place_constraint (both
             fixed, or no free site far enough away)

SEE ALSO
    set_place_constraint, move_obj, move_spine_to_boundary, read_def,
    read_lef, create_inst, route_net, set_db
