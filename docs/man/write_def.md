NAME
    write_def - write the instances, straps and routed nets as DEF

SYNOPSIS
    write_def -output <file> [-sections {components specialnets nets}]
              [-overwrite]

DESCRIPTION
    Writes what htree4 added to the design as a DEF 5.8 file, for defIn
    (incremental) in the place and route tool. The header (VERSION,
    DIVIDERCHAR, BUSBITCHARS, DESIGN, UNITS, DIEAREA) comes from the DEF
    read with read_def: its design name, units and die area. Coordinates
    are written in those units.

    Sections (all three by default, always in this order):
      COMPONENTS   every instance (create_inst, create_spine -build): cell,
                   + PLACED, + FIXED or + COVER (its .place_status, set
                   with set_db), lower-left corner, orientation.
      SPECIALNETS  power nets of route_pin (VSS, VDD_SOC, ...): their
                   straps and power pin wires as + SHAPE STRIPE wires (as
                   wide as the shape's short side, along its long side),
                   with the cell power pins they cover.
      NETS         every spine net: its connections (the driver's output
                   pin, each load's input pin) and + USE CLOCK, then every
                   shape shorted to it, each as ( x y ) RECT ( 0 0 w h ):
                   route_net wires and strap extensions, and the straps and
                   pin wires route_net connected (they carry the net's name
                   after route_net). Crossing boxes are overlaps of wires
                   already written, so they are not repeated. A net with no
                   route has its connections only.

    Straps and pin wires still on net SIGNAL (no route_net connected them)
    belong to no net; they are left out, with a warning (HT4-182).

OPTIONS
    -output <file>
        DEF file to write. Required.
    -sections {components specialnets nets}
        Sections to write. Default all three.
    -overwrite
        Replace -output if it exists.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The file name.

EXAMPLES
    htree> write_def -output htree.def
    DEF written to '/work/run/htree.def': COMPONENTS 34, SPECIALNETS 2, NETS 34
    htree> write_def -output comps.def -sections components -overwrite

ERRORS
    HT4-001  missing -output, or a -sections word that is not a section
    HT4-180  -output exists (use -overwrite)
    HT4-181  -output cannot be written
    HT4-182  WARN: straps or pin wires on net SIGNAL are not written

SEE ALSO
    write_logical, route_net, route_pin, create_spine, write_db
