NAME
    assign_track_for_route - assign a repeating net pattern to a layer's tracks

SYNOPSIS
    assign_track_for_route -net {<net|-|NA> ...} -layer <layer>

DESCRIPTION
    Assigns nets to the routing tracks of a layer by repeating a pattern.
    Tracks are numbered from the lowest coordinate; track 1 gets the first
    entry of the pattern, track 2 the second, and so on, starting over
    after the last entry. Two words are reserved:
        -    the track is free for any signal
        NA   the track is left blank: nothing may use it

        assign_track_for_route -net {VDD_SOC, -, VSS, -} -layer IA

    gives track 1 VDD_SOC, track 2 signal, track 3 VSS, track 4 signal,
    track 5 VDD_SOC, track 6 signal, track 7 VSS, ...

        assign_track_for_route -net {VDD_SOC, -, NA, VSS, -, NA} -layer IA

    gives VDD_SOC, signal, blank, VSS, signal, blank, then repeats.

    Which tracks: the layer's routing tracks run in its tech DIRECTION. A
    HORIZONTAL layer (IA) uses the DEF 'TRACKS Y' patterns (horizontal
    lines at y positions); a VERTICAL layer (IB, D12) uses 'TRACKS X'.
    When several patterns cover the layer in that direction (for example
    one per mask), their tracks are merged and numbered together.
    Numbering runs over all tracks of the pattern; tracks that fall in a
    notch outside a rectilinear boundary still take their place in the
    count.

    The layer must be in the tech data (only tech layers are used in
    calculations) and must have DEF tracks in its direction. Each net in
    the pattern is checked against the nets of the design's ports, and a
    warning is printed for one that is not found (a likely typo).

    The assignment is stored per layer and saved by write_db. Running the
    command again for the same layer replaces it, with a warning. Track
    positions come from the DEF tracks when queried, so a new read_def
    keeps the pattern and applies it to the new tracks.

OPTIONS
    -net {<net|-|NA> ...}
        The pattern: net names, '-' (any signal) and 'NA' (blank),
        separated by spaces and/or commas. At least one net name.
        Required.
    -layer <layer>
        Tech layer whose tracks are assigned. Required.

OBJECTS AND ATTRIBUTES
    track_assignment:<layer>
        obj_type, name and layer (the layer), direction (x or y: which DEF
        TRACKS are numbered), pattern, period (pattern length), num_tracks,
        counts ("net count ..." with '-' for signal and 'NA' for blank
        tracks), tracks (one {coordinate net} pair per track, lowest first)
    get_db track_assignments lists them.

RETURN VALUE
    None. Prints the layer, number of tracks and their range, the pattern,
    and for each net its track count and first track.

EXAMPLES
    htree> assign_track_for_route -net {VDD_SOC, -, VSS, -} -layer IA
    Track assignment for IA (horizontal, DEF TRACKS Y): 19645 tracks, y 0.36 .. 14144.04
      Pattern (repeats every 4): VDD_SOC - VSS -
      VDD_SOC     : 4912 tracks, first at y 0.36
      VSS         : 4911 tracks, first at y 1.8
      signal      : 9822 tracks, first at y 1.08
    htree> lrange [get_db track_assignment:IA .tracks] 0 3
    {0.36 VDD_SOC} {1.08 -} {1.8 VSS} {2.52 -}
    htree> foreach t [get_db track_assignment:IA .tracks] {
               lassign $t y net
               if {$net eq "VSS"} { lappend vss_y $y } }

ERRORS
    HT4-001  -net or -layer missing, empty pattern, or a pattern with no net
             (only '-' and 'NA')
    HT4-110  no tech data, layer not in tech, or layer has no direction
    HT4-111  no design, or no DEF tracks on the layer in its direction
    HT4-112  WARN: a net in the pattern is not the net of any port
    HT4-113  WARN: the layer's previous assignment was replaced

    In the GUI (gui_show), open the arrow next to Tracks to see each
    assignment and show or hide the tracks of each net. Blank (NA) tracks
    start hidden; checked, they are drawn as dim dashed lines.

SEE ALSO
    read_def, read_tech, get_db, gui_show
