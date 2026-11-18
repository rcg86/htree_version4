NAME
    remove_layer - remove layers from the tech data; add_layer puts them
    back

SYNOPSIS
    remove_layer -layer <layers>

DESCRIPTION
    Takes the layers given out of the tech data of the database. A full
    tech LEF has layers a clock tree is never built on (also between two
    layers of a read_tech layer range); they fill the layer list of the
    GUI. The tech LEF file is not read and not changed.

    A layer removed is, for every command, a layer that is not in tech,
    as one that a layer range of read_tech leaves out:
      - Layers: the layer is no layer object (get_db layers, layer:<name>)
        and no layer of the tech order. The other layers keep their order.
      - Vias: the via definitions of the tech LEF with a shape on a
        removed layer go with it (removing a cut layer removes the vias
        through it). The via definitions of the DEF stay. A via of the
        routes that used a definition removed is drawn as its box again
        (see 'man assign_via_for_route').
      - What the database has on the layer stays: route rules, track
        assignments, wires, cell pin and port shapes (.in_tech false,
        ignored in calculations). A warning names a removed layer that
        route rules, track assignments or route wires are on (HT4-016).
      - GUI: the layer is not listed and what is on it is not drawn (see
        'man gui_show').
      - The names removed are kept with the tech data (tech
        .removed_layers; write_db saves them) until add_layer puts the
        layer back or read_tech reads tech data again.

    Every word of -layer is checked before anything is removed. At
    least one layer has to stay in tech.

OPTIONS
    -layer <layers>
        The layers to remove, as a Tcl list: tech layer names, layer
        handles (layer:<name>, e.g. from get_db) or patterns with * and
        ? matched against the tech layer names. Required.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The names of the layers removed, in tech order. Prints them, the
    layers left and the vias removed.

EXAMPLES
    htree> remove_layer -layer XM
    remove_layer: removed 1 layer(s) from tech: XM
      Layers      : 13 (D12 C1 H1 C2 H2 C3 G1 C4 G2 C5 IA C6 IB)
      add_layer -layer <layers> puts them back

    A cut layer and a routing layer: their vias go with them.
    htree> remove_layer -layer {C6 G1}
    remove_layer: removed 2 layer(s) from tech: G1 C6
      Layers      : 11 (D12 C1 H1 C2 H2 C3 C4 G2 C5 IA IB)
      Vias        : 4 removed, a layer of theirs is removed (V_H2_G1 V_G1_G2 V_IA_IB V_IA_IB_2)
      add_layer -layer <layers> puts them back
    htree> get_db tech .removed_layers
    XM G1 C6

    By pattern, or the layers get_db finds:
    htree> remove_layer -layer C*
    htree> remove_layer -layer [get_db layers -if {.type == masterslice}]

ERRORS
    HT4-001  -layer missing or empty, or an unknown option
    HT4-016  WARN: a layer removed has route rules, track assignments or
             route wires of the database on it
    HT4-017  a word of -layer is no tech layer and matches none; nothing
             is removed
    HT4-018  -layer names every tech layer; nothing is removed
    HT4-025  no tech data; run read_tech first

SEE ALSO
    add_layer, read_tech, get_db, gui_show
