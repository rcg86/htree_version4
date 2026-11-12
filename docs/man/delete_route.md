NAME
    delete_route - remove the physical routing of nets; the nets stay

SYNOPSIS
    delete_route -nets <nets>

DESCRIPTION
    Removes the routing of the nets given, and nothing else: the nets, the
    instances, their connections and route rules stay, so the nets can be
    routed again (route_net, route_final_stub) and write_logical still
    writes them.

      - A stub (get_db stubs): its route_final_stub wire and crossing
        boxes are removed. Its leaf net keeps its route.
      - A spine net: what route_net made for it is removed: wires, strap
        extensions, crossing boxes, shields and shield extensions. The
        route_pin straps and pin wires route_net had named after the net
        go back to SIGNAL, as they connect to nothing now (the straps keep
        their size; route_pin made them). A leaf net keeps its stub's wire.

    The report gives what each net lost. Nets that had no routing are
    counted; when none had any, a warning says nothing was removed.

OPTIONS
    -nets <nets>
        Net or stub names, glob patterns, spine_net: or stub: handles, as a
        Tcl list: [get_db stubs], [get_db nets *L7*], {temp_L1_inv1_Y stub3}
        all work. A name matching both a net and a stub selects both.
        Every word must match one. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the nets and stubs whose routing was removed.

EXAMPLES
    htree> delete_route -nets [get_db stubs]
      stub temp/stub1: 2 wire(s) and crossing box(es) removed (from net temp_L7_inv1_Y)
      ...
    delete_route: routing removed from 6 of 6 net(s); the nets stay
    htree> delete_route -nets temp_L1_inv1_Y

ERRORS
    HT4-001  missing -nets
    HT4-195  no net or stub matches a -nets word
    HT4-196  WARN: none of the nets had routing; nothing removed

SEE ALSO
    route_net, route_final_stub, get_db, write_def
