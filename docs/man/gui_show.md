NAME
    gui_show - open the layout GUI

SYNOPSIS
    gui_show

DESCRIPTION
    Opens the layout window and returns to the htree> prompt at once. The
    terminal stays usable: commands typed there run in the same session
    as the window, and the layout reloads after any command that changes
    the database (read_def, read_tech, read_db, ...). Running gui_show
    again brings the window to the front.

    Window:
      top      menu bar:
                 File    Close Window (Ctrl+W; the terminal session stays)
                 View    Fit (F), Zoom Selected, Blink Selected,
                         Show View Panel
                 Select  Clear Selection (Esc)
               and under it a toolbar with small buttons: Fit, Zoom
               Selected, Blink Selected.
                 Zoom Selected   fits the view to the selected objects with a
                                 margin, showing at least 5 microns, so one
                                 tiny pin is shown with its neighbours.
                 Blink Selected  flashes the selected shapes 4 times (about
                                 1.6 s) together with a magenta box at least
                                 30 pixels across, so a selection is easy to
                                 find even at full-design zoom, where a pin
                                 is smaller than a pixel. Shapes on hidden
                                 layers stay hidden.
               Both report "Nothing selected" in the status bar when nothing
               is selected, or that the selected objects are not drawn
               (for example a design or a spine spec).
      center   the layout: design boundary, port shapes coloured by layer,
               and routing tracks (drawn once few enough are visible,
               clipped to the boundary).
      right    "View" panel with checkboxes:
                 Objects  Boundary, Ports, Tracks, Nets, Cells, Spine.
                          Categories with no data in the database are
                          greyed out (nets, placed cells and spine
                          geometry are not created yet).
                 Layers   one per layer, with its colour and object
                          counts. Tech layers come first and start
                          checked; layers marked * are not in tech and
                          start unchecked. All / None / Tech only buttons.
      bottom   cursor position in microns, and the selected object.

    Mouse and keys:
      left drag          draw a box; the view zooms to it
      Shift+left drag    select every object with a shape fully inside the
                         box (several at once); Ctrl+Shift+drag adds to the
                         selection
      left click         select the port under the cursor (the nearest
                         visible port shape within 3 pixels; all shapes of
                         the port light up); Ctrl+click adds or removes it;
                         a click on empty space clears the selection
      middle drag        pan; the design can be moved past any edge
      arrow keys         pan a quarter of the window
      wheel              zoom about the cursor (zoom-out stops when the
                         design is about 20 pixels across)
      F                  fit the design
      Esc                clear the selection

    Selection belongs to the session: 'get_db selected' returns it, and
    select_obj / deselect_obj in the terminal change it and the highlight
    follows. One selected object is described in the terminal and the
    status bar; for several, the count is shown. Shapes on hidden layers
    cannot be picked. Ports are selectable now; nets and instances will be
    once the database holds them.

    The window and the prompt share one thread: while the prompt waits for
    input, the window is live. While a command runs, the window does not
    repaint until the command finishes. Closing the window does not end
    the session.

    A display is needed (VNC, or ssh -X). gui_show checks it first, so a
    missing display gives an error instead of ending the session.

OPTIONS
    None.

RETURN VALUE
    None.

EXAMPLES
    htree> read_tech -file tech.lef
    htree> read_def -file cf999.def
    htree> gui_show
    GUI opened. Commands typed here update the layout.

ERRORS
    HT4-100  PySide6 is not installed
    HT4-101  no usable display (DISPLAY unset or unreachable)

SEE ALSO
    read_def, read_tech, get_db, select_obj, deselect_obj
