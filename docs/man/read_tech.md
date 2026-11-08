NAME
    read_tech - read a tech LEF file into the design database

SYNOPSIS
    read_tech -file <lef_file>

DESCRIPTION
    Parses a technology LEF file and stores its contents in the in-memory
    design database. If tech data is already loaded, it is replaced and a
    warning is printed. A parse error leaves the database unchanged.

    Modeled data:
      tech   : VERSION, UNITS DATABASE MICRONS, MANUFACTURINGGRID
      layer  : TYPE, DIRECTION, PITCH (x y, or one value for both), OFFSET
               (same), WIDTH, MINWIDTH, MAXWIDTH, AREA, MINENCLOSEDAREA,
               MINSTEP [MAXEDGES], plain SPACING <value> (smallest wins)

    Nothing is dropped:
      - Layer statements that are not modeled (other SPACING forms,
        SPACINGTABLE, PROPERTY, ...) are kept verbatim in the layer's
        .extra attribute.
      - The full original text of every LAYER block, comments included, is
        kept in the layer's .lef_text attribute.
      - Top-level statements and blocks that are not modeled (VIA, VIARULE,
        SITE, MACRO, BUSBITCHARS, ...) are kept verbatim in tech .extra, with
        one warning per kind.

    Use 'write_db' to save the database to disk.

OPTIONS
    -file <lef_file>
        Tech LEF file to read. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    None. Prints the file, LEF version, DB units and layer names.

EXAMPLES
    htree> read_tech -file tech.lef
    Reading tech LEF '/path/to/tech.lef'
      LEF version : 5.8
      DB units    : 4000
      Layers      : 6 (H1 H2 G1 G2 IA IB)

ERRORS
    HT4-001  -file missing, or an unknown option
    HT4-010  file not found
    HT4-011  parse error (message gives file and line)
    HT4-012  WARN: existing tech data replaced
    HT4-013  WARN: top-level statements not modeled, kept verbatim

SEE ALSO
    get_db, write_db, read_db
