NAME
    write_def - write the instances and the routing as DEF

SYNOPSIS
    write_def -output <file> [-sections {components specialnets nets}]
              [-overwrite]

DESCRIPTION
    Writes what htree4 added to the design as a DEF 5.8 file, for
    read_def (incremental) in Innovus after the script of write_logical
    has made the nets and instances. The routing is written as special
    wiring, the way Innovus itself writes routed clock nets and power
    nets. The header (VERSION, DIVIDERCHAR, BUSBITCHARS, DESIGN, UNITS,
    DIEAREA) comes from the DEF read with read_def: its design name,
    units and die area. Coordinates are written in those units.

    Sections, in this order (components and specialnets by default):
      COMPONENTS   every instance (create_inst, create_spine -build): cell,
                   + PLACED, + FIXED or + COVER (its .place_status, set
                   with set_db), lower-left corner, orientation.
      SPECIALNETS  the routing. First each routed signal net (the spine
                   nets, and the nets of no spine with a pin on them),
                   then each power net that has shapes of htree4:

                   - sp_L1_inv1_Y
                     + FIXED + RECT IB ( 22780800 22561920 ) ( 22783680 27349772 )
                     + FIXED + RECT IA ( 22780800 22561956 ) ( 22781760 22563396 )
                     + FIXED IA 0 ( 22782240 22562676 ) V_IA_IB
                       NEW G2 0 ( 22782240 22562676 ) V_G2_IA
                    ;
                   - VSS ( sp_L1_inv1 VSS ) ( sp_L2_inv1 VSS )
                     + ROUTED + RECT IB ( 22777920 22561920 ) ( 22778280 27349772 )
                     + ROUTED IA 0 ( 22778100 22562676 ) V_IA_IB
                     + USE GROUND
                    ;

                   A signal net: its route_net wires and strap extensions,
                   its stub's wires (route_final_stub), and the route_pin
                   straps and pin wires route_net connected (they carry the
                   net's name after route_net), each + FIXED + RECT; then
                   its vias. It lists no pins and no USE: the script of
                   write_logical made the net and connected its pins.
                   A power net (VSS, VDD_SOC): route_pin straps and power
                   pin wires (the cell pins they cover on the net line),
                   the shields route_net -shield and route_final_stub
                   -shield made, shield extensions and power links
                   (optimize_pg_connection), each + ROUTED + RECT; its
                   vias; then + USE as the design's port of the net has it
                   (POWER, GROUND), else as the library pin, else POWER.
                   Nets with neither a shape nor a via are not written.
      NETS         only when asked for: the connections of the signal
                   nets, no routing. Each spine net with its driver's
                   output pin, each load's input pin and the pins
                   connect_pin put on it; each net of no spine with the
                   pins on it and its port as ( PIN <port> ); + USE CLOCK.
                   For a design whose nets were not made by write_logical's
                   script: Innovus connects the pins of a net it reads.

    Vias. One per layer change of the via table (get_db vias): the wire
    crossings of route_net and route_final_stub, the pin wires on the cell
    pins and on their straps, and the vias of stretch_wire and
    insert_vias. Each is written on its net as <bottom layer> 0 ( x y )
    <via definition> at its centre: the first with + FIXED (a power net:
    + ROUTED), the others on NEW lines. A via needs a definition for its
    layers, from assign_via_for_route; one with none is left out with a
    warning (HT4-183), and the route is then open at that layer change in
    Innovus. Run assign_via_for_route for every layer pair before
    write_def.

    Shields are shapes of their power net. The DEF + SHIELD route is not
    used: Innovus checks it against the signal net's + SHIELDNET and
    rejects the shield when the net does not list it (IMPDF-168).
    Crossing boxes are overlaps of wires already written and are not
    repeated. Straps and pin wires still on net SIGNAL (no route_net
    connected them) belong to no net; they are left out, with a warning
    (HT4-182).

OPTIONS
    -output <file>
        DEF file to write. Required.
    -sections {components specialnets nets}
        Sections to write. Default components and specialnets.
    -overwrite
        Replace -output if it exists.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The file name.

EXAMPLES
    htree> assign_via_for_route -via {V_IA_IB V_G2_IA}
    htree> write_def -output htree.def
    DEF written to '/work/run/htree.def': COMPONENTS 34, SPECIALNETS 36
    htree> write_def -output comps.def -sections components -overwrite
    htree> write_def -output conn.def -sections nets -overwrite

    In Innovus, after the script of write_logical:
    innovus> read_def htree.def

ERRORS
    HT4-001  missing -output, or a -sections word that is not a section
    HT4-180  -output exists (use -overwrite)
    HT4-181  -output cannot be written
    HT4-182  WARN: straps or pin wires on net SIGNAL are not written
    HT4-183  WARN: vias with no via definition for their layers are not
             written (assign_via_for_route)

SEE ALSO
    write_logical, assign_via_for_route, route_net, route_final_stub,
    route_pin, optimize_pg_connection, write_db
