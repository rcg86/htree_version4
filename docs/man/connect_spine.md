NAME
    connect_spine - connect the inputs of spines, input pins, and output
    ports through a buffer, to the nearest stub of a spine (the netlist)

SYNOPSIS
    connect_spine -from <spine> -to <spines | pins | ports>
                  [-ref_name <lib_cell> -distance <um> [-name <prefix>]]

DESCRIPTION
    Makes the spine given with -from the driver of what -to names: each
    spine of -to, and each pin, goes onto the net of the stub of -from
    that is nearest to it. An output port of -to is driven through a
    buffer, which this command makes and places (see 'A port' below).
    Else only the netlist changes: get_db pin:<inst>/<pin> .net shows
    it, write_logical and write_def write it. No wire is made, moved or
    removed.

    The driver (-from) is one built spine (create_spine -build), by name
    or handle (spine:<name>). Its stubs are the ones a leaf drives (get_db
    spine:<name> .stubs); the net of a stub is the net of its leaf,
    <leaf>_<output pin>.

    What -to takes, one or a Tcl list:
      a spine      name or spine:<name>. Its input is the first signal
                   input pin of its root cell. A mirrored spine
                   (create_spine -mirror) has two roots: both pins are
                   connected, to the same stub.
      a pin        pin:<inst>/<pin> or <inst>/<pin>, an input pin of an
                   instance (a buffer, say). Any other direction is an
                   error (HT4-251).
      a port       port:<design>/<port> or <port>, an output port of the
                   design (or an inout one). It needs -ref_name and
                   -distance. An input port is an error (HT4-251).

    The nearest stub. Each of -to picks its stub on its own, so two of
    them may pick the same one: a stub can drive any number. The distance
    is the Manhattan distance (in x plus in y) from a point of the target
    to the nearest point of the centre line of the stub (get_db
    stub:<spine>/<stub> .points), bends included. The point of the target
    is the centre of the shapes of its pin; for a mirrored spine the
    middle of its two root pins; for a port the centre of its shapes
    (where it is placed, when it has none). Of two stubs at the same
    distance the first of the spine is taken. The report gives the stub
    and the distance of each.

    A port. A stub does not drive a port itself: a buffer goes between
    them. For each port of -to the command makes an instance of
    -ref_name, puts its input pin on the net of the stub nearest to the
    port and its output pin on the net of the port (get_db
    port:<design>/<port> .net), which it then drives: get_db net:<net>
    .driver gives pin:<buffer>/<output pin>, .ports the port. No net is
    made.
      The cell     needs a SIZE, a signal input pin and a signal output
                   pin (HT4-257); the first of each is used.
      The name     <prefix>_<port>, with the prefix of -name (default
                   buf); <prefix>_<port>_2, _3 ... when an instance of
                   that name exists. Characters of the port name other
                   than letters, digits and _ become _: the buffer of
                   d[3] is <prefix>_d_3.
      The place    the centre of the output pin of the buffer is
                   -distance from the centre of the port, in x plus y,
                   on the way to the nearest point of the stub: along
                   the longer of the two legs (x, y) first, then along
                   the other. When that puts the cell outside the design
                   boundary the other leg is taken first; when both do,
                   the way that keeps the pin inside it (a way along the
                   edge of the die: the cell is across the edge, and the
                   legalization takes it off the edge). A port whose
                   stub is nearer than -distance gets its buffer at the
                   stub, and the report says so. The cell has the
                   orientation of the leaf that drives the stub, and its
                   corner is on the manufacturing grid.
      On sites     the buffers are then legalized (legalize_placement
                   -inst <the buffers>, its messages are part of the
                   output): each moves to the nearest free site, so it
                   may end up a site step or a row beside its point. The
                   report gives the centres and the distances from the
                   port as placed. Without placement rows the buffers
                   stay on the manufacturing grid (HT4-264). A buffer
                   that still overlaps another instance (HT4-261), or is
                   not inside the design boundary (HT4-262), is named in
                   a warning and still made.
    The buffer is an instance of no spine, as create_inst makes one: no
    spine moves it. A port that is nowhere (no shapes and no location in
    the DEF PINS) is an error (HT4-269): its nearest stub is not known.
    A port driven already. One whose buffer is on the net of its nearest
    stub (this command run again) is left as it is. One with any other
    driver is an error (HT4-269): take the driver off first
    (disconnect_pin -pin <buffer>/<output pin>; the instance stays, there
    is no command that removes it).
    The buffer options are used for ports only: without a port in -to
    they are not looked at.

    A pin on a net already. A pin that is on the net of its stub is left
    as it is. One that is on another net is taken off that net first, as
    disconnect_pin does, and the report names it: the root of a spine is
    on the root_net of its spine spec until it is connected, and a pin
    that an earlier connect_spine put on another stub moves to the new
    one.

    Loops. A spine cannot drive itself: -to may not hold the -from spine,
    a pin of one of its cells, or a spine or pin whose instance drives
    the -from spine through any number of cells (HT4-268).

    Everything is checked before anything is changed: on an error nothing
    is connected and no buffer is made.

    Routing. A leaf's net keeps its stub as its only load for route_net
    (get_db spine_net:<spine>/<net> .loads): the connections made here are
    in the netlist only, and route_net does not route the stub's net to
    these pins. The routing of the stub's net is as it was. So is that of
    a net a pin was taken off: a routed net of no spine (a port's, a
    buffer's) still has its wires to the pin (HT4-254); route it again.
    The buffer of a port gets no pin routes (run route_pin on it), and
    route_net does not route the net from its output to the port: a net
    of no spine is routed to input pins of instances only (see 'man
    route_net').

OPTIONS
    -from <spine>
        The spine whose stubs drive: one built spine. Required.
    -to <spines | pins | ports>
        The spines, input pins and output ports to connect, as a Tcl
        list. Required.
    -ref_name <lib_cell>
        The library cell of the buffers of the ports, or its handle.
        Required with a port in -to.
    -ref_cell <lib_cell>
        The same as -ref_name, under the name the other commands give
        the option. One of the two, not both.
    -distance <um>
        The distance from a port to the output pin of its buffer, in x
        plus y, microns, above 0. Required with a port in -to.
    -name <prefix>
        The prefix of the buffer names. Default: buf.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the pins of -to (pin:<inst>/<pin>): the root input
    pins of the spines, the pins given, and for a port the input pin of
    its buffer.

EXAMPLES
    htree> connect_spine -from sp -to {sp2 spine:sp3 buf1/A}
    connect_spine: spine sp (2 stub(s)) -> 3 of -to, 4 pin(s) connected
      To          Stub   Net           Distance  Pins
      spine sp2   stub1  sp_L3_inv1_Y    32.521  sp2_L1_inv1/A
      spine sp3   stub2  sp_L3_inv2_Y    47.472  sp3_L1_inv1/A sp3_mirror_L1_inv1/A
      pin buf1/A  stub1  sp_L3_inv1_Y    23.192  buf1/A
      disconnected first: sp2_L1_inv1/A from net net, sp3_L1_inv1/A from net net, sp3_mirror_L1_inv1/A from net net
      netlist only: no wire is made, and route_net does not route a leaf's net to these pins
    pin:sp2_L1_inv1/A pin:sp3_L1_inv1/A pin:sp3_mirror_L1_inv1/A pin:buf1/A
    htree> get_db pin:sp2_L1_inv1/A .net
    spine_net:sp/sp_L3_inv1_Y
    htree> get_db pin:sp3_mirror_L1_inv1/A .net.driver
    inst:sp_L3_inv2
    htree> connect_spine -from sp2 -to sp
    **ERROR: (HT4-268): connect_spine: spine sp is in spine sp2 or drives it (sp_L1_inv1): its stub cannot drive it
    htree> connect_spine -from sp -to {q top} -ref_name INV_RP -distance 10 -name out
    connect_spine: spine sp (2 stub(s)) -> 2 of -to, 2 pin(s) connected, 2 buffer(s) made
      To        Stub   Net           Distance  Pins
      port q    stub1  sp_L3_inv1_Y     91.36  out_q/A
      port top  stub2  sp_L3_inv2_Y     71.36  out_top/A
      buffers (INV_RP, the output pin 10 um from the port, x + y; as placed):
        Port  Buffer   Drives                Centre          From port
        q     out_q    out_q/Y -> net q_net  {90.36 9.989}   10
        top   out_top  out_top/Y -> net top  {20.36 89.989}  10
      netlist only: no wire is made, and route_net does not route a leaf's net to these pins, nor the net of an output port
      Next: legalize_placement, route_pin -inst {out_q out_top}
    pin:out_q/A pin:out_top/A
    htree> get_db net:q_net .driver
    pin:out_q/Y
    htree> connect_spine -from sp2 -to q -ref_name INV_RP -distance 10
    **ERROR: (HT4-269): connect_spine: port q is driven already, by out_q/Y: take that off first (disconnect_pin -pin out_q/Y)

ERRORS
    HT4-001  -from or -to missing, -from with more than one spine, an
             unknown option; with a port in -to: -ref_name or -distance
             missing, -ref_name and -ref_cell both given, a distance
             that is not a number above 0, or a bad prefix
    HT4-022  no built spine of that name, or -to names neither a spine,
             a pin nor a port
    HT4-026  a port in -to and no physical library loaded (read_lef)
    HT4-251  a -to pin is not an input pin of an instance, the root of a
             -to spine has no signal input pin, or a -to port is an
             input port
    HT4-254  WARN: a pin was taken off a net that is routed to it; its
             routing is not changed
    HT4-257  the cell of the buffers is not in the library, or has no
             SIZE, signal input pin or signal output pin
    HT4-261  WARN: a buffer overlaps another instance
    HT4-262  WARN: a buffer is not inside the design boundary
    HT4-264  WARN: the buffers are not on placement sites: the design has
             no rows, or legalize_placement failed (its message follows)
    HT4-267  the -from spine has no stub driven by a leaf
    HT4-268  a loop: -to holds the -from spine, one of its pins, or a
             spine or pin that drives it
    HT4-269  a -to port is nowhere (no shapes, no location), or is
             driven already by another pin

SEE ALSO
    connect_pin, disconnect_pin, create_spine, add_buffer_on_net,
    legalize_placement, route_pin, route_net, write_logical, get_db
