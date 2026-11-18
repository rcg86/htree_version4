NAME
    rename_obj - rename a net or an instance

SYNOPSIS
    rename_obj -from <net or instance> -to <new name>

DESCRIPTION
    Gives a net or an instance a new name everywhere htree4 names it, so
    every later command, write_def and write_logical use the new name.

    A net. A spine net (<inst>_Y), the root net of a spine
    (<spine>_primary_input, see create_spine), or a net connect_pin
    made. Renamed with it: its spine net row, the root net of every
    spine it is the root net of, the connect_pin connections on it, the
    route_pin straps and pin wires on it, its route_net wires
    (net_wire:<new>/<n>) and its final stub's wires
    (net_wire:<new>_stub/<n>), the auto vias on them, its route rule,
    route status and via assignments. The vias are derived again under
    the new name.

    Not renamed: the net of a port (it is the design's, from the DEF),
    and a net on no pin (a power net such as VSS, SIGNAL).

    An instance. Renamed with it: its spine membership (as a cell and as
    the driver of the next level), the spine nets and stub it drives or
    loads, its route_pin straps and pin wires, the connect_pin
    connections on its pins, its optimize_pg_connection wires and the
    auto vias on its straps and pin wires. The nets it drives keep their
    names: rename them too if they should follow (rename_obj -from
    <inst>_Y -to <new>_Y).

    The selection, the show_only filter and the highlight colours follow
    the new name.

OPTIONS
    -from <net or instance>
        One net or instance: a name (get_db <object> .name), or a handle
        (net:<name>, spine_net:<spine>/<net>, inst:<name>). A name that
        is both a net and an instance must be given by its handle.
    -to <new name>
        The new name: one word without blanks, '/', ':', braces,
        brackets, quotes, '$' or ';'. No other net (instance) may have
        it, and a net name may not end in _stub (the name of a stub's
        wires).
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handle of the renamed object (inst:<new>, spine_net:<spine>/<new>
    or net:<new>).

EXAMPLES
    The root net of a spine:
    htree> get_db spine:sp .root_net
    net:sp_primary_input
    htree> rename_obj -from [get_db [get_db spine:sp .root_net] .name] -to clk_root
    rename_obj: root net of spine sp sp_primary_input renamed clk_root (0 wire(s))
    net:clk_root

    A spine net, and an instance:
    htree> rename_obj -from sp_L1_inv1_Y -to sp_root_out
    htree> rename_obj -from [get_db inst:sp_L1_inv1 .name] -to sp_root_buf

ERRORS
    HT4-001  -from or -to missing, more than one object in -from, or an
             unknown option
    HT4-022  a handle of -from names an object that does not exist
    HT4-292  -from names no net or instance
    HT4-293  -from is both a net and an instance: give its handle
    HT4-294  the new name is taken (or the same as the old one), or a
             net name ends in _stub
    HT4-295  -from is not a net or an instance, is a port's net, or is
             on no pin (a power net)
    HT4-296  -to is not a name

SEE ALSO
    create_spine, write_logical, write_def, connect_pin, get_db
