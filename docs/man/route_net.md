NAME
    route_net - route spine nets on the tracks of a route rule, from the
    driver's output pin to every load's input pin or stub

SYNOPSIS
    route_net -net <nets> -rule <route_rule> [-via_weight <um>]
              [-shield] [-shield_nets {<left/above> <right/below>}]

DESCRIPTION
    Routes each net on two layers of the route rule: its first horizontal
    layer (IA) and its first vertical layer (IB), in the rule's layer
    order. Every wire runs on a track: horizontal wires on the DEF TRACKS Y
    of the horizontal layer, vertical wires on the DEF TRACKS X of the
    vertical layer. When assign_track_for_route has given a layer a
    pattern, only its signal ('-') tracks are used. Wires take the rule's
    width on each layer.

    Lee maze routing. The grid is every track crossing around the net's
    terminals (10 tracks of room on each side). A step along a track costs
    its length; a layer change costs -via_weight um on top (default 5), so
    the router takes the shortest route, and of routes of about the same
    length, the one with the fewest layer changes. Raising -via_weight
    trades longer wire for fewer layer changes. The search is ordered by
    cost plus the distance left (A*), which finds the same cheapest route
    faster. A net with several loads is grown as a tree: from the driver to
    the nearest load, then from any point of the tree to the next nearest,
    until all are reached.

    Pin ends, in two steps. The driver's output pin (direction out) and
    each load's input pin (direction in) are the ends.
      a. Pin routes first. Before any net is routed, the strap of every
         connected signal pin of the nets (route_pin done; the pin wire's
         strap) is extended left and right to the nearest signal track of
         the vertical layer beyond each cell edge: the first signal ('-')
         track, after assign_track_for_route, whose wire is not already
         on the strap, the extension covering that wire. Each side is at
         most the strap's max_extension (max_strap_extension in the pin
         routing spec, default 3 um) and must keep the strap layer's tech
         spacing to other nets' shapes; a side that cannot is left
         unextended and the report says why (no track, too far, blocked).
         The extensions are stored with the net (kind extension, on the
         strap layer); the strap keeps its size.
      b. The route only reaches the pin routes: a vertical wire across the
         extended strap on any signal track it covers, from the horizontal
         track nearest the strap centre. The route never goes to the pin
         itself, and does not decide the extensions.
      - route_pin not done: a warning (HT4-172), and the route ends at the
        track crossing nearest the pin centre, on either layer, not
        connected.
    A leaf net's load is its stub: the route ends at the track crossing
    nearest the stub's tap. The stub itself is not routed.

    Overlap at layer changes. Each wire end is extended by half the width
    of the other layer, so where a horizontal and a vertical wire meet they
    overlap in a full box of (vertical width) x (horizontal width): IB width
    x IA width, not just touching at the centre lines. At a strap the box
    is IB width x the strap width. These boxes are stored with the wires
    (kind cross) for the vias to come; no via is made yet.

    Obstacles. A track crossing is not used on a layer when a box there
    would come closer than the rule spacing to a route_pin strap or pin
    wire on that layer, or to a wire of another routed net. Crossings
    between grid points are not checked.

    Shields (-shield). After a net is routed, each of its wires (the main
    route) at least ignore_shield_less_than_routing_length long (root
    attribute, set_db; default the spec's placement.deviation, else 10 um)
    gets exactly one shield on each side (shorter wire pieces get none;
    the report lists them as "not shielded"), on the same layer, as
    wide as the rule width, on the nearest track whose centre is at least
    width + spacing from the signal's centre (with r1, 0.36 / 0.36, the
    next track, 0.72 away). The shield follows the track: when the layer
    has a track assignment (assign_track_for_route), the shield takes its
    track's net, VDD_SOC on a VDD_SOC track and VSS on a VSS track; next
    to a signal ('-') or blank (NA) track there is no shield on that side
    (warning HT4-177). With
        assign_track_for_route -net {VDD_SOC - VSS -} -layer IB
    the signal runs on a '-' track and the tracks beside it are always one
    VDD_SOC and one VSS. A layer with no track assignment uses
    -shield_nets: the first net left of vertical wires and above
    horizontal ones, the second on the other side (default VDD_SOC VSS).
    A vertical shield runs over the signal wire's span and over the whole
    strap stack of the cells at its ends, so every power strap of those
    cells has the shield of its net beside it. It is cut where it would
    come closer than the rule spacing to another shape on its layer:
    route_pin straps and pin wires, other nets' wires and shields of the
    other power net (shapes of its own power net may touch it), the
    net's own wires (at a jog) and the other shield; pieces shorter than
    the width are dropped. The report gives each shield net's length and
    how much was cut. Shields are stored with the signal net (kind
    shield, .shield_net VDD_SOC or VSS), replaced when the net is routed
    again, drawn labelled with their power net, and written by write_def
    under SPECIALNETS as + SHIELD <signal net> wiring, with + SHIELDNET on
    the signal net.

    Power pins (with -shield). The main route and its shields are never
    extended to the cells; only the cells' pin routes are. The power pins
    reach the shields through their route_pin pin wire and strap: each
    VDD_SOC and VSS strap of the net's cells (two of each in the
    pin routing spec stack) is joined to the shield of its net: crossed
    directly when the shield runs over the strap, otherwise the strap is
    extended left or right to cover the shield, by at most its
    max_extension (max_strap_extension in the pin routing spec), the
    shortest way. With one shield per net, a cell's two VDD_SOC straps both
    join the VDD_SOC shield, and its two VSS straps the VSS shield. An
    extension must keep the rule spacing to shapes of other nets on the
    strap layer. A strap another routed net has already joined (a cell is
    on two nets: its input and its output) is left as it is and reported
    as already joined. Extensions are stored with the net (kind
    shield_ext, .shield_net VDD_SOC / VSS), with a crossing box where strap
    and shield meet, and written by write_def as stripes of the power net.
    At the end the report says how many power pins of the nets' cells are
    connected (the pin's pin wire goes to a joined strap) and warns
    (HT4-177) about the others. Horizontal shields are on the strap layer,
    so straps do not join them.

    Net names. A strap route_net connects, and the pin wire of that pin,
    are shorted to the net, so they take its name: their .net changes from
    SIGNAL to the routed net (e.g. temp_L1_inv1_Y), and write_def writes
    them under that net. Running route_pin again on the instance rebuilds
    its straps on SIGNAL.

    Running route_net again on nets replaces their routing (HT4-173): the
    old wires, extensions, crossing boxes and shields of all the nets given
    are removed before any of them is routed, so none of the old routing
    blocks the new (after move_obj -legal, for example). Their stub wires
    stay (route_final_stub's). The
    net's .route_rule is set to -rule. Wires and boxes are drawn in the
    GUI under "Routes (route_pin, route_net)": wires in their layer colour,
    crossing boxes as white outlines. write_db saves them.

OPTIONS
    -net <nets>
        Spine net names, glob patterns (*temp_L7*), or spine_net: handles,
        as a Tcl list: [get_db nets], [get_db nets .name] and
        {temp_L1_inv1_Y temp_L2*} all work. Every word must match a net.
        get_db nets also lists the final stubs (stubs are nets); route_net
        leaves them to route_final_stub and says which it left. Required.
    -rule <route_rule>
        A rule from create_route_rule with at least one horizontal and one
        vertical layer. Not 'default'. Required.
    -via_weight <um>
        Cost of one layer change, in um of wire. Default 5; 0 counts wire
        length only.
    -shield
        Add one power shield on each side of every wire of the net (its
        track's net), and join the cells' power straps to them.
    -shield_nets {<left/above> <right/below>}
        Shield nets for a layer with no track assignment (implies
        -shield). Default {VDD_SOC VSS}.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    net_wire:<net>/<n>
        a wire, strap extension, crossing box or shield of a routed net:
        obj_type, name (n), kind (wire | extension | cross | shield |
        shield_ext),
        shield_net (a shield's power net), layer (a cross: "<layer>/<layer>"), rect
        ("x1 y1 x2 y2"), width and length (a wire: across and along it;
        a cross: x and y size), net (spine_net handle)
    spine_net:<spine>/<net> .net_wires lists one net's; get_db net_wires
    lists all.

RETURN VALUE
    The handles of the nets that were routed.

EXAMPLES
    htree> create_route_rule -name r1 -layer IA -width 0.36
    htree> create_route_rule -name r1 -layer IB -width 0.36 -append
    htree> route_pin -inst v_L1_inv1 -spec pin_routing_spec.yaml
    htree> route_pin -inst v_L2_inv1 -spec pin_routing_spec.yaml
    htree> route_net -net v_L1_inv1_Y -rule r1
    route_net: rule r1: IA horizontal (width 0.36, spacing 0.36), IB vertical (width 0.36, spacing 0.36); a layer change costs 5 um
      v_L1_inv1_Y: 1 wires, track length 1029.6 um + 0.828 um from the tracks to the strap centres, 0 layer change(s), 2 crossing box(es)
        driver v_L1_inv1/Y (strap 5): connected across the strap (strap extended 0.128 right) at {5624.28 10074.6}
        load v_L2_inv1/A (strap 3): connected across the strap at {5624.28 11104.2}
    htree> route_net -net [get_db nets *L7*] -rule r1 -via_weight 10

ERRORS
    HT4-001  missing -net or -rule, a bad -via_weight, or -shield_nets
             not two nets
    HT4-025  no tech data loaded (read_tech)
    HT4-170  no spine net matches a -net word, or a cell has no signal
             input or output pin
    HT4-171  no such rule, 'default', or a rule without a horizontal and
             a vertical layer
    HT4-172  WARN: route_pin not done on a driver or load: the route ends
             near the pin, not connected
    HT4-173  WARN: the net's old wires were replaced
    HT4-174  WARN: a terminal cannot be reached (blocked); the net is
             routed without it, or not at all
    HT4-176  WARN: a pin or stub is beyond the signal tracks (outside the
             die): its end is taken from the last track
    HT4-177  WARN: power pins whose strap reaches no shield of its net,
             or no shield beside a wire whose next track is not a power
             track
    HT4-175  a rule layer has no DEF tracks in its direction, or its track
             assignment leaves no signal track

SEE ALSO
    create_route_rule, route_pin, assign_track_for_route, create_spine,
    set_db, get_db, gui_show
