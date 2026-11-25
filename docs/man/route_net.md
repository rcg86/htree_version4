NAME
    route_net - route nets on the tracks of a route rule, from the
    driver's output pin to every load's input pin or stub

SYNOPSIS
    route_net -net <nets> -rule <route_rule> [-via_weight <um>]
              [-shield] [-shield_nets {<left/above> <right/below>}]
              [-min_routing_distance <um> [-max_routing_distance <um>]]
              [-force] [-eco]

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
         unextended and the report says why (no track, too far, blocked,
         outside the design boundary).
         The strap itself is lengthened: one shape on its own y, no
         piece of metal beside it, so the strap, the route's crossing box
         and its via stay aligned. The stretch is the net's: routing the
         net again or delete_route takes it back (the strap goes back to
         the size route_pin gave it), and route_pin making the cell's
         straps again drops it (HT4-162 names the nets to route again).
         get_db strap .rect is the lengthened strap; max_extension is
         counted from route_pin's.
      b. The route only reaches the pin routes: a vertical wire across the
         extended strap on any signal track it covers, from the horizontal
         track nearest the strap centre. The route never goes to the pin
         itself, and does not decide the extensions.
      - route_pin not done: a warning (HT4-172), and the route ends at the
        track crossing nearest the pin centre, on either layer, not
        connected.
    A leaf net's load is its stub: the route ends at the stub's tap (half
    way along the stub, bends included), on the track route_final_stub
    gives the stub. That is the track the stubs of the spine on one
    centre line share, which need not be the one nearest this stub (see
    'man route_final_stub'); route_net works it out the same way, once a
    run, from the shapes as they are when the first leaf net of the spine
    is routed. The stub itself is not routed, and its track is not kept
    free for it: a net routed later may take it, and route_final_stub
    then moves the stubs (HT4-192 there for a leaf route that ends short).
    When the stub is routed already (route_final_stub), the route ends on
    its wire, at the track crossing nearest the point of the wire nearest
    the tap.

    Nets of no spine. -net also takes a net that is no spine's (net:<name>;
    get_db pin:<inst>/<pin> .net gives it): the net of an input port of
    the design, or one connect_pin, connect_spine or add_buffer_on_net
    made. It needs one driver (an input port, or an output pin) and one
    or more loads: input pins of instances, or output ports of the design
    (the net of a buffer that drives a port). A net without is left as it
    is (HT4-265; without
    a message when it only matched a pattern). The ends are the pins on
    the net, whichever pin of its cell each is, with their pin routes as
    above (steps a and b). The pins of spine cells are pins as any
    other: the net of a port on the input of the root of a spine is
    routed to that pin.
    A port has no pin route.
      On a layer of the rule: the route ends at the track crossing
      nearest the centre of the port's shapes that is inside the
      boundary. When a wire of the route lies on a shape of the port, on
      the layer of that shape, it is connected ('connected on <layer>').
      When it does not, but a wire on the track of the crossing in that
      layer would overlap the shape, the route goes on along that track
      to the middle of the shape (a crossing box at the crossing when the
      route comes to it on the other layer), clear of other nets by the
      layer's spacing; connected too.
      On no layer of the rule (below it, on the die edge): left to the
      top level. The route stops at the track crossing nearest the port
      that is at least 1 um (x plus y) from its shapes, so nothing of it
      lies over the port; not connected (HT4-266). No wire and no via is
      made down to a port. promote_port_to_layer puts a port on a layer
      of the rule.
    A pin route_pin gave no strap (its net comes from the side) is
    reached on the strap layer: along the track its pin wire was extended
    to, from a crossing with a vertical signal track near it, the wire
    then extended over the pin wire, with an H2/IA crossing box for the
    via ("connected on its pin wire, along the track"). Step a keeps each
    such pin's way out (from the first vertical track left of its cell to
    the first right of it) free of other nets' strap extensions.
    A spine net is routed to the loads of the spine net (get_db
    spine_net:... .loads) and to the input pins connect_pin or
    connect_spine put on it besides (a pin on a leaf's net, a pin that is
    not the first input of its cell, a buffer of connect_spine). With
    -force a fixed net keeps its route and only these are routed to it.

    Side pins. A pin route_pin gave no strap is reached along the track its
    pin wire was extended to; the stretch of that track over the pin wire
    is kept free of every other net, so another net's wire cannot run over
    the place the pin is reached at.

    Routing direction. A cell routed with a pin spec that has
    routing_direction (route_pin, read_pin_spec) is reached only that way:
    vertical, along the vertical layer onto its strap (from above or below;
    a side pin of it by a via from the vertical layer); horizontal, along
    the horizontal layer onto its side pin's track (from the left or the
    right; a strap of it by a via from the horizontal layer). With no way
    in that direction the pin is not routed (HT4-174, "in the routing
    direction of its pin specs").

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

    Design boundary. The boundary (DEF DIEAREA) is a hard limit: nothing
    route_net stores lies outside it. A wire on the boundary line is
    inside; no clearance to the boundary is kept.
      - A track crossing is part of the grid only when its box (vertical
        width x horizontal width) is inside the boundary, and a step along
        a track is taken only when the whole wire of that step is: the
        route goes round a notch or a corner of the boundary, also a
        longer way with more layer changes, never across it.
      - A pin route (step a) is not extended to a track where the
        extension would leave the boundary. At a strap the route ends on
        a crossing whose wire over the whole strap is inside; when the
        track nearest the strap centre has none, the track on the other
        side of the centre is taken.
      - At a stub or an unrouted pin the route ends on the nearest of the
        crossings round the point that is inside.
      - A pin or stub with no such crossing is outside the boundary: its
        net is not routed (HT4-178). When the only way to a load leaves
        the boundary, that load is not routed (HT4-174, "no path inside
        the design boundary").
      - Shields are cut where they would leave the boundary (the report
        gives the length), and a power strap is not extended across it.
    The boundary must be rectilinear (HT4-179 otherwise). A design with no
    boundary (no DIEAREA) is routed without this limit.

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
    the width are dropped. It is also cut where it would leave the design
    boundary. The report gives each shield net's length and how much was
    cut, for either reason. Shields are stored with the signal net (kind
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
    strap layer and stay inside the design boundary. A strap another
    routed net has already joined (a cell is on two nets: its input and
    its output) is left as it is and reported as already joined.
    The power strap itself is lengthened (as the signal straps in step
    a: one shape, no piece beside it), the stretch the net's, with a
    crossing box where strap and shield meet; write_def writes the strap
    as one RECT of the power net.
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
    crossing boxes as white outlines. The via of a crossing box is drawn
    under "Vias", with the via_<bottom>_<top> row of the layer list
    (via_IA_IB). write_db saves them.

    Via definitions. At the end, every via of the routing that has no
    via definition gets one: for each net and layer pair with no
    assignment of assign_via_for_route (neither the net's own nor one for
    every net), the definition of those layers that fits the most of the
    net's vias, each pad inside the net's own metal on its layer (wires,
    straps, pin wires, pin shapes) and each cut inside both. A DEFAULT via
    of the tech LEF comes before another (a power via the DEF generated),
    then, of those that fit every via, the one with the most cuts, then
    pads that run the way their layers do, then the smallest pads. The
    choice is stored as the net's assignment (assign_via_for_route lists
    it and can change it), so write_def writes every via. Printed: the
    definitions given, per layer pair, with the number of nets and vias;
    HT4-297 when no definition of a pair fits some of the vias.
    Before the definitions are chosen, every crossing box is made the
    full crossing of its net's two wires: the vertical wire's width by the
    horizontal wire's width, so each via sits in the middle of the
    crossing. A routed wire that stops short of the other wire's far edge
    is lengthened to it (no further than the box is long); straps, pin
    wires and pins are not. Fixed nets are left. Printed: how many boxes
    moved and wires lengthened.
    A via of a crossing box that its net's definition does not fit (its
    pads past the metal there) while another of the same layers does gets
    that one as its own, kept on the box as insert_vias -via_ref keeps one
    (of those that fit, the first in the order above); the net's
    assignment stays. Every net's vias are looked at, not only the nets
    routed. Printed: how many vias, per layer pair.

    Route length (-min_routing_distance, -max_routing_distance). Each net
    is routed the shortest way first. When the wire from its driver to its
    nearest load is shorter than -min_routing_distance, it is routed again
    as a hairpin: from the driver's crossing a straight leg out (down,
    up, left or right; a leg along the horizontal layer first leaves the
    cell's straps up or down its track), a jog of one track, then the
    shortest way to the loads, back past the driver (over its strap, not
    connected to it). The leg is the shortest that makes the length at
    least -min_routing_distance. Of the four ways and the two jog sides,
    the one whose length is in -min_routing_distance ..
    -max_routing_distance, then with the fewest turns (layer changes:
    the way where the tracks are free, so the route needs no more jogs),
    then the length nearest -min_routing_distance. The report gives the
    length, the way and leg, the turns and the length to each load. A
    route the shortest way already long enough is kept; one longer than
    -max_routing_distance, or one no hairpin on free tracks can make long
    enough, is routed the shortest way with a warning (HT4-300). A
    length a little over -max_routing_distance (the leg steps a whole
    track) is said too. Shields, power links and vias follow the route
    as made.

OPTIONS
    -net <nets>
        Net names, glob patterns (*temp_L7*), or spine_net: and net:
        handles, as a Tcl list: [get_db nets], [get_db nets .name] and
        {temp_L1_inv1_Y temp_L2*} all work. Every word must match a net.
        A pattern takes the spine nets, and the nets of no spine that can
        be routed.
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
    -min_routing_distance <um>
        The least length of the wire from each net's driver to its
        nearest load, along the route (the drops from the tracks to the
        strap centres not counted). A shorter route goes out and back:
        see "Route length".
    -max_routing_distance <um>
        The most that length may be; with -min_routing_distance. Default
        -min_routing_distance + 10. A wider window (e.g. 2600 .. 2700)
        leaves the router more ways to make it.
    -force
        Route the fixed nets given too (set_db .route_status fixed;
        without it they are left, HT4-286), keeping every shape they have:
        their wires, their stubs' wires, shields, vias and lengthened
        straps. Only the pins not on the route yet (an input pin
        connect_pin or connect_spine put on the net, a strap still on
        SIGNAL) are routed, from the nearest point of the existing wires;
        only those new wires, their crossing boxes, shields and power links
        are added. The net stays fixed.
    -eco
        Mend the nets that are open or shorted, keep the rest. Of the nets
        of -net (without -net: every net), those check_drc finds a signal
        open on (a piece cut off from the driver: wires, straps, pins) or
        in a short are routed, and only from where their routing stops: every
        shape the net has stays (as -force keeps them), the pieces cut off
        and their pins are reached from the nearest point of it, and only
        the new wires, their crossing boxes, extensions and shields are
        added. A net in a short has its own route wires in the short taken
        out first (not a fixed wire, nor a strap, pin route, stub wire or
        shield: those are said, HT4-312), then is completed as an open one.
        Nets with no open and no short are not touched. After routing, the
        nets are checked again: what is left is said (HT4-312). Not with
        -force or -min_routing_distance. Fixed nets (set_db .route_status
        fixed, as a flow leaves the whole design) are mended too: their
        shapes stay, and they stay fixed; only a wire fixed on its own is
        not taken out of a short. -net is optional with -eco: every net,
        the stubs left to route_final_stub (an open one is said).
    -help
        Print the definition, usage, options and an example of the command.

SPINE SPEC TRACKS
    When the spine spec gives its cells tracks (track: {input, output},
    man read_spine_spec, TRACKS), a net of the spine lies, along the
    spine, on its numbers only: its driver's output track and its loads'
    input tracks, on each stretch of the spine (vertical wires on a
    vertical stretch, horizontal ones on a horizontal stretch; hops across
    on the other layer are free). Its pins' straps are extended to those
    tracks. It stays on the output track as long as it can, so it changes
    to a load's input track near that load. Where a cell's input and
    output share a track, the piece of it past the input strap belongs to
    the output net (the net coming in stops at the input). The stubs'
    track is the leaves' output track: route_net keeps it free and removes
    stubs routed before on another track (HT4-279); route_final_stub puts
    them there. A pin whose track is taken or out of reach is not routed
    (HT4-174, "on its spine spec track").

PIN ACCESS THROUGH A CELL
    A net reaches a route_pin strap at a crossing on the signal track
    nearest the strap centre. On a cell with two signal straps (A and Y)
    it may also reach a strap from the track on its outer side, away from
    the other signal strap, for the longer drop: the net coming from
    below then stops under the lower strap, and the net leaving the upper
    strap goes up from over it, on the same vertical track (with 0.36
    straps 0.72 apart, the two wires end 1.08 um apart). And a strap is
    best reached on the track the cell's other signal strap is already
    crossed on: another track costs two signal-track pitches more, so a
    straight net keeps one track through its cells unless a jog saves
    more. The nets of a spine are routed in the order the signal runs (a
    net before the nets its loads drive), so the track is the incoming
    net's. legalize_placement turns each cell so its input pin faces the
    net coming in (man legalize_placement), and route_pin gives the
    higher pin the higher strap.

FIXED WIRES
    A wire fixed alone (set_db <net_wire> .route_status fixed, a wire of
    kind wire, e.g. one moved by hand with move_wire) is kept when the
    net is routed again: route_net routes the rest of the net to it, as
    to a load, and from then on any track crossing on it is part of the
    net, so branches may leave it anywhere. It is not drawn again: only
    the crossing boxes where the route joins it are added, and no new
    wire is laid on top of it. With -shield its shields are made again
    round it where it lies now (its old shields are not fixed and go).
    A fixed wire whose centre line is not on a signal track of the rule's
    layers cannot be joined; it stays and is reported (HT4-287). The
    router does not check a fixed wire against other nets: a wire moved
    onto another net's track is a short check_drc reports.

    htree> move_wire -wires net_wire:sp_L2_inv1_Y/1 -next_track right
    htree> set_db net_wire:sp_L2_inv1_Y/1 .route_status fixed
    htree> route_net -net sp_L2_inv1_Y -rule r -shield
        fixed wire net_wire:sp_L2_inv1_Y/1: kept; the route joins it at {76.68 111.24}
    htree> set_db [get_db selected -if {.kind == wire}] .route_status fixed

OBJECTS AND ATTRIBUTES
    net_wire:<net>/<n>
        a wire, crossing box or shield of a routed net (a route lengthens
        a strap, see step a: no wire): obj_type, name (n), kind (wire |
        cross | shield; extension or shield_ext only for a piece on no
        strap of its net),
        shield_net (a shield's power net), layer (a cross: "<layer>/<layer>"), rect
        ("x1 y1 x2 y2"), width and length (a wire: across and along it;
        a cross: x and y size), net (spine_net or net handle),
        route_status (fixed: fixed alone or with its net; else routed)
    spine_net:<spine>/<net> .net_wires and net:<name> .net_wires list
    one net's; get_db net_wires lists all.
    via:<net>/<n>
        each crossing box is also a via object, one per cut layer between
        its two layers: spine_net:<spine>/<net> .vias, net:<name> .vias,
        get_db vias. See 'man assign_via_for_route'.

RETURN VALUE
    The handles of the nets that were routed (spine_net:<spine>/<net>,
    net:<name>).

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
    htree> connect_pin -from clk -to buf1/A
    htree> route_pin -inst buf1
    htree> route_net -net [get_db pin:buf1/A .net] -rule r1
    net:clk_in

ERRORS
    HT4-001  missing -net or -rule, a bad -via_weight, -shield_nets
             not two nets, a -min_routing_distance or -max_routing_distance
             that is not above 0, the most below the least, or
             -max_routing_distance alone
    HT4-025  no tech data loaded (read_tech)
    HT4-170  no net matches a -net word, or a cell has no signal input
             or output pin
    HT4-171  no such rule, 'default', or a rule without a horizontal and
             a vertical layer
    HT4-172  WARN: route_pin not done on a driver or load: the route ends
             near the pin, not connected
    HT4-173  WARN: the net's old wires were replaced
    HT4-174  WARN: a terminal cannot be reached (blocked, or no path
             inside the design boundary); the net is routed without it,
             or not at all
    HT4-176  WARN: a pin or stub is beyond the signal tracks (outside the
             die): its end is taken from the last track
    HT4-177  WARN: power pins whose strap reaches no shield of its net,
             or no shield beside a wire whose next track is not a power
             track
    HT4-178  WARN: a pin or stub is outside the design boundary (no track
             crossing at it holds a wire inside); the net is not routed
    HT4-179  the design boundary has a slanted edge: routes are kept
             inside a rectilinear boundary only
    HT4-175  a rule layer has no DEF tracks in its direction, or its track
             assignment leaves no signal track
    HT4-265  WARN: a net of no spine is not routed: no driver, more than
             one, no input pin or output port on it, or a port of it has
             no shapes and no
             location
    HT4-266  WARN: the route of a port's net ends near the port, not
             connected to it (left to the top level)
    HT4-287  WARN: a fixed wire is not on a signal track (or every
             crossing on it is blocked): the route does not join it
    HT4-300  WARN: a route cannot be made -min_routing_distance ..
             -max_routing_distance long (routed the shortest way), or
             is a little longer than -max_routing_distance
    HT4-312  WARN: -eco: a short it does not mend (a strap, pin route,
             stub wire, shield or fixed wire of the net), a stub with no
             wire, or an open or short left after routing
    HT4-286  WARN: a fixed net (set_db .route_status fixed) is not
             routed again; its routes stay and block the others
    HT4-297  WARN: vias that no definition of their layer pair fits

SEE ALSO
    route_track, create_route_rule, route_pin, assign_track_for_route,
    create_spine, set_db, get_db, gui_show, assign_via_for_route
