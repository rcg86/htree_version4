NAME
    create_inst - place an instance of a library cell

SYNOPSIS
    create_inst -ref_cell <lib_cell> -location {x y} [-name <name>]
                [-orient <orient>]

DESCRIPTION
    Creates an instance of a cell from the physical library (read_lef) and
    places it. The location is the lower-left corner of the placed cell's
    bounding box, as in DEF and Innovus placement, for every orientation.

    Checks (errors): the cell must be in the library and have a SIZE in
    its LEF; the name must be new and contain no '/' or spaces; the
    location must be two numbers; the orientation must be valid.

    Checks (warnings, the instance is still created): the cell's bbox is
    not inside the design boundary (read_def); it overlaps another
    instance (touching edges do not count); the location is not on the
    tech manufacturing grid.

    Row and site alignment are not checked: read_def does not read ROW
    statements.

    The instance is shown in the GUI (Cells checkbox) as a cell outline
    with the cell's pin shapes in their layer colours, and can be selected
    there or with select_obj. write_db saves instances.

OPTIONS
    -ref_cell <lib_cell>
        Library cell name, or its handle (lib_cell:<name>). Required.
    -location {x y}
        Lower-left corner of the placed cell, in microns. Required.
    -name <name>
        Instance name. Default: inst_1, inst_2, ... (the first free one).
    -orient <orient>
        N (default), S, E, W, FN, FS, FE, FW, as in DEF.

OBJECTS AND ATTRIBUTES
    inst:<name>
        obj_type, name, ref_name (cell name), lib_cell (handle), location
        ("x y", lower-left), orient, bbox ("x1 y1 x2 y2"), status (placed),
        pins (handles)
    pin:<inst>/<pin>
        a pin of an instance: obj_type, name, inst (handle), lib_pin
        (handle), direction, use, layers, rect (placed bounding box of the
        pin's shapes, all layers)
    get_db insts lists all instances; get_db inst:<name> .pins its pins.
    Pins can be selected in the GUI (click a shown pin) or with select_obj.

RETURN VALUE
    The new instance handle, inst:<name>.

EXAMPLES
    htree> create_inst -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -location {5622.772 10066.7}
    Created inst:inst_1 (INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04) at {5622.772 10066.7} N, bbox {5622.772 10066.7 5625.892 10068.478}
    inst:inst_1
    htree> get_db inst:inst_1 .bbox
    5622.772 10066.7 5625.892 10068.478

ERRORS
    HT4-001  missing -ref_cell or -location, bad location, bad
             orientation, or a bad name
    HT4-026  no physical library loaded (read_lef)
    HT4-120  cell not in the library, or it has no SIZE
    HT4-121  an instance with that name exists
    HT4-122  WARN: the cell is not inside the design boundary
    HT4-123  WARN: the cell overlaps another instance
    HT4-124  WARN: the location is not on the manufacturing grid

SEE ALSO
    read_lef, read_def, get_db, select_obj, gui_show
