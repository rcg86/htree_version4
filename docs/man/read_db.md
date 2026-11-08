NAME
    read_db - read a design database written by write_db and continue from it

SYNOPSIS
    read_db -file <file>

DESCRIPTION
    Loads a database written by write_db, replacing the current one, so
    work continues where it was saved: everything the earlier session
    read or created is back (tech, physical library, spine specs, design
    boundary, ports and tracks, track assignments, route rules,
    instances), and every command (get_db, create_inst,
    assign_track_for_route, create_route_rule, gui_show, write_db, ...)
    works on it as if the reads had just been run. The LEF, DEF and YAML
    files are not needed again.

    Prints what the database holds. The file is opened read-only and is
    not changed. Its schema version must match this tool's: a database
    written by an older version of the tool is rejected and has to be
    rebuilt from the source files.

    Not saved, so not restored: the selection (it is cleared), the GUI
    view, Tcl variables and procs. An open GUI window redraws with the
    loaded data.

    The file may also be given without -file (read_db <file>).

OPTIONS
    -file <file>
        Database file written by write_db. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None. Prints the absolute path read and a summary of the contents.

EXAMPLES
    htree> read_db -file cf999.db
    Database read from '/path/to/cf999.db'
      Tech              : tech.new.lef (7 layers: D12 H1 H2 G1 G2 IA IB)
      Library           : 1 LEF file(s), 6 cells
      Spine specs       : custom_spine_5000 custom_spine_5001
      Design            : cf999 (110728 ports, 56 track patterns)
      Track assignments : IA
      Route rules       : H2
      Instances         : 1
    htree> create_inst -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -location {5630 10066.7}

ERRORS
    HT4-001  file name missing or given twice, or an unknown option
    HT4-040  file not found
    HT4-041  not an htree database, or schema version mismatch

SEE ALSO
    write_db, get_db
