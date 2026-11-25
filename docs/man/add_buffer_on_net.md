NAME
    add_buffer_on_net - put buffers on nets at even distances along their
    centre lines, and on placement sites

SYNOPSIS
    add_buffer_on_net -net <nets> -ref_cell <lib_cell> -distance <um>
                      [-first_distance <um>] [-last_distance <um>]
                      [-name <suffix>] [-spec <yaml>]
                      [-buffer_count <n> [-spread]]
    add_buffer_on_net -net <nets> -ref_cell <lib_cell> -buffer_count <n>
                      -spread [-name <suffix>] [-spec <yaml>]

DESCRIPTION
    Puts instances of -ref_cell on the nets of a built spine (create_spine
    -build), one every -distance um along the net, and legalizes them
    (legalize_placement). A net of 1000 um with -first_distance 30
    -distance 100 gets a buffer 30, 130, 230, ... 930 um from its driver.
    A net of no spine, the net of a port for one, is taken as well: see
    'A net of no spine' below.

    Where the distances are measured. Along the centre lines create_spine
    planned for the net (get_db spine_net:<spine>/<net> .route), from the
    centre of the driver. The centre lines branch where the net has loads
    in more than one direction (a load on each side of the driver, or in
    more than one column), and every branch is measured from the driver
    on its own: two branches that part 10 um from the driver each get
    their buffer 30 um from it. A buffer on the point where they part is
    one buffer, for both. The distances are those of the straight spine:
    on a spine bent by move_spine_to_boundary they follow the bends.

    Where a buffer goes.
      -first_distance, then every -distance
            on each branch, as long as the point is before the farthest
            load of the branch. No buffer goes on that load or behind it.
            Without -first_distance the first buffer is -distance from
            the driver.
      -last_distance
            each load gets, besides, a last buffer, and the row above
            stops before the last of these. The distance is the Manhattan
            distance (in x plus in y, in the layout) from the output pin
            of the buffer to the input pin of the load, each taken at the
            centre of its shapes: going back from the load along the net,
            the buffer is on the first point where its pin is that far
            from the pin of the load. On a straight net with the pins in
            line that is -last_distance of net: with -first_distance 30
            -distance 100 -last_distance 50 on 1000 um the buffers are at
            30, 130, ... 930 and 950. Pins that are, say, 1.5 um apart
            across the net leave 48.5 um along it. The stretch before a
            last buffer is as short as it comes out.
            A load gets no last buffer when all of the net back to the
            driver is nearer to its pin than that (the row then keeps
            -last_distance of net before the load free), or when the net
            does not come that near the pin (a connect_pin load far from
            the spine). The report names these loads.
    A load that lies on a buffer point is before the buffer.

    The buffers. Each is an instance of -ref_cell, centred on its point
    (its corner on the manufacturing grid), with the orientation of the
    driver of the net, and is then put on a placement site (see below).
    The cell needs a SIZE, a signal input pin and a signal output pin;
    the first of each is used. The name is
    <driver>_<suffix><n>, numbered from the driver down each branch in
    turn, with the first numbers that are free. A buffer is a member of
    its spine (level 'buffer'): move_obj and move_spine_to_boundary move
    it with the spine, get_db spine:<name> .insts lists it and
    write_logical and write_def write it.

    The nets. The net given keeps its name and its driver, and ends at
    its first buffers. Each buffer drives a new spine net,
    <buffer>_<output pin>, with the centre lines from the buffer to the
    next buffers, which are its loads together with the loads of the net
    that lie on that stretch. A load is taken at the point of the centre
    lines nearest to its centre. The loads connect_pin put on the net by
    another pin go onto the net of their stretch as well. The lengths are
    those of the centre lines; a detour of the net (create_spine) is not
    drawn and no longer counted.

    The buffers are counted for each load: with an inverting cell an odd
    number of them inverts the signal at that load.

    Legalization. Once the buffers are stored, legalize_placement -inst
    <the buffers> puts them on the nearest free sites of their cell and
    applies the spacing of set_place_constraint; its messages are part of
    the output. Only the buffers move: the cells that were there stay. The
    centre lines of the nets are not changed, so a buffer may end up a
    site step or a row beside the point planned for it; the report gives
    the centres as placed and, with -last_distance, the distance from pin
    to pin as placed. Without placement rows (a DEF without ROW
    statements) the buffers stay on the manufacturing grid (HT4-264): run
    legalize_placement on them once the rows are read. A buffer that
    still overlaps another instance (HT4-261), or is not inside the
    design boundary (HT4-262), is named in a warning and still made.

    A net of no spine. -net also takes a net that is no spine's (get_db
    pin:<inst>/<pin> .net gives net:<name>): the net of an input port of
    the design, or one connect_pin made, with its driver (the port, or an
    output pin) and one or more input pins on it. The pins of spine cells
    are pins as any other: the net of a port that connect_pin put on the
    input of the root of a spine is buffered from the port to that pin.
    What differs from a net of a spine:
      The centre lines. The net has none, so they are made, in the
      layout: a trunk along x or y, whichever the driver and the pins
      are spread over more, at the middle one of the pins across it (of
      two, the lower), and a line straight across to the trunk from the
      driver and from every pin beside it. A port is taken at the centre
      of its shapes, a pin at the centre of its shapes. Nothing looks at
      what the lines cross: the legalization moves a buffer off a cell,
      and a buffer outside the boundary is named (HT4-262). The lines are
      not stored.
      The buffers. Named <port>_<suffix><n> on the net of a port, else
      <driver instance>_<suffix><n>; in the orientation of the driver
      instance, on the net of a port in that of the first pin's
      instance. They are instances of no spine (as create_inst makes
      them): no spine moves them.
      The nets. Each buffer drives a new net <buffer>_<output pin>, a
      net:<name> object, connected as connect_pin connects (get_db
      net:<name> .driver .pins); the pins behind a buffer go onto its
      net. write_logical and write_db write them.
      The routing. route_net routes these nets as the nets of a spine,
      to the pins on them. The net of a port ends at the track crossing
      nearest the port: route_net does not connect it to the port (see
      'man route_net').
    A net without a driver, with more than one, without an input pin, or
    of a port that is nowhere (no shapes, not placed) is left as it is
    (HT4-259).

    Routed nets of no spine. A net of no spine that route_net routed is
    buffered along its wires, and the wires are cut where the buffers go:
      The route. Its signal wires (kind wire) on the two layers of its
      route rule, joined where a crossing box touches two of them, are
      followed from the driver end (the end nearest the input port or
      the output pin). The points -first_distance, + -distance, ... um
      along it that lie before the last load of their branch get a
      buffer; a branch is measured from the driver as on a spine.
      The buffers. Each is centred under its point, in the orientation
      (N or FS) that puts its input pin on the driver's side of its
      output pin along the wire, then put on a site (legalize_placement)
      and given its pin routes (route_pin, with -spec). Where the cell
      or its pin routes (the straps' reach, as on another cell of the
      same type that has them) would come within the rule spacing of
      another cell's, or of a wire on the straps' layer, it slides along
      its wire, at most half -distance and not past the ends of that
      stretch of the route, to the nearest free place (reported, with
      how far). A buffer with no such place is not made (HT4-261): what
      it would drive stays on the net before it.
      Named <name>_<n> from the driver (-name; default <port or driver
      instance>_buf); each drives net <buffer>_<output pin>.
      The cut. The wires are cut over each buffer: over its cell, on the
      straps' layer also over the straps' reach, and the rule spacing
      each side. Each piece goes on the net of the nearest buffer before
      it; the pieces before the first buffer keep the net's name. The
      loads go on the net of the buffer before them.
      The joins. route_net then routes every net made or cut (with
      -shield when the net had shields), all the pieces held as they
      are (route_status fixed while it runs): it only joins them to the
      pins of the buffers and loads, and makes the crossing boxes, the
      pin routes' extensions and (with -shield) the shields and power
      links again. A piece of a fixed wire stays fixed; the others are
      freed again.
      -last_distance is not taken on routed nets yet (HT4-001).

    What is not done.
      A leaf's net is left as it is (HT4-259): its load is a stub, and
      this command does not buffer the stub nets.
      A routed net of a spine is an error (HT4-258): remove its routing
      first (delete_route -nets). On a net that is not routed the
      buffers get no pin routes: run route_pin on them, then route_net
      on the nets.
      There is no command that removes a buffer: write_db before, and
      read_db to go back.
    Everything is checked before anything is stored: on an error no
    buffer is made.

OPTIONS
    -net <nets>
        The nets: names, glob patterns or handles
        (spine_net:<spine>/<net>, net:<name>), as a Tcl list. A pattern
        takes the nets of the spines and the other nets with a pin on
        them. Required.
    -ref_cell <lib_cell>
        The library cell of the buffers, or its handle. Required.
    -distance <um>
        The distance from one buffer to the next, microns. Required.
    -first_distance <um>
        The distance from the driver to the first buffer. Default:
        -distance.
    -last_distance <um>
        The Manhattan distance from the output pin of the last buffer
        before a load to the input pin of the load. Default: no buffer
        is placed for the loads.
    -buffer_count <n>
        At most n buffers in a row from the driver to any load (each
        branch of a net counts its own row). The buffers go every
        -distance um as without it; once the n-th is placed, the points
        past it get none: HT4-307 (max buffer count reached) names the
        net and the points left, and the command goes on with the rest
        (the other nets, legalizing, the report). E.g. -buffer_count 3
        -distance 100 on a net 700 um long: buffers at 100, 200 and 300
        um, the 3 points at 400, 500, 600 um left.
    -spread
        With -buffer_count n: the n buffers spread evenly instead, the
        way from the driver to the farthest load (L) cut into n + 1
        equal parts, a buffer every L / (n + 1) um. E.g. 600 um and
        -buffer_count 3: 4 parts, buffers at 150, 300 and 450 um. A
        branch that ends nearer gets only the points on it. -distance is
        not needed (if given it is not used); not with -first_distance
        or -last_distance.
    -name <suffix>
        The suffix of the buffer names: <driver>_<suffix><n>. Default:
        buf. On a routed net, the prefix: <name>_<n> (default
        <driver>_buf).
    -spec <yaml>
        On a routed net: the pin routing spec route_pin gives the
        buffers (as route_pin -spec). Default: route_pin's defaults.
    -spec_name <name>
        On a routed net: a named pin routing spec for the buffers (as
        route_pin -spec_name: read by read_pin_spec, or one of -spec).
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The handles of the new instances (inst:<name>), empty when no buffer
    fits on the nets.

EXAMPLES
    htree> add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -first_distance 6 -distance 6
    add_buffer_on_net: INV_RP every 6 um, the first 6 um from the driver
    legalize_placement: 3 instance(s) moved onto sites (up to 2.061 um), 0 already legal, 0 fixed (not moved)
      sp_L2_inv1_Y (L2-L3, 23.88 um, driver sp_L2_inv1): 3 buffer(s)
        Buffer           From driver      After  Centre
        sp_L2_inv1_buf1            6          6  {75.76 114.681}
        sp_L2_inv1_buf2           12          6  {75.76 118.237}
        sp_L2_inv1_buf3           18          6  {75.76 125.349}
        load sp_L3_inv1: behind 0 buffer(s), 2.88 um after sp_L2_inv1
        load sp_L3_inv2: behind 3 buffer(s), 5.88 um after sp_L2_inv1_buf3
        an odd number of inverting cells before a load inverts its signal
    Added 3 buffer(s) on 1 net(s), now 4 nets. Next: route_pin for the buffers, then route_net -net {sp_L2_inv1_Y sp_L2_inv1_buf1_Y sp_L2_inv1_buf2_Y sp_L2_inv1_buf3_Y} -rule <rule>
    inst:sp_L2_inv1_buf1 inst:sp_L2_inv1_buf2 inst:sp_L2_inv1_buf3
    htree> get_db spine_net:sp/sp_L2_inv1_buf3_Y .loads
    sp_L3_inv2
    htree> add_buffer_on_net -net sp_L1_inv1_Y -ref_cell INV_RP -distance 100 -last_distance 9 -name rep
    htree> set bufs [add_buffer_on_net -net sp_L* -ref_cell INV_RP -first_distance 30 -distance 100]
    htree> route_pin -inst $bufs
    htree> connect_pin -from clk -to sp_L1_inv1/A -disconnect
    htree> add_buffer_on_net -net clk_in -ref_cell INV_RP -first_distance 100 -distance 100 -name rep
    add_buffer_on_net: INV_RP every 100 um, the first 100 um from the driver
      clk_in (the net of a port, 401.825 um, driver port clk): 4 buffer(s)
        Buffer    From driver      After  Centre
        clk_rep1          100        100  {1.168 301.832}
        ...
    htree> get_db pin:sp_L1_inv1/A .net.driver
    pin:clk_rep4/Y
    htree> add_buffer_on_net -net clk_in -ref_cell INV_RP -first_distance 100 \
               -distance 100 -name rep -spec pin_routing_spec.yaml
      clk_in: buffers moved along the route, off the cells under it (um, + is away from the driver): rep_1 -10.08, rep_3 -10.08
    add_buffer_on_net: clk_in: 4 buffer(s) along its route, its 4 wire(s) cut into 8 piece(s) on 5 net(s); route_net joins them to the pins
      clk_in: 4 buffer(s) along its route
        Buffer  From driver  Centre               Input net -> output net
        rep_1        89.92  {1.44 311.84}        clk_in -> rep_1_Y
        rep_2          200  {1.44 201.76}        rep_1_Y -> rep_2_Y
        rep_3       289.92  {1.44 111.84}        rep_2_Y -> rep_3_Y
        rep_4          400  {14.8 15.12}         rep_3_Y -> rep_4_Y
        load sp_L1_inv1/A: on rep_3_Y, behind rep_3
        load d1/A: on rep_4_Y, behind rep_4

ERRORS
    HT4-001  -net, -ref_cell or -distance missing (-distance: unless
             -spread), a distance that is not a number above 0, a bad
             suffix, a -buffer_count that is not a whole number above 0,
             -spread without -buffer_count or with -first_distance or
             -last_distance, or an unknown option
    HT4-026  no physical library loaded (read_lef)
    HT4-256  no net of that name
    HT4-257  the cell is not in the library, or has no SIZE, signal input
             pin or signal output pin
    HT4-258  a net of a spine given is routed, or a routed net has no
             route rule
    HT4-259  WARN: a leaf's net was left as it is (stub nets are not
             buffered by this command), a net of no spine was (no single
             driver, no input pin on it, or its port is nowhere), or no
             buffer fits on a net (it is shorter than the first distance)
    HT4-260  the net has no centre lines, they do not lead from the
             driver to a load, or its spine has no straight-spine
             coordinates (build it again)
    HT4-261  WARN: a buffer overlaps another instance
    HT4-262  WARN: a buffer is not inside the design boundary
    HT4-263  more than 500 buffers on one net: check -distance
    HT4-264  WARN: the buffers are not on placement sites: the design has
             no rows, or legalize_placement failed (its message follows)
    HT4-307  WARN: max buffer count reached: -buffer_count buffers in a
             row, the points past them left without one

SEE ALSO
    create_spine, create_inst, connect_pin, legalize_placement,
    set_place_constraint, route_pin, route_net, delete_route,
    move_spine_to_boundary, write_logical
