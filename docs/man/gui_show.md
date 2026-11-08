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
                 View    Fit (F), Zoom Selected, Blink Selected, Ruler,
                         Clear Rulers, Show View Panel
                 Select  Clear Selection (Esc; first cancels a ruler in
                         progress)
               and under it a toolbar with small buttons: Fit, Zoom
               Selected, Blink Selected, Ruler.
                 Zoom Selected   fits the view to the selected objects with a
                                 margin, showing at least 5 microns, so one
                                 tiny pin is shown with its neighbours.
                 Blink Selected  flashes the selected shapes 4 times (about
                                 1.6 s) together with a magenta box at least
                                 30 pixels across, so a selection is easy to
                                 find even at full-design zoom, where a pin
                                 is smaller than a pixel. Shapes on hidden
                                 layers stay hidden.
                 Ruler           toggles ruler mode: click the start point,
                                 move (a live line follows), click the end
                                 point. The ruler stays on the layout with
                                 its length; the length and end points are
                                 printed in the terminal and the status bar.
                                 Right click or Esc cancels a ruler in
                                 progress; wheel zoom and middle-drag pan
                                 still work while measuring. The small arrow
                                 beside the button opens its options:
                                   Orthogonal / Diagonal  orthogonal (default)
                                     holds the ruler horizontal or vertical,
                                     whichever is closer to the mouse move;
                                     diagonal measures a straight line at any
                                     angle and also shows dx and dy.
                                   Snap to nearest object edge (on by
                                     default)  each click moves to the nearest
                                     edge or corner within 10 pixels of
                                     something drawn: visible port shapes, the
                                     boundary when shown, and the tracks drawn
                                     at the current zoom. Objects not shown
                                     (hidden layers, unchecked categories,
                                     tracks too dense to draw) are never
                                     snapped to. A small square under the
                                     cursor shows where a click will snap.
                                   Clear Rulers  removes all rulers (also in
                                     the View menu).
               Zoom Selected and Blink Selected report "Nothing selected" in
               the status bar when nothing is selected, or that the selected
               objects are not drawn (for example a design or a spine spec).
      center   the layout: design boundary, port shapes coloured by layer,
               and routing tracks (drawn once few enough are visible,
               clipped to the boundary). A tech layer shows only the tracks
               of its preferred direction from the tech LEF: a HORIZONTAL
               layer (IA) its DEF TRACKS Y, a VERTICAL layer (IB) its
               TRACKS X. Layers that are not in tech have no direction and
               show all their tracks. get_db track_patterns still lists
               every TRACKS statement of the DEF.
      right    "View" panel with checkboxes:
                 Objects  Boundary, Ports, Tracks, Nets, Cells
                          (instance outlines), Pins (instance pin shapes)
                          with Label beside it, Spine.
                          Label writes each pin's name at the centre of its
                          shapes, for instance pins and ports that are
                          shown, at a fixed size; with more than 2000 pins
                          in view no labels are drawn until you zoom in.
                          The arrow next to Tracks opens the track
                          assignments (assign_track_for_route): for each
                          assigned layer its direction, track count and
                          pattern, and a checkbox per net of the pattern
                          (signal tracks are '-') with its colour and
                          track count. Assigned tracks are drawn in their
                          net's colour (signal tracks grey dotted; blank
                          'NA' tracks dim dashed and hidden at first), when
                          Tracks and the layer are checked and the view is
                          zoomed in far enough; unchecking a net hides its
                          tracks. The other tracks of the layer keep the
                          layer colour.
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
                         box (several at once); an instance fully inside is
                         selected as the instance, not pin by pin;
                         Ctrl+Shift+drag adds to the selection
      left click         select the object under the cursor (the nearest
                         visible shape within 3 pixels): a port, an
                         instance pin (pin:<inst>/<pin>) when Pins are
                         shown, or the instance when the click is inside the
                         cell but off its pins (or Pins are hidden). All
                         shapes of the selected object light up; selecting
                         an instance lights up its pins too. When the whole
                         cell is smaller than the click area, the instance
                         is picked. Ctrl+click adds or removes; a click on
                         empty space clears the selection
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
    -help
        Print the definition, usage, options and an example of the command.

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
