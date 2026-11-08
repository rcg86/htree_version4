NAME
    deselect_obj - remove objects from the selection

SYNOPSIS
    deselect_obj <objects> [<objects> ...]
    deselect_obj -all

DESCRIPTION
    Removes objects from the selection, or clears it with -all. Objects
    that are not selected are ignored; every object must exist. The GUI
    highlight follows.

OPTIONS
    <objects>
        Object handles or Tcl lists of handles.
    -all
        Clear the selection.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None.

EXAMPLES
    htree> deselect_obj port:cf999/clk
    htree> deselect_obj -all

ERRORS
    HT4-001  no arguments, or -all combined with objects, or a word that
             is not a handle
    HT4-022  an object does not exist

SEE ALSO
    select_obj, get_db, gui_show
