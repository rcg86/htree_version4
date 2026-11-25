NAME
    promote_port_to_layer - put ports of the design on a routing layer,
    a given width wide

SYNOPSIS
    promote_port_to_layer -port <ports> -layer <layer> -width <um>
                          [-snap_to_track]

DESCRIPTION
    Replaces the shapes of each port given (DEF PINS) with one rectangle
    on -layer, so a route on that layer can reach it. A port on a layer
    below the route rule's is left to the top level by route_net: the
    route stops at least 1 um from it, not connected (HT4-266). Promoted
    to one of the rule's layers, the route ends on it, connected.

    The rectangle:
      - across the layer's direction (x on a vertical layer, y on a
        horizontal one) it is -width;
      - along it, as long as the old shapes were, and at least -width;
        a layer with no direction gets a -width square;
      - its centre is the centre of the old shapes (or of the port's
        location when it has none);
      - when it would stick out of the design boundary it is moved in
        just far enough: a port on the die edge stays on the edge;
      - with -snap_to_track, it is then moved across the layer's
        direction so its centre line is on the nearest signal track of
        the layer that keeps it inside the boundary: the tracks route_net
        uses (every DEF track of the layer, or the '-' ones of
        assign_track_for_route). A route on that track then runs straight
        onto the port. The report gives the track and how far the port
        moved; a move of more than one track pitch is warned (HT4-318);
      - its corners are on the manufacturing grid.

    The database keeps it (write_db). write_def writes each promoted port
    in PINS, its new shape and layer in place of the old. read_def of the
    design gives the ports their old shapes again (write_def then leaves
    them out).

OPTIONS
    -port <ports>
        The ports, as a Tcl list of names or port:<design>/<name>
        handles (get_db ports). Required.
    -layer <layer>
        A routing layer of the tech. Required.
    -width <um>
        The width of the new shape across the layer's direction, in
        microns, above 0. Required.
    -snap_to_track
        Put the port's centre line on the nearest signal track of the
        layer. Default: centred where the old shapes were.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the ports promoted.

EXAMPLES
    htree> promote_port_to_layer -port mgt_clk_ctm2_iose_local_clk_25 -layer IB -width 0.72
    promote_port_to_layer: port mgt_clk_ctm2_iose_local_clk_25: on IB at {5559.838 0 5560.558 0.72}, 0.72 x 0.72 (was D12 {5560.138 0 5560.258 0.09175})
    port:cf999/mgt_clk_ctm2_iose_local_clk_25
    htree> promote_port_to_layer -port mgt_clk_ctm2_iose_local_clk_25 -layer IB -width 0.72 -snap_to_track
    promote_port_to_layer: port mgt_clk_ctm2_iose_local_clk_25: on IB at {5559.84 0 5560.56 0.72}, 0.72 x 0.72 (was D12 {5560.138 0 5560.258 0.09175}), on the IB signal track at x 5560.2 (moved 0.002)
    htree> route_net -net [get_db nets mgt_clk_ctm2_iose_local_clk_25] -rule rule1

ERRORS
    HT4-001  an option missing, -port empty, -width not a number
             above 0, or -snap_to_track on a layer with no direction or
             with no signal track that keeps the port inside the boundary
    HT4-025  no tech read (read_tech)
    HT4-315  no such port, or a port with no shapes and no location
    HT4-316  -layer is not a routing layer of the tech
    HT4-317  (warning) the new shape is not inside the design boundary
    HT4-318  (warning) -snap_to_track moved the port more than a track
             pitch

SEE ALSO
    route_net, get_db, read_def
