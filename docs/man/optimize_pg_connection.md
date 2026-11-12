NAME
    optimize_pg_connection - extend the cells' power straps to reach more of
    the power grid

SYNOPSIS
    optimize_pg_connection -inst <insts> [-extend <um>]

DESCRIPTION
    Looks at every power strap of the instances (a route_pin strap on a
    power net: not SIGNAL and not a routed signal net, so VDD_SOC and VSS)
    for a chance to connect it to more of its power net by extending it
    horizontally, and makes those connections, so the cells' power pins
    have more paths to the power grid.

    The power grid here is what the tools built: the VDD_SOC and VSS
    shields of route_net -shield and route_final_stub -shield, and the
    cells' own power straps. (The DEF has no SPECIALNETS read.)

    For each power strap:
      - Its reach is the strap with the extensions it already has on its
        band (route_net's to its shields, this command's earlier ones).
      - On each side it may grow up to -extend um beyond that reach, to
        the farthest shape of its own net in range, so it picks up every
        one on the way:
          a vertical power wire of the same net crossing the whole strap
          band (a shield on the vertical layer): the strap is extended to
          cover it, and a crossing box is stored for the via;
          a same-net strap of a neighbouring cell on the same band: the
          strap is extended to touch it.
      - The extension must keep the strap layer's tech spacing to shapes
        of other nets on that layer; if the farthest target is blocked,
        the next nearer one is tried.

    The pieces are stored per instance, as net_wire rows of net
    pg:<inst> (kind pg_ext and pg_cross, .shield_net the power net).
    Running the command again on an instance replaces its pieces.
    move_obj and legalize_placement move them with the instance; route_pin
    on the instance (which rebuilds its straps) removes them. write_def
    writes the extensions as stripes of their power net; the GUI draws
    them labelled with it.

    The report gives, per instance, each strap extended, how many
    connections it had before, how far it grew on which side and what it
    gained; and the total of new connections.

OPTIONS
    -inst <insts>
        Instance names, glob patterns or inst: handles, as a Tcl list:
        [get_db insts], *temp_*. Required.
    -extend <um>
        How much further a strap may grow on each side. Default 1.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the instances that got new connections.

EXAMPLES
    htree> optimize_pg_connection -inst [get_db insts] -extend 3
      temp_L2_inv1: strap 2 VDD_SOC (2 connection(s) before): extended 1.68 left +1 crossing(s); strap 6 VDD_SOC (2 connection(s) before): extended 1.68 left +1 crossing(s)
      ...
    optimize_pg_connection: 45 new power connection(s) on 25 instance(s), straps extended up to 3 um more on each side

ERRORS
    HT4-001  missing -inst, or -extend not a positive number
    HT4-215  no instance matches a -inst word
    HT4-216  WARN: the instances have no power straps (route_pin)

SEE ALSO
    route_pin, route_net, route_final_stub, write_def, move_obj
