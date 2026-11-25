NAME
    connect_pin - connect input pins, and output ports through a buffer, to
    an output pin or an input port (the netlist)

SYNOPSIS
    connect_pin -from <pin | port> -to <pins | ports> [-disconnect]
                [-ref_cell <lib_cell> [-distance <um>] [-name <prefix>]]

DESCRIPTION
    Connects the pins of -to to the driver given with -from. Only the
    netlist changes: get_db pin:<inst>/<pin> .net shows it, write_logical
    writes it. No wire is made, moved or removed. An output port in -to
    also gets a placed buffer (below).

    The driver (-from) is one of:
      an output pin of an instance   pin:<inst>/<pin> or <inst>/<pin>
      an input port of the design    port:<design>/<port> or <port>
                                     (an input port drives the nets
                                     inside the design)
    The loads (-to) are input pins of instances and output ports of the
    design, one or a Tcl list. Any other direction is an error (HT4-251):
    an input pin or an output port as -from, a pin that is not an input
    (output, inout, a power pin without a direction) or an input port in
    -to.

    An output port. A net does not join a driver and an output port
    straight: each output port of -to is driven through a buffer, always
    (-ref_cell is then required). The buffer is an instance of -ref_cell,
    oriented N, its output pin -distance um (default 10, x + y) from the
    port on the way to the driver (inside the design boundary where it
    can), then put on a site (legalize_placement). Its input goes on the
    net of the driver, its output on the net of the port: it drives the
    port. Its name is <prefix>_<port> (-name, default buf; a bit of a bus
    d[3] gives buf_d_3; _2, _3 ... when taken). A port driven already is an
    error (HT4-308); with -disconnect its driver is taken off it first. A
    port on the driver's net is an error too (HT4-308): the buffer needs
    two nets. -ref_cell is taken to be what you say it is: one inverter
    inverts the port's signal (all_fanout counts it). Everything is checked before
    anything is changed: on an error nothing is connected.

    The net. There is no net option: a net is known by its driver, and the
    loads go onto the net of the driver:
      a port                       the net of the port (DEF PINS, + NET)
      the output of a spine cell   its spine net, <inst>_Y
      another output pin           <inst>_<pin>, a new net with the first
                                   load; write_logical creates it
    A net whose last load is taken off (disconnect_pin, -disconnect) is
    gone, unless it is a spine net.

    A pin on a net already. A -to pin that is on the driver's net is left
    as it is. One that is on another net is an error (HT4-253) and nothing
    is connected. With -disconnect such a pin is taken off its net first,
    as disconnect_pin does, then connected to the driver. The connections
    a pin can have before connect_pin:
      - the ones create_spine -build made: a spine cell's input is on the
        net of the cell that drives it;
      - the root of a spine: its input is on the spine's root net
        (<spine>_primary_input when the spec's root_net is the
        placeholder 'net'; get_db spine:<name> .root_net).
        Once taken off, it goes back onto that net only from a port
        whose net it is: no other driver of it is known here;
      - the ones of an earlier connect_pin.

    Spine nets. A load connected to the output of a spine cell by the
    first signal input pin of its cell becomes a load of that spine net,
    as if the spine had been built with it (get_db spine_net:... .loads):
    route_net routes to it, write_def lists it, check_drc checks it. This
    is not so for a leaf's net (it keeps its stub as its only load there)
    and for a pin that is not the first input of its cell: such a
    connection is in the netlist only, and connect_pin says so.

    Nets of no spine. A net that is not a spine net (driven by a port or
    by an instance of create_inst) is a net:<name> object. route_net
    routes it as well, to the pins on it, once it has one driver and an
    input pin on it (route_net -net net:<name>); write_def writes it and
    check_drc checks it.

    Routing. A net that is routed keeps its wires as they are: they do
    not reach a new load, and still go to a pin taken off the net
    (HT4-254). Route the net again. The lengths and centre lines the
    spine build planned for a spine net are not worked out again.

OPTIONS
    -from <pin | port>
        The driver: one output pin of an instance or one input port of
        the design. Required.
    -to <pins | ports>
        The input pins and output ports to connect, as a Tcl list.
        Required.
    -disconnect
        Take a -to pin that is on another net off that net first, and a
        -to port's driver off the port. Without it either is an error.
    -ref_cell <lib_cell>
        The cell of the buffer of each output port of -to. Required when
        -to has an output port.
    -distance <um>
        How far the buffer's output pin is from its port, x + y. Default
        10.
    -name <prefix>
        The prefix of the buffer names: <prefix>_<port>. Default buf.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the -to pins (pin:<inst>/<pin>), then the buffer of
    each -to port (inst:<name>).

EXAMPLES
    htree> connect_pin -from port:top/clk -to buf1/A
    connect_pin: net clk: port clk -> buf1/A
      a net of no spine: route_net -net net:clk -rule <rule> routes it
    htree> connect_pin -from buf1/Y -to sp_L1_inv1/A
    **ERROR: (HT4-253): connect_pin: already connected: sp_L1_inv1/A (net net); -disconnect takes a pin off its net first
    htree> connect_pin -from buf1/Y -to sp_L1_inv1/A -disconnect
    connect_pin: net buf1_Y (new): buf1/Y -> sp_L1_inv1/A
      disconnected first: sp_L1_inv1/A from net net
      a net of no spine: route_net -net net:buf1_Y -rule <rule> routes it
    htree> get_db pin:sp_L1_inv1/A .net
    net:buf1_Y
    htree> get_db pin:sp_L1_inv1/A .net.name
    buf1_Y
    htree> connect_pin -from sp_L2_inv1/Y -to {dummy1/A dummy2/A}
    connect_pin: net sp_L2_inv1_Y: sp_L2_inv1/Y -> dummy1/A dummy2/A
    htree> connect_pin -from [get_db ports clk] -to [get_db ports q] -ref_cell INV_RP
    **WARN: (HT4-264): connect_pin: no placement rows (read_def a DEF with ROW statements), so the buffers are on the manufacturing grid, not on sites: run legalize_placement on them once the rows are read
    connect_pin: net clk: port clk -> buf_q/A
      output ports, each driven through a buffer (its output pin from the port, x + y; as placed):
        port q: buf_q (INV_RP) at {90.36 9.989}, 10 um; buf_q/Y -> net q_net
      Next: legalize_placement, route_pin -inst {buf_q}, then route_net -net {clk q_net}
    inst:buf_q

ERRORS
    HT4-001  -from or -to missing, -from with more than one pin, an
             output port in -to without -ref_cell, a -distance that is
             not above 0, a bad -name, or an unknown option
    HT4-022  no such pin or port, or an object that is neither
    HT4-251  wrong direction: -from is not an output pin or an input
             port, or a -to pin is not an input pin of an instance
    HT4-252  the new net <inst>_<pin> would have the name of another net
    HT4-253  a -to pin is on another net; use -disconnect
    HT4-254  WARN: a net with routing got or lost a pin; its routing is
             not changed
    HT4-257  -ref_cell is not in the library, or has no SIZE, signal
             input or signal output pin
    HT4-264  WARN: the buffers are not on placement sites
    HT4-308  a -to port is driven already (use -disconnect), is on the
             driver's net, or has no place

SEE ALSO
    disconnect_pin, connect_spine, create_inst, create_spine, route_net,
    write_logical, get_db
