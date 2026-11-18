NAME
    show_only - show only some nets, instances or spines in the GUI;
    -show_all shows everything again

SYNOPSIS
    show_only -object <objects>
    show_only -show_all

DESCRIPTION
    A display filter for debugging. show_only -object draws the nets,
    instances and spines given and hides every other instance and the
    routing of every other net, so one route or one cell can be looked at
    without the rest of the design over it. show_only -show_all ends the
    filter: every instance and all net routing are drawn again.

    Only the display changes. The database is not changed, and every
    command works on hidden objects as before (get_db, route_net,
    check_drc, write_def). A hidden shape cannot be picked in the window.

    What is shown of each object:
      - instance: its outline, its pins, its route_pin straps and pin
        wires, the power connections optimize_pg_connection made for it,
        and the vias of those.
      - net: its wires with their extensions, shields and crossing boxes,
        its vias, its centre line (a net of a spine), every other route
        shape on the net (straps and pin wires; for a power net such as
        VSS its straps and the shields on it), and the pins on the net
        with their pin wires and the straps those reach. The instances
        of those pins are not shown: give them too to see them.
      - stub: its bar, its route_final_stub wires and the vias on them.
      - spine: its instances, its nets and its stubs, each as above.

    The filter works over the View panel of the window: a shown object
    is still drawn only while its box of Objects (Cells, Pins, Spine,
    Routes, Vias) and its layer are ticked. The boundary, the ports, the
    tracks and the rows are not instances or net routing and are not
    hidden.

    A second show_only -object replaces the first: the objects given are
    the only ones shown, not added to those shown before. Give all of
    them in one list.

    The filter is kept by what it shows, not by shape: a net that is
    routed again, or an instance that is moved, is shown as it is then.
    An object of the filter that is deleted shows nothing. While a filter
    is set, the status bar of the window says "Showing only: ..." with
    the objects.

    The filter is session state, like the selection: write_db does not
    save it and read_db ends it. It can be set before gui_show; the
    window then opens with it.

OPTIONS
    -object <objects>
        What to show, as a Tcl list. Each word is one of:
          - a handle of a spine, an instance, a net or a stub
            (spine:<name>, inst:<name>, spine_net:<spine>/<net>,
            net:<name>, stub:<spine>/<stub>), e.g. from get_db;
          - a handle of a pin, a wire or a via (pin:, strap:, pin_wire:,
            net_wire:, via:), e.g. from 'get_db selected' after a click
            in the window: it stands for its instance (pin, strap, pin
            wire) or its net (net wire, via);
          - a name, or a pattern with * and ?: every spine, instance,
            net and stub of that name is shown. A power net (VSS) is
            given by its name.
    -show_all
        Show every instance and all net routing again.
    -help
        Print the definition, usage, options and an example of the command.

    One of -object and -show_all is required, not both.

RETURN VALUE
    -object: the handles of the objects shown, as a Tcl list. Prints
    them by kind. -show_all: none.

EXAMPLES
    One net:
    htree> show_only -object sp_L1_inv1_Y
    show_only: showing only 1 object(s); the other instances and net routing are hidden
      Nets        : 1 (sp/sp_L1_inv1_Y)
      show_only -show_all shows everything again

    A net with its driver and its load:
    htree> show_only -object {sp_L1_inv1_Y sp_L1_inv1 sp_L2_inv1}

    A whole spine, an instance by handle, what a pattern matches:
    htree> show_only -object spine:sp
    htree> show_only -object [get_db insts u1]
    htree> show_only -object sp_L3*

    What was clicked in the window (a wire: its net):
    htree> show_only -object [get_db selected]

    The ground net: its straps, pin wires and shields:
    htree> show_only -object VSS

    Everything again:
    htree> show_only -show_all
    show_only: every instance and all net routing are shown again

ERRORS
    HT4-001  neither -object nor -show_all, both, an empty -object, or
             an unknown option
    HT4-022  a handle of -object names an object that does not exist
    HT4-270  a name or pattern of -object matches no net, instance,
             spine or stub; the display is not changed
    HT4-271  a handle of -object is not a net, an instance, a spine or a
             stub, nor a pin, wire or via of one (a layer, a port); the
             display is not changed

SEE ALSO
    gui_show, select_obj, get_db, get_obj_in_area, check_drc
