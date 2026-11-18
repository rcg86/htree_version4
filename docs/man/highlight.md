NAME
    highlight - colour objects in the GUI; -clear takes the colour off

SYNOPSIS
    highlight -object <objects> -color <colour>
    highlight -clear [-object <objects>]

DESCRIPTION
    Paints objects in a colour in the layout of the window, as the
    palette of Edit > Highlight does for the selected objects. The
    command and the panel share the colours: what one colours the other
    can clear.

    What is coloured of each object:
      - a wire, strap, pin wire, via, pin, port or port shape: itself.
      - an instance: its outline and its pins.
      - a net: its wires with their shields, extensions and crossing
        boxes, its vias, its centre line (a net of a spine), and the
        pins on it, as show_only shows a net.
      - a stub: its bar, its route_final_stub wires and their vias.
      - a spine: its instances, nets and stubs, each as above.
    A filled shape takes the colour in its fill and its outline; an
    outline (a crossing box, a via pad) and a line in its outline. A
    selected object keeps its yellow selection outline until it is
    deselected.

    A later colour wins: colour a net red and then one of its wires
    blue, and that wire is blue. highlight -clear -object on that wire
    gives it back its layer colour, not the net's red. A net keeps its
    colour on the wires it is routed with later; a colour on a wire that
    is deleted is dropped.

    The colours are session state, like the selection and show_only:
    the database does not change, write_db does not save them and
    read_db drops them. They can be set before gui_show; the window then
    opens with them.

OPTIONS
    -object <objects>
        The objects, as a Tcl list. Each word is one of:
          - a handle of any drawn object (spine:, inst:, spine_net:,
            net:, stub:, pin:, port:, port_shape:, strap:, pin_wire:,
            net_wire:, via:), e.g. from get_db or get_db selected;
          - a name, or a pattern with * and ?: every spine, instance,
            net and stub of that name, as show_only takes it.
    -color <colour>
        A name: red, orange, yellow, lime, green, teal, cyan, blue,
        indigo, purple, magenta, pink, white, grey (or gray), brown,
        black (the palette of Edit > Highlight, in that order); or
        #rrggbb or #rgb. <tab> after -color lists the names.
    -clear
        Take the colour off the objects of -object, or off every object
        without -object.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the objects coloured or cleared, as a Tcl list; none
    for -clear without -object.

EXAMPLES
    A net in red:
    htree> highlight -object sp_L1_inv1_Y -color red
    highlight: 1 object(s) coloured #ff1744: spine_net:sp/sp_L1_inv1_Y

    What is selected in the window, in any colour:
    htree> highlight -object [get_db selected] -color #00c853

    Every cell of level 3, and a whole spine:
    htree> highlight -object sp_L3* -color yellow
    htree> highlight -object spine:sp -color cyan

    Colours off one net, then off everything:
    htree> highlight -clear -object sp_L1_inv1_Y
    htree> highlight -clear

ERRORS
    HT4-001  neither -object with -color nor -clear, -clear with -color,
             an empty -object, or an unknown option
    HT4-022  a handle of -object names an object that does not exist
    HT4-290  -color is not a colour name, #rrggbb or #rgb
    HT4-291  a name or pattern of -object matches no net, instance,
             spine or stub, or a net: handle names no net; nothing is
             coloured

SEE ALSO
    gui_show, show_only, select_obj, get_db
