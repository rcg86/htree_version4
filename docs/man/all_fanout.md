NAME
    all_fanout - the paths from a port forward, with the buffers and
    inverters on each

SYNOPSIS
    all_fanout -from <port or output pin> [-to <port or input pin>]

DESCRIPTION
    Follows the netlist from -from (an input port of the design, or an
    output pin of an instance) forward: from a net to the input pins on
    it, through each cell to the nets of its signal outputs, and on. Each
    path ends at -to (an output port or an input pin), or without -to at
    each end of the fanout: an output port, a stub of a spine (a leaf's
    net ends at its stubs, shown as stub <spine>/<stub>), an input pin of
    a cell whose outputs drive nothing, or the driving pin of a net with
    nothing more on it. The netlist is as get_db pin .net has
    it: the spines, connect_pin, and the cells of add_buffer_on_net,
    connect_spine and create_buffer_tree. A loop is not followed round
    again; at most 10000 paths are listed.

    For each path: every cell on it with its library cell, then the
    number of buffers and the number of inverters (and of other cells),
    and "(polarity inverted)" when the inverters are odd. A cell is an
    inverter or a buffer as create_buffer_tree was told (-inverter_ref,
    -buffer_ref; kept in the database). A library cell it was not told
    about is an inverter when its name has INV in it, a buffer when it has
    BUF (any case); any other is counted apart.

OPTIONS
    -from <port or output pin>
        Where the paths start: one input port (handle or name) or one
        output pin (pin:<inst>/<pin> or <inst>/<pin>).
    -to <port or input pin>
        Where they end: one output port or input pin. Without it, every
        end of the fanout.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    A list with an element per path: {{<end>} <buffers> <inverters>}, e.g.
    lindex [lindex $r 0] 2 is the inverters of the first path.

EXAMPLES
    htree> all_fanout -from [get_db ports clk] -to s1/A
    path 1: port clk -> ct_1 (INV_RP) -> ct_2 (INV_RP) -> ct_3 (INV_RP) -> ct_4 (INV_RP) -> ct_5 (INV_RP) -> ct_6 (INV_RP) -> ct_7 (BUF_RP) -> s1/A
      number of buffers: 1  number of inverters: 6
    {{s1/A} 1 6}

    htree> all_fanout -from sp_L1_inv1/Y
    path 1: sp_L1_inv1/Y -> sp_L2_inv1 (INV_RP) -> sp_L3_inv1 (INV_RP) -> stub sp/stub1
      number of buffers: 0  number of inverters: 2
    path 2: sp_L1_inv1/Y -> sp_L2_inv1 (INV_RP) -> sp_L3_inv2 (INV_RP) -> stub sp/stub2
      number of buffers: 0  number of inverters: 2
    2 path(s); buffers 0 .. 0, inverters 2 .. 2
    {{stub sp/stub1} 0 2} {{stub sp/stub2} 0 2}

ERRORS
    HT4-001  -from missing, -from or -to not one port or pin, or a -from
             that drives nothing
    HT4-022  -from or -to names no port or pin
    HT4-305  no path from -from (to -to) in the netlist

SEE ALSO
    create_buffer_tree, connect_spine, add_buffer_on_net, get_db
