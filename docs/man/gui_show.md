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
                 Edit    Select, Stretch (S), Move (M), Snap, Undo Edit,
                         Shortcuts...
                 View    Fit (F), Zoom In, Zoom Out, Zoom Selected, Blink
                         Selected, Ruler (K), Clear Rulers (Shift+K), Show
                         View Panel
                 Select  Clear Selection (Esc; first cancels a ruler in
                         progress)
               and under it a toolbar with small buttons: Fit, Zoom
               Selected, Blink Selected, Ruler, Zoom In, Zoom Out, Tools.
                 Zoom In / Zoom Out  zoom by 1.5x about the view centre (about
                                 the cursor when used by a shortcut with the
                                 cursor over the layout). No shortcut until
                                 one is made in Edit > Shortcuts.
                 Shortcuts...    lists every shortcut (action, keys, built in
                                 or user). New... makes one: pick the action
                                 (any menu or toolbar action but Close
                                 Window: Fit, Zoom In / Out, Zoom Selected,
                                 Blink Selected, Ruler, Clear Rulers,
                                 Select, Stretch, Move, Snap, Undo Edit,
                                 Clear Selection, Shortcuts...), click Keys,
                                 press the combination (Ctrl+Z, or
                                 Ctrl+Shift+Z for Ctrl with a capital Z),
                                 OK. Keys already used by another action are
                                 refused. A user shortcut replaces the
                                 action's built in one. Remove deletes a
                                 user shortcut; the built in one comes back.
                                 Built in: F Fit, K Ruler, Shift+K Clear
                                 Rulers, S Stretch, M Move (S or M again:
                                 back to Select), Esc Clear Selection (first
                                 drops a drag or ruler in progress), Ctrl+W
                                 Close Window.
                                 User shortcuts are saved in
                                 ~/.config/htree4/shortcuts.json (or the
                                 file $HTREE4_SHORTCUTS names) and come back
                                 the next time the GUI opens.
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
                 Tools           the toolbox for fixing routes by hand, a
                                 dropdown; the button shows the mode in use
                                 (Tools: Move). Edits apply to route shapes:
                                 route_net / route_final_stub /
                                 optimize_pg_connection wires, shields and
                                 crossing boxes, route_pin straps and pin
                                 wires. Each edit runs a command, printed in
                                 the terminal with its output, so it can be
                                 repeated in a script.
                                   Select  the usual click, drag and zoom
                                     (default).
                                   Stretch  hover an edge of a wire (the
                                     cursor turns into a resize arrow) and
                                     drag it: the wire gets longer or
                                     shorter, the other edges stay. Runs
                                     stretch_wire, which adds a via where
                                     the wire newly crosses a wire of its
                                     net up to
                                     route_auto_via_insertion_during_stretch
                                     layers away (drawn as an outline).
                                   Move  drag a wire anywhere. Dragging a
                                     selected wire moves every selected wire
                                     together (other selected objects stay).
                                     Runs move_wire.
                                   Snap (tracks, edges, grid), on by default:
                                     Move puts the wire's centre line on the
                                     nearest track of its layer (along the
                                     wire, the manufacturing grid); Stretch
                                     puts the edge on an edge of a shape or
                                     a drawn track line within 10 pixels of
                                     the cursor, else on the grid.
                                   Undo Edit  reverses the last Stretch or
                                     Move (repeatable; also in the Edit menu).
                                 A click without a drag still selects; Esc
                                 drops a drag in progress. Choosing the
                                 Ruler ends an edit mode, and an edit mode
                                 ends the Ruler. Only the edited wires are
                                 redrawn and the view stays. Crossing boxes
                                 and connected shapes do not follow a wire.
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
                          Rows (sites), off at first: the placement rows
                          of the DEF (ROW, read_def), each outlined in
                          its site's colour with a mark at its left end
                          for the orientation (bottom corner N, top
                          corner FS), once a row is a few pixels tall;
                          zoomed in further, the site boundaries (dotted).
                          The arrow next to Rows opens a checkbox per site
                          with its colour and row count. The site height
                          is the row pitch (else the cells' height for a
                          single row), its width the row STEP.
                          Categories with no data in the database are
                          greyed out (nets, placed cells and spine
                          geometry are not created yet).
                 Layers   one per layer, with its colour and object
                          counts. Tech layers come first and start
                          checked; layers marked * are not in tech and
                          start unchecked. All / None / Tech only buttons.
                          The arrow beside Layers opens and closes the
                          list (open at start; closing it only hides the
                          list, not the layers).
                          Beside each layer, three small boxes, all
                          checked at start: S (signal), P (power) and G
                          (ground). Unchecking one hides that class of
                          the layer's ports, cell pins, straps, pin wires
                          and routed wires: P hides VDD_SOC, G hides VSS.
                          The All layers row on top has the same S P G
                          boxes for every layer at once: unchecking All
                          layers P unchecks P on every layer. It is
                          checked while every layer's box is.
                          A net is power or ground by its LEF/DEF USE
                          POWER / GROUND, else by name (VDD*, VCC* power;
                          VSS*, GND* ground); everything else is signal.
                          Shields, shield extensions and their crossing
                          boxes go by their shield net. Track lines keep
                          their own per-net boxes under Tracks.
      bottom   status bar: left the cursor position in microns; centre
               the selected object's name (a wire's net, a shield's or
               power extension's power net, an instance's name, inst/pin
               for a pin, a port's name; a strap of an unrouted signal pin
               its inst/pin; several: up to 3 names, all in its tooltip);
               right the selected object's details.

    Mouse and keys:
      left drag          draw a box; the view zooms to it
      Shift+left drag    select every object with a shape fully inside the
                         box (several at once); an instance fully inside is
                         selected as the instance, not pin by pin;
                         Ctrl+Shift+drag adds to the selection
      right drag         select every shown object with any part of a
                         shape touching the box: ports, instances,
                         instance pins, spine nets (their routed centre
                         lines) and spine stubs. An instance touched is
                         selected as the instance, not pin by pin.
                         Ctrl+right drag adds to the selection; a right
                         click without dragging does nothing
      left click         select the object under the cursor (the nearest
                         visible shape within 3 pixels): a port, a spine
                         net or stub (within 3 pixels of its line), an
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
    cannot be picked. Selectable: ports, instances, instance pins, and the
    nets and stubs of built spines (spine_net:<spine>/<net>,
    stub:<spine>/<stub>); all segments of a net light up together.
    Signal nets from DEF are not read yet, so they cannot be selected.

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
