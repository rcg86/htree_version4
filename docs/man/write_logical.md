NAME
    write_logical - write the new nets, instances and connections as an
    Innovus script

SYNOPSIS
    write_logical -output <file> [-overwrite]

DESCRIPTION
    Writes the logical changes htree4 made to the design as an Innovus
    (Stylus) script to source, in the form htree version 3 dumped them:

        create_net -name <net>
        create_inst -cell <cell> -name <inst>
        place_inst <inst> <x> <y> <orientation>
        connect <inst>/<pin> -net <net>

    Step 1 creates every spine net: the output net of each spine cell
    (<inst>_Y), mirrored halves included. Then one step per spine level,
    from the root: each cell is created, placed at its lower-left corner
    in microns, and its input pin and output pin connected. The root's
    input takes the spine spec's root_net, which must already exist in the
    design (the script says so in a comment; it does not create it). A
    leaf's output net is the net of its stub.

    Orientations are written as Innovus names: N R0, S R180, FN MY, FS MX
    (mirrored spine cells), W R90, E R270, FW MX90, FE MY90.

    An instance whose .place_status is fixed (or cover) gets
        set_db inst:<inst> .place_status fixed
    after its place_inst.

    Instances that belong to no spine (create_inst) are created and placed
    in a last step, not connected.

    Routing is not in this script; write_def writes it.

OPTIONS
    -output <file>
        Script to write. Required.
    -overwrite
        Replace -output if it exists.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The file name.

EXAMPLES
    htree> write_logical -output htree_logical.tcl
    Logical changes written to '/work/run/htree_logical.tcl': 34 nets, 34 instances

    The script starts:
        create_net -name temp_L1_inv1_Y
        ...
        create_inst -cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -name temp_L1_inv1
        place_inst temp_L1_inv1 5621.212 10075.811 R0
        connect temp_L1_inv1/A -net net
        connect temp_L1_inv1/Y -net temp_L1_inv1_Y

ERRORS
    HT4-001  missing -output
    HT4-185  -output exists (use -overwrite)
    HT4-186  -output cannot be written

SEE ALSO
    write_def, create_spine, create_inst
