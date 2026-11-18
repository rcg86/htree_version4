NAME
    copy_obj - copy a built spine, with its cells, pin routes and
    routing, to a new name, shifted

SYNOPSIS
    copy_obj -from <spine> -name <name> [-x_shift <um>] [-y_shift <um>]

DESCRIPTION
    Makes a new spine, -name, that is a copy of the spine -from moved by
    -x_shift in x and -y_shift in y. The copy is a spine like one
    create_spine builds: get_db, move_obj, route_net, route_final_stub,
    delete_route and the GUI treat it as any other.

    Copied, all shifted by the same amount:
      - the spine: its location, its bent path (move_spine_to_boundary),
        its spec, levels and settings;
      - its instances (same cell, orientation and placement status);
      - their route_pin straps and pin wires, and their
        optimize_pg_connection wires;
      - its stubs and its nets' centre lines;
      - the routed shapes of its nets and stubs: wires, strap
        extensions, crossing boxes, shields, shield extensions, stub
        wires and stub shields, and the auto vias of stretch_wire and
        insert_vias on them. The via table follows from these, so the
        copy has the same vias as the original (an auto via carries the
        copy's net);
      - the route rule and route_status of each net and stub (set_db
        .route_rule, .route_status), and the connect_pin connections of
        its instances. An output put on
        the net of a port (connect_port) is not copied: a net has one
        driver (HT4-285).

    Names. A name that starts with <from>_ has that part replaced by
    <name>_: with -from sp -name sp2, instance sp_L1_inv1 becomes
    sp2_L1_inv1 and net sp_L1_inv1_Y becomes sp2_L1_inv1_Y. Any other
    instance or net name of the spine gets <name>_ in front. Stubs keep
    their names (stub:sp2/stub1); they are named within their spine.
    Shapes on other nets keep their net: power (shields, power straps),
    SIGNAL (straps of unrouted pins). The copy's root input is on a root
    net of its own, <name>_primary_input, as a spine create_spine builds
    has (unless the spec's root_net names a net of the design: then the
    copy's root is on it too).

    Snapping. Cells, pin routes, routes and vias all move by one shift,
    so every connection holds and nothing is legalized after the copy.
    Each shift snaps to the nearest whole number of the legal step, at
    least one step when it is not 0; a snapped shift is reported
    (HT4-282). The legal step along an axis is the least common
    multiple of:
      - the track-pattern period of the layers whose tracks run across
        it (the spine's route layers and the layers with a track
        assignment): track pitch x assign_track_for_route pattern
        length, 5.76 with 0.72 tracks and an 8-track pattern. Signal
        wires land on signal tracks and shields on tracks of their own
        power net. One period, not one signal track: with
        {VDD NA - NA VSS NA - NA} the signal tracks are 2.88 apart, but
        a shift of 2.88 would put the VDD shields on VSS tracks;
      - the site step of the DEF rows of the cells' sites: in x the site
        width step (STEP of the ROW), in y the row pitch, doubled when
        neighbouring rows have the other orientation (N and FS in
        turn), so each cell lands on a site of its own orientation.
    With 0.06 sites and 0.254 rows in turn N and FS, the step is 5.76 in
    x and 731.52 in y (5.76 and 0.508). A vertical spine of 6 signal
    tracks is 18.0 um wide shield to shield, and a copy 17.28 to its
    side (3 steps) shares the shield between the two.

    Reported, not changed:
      - copied instances not on a site of their orientation (HT4-283):
        rows that are not regular, no rows where the shift puts them,
        or an original that is not on a site; the cell is not moved to
        a site, as that would break its connections;
      - copied route shapes outside the design boundary (HT4-284), and
        instances outside it (HT4-203) or over another instance
        (HT4-204).
    Shorts and spacing between the copy's routes and other routes are not
    checked here: run check_drc. Copies of a spine bent by
    move_spine_to_boundary have their jogs at the same height as the
    original's, so side-by-side copies short there until the jogs are
    moved or routed again.

OPTIONS
    -from <spine>
        The spine to copy: a name or spine: handle ([get_db spine sp]).
        One spine. Required.
    -name <name>
        The name of the new spine; also the prefix of its instance and
        net names. A plain name: no blanks, / : or glob characters, and
        no spine, instance or net of the copy's names may exist.
        Required.
    -x_shift <um>
        Shift in x, microns; negative is left. Snapped to whole legal
        steps (track period and site step). Default 0.
    -y_shift <um>
        Shift in y, microns; negative is down. Snapped to whole legal
        steps (track period and row step). Default 0.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handle of the new spine (spine:<name>).

EXAMPLES
    htree> copy_obj -from [get_db spine sp] -name cp -x_shift 11.52
    Copied spine:sp to spine:cp (x 11.52, y 0): 8 instance(s), 8 net(s), 56 strap(s), 32 pin wire(s), 30 routed shape(s) (wires, crossing boxes, shields, stubs), 28 strap stretch(es)
    spine:cp
    htree> copy_obj -from sp -name a -x_shift 18
    **WARN: (HT4-282): copy_obj: -x_shift 18 snapped to 17.28, the nearest whole number of the legal step 5.76 (track period 5.76): signal wires on signal tracks, shields on their nets' tracks, cells on sites
    htree> foreach k {1 2 3} {
               copy_obj -from sp -name sp_c$k -x_shift [expr {-17.28 * $k}]
           }
    htree> check_drc

ERRORS
    HT4-001  -from or -name missing, a shift that is not a number, or a
             -name that is not a plain name
    HT4-280  -from is not one built spine
    HT4-281  a spine of that name exists, or names of the copy's
             instances or nets are taken
    HT4-282  WARN: a shift snapped to whole legal steps
    HT4-283  WARN: copied instances not on a placement site
    HT4-284  WARN: copied route shapes outside the design boundary
    HT4-285  WARN: an output on the net of a port is not copied
    HT4-203  WARN: copied instances outside the design boundary
    HT4-204  WARN: a copied instance overlaps another instance

SEE ALSO
    create_spine, move_obj, move_spine_to_boundary, route_net,
    route_final_stub, delete_route, check_drc, get_db
