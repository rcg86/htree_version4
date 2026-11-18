"""route_track -net <nets> -rule <rule> [-compact] [-via_weight <um>]: route
nets as route_net does, and report the signal tracks they use; -compact packs
them on the fewest tracks.

    route_track -net [get_db nets .name] -rule rule1 -shield -compact
    route_track -net sp_L1_inv1_Y -rule rule1

The router is route_net's (core/commands/route_net.py: the nets, the pin
routes, the design boundary, -shield): without -compact the wires are the
same. After the nets, the table of the signal tracks they lie on, in bands of
tracks next to each other: the wire on every track, and the empty ones.

-compact, for a design short of horizontal and vertical tracks:
  - the tracks route_final_stub gives the stubs are kept free, so the stubs
    take the track next to the cells and no net lies between them and the
    cells; a stub routed before on another track loses its wires (HT4-279);
  - a net keeps to the tracks of its pins: a wire on a track beyond them
    costs more of its length for every track further out, so a net leaves its
    track only to pass what blocks it and takes the nearest free one; of
    tracks that are equal, the one nearest the stubs of its spine;
  - a branch may leave the driver's strap on either side of its cell (any
    signal track the extended strap covers), not only where the first branch
    left it; another place costs one layer change.
The nets are still routed one after another, in the order given.
"""

from core.commands import route_net

NAME = "route_track"
SUMMARY = "Route nets as route_net and report the tracks used; -compact packs the tracks"

OPTIONS = dict(route_net.OPTIONS, **{"-compact": "flag"})


def run(session, argv):
    return route_net.run_as(session, argv, NAME, OPTIONS)
