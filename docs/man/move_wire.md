NAME
    move_wire - move route wires (net wires, straps, pin wires) by a
    distance

SYNOPSIS
    move_wire -wires <wires> -delta {<dx> <dy>}

DESCRIPTION
    Moves each wire by dx in x and dy in y (microns). A wire keeps its
    size, net and layer; only its place changes. Wires are route shapes:
      net_wire:<net>/<n>   route_net, route_final_stub and
                           optimize_pg_connection wires, extensions,
                           shields, shield extensions and crossing boxes
      strap:<inst>/<n>     route_pin straps
      pin_wire:<inst>/<pin> route_pin pin wires
    Every handle is checked before anything moves.

    Nothing else follows a moved wire: the crossing boxes on it and the
    shapes it connected to stay where they are. A wire whose centre line
    is then off its layer's tracks (a horizontal wire: DEF TRACKS Y, a
    vertical one: TRACKS X) is reported (HT4-222). route_net, route_pin
    and route_final_stub replace hand edits when they run again. The
    auto vias stretch_wire added to a moved wire are removed.

    The GUI's Tools > Move runs this command when a wire is dragged
    (several when the dragged wire is selected with others); Tools > Undo
    Edit moves it back.

OPTIONS
    -wires <wires>
        Wire handles as a Tcl list, e.g. [get_db selected]. Required.
    -delta {<dx> <dy>}
        How far to move, in microns. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the wires moved.

EXAMPLES
    htree> move_wire -wires net_wire:temp_L2_inv1_Y/3 -delta {0 1.44}
    move_wire: moved 1 wire(s) by 0 1.44
    htree> move_wire -wires [get_db selected] -delta {-0.72 0}

ERRORS
    HT4-001  missing -wires or -delta, or -delta not two numbers
    HT4-220  no wires, or a handle that is not a route wire
    HT4-222  WARN: a wire is off the tracks of its layer

SEE ALSO
    stretch_wire, route_net, route_pin, gui_show
