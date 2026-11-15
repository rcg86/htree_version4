NAME
    get_obj_in_area - return the vias, nets, wires, pins and instances in
    an area

SYNOPSIS
    get_obj_in_area -area {x1 y1 x2 y2} [-type <types>] [-enclosed | -touching]

DESCRIPTION
    Returns the handles of the objects in a rectangle of the design
    (microns; any two opposite corners).

    -enclosed (the default) returns the objects that lie fully inside the
    area; an edge on the area's edge is inside. -touching returns every
    object that overlaps the area or touches it, a shared edge or corner
    included.

    What is compared with the area, by type:
      inst    the instance's outline
      pins    the shapes of an instance pin (pin:<inst>/<pin>); a polygon
              by its bounding box. Enclosed: every shape of the pin
              inside; touching: one of them
      wires   one rect each: straps, pin wires and net wires (wires,
              extensions, shields, stubs). A crossing box is not a wire:
              its via stands for it
      vias    the via's .rect: the shapes of its definition, or the box of
              the crossing when it has none (assign_via_for_route)
      nets    spine_net, and net (a routed net of no spine): every
              wire and via that carries the net, its
              straps and pin wires included. Enclosed: all of them
              inside; touching: one of them. stub: the stub's own wire.
              Power nets are not returned (they are not net objects);
              their shapes are found as wires and vias
    The ports of the design (read_def pins) are not searched.

    The objects come in the order of -type, and within a type in database
    order. The result is a Tcl list, so it can go to get_db, select_obj,
    delete_wire or move_wire.

OPTIONS
    -area {x1 y1 x2 y2}
        The rectangle, in microns. Required.
    -type <types>
        One or more of vias, nets, wires, pins, inst, as a Tcl list (the
        singular and plural of each are accepted). Default: all, in the
        order inst pins nets wires vias.
    -enclosed
        Objects fully inside the area. The default.
    -touching
        Objects that overlap or touch the area. Not with -enclosed.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the objects found; empty when there are none.

EXAMPLES
    htree> get_obj_in_area -area {-2 -5 2 5} -type inst
    inst:sp_L1_inv1
    htree> get_obj_in_area -area {-2 -5 2 5} -type {nets vias} -touching
    spine_net:sp/sp_L1_inv1_Y via:sp_L1_inv1_Y/1 via:VDD_SOC/1 ...
    htree> get_db [get_obj_in_area -area {-2 -5 2 5} -type vias] .cut_layer
    htree> select_obj [get_obj_in_area -area {0 0 10 20} -type wires]

ERRORS
    HT4-001  -area missing, -touching with -enclosed, or an unknown option
    HT4-245  -area is not four numbers
    HT4-246  an unknown word in -type

SEE ALSO
    get_db, select_obj, assign_via_for_route, delete_wire, move_wire
