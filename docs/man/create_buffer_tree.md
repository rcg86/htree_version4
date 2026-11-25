NAME
    create_buffer_tree - drive the sinks of an input port through a tree of
    inverters, keeping their polarity

SYNOPSIS
    create_buffer_tree -from <input port> -inverter_ref <lib_cell>
                       [-buffer_ref <lib_cell>] -distance <um> [-name <prefix>]
                       [-topology fishbone | shortest]

DESCRIPTION
    Builds a tree of inverters from an input port of the design to the
    sinks on its net (the input pins on it), so that every end of the
    port's fanout sees an even number of inversions from the port: the
    same polarity as at the port, at every end alike.

    The tree, -topology fishbone (the default): the least total way, so
    the fewest inverters. A trunk the sinks share and a rib off it to
    each: grown from the port, each time the sink nearest the tree so far
    is joined to it the shortest way inside the design boundary (the tree
    itself free to reach; the shortest-path heuristic for Steiner trees),
    on a grid of the lines through the port, the sinks and the middle of
    each band of the boundary. On a comb-shaped die: one trunk down the
    spine, a rib into each arm. A sink's way from the port may be longer
    than the shortest (more inverters to it, and to some sinks than to
    others); the report gives the total way.

    -topology shortest: a shortest-path rectilinear tree from the port to the sinks
    that shares its trunk as far as it can and branches as late as it can:
    every sink is reached the shortest way (x plus y), and two sinks share
    the way to the point both pass through (a rectilinear Steiner
    arborescence, the merge heuristic of Rao et al.). Each part of the tree
    runs along x, then along y.
      Inside the design boundary. When a part of that tree would leave the
    die (an L- or comb-shaped boundary, its ways across the gaps between
    the arms), the tree is made of the shortest ways inside the boundary
    instead, on a grid of the lines through the port, the sinks and the
    middle of each band of the boundary. A way off the middle of an arm
    (along the port's or a sink's line, maybe by the die's edge) counts
    twice its length, so the ways go to the middle of the arm and share
    one trunk down it, not a second one beside it.
    The report says so. A sink no way inside reaches is an error
    (HT4-303).

    The cells. The first at the port: the port drives that one cell only
    (moved in off the die's edge when the port is on it). Then along the
    tree an inverter (-inverter_ref) every -distance um of way; on a part
    two or more sinks share, one for all of them. A sink nearer the port
    than -distance is driven by the cell at the port.

    Polarity. The cells are what the options say: -inverter_ref is an
    inverter, -buffer_ref a buffer (no check of the cells; one cell given
    as both is an inverter). The ends are those all_fanout finds from the
    port before the tree is made; the inverters from a sink to its ends
    (the sink's cell and those after it) are "Inverters after". A sink's
    way through the tree gets an odd number of inverters when those are
    odd, else an even number, so the count from the port to every end is
    even. A sink whose way is wrong gets the last cell before it made a
    buffer (-buffer_ref) when that cell drives sinks only and all of them
    are wrong; else, or when no -buffer_ref is given, one more inverter,
    placed at the sink (a sink on the port's net too). A sink whose ends differ, one odd and one even,
    cannot have them all even: HT4-304 warns, and its way is made even.

    Each cell is a plain instance <prefix>_<n> (-name, default
    <port>_tree), placed N with its input pin on the tree, then put on a
    free site (legalize_placement). Its input goes on the net of the cell
    before it (the port's net for the first); its output drives a net of
    its own, <prefix>_<n>_<output pin>; each sink goes on the net of the
    last cell before it. Only the netlist and the placement change
    (write_logical, get_db pin .net): run route_pin on the cells and
    route_net on the nets next. Wires of the port's net that went to the
    sinks are not changed (HT4-254).

    The report lists every sink: its way from the port (x plus y), the
    inverters and buffers of the tree before it, the inverters after it
    (fewest .. most when its ends differ) and its last cell. all_fanout
    lists the paths afterwards.

OPTIONS
    -from <input port>
        The input port the tree is driven from (a port: handle or name).
        It must have a place (shapes or a DEF location).
    -inverter_ref <lib_cell>
        The library cell of the stages: an inverter.
    -buffer_ref <lib_cell>
        A buffer: the library cell that ends a way whose inverters would
        otherwise make the count to an end odd. Optional: without it such
        a way gets one more inverter, at its sink, and the tree has
        inverters only.
    -distance <um>
        The way, in um above 0, from one cell to the next along the tree.
    -topology fishbone | shortest
        The tree: fishbone, the least total way (the fewest inverters), or
        shortest, every sink the shortest way from the port. Default
        fishbone.
    -name <prefix>
        The prefix of the cell names. Default <port>_tree.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The names of the cells made.

EXAMPLES
    htree> create_buffer_tree -from [get_db ports clk] -inverter_ref INV_RP -buffer_ref BUF_RP -distance 30 -name ct
    create_buffer_tree: port clk (net clk) -> 3 sink(s): 7 cell(s), 6 inverter(s) (INV_RP), 1 buffer(s) (BUF_RP), one every 30 um of the tree
      Sink  Way      Inverters  Buffers  Inverters after  Last cell
      s1/A  213.624  6          1        0                ct_7
      s2/A  225.624  6          1        0                ct_7
      s3/A  21.832   0          0        0                - (on the port's net)
    ct_1 ct_2 ct_3 ct_4 ct_5 ct_6 ct_7

ERRORS
    HT4-001  a required option missing, -from not one port, a -distance
             that is not a number above 0, or a bad -name
    HT4-022  -from names no port
    HT4-257  a cell is not in the library, or has no SIZE, signal input
             or signal output pin
    HT4-302  -from is not an input port, or has no place
    HT4-303  no input pin is on the port's net, or no way inside the
             design boundary reaches a sink
    HT4-304  WARN: no placement rows (the cells are not on sites), a cell
             outside the design boundary, a sink whose ends differ in
             polarity, or an end left with an odd
             number of inverters from the port
    HT4-261  WARN: a cell overlaps another instance
    HT4-254  WARN: a sink taken off a routed net

SEE ALSO
    all_fanout, add_buffer_on_net, connect_spine, legalize_placement,
    route_pin, route_net, write_logical
