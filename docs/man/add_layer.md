NAME
    add_layer - add layers of the tech LEF to the tech data: those
    remove_layer removed, or those a layer range left out

SYNOPSIS
    add_layer -layer <layers> [-file <lef_file>]

DESCRIPTION
    Puts layers back into the tech data of the database: the layers
    remove_layer took out, and as well any other layer of the tech LEF
    that is not in tech (one a read_tech layer range left out).

    The layers are read from the tech LEF the tech data was read from
    (tech .file), which is read again:
      - Layers: the tech layers of the database and the layers given,
        in the order of the LAYER statements of the file. A layer added
        is a tech layer again for every command, with the data of the
        file.
      - Vias: a VIA of the file is in the database when every layer of
        its shapes is in tech now, so the vias remove_layer took out
        with a layer come back with it. A via needs all its layers:
        after removing a routing layer and its cut layer, adding the
        routing layer alone does not bring the via back. A via the DEF
        also defines stays the DEF's.
      - The whole tech data is taken from the file as it is now: if the
        file was edited since it was read, the other layers and the
        top-level statements follow it too.
      - The layer range of read_tech (tech .min_layer, .max_layer) is
        kept as it was given, also when a layer outside it is added.
        The layers added are no longer in tech .removed_layers.
      - GUI: the layers added are listed again, checked (see 'man
        gui_show').

    A layer given that is already in tech is passed over. Every word of
    -layer is checked, and the file read, before anything is changed.

OPTIONS
    -layer <layers>
        The layers to add, as a Tcl list: layer names of the tech LEF,
        layer:<name>, or patterns with * and ? matched against the
        layer names of the file (-layer * adds every layer of the
        file). Required.
    -file <lef_file>
        The tech LEF to read the layers from, when the file the tech
        data was read from has moved. It has to have every tech layer
        of the database; it is tech .file afterwards. Default: tech
        .file.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The names of the layers added, in the order of the file; empty when
    all were in tech already. Prints them, the tech layers and the vias
    added.

EXAMPLES
    htree> add_layer -layer XM
    add_layer: added 1 layer(s) to tech from '/path/to/tech.lef': XM
      Layers      : 12 (D12 C1 H1 C2 H2 C3 C4 G2 C5 IA XM IB)

    A routing layer and a cut layer removed before, with their vias:
    htree> add_layer -layer {G1 C6}
    add_layer: added 2 layer(s) to tech from '/path/to/tech.lef': G1 C6
      Layers      : 14 (D12 C1 H1 C2 H2 C3 G1 C4 G2 C5 IA C6 XM IB)
      Vias        : 4 added, their layers are all in tech now (V_H2_G1 V_G1_G2 V_IA_IB V_IA_IB_2)

    Everything remove_layer removed:
    htree> add_layer -layer [get_db tech .removed_layers]

    A layer below the range of read_tech -min_layer G1:
    htree> add_layer -layer H2

ERRORS
    HT4-001  -layer missing or empty, or an unknown option
    HT4-010  the tech LEF is not found (give it with -file)
    HT4-011  parse error in the tech LEF (message gives file and line)
    HT4-017  a word of -layer is no layer of the tech LEF and matches
             none; nothing is added
    HT4-019  a tech layer of the database is not in the file: not the
             tech LEF the tech data was read from; nothing is added
    HT4-025  no tech data; run read_tech first

SEE ALSO
    remove_layer, read_tech, get_db, gui_show
