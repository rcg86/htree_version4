NAME
    set_place_constraint - keep instances of a lib cell at least space_x /
    space_y apart (legalize_placement)

SYNOPSIS
    set_place_constraint -ref_name <cells> [-space_x <um>] [-space_y <um>]
    set_place_constraint -ref_name <cells> -remove
    set_place_constraint

DESCRIPTION
    Sets the spacing the instances of the lib cells in -ref_name (names,
    glob patterns or lib_cell: handles, as a Tcl list) must keep from
    other instances. Two instances are too close when the gap between
    their boxes is less than space_x in x and less than space_y in y at
    the same time: the box of one, grown by space_x left and right and
    space_y below and above, overlaps the other. Cells side by side in a
    row with space_x 0 are fine; with space_x 1 they must be 1 um apart,
    or space_y apart in y. A pair is checked when either cell has a
    constraint; with both, the larger spacing of each axis counts. A
    missing -space_x or -space_y is 0. Setting a cell again replaces its
    constraint; -remove deletes it. With no options the constraints are
    listed. write_db saves them.

    legalize_placement reads them: after putting the instances on sites,
    it moves too-close instances apart, each along its spine (a cell of a
    vertical spine in y, of a horizontal spine in x; a cell in no spine the
    way that needs the shorter move), to the nearest free site of its site
    and orientation far enough away. A fixed (or cover) instance never
    moves: a placed one beside it moves the whole distance. Two placed
    instances move about half the distance each. Pairs that stay too close
    (both fixed, or no free site) are reported (HT4-214).

OPTIONS
    -ref_name <cells>
        Lib cells whose instances are kept apart. Required, except to list.
    -space_x <um>
        The least gap in x. Default 0.
    -space_y <um>
        The least gap in y. Default 0.
    -remove
        Delete the constraints of the cells.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The lib cells set or removed; with no options, the cells with a
    constraint.

EXAMPLES
    htree> set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -space_x 0 -space_y 2
    set_place_constraint: INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04: instances at least 0 um apart in x or 2 um in y (legalize_placement)
    htree> legalize_placement -inst [get_db insts]
    htree> set_place_constraint -ref_name INV12* -remove

ERRORS
    HT4-001  -space_x or -space_y not a number >= 0, no spacing given, or
             no -ref_name with -space_x / -space_y / -remove
    HT4-225  no lib cell matches a -ref_name word

SEE ALSO
    legalize_placement, set_db, move_obj
