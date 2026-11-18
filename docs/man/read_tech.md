NAME
    read_tech - read a tech LEF file into the design database

SYNOPSIS
    read_tech -file <lef_file> [-min_layer <layer>] [-max_layer <layer>]

DESCRIPTION
    Parses a technology LEF file and stores its contents in the in-memory
    design database: all of its layers and vias, or with -min_layer and
    -max_layer the layers of a range and their vias. If tech data is
    already loaded, it is replaced and a warning is printed. A parse
    error leaves the database unchanged.

    Modeled data:
      tech   : VERSION, UNITS DATABASE MICRONS, MANUFACTURINGGRID
      layer  : TYPE, DIRECTION, PITCH (x y, or one value for both), OFFSET
               (same), WIDTH, MINWIDTH, MAXWIDTH, AREA, MINENCLOSEDAREA,
               MINSTEP [MAXEDGES], plain SPACING <value> (smallest wins)
      via_def: every VIA block: its DEFAULT flag and its shapes (RECT and
               POLYGON on each LAYER), or the shapes generated from its
               VIARULE parameters (CUTSIZE, LAYERS, CUTSPACING, ENCLOSURE,
               ROWCOL, ORIGIN, OFFSET; a cut PATTERN is not applied).
               The via definitions say which cut layer joins which two
               layers; see 'man assign_via_for_route'. A via the DEF
               also defines stays the DEF's (HT4-014)

    Nothing is dropped:
      - Layer statements that are not modeled (other SPACING forms,
        SPACINGTABLE, PROPERTY, ...) are kept verbatim in the layer's
        .extra attribute.
      - The full original text of every LAYER block, comments included, is
        kept in the layer's .lef_text attribute.
      - Top-level statements and blocks that are not modeled (VIARULE,
        SITE, MACRO, BUSBITCHARS, ...) are kept verbatim in tech .extra, with
        one warning per kind.

    A layer range (-min_layer, -max_layer). A full tech LEF has many
    more layers than a clock tree is built on; they fill the layer list
    of the GUI. With a range only its layers are read:
      - Layers: the layers from -min_layer to -max_layer, both included,
        in the order of the LAYER statements of the file (the order of
        the stack): the cut layers between two routing layers of the
        range too. With only -max_layer the range starts at the first
        layer of the file, with only -min_layer it ends at the last.
      - Vias: a VIA is read when every layer of its shapes is in the
        range. The via from the top layer of the range to the layer
        above it is so left out, as is the one below the bottom layer.
      - The other layers and vias of the file are not in the database:
        for every command a layer left out is a layer that is not in
        tech (no route rule, track assignment or route on it; cell pin
        and port shapes on it are kept, .in_tech false, and ignored in
        calculations). Give a range that has every layer the cells'
        pins, the straps and the routes are on. A warning names a layer
        left out that route rules, track assignments or route wires of
        the database are on (HT4-016).
      - VIARULE and the other top-level statements that are not modeled
        are kept whole, also the rules of layers left out.
      - GUI: only the layers of the range are listed and drawn (see
        'man gui_show'). A cut layer is not listed by its name: the
        vias between two layers have a row via_<bottom>_<top> there.
      - More layers later: read the file again with the new range. The
        tech data is replaced (HT4-012), so the range given is the
        whole range wanted, not the layers to add: after -min_layer G1
        -max_layer IB, -min_layer H1 -max_layer IB adds H1 and H2.
        Without the two options the whole file is read again.
        A single layer is taken out with remove_layer and put in with
        add_layer, without giving the range again; read_tech forgets
        what remove_layer removed.
      - The range is kept with the tech data (tech .min_layer and
        .max_layer, empty when not given; write_db saves it).

    Use 'write_db' to save the database to disk.

OPTIONS
    -file <lef_file>
        Tech LEF file to read. Required.
    -min_layer <layer>
        The first layer to read: a layer name of the file. Default: the
        first layer of the file.
    -max_layer <layer>
        The last layer to read: a layer name of the file. Default: the
        last layer of the file.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None. Prints the file, LEF version, DB units, layer names and the
    number of vias.

EXAMPLES
    htree> read_tech -file tech.lef
    Reading tech LEF '/path/to/tech.lef'
      LEF version : 5.8
      DB units    : 4000
      Layers      : 6 (H1 H2 G1 G2 IA IB)

    The layers from G1 up only, then H1 and H2 as well:
    htree> read_tech -file tech.lef -min_layer G1 -max_layer IB
    Reading tech LEF '/path/to/tech.lef'
      LEF version : 5.8
      DB units    : 4000
      Layer range : G1 .. IB (-min_layer G1, -max_layer IB); 2 of the 6 layers of the file left out
      Layers      : 4 (G1 G2 IA IB)
    htree> read_tech -file tech.lef -min_layer H1 -max_layer IB
    **WARN: (HT4-012): replacing existing tech data with 'tech.lef'
    ...
      Layers      : 6 (H1 H2 G1 G2 IA IB)
    htree> get_db tech .min_layer
    H1

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-010  file not found
    HT4-011  parse error (message gives file and line)
    HT4-012  WARN: existing tech data replaced
    HT4-013  WARN: top-level statements not modeled, kept verbatim
    HT4-014  WARN: a via the DEF also defines; the DEF's is kept
    HT4-015  -min_layer or -max_layer is not a layer of the file, or
             -min_layer comes after -max_layer in it; the database is
             unchanged
    HT4-016  WARN: a layer the range leaves out has route rules, track
             assignments or route wires of the database on it

SEE ALSO
    remove_layer, add_layer, get_db, write_db, read_db, gui_show
