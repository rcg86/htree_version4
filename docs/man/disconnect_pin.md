NAME
    disconnect_pin - take pins off their nets (the netlist)

SYNOPSIS
    disconnect_pin -pin <pins | ports>

DESCRIPTION
    Takes each pin given off its net. Only the netlist changes: get_db
    pin:<inst>/<pin> .net shows it, write_logical writes it. No wire is
    made, moved or removed.

    What is given decides what goes:
      an input pin of an instance   the pin is taken off its net. The net
                                    and its other pins stay.
      a driver: an output pin of    every load is taken off its net: a
      an instance, or an input      net is known by its driver, so one
      port of the design            without its driver would have no
                                    name. A port and a spine cell's
                                    output keep their net, without loads;
                                    a net connect_pin made (<inst>_<pin>)
                                    is gone.
      an output pin that drives     the pin is taken off the net of the
      an output port (the buffer    port, and so is every load on it.
      connect_spine made for the    The port keeps its net and has no
      port)                         driver again. The instance stays.
    A pin is given as pin:<inst>/<pin> or <inst>/<pin>, a port as
    port:<design>/<port> or <port>; several as a Tcl list.

    The connections that can be taken off are those of connect_pin, those
    create_spine -build made (a spine cell's input on the net of the cell
    that drives it: the cell leaves the loads of that spine net, and
    route_net no longer routes to it) and the spine spec's root_net on
    the input of a spine's root (write_logical then leaves the root's
    input unconnected). A stub is no pin: it stays on its leaf's net.

    A pin with nothing to take off (on no net, or a driver without a load
    pin) is named in a warning (HT4-255); the others given are done.

    Routing. A routed net keeps its wires as they are: they still go to
    the pin taken off (HT4-254). Route the net again, or remove its
    routing (delete_route). The lengths and centre lines the spine build
    planned for a spine net are not worked out again.

OPTIONS
    -pin <pins | ports>
        The pins and ports to disconnect, as a Tcl list. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the pins taken off a net (pin:<inst>/<pin>): the input
    pins given, the loads of the drivers given, and an output pin that
    drove a port.

EXAMPLES
    htree> disconnect_pin -pin sp_L3_inv2/A
    disconnect_pin: net sp_L2_inv1_Y: sp_L3_inv2/A taken off
    htree> disconnect_pin -pin sp_L2_inv1/Y
    disconnect_pin: net sp_L2_inv1_Y: sp_L2_inv1/Y drives it, 1 load(s) taken off: sp_L3_inv1/A
    htree> disconnect_pin -pin sp_L3_inv2/A
    **WARN: (HT4-255): disconnect_pin: nothing to disconnect on sp_L3_inv2/A: it is on no net, or drives a net without a load pin
    htree> disconnect_pin -pin port:top/clk
    htree> disconnect_pin -pin out_q/Y
    disconnect_pin: net q_net: out_q/Y taken off, it drove port q

ERRORS
    HT4-001  -pin missing, or an unknown option
    HT4-022  no such pin or port, or an object that is neither
    HT4-254  WARN: a net with routing lost a pin; its routing is not
             changed
    HT4-255  WARN: nothing to disconnect on a pin given

SEE ALSO
    connect_pin, connect_spine, delete_route, route_net, write_logical,
    get_db
