NAME
    insert_pg_grid - lay power wires on a layer's power tracks, from the
    design boundary to the boundary

SYNOPSIS
    insert_pg_grid -layer <layer> [-pull_back_distance <um>]

DESCRIPTION
    Completes the VDD_SOC and VSS routing of a layer over the whole block:
    every power track of the layer gets a wire of its net from one side of
    the design boundary to the other.

    The power tracks are those the layer's track assignment gives a power
    net: with assign_track_for_route -layer IA -net {VDD_SOC NA - NA VSS
    NA - NA} the VDD_SOC tracks get VDD_SOC and the VSS tracks VSS; signal
    ('-') and blank (NA) tracks get nothing. The tracks run as the
    assignment numbers them: horizontal on a layer with y tracks, vertical
    on one with x tracks.

    Each wire runs along every part of its track that is inside the
    design boundary (DEF DIEAREA, rectilinear: an L or a notch gives a
    track two parts, or one shorter part), stopping -pull_back_distance um
    short of the boundary at each end.

    No short: where a shape of another net is on the layer (the spine
    cells' straps and pin routes, signal wires, the other power net's
    shields, via pads) the wire is broken, clear of it by the spacing, as
    route_net's shields are. Shapes of its own net may touch it (a cell's
    VDD_SOC strap on a VDD_SOC track joins it). A piece shorter than the
    wire is wide is left out.

    Width and spacing: those of the first route rule with the layer
    (create_route_rule), else the layer's tech width and spacing; the
    spacing is at least the tech spacing for the two shapes' widths.

    The wires are net_wire rows of net pg_grid:<layer> (kind pg_grid,
    .shield_net the power net). Running the command again on a layer
    replaces them. check_drc and write_def count and write them under
    their power net (DEF SPECIALNETS).

    No via is made. Run insert_vias (or assign_via_for_route) after it to
    join the grid to the power wires that cross it; until then check_drc
    reports the wires as power opens. A grid on two layers (IA and IB)
    makes a mesh; insert_vias over the whole design then has a crossing at
    every power track pair, which takes long on a large die.

OPTIONS
    -layer <layer>
        The routing layer (name or layer: handle). It needs a track
        assignment (assign_track_for_route). Required.
    -pull_back_distance <um>
        How far short of the design boundary each wire stops, at each end.
        Default 1; 0 runs it to the boundary.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the wires (net_wire:pg_grid:<layer>/<n>).

EXAMPLES
    htree> assign_track_for_route -layer IA -net {VDD_SOC NA - NA VSS NA - NA}
    htree> insert_pg_grid -layer IA -pull_back_distance 1
    insert_pg_grid: IA horizontal power tracks, 0.72 wide, 0.72 (at least the tech spacing) from other nets, 1 um short of the boundary: 5223 wire(s), 924179.72 um
      VDD_SOC: 2456 track(s), 2614 piece(s), 453633.48 um
      VSS: 2455 track(s), 2609 piece(s), 470546.24 um
      2011.24 um left out where shapes of other nets are on IA (the spine cells' straps and routes): no short
      no via is made: assign_via_for_route or insert_vias to join it to the crossing power wires
    htree> insert_vias -bottom_layer IA -top_layer IB

ERRORS
    HT4-001  -layer missing, a layer not in tech, a -pull_back_distance
             below 0, no design boundary, or no width for the layer
    HT4-309  the layer has no track assignment, or it gives no track a
             power net
    HT4-310  WARN: a power track got no wire: blocked all the way, or too
             short inside the boundary

SEE ALSO
    assign_track_for_route, create_route_rule, insert_vias,
    assign_via_for_route, route_net, optimize_pg_connection, check_drc,
    write_def
