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

    Mouse and keys: wheel zooms about the cursor, left drag pans, left
    click selects the port shape under the cursor (it is highlighted and
    its port, layer, rect, direction and net are printed in the terminal
    and the status bar), F fits the design.

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
    read_def, read_tech, get_db
