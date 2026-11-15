NAME
    delete_wire - delete route wires (net wires, straps, pin wires);
    -undo puts them back

SYNOPSIS
    delete_wire -wires <wires>
    delete_wire -undo

DESCRIPTION
    Removes the wires given from the database. Wires are the route shapes
    of move_wire:
      net_wire:<net>/<n>   route_net, route_final_stub and
                           optimize_pg_connection wires, extensions,
                           shields, shield extensions, crossing boxes and
                           auto vias
      strap:<inst>/<n>     route_pin straps
      pin_wire:<inst>/<pin> route_pin pin wires
    Every handle is checked before anything is deleted.

    Only the wires given go, and what cannot stay without them:
      - the pin wires that end on a deleted strap (the pin is then as
        before route_pin: route_net ends near it, not connected, HT4-172);
      - the auto vias stretch_wire added to a deleted wire.
    Nothing else follows a deleted wire: the crossing boxes on it and the
    shapes it connected to stay, and its net is left open there. The other
    wires keep their handles (the numbers of a net's wires and of an
    instance's straps are not closed up). To remove the whole routing of
    a net use delete_route; route_net, route_pin and route_final_stub
    replace hand edits when they run again.

    Undo. The wires of each delete_wire are kept, in this session only
    (write_db does not save them, read_db forgets them). delete_wire -undo
    puts the wires of the last delete_wire back as they were, with the
    same handles; -undo again, those of the one before. A wire is not put
    back (HT4-224) when a wire made since has its handle (the net was
    routed again, route_pin ran again on the instance), or its instance
    is gone.

    The GUI's Tools > Delete runs this command on the selected wires;
    Tools > Undo Edit runs delete_wire -undo.

OPTIONS
    -wires <wires>
        Wire handles as a Tcl list, e.g. [get_db selected].
    -undo
        Put back the wires the last delete_wire removed. Not with -wires.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the wires deleted (those that went with them included),
    or with -undo of the wires put back.

EXAMPLES
    htree> delete_wire -wires net_wire:temp_L2_inv1_Y/3
    delete_wire: deleted 1 wire(s)
      delete_wire -undo puts them back
    htree> delete_wire -wires strap:temp_L2_inv1/3
    delete_wire: deleted 1 wire(s)
      and 1 that cannot stay without them (pin wires on a deleted strap, auto vias): pin_wire:temp_L2_inv1/A
      delete_wire -undo puts them back
    htree> delete_wire -undo
    delete_wire: put back 2 wire(s): strap:temp_L2_inv1/3 pin_wire:temp_L2_inv1/A
    htree> delete_wire -wires [get_db selected]

ERRORS
    HT4-001  neither -wires nor -undo, or both
    HT4-220  no wires, or a handle that is not a route wire
    HT4-223  -undo with no deleted wires to put back
    HT4-224  WARN: -undo could not put a wire back (its handle is taken,
             or its instance is gone)

SEE ALSO
    move_wire, stretch_wire, delete_route, route_net, route_pin, gui_show
