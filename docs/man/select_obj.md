NAME
    select_obj - add objects to the selection

SYNOPSIS
    select_obj <objects> [<objects> ...]

DESCRIPTION
    Adds objects to the selection. Each argument is a handle or a Tcl list
    of handles, such as the result of get_db. Objects already selected
    stay selected once. Every object must exist; if one does not, nothing
    is added.

    The selection is the same one the GUI uses: objects selected here are
    highlighted in the layout window, and objects clicked in the window
    are returned by 'get_db selected'. The GUI highlights the objects it
    draws (ports and port shapes); other objects can still be selected
    and queried.

    The selection is session state. write_db does not save it, and
    objects that stop existing (for example after read_def of another
    design) drop out of it.

OPTIONS
    <objects>
        Object handles, e.g. port:cf999/clk or [get_db ports -if {...}].

RETURN VALUE
    None.

EXAMPLES
    htree> select_obj [get_db ports -if {.direction == out}]
    htree> get_db selected .name
    htree> select_obj {port:cf999/data[3]}

ERRORS
    HT4-001  no objects given, or a word that is not a handle
    HT4-022  an object does not exist

SEE ALSO
    deselect_obj, get_db, gui_show
