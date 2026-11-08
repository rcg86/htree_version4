NAME
    create_route_rule - set the wire width and the spacing on each side for routes on a layer

SYNOPSIS
    create_route_rule -layer <layer> -width <width> [-spacing <spacing>]

DESCRIPTION
    Defines how routes on a layer are drawn: the wire width, and the
    spacing kept clear on the left and on the right side of the wire.
    There is one rule per layer; a new rule for the same layer replaces
    the old one (with a warning).

    Without -spacing, the rule takes the spacing the tech asks of a wire
    of this width next to a minimum-width wire:
      SPACINGTABLE TWOWIDTHS     the row for this width, first column
      SPACINGTABLE PARALLELRUNLENGTH
                                 the row for this width, last column
                                 (the longest parallel run)
      SPACING                    a floor under both
    Parallel-run-length conditions are not applied, which is the safe
    side: the value can be larger than a short parallel run needs.

    Checks (errors): the layer is a routing layer in tech; the width is
    at least the layer's WIDTH / MINWIDTH and at most its MAXWIDTH; a
    given spacing is at least the tech spacing for this width.

    Checks (warnings, the rule is still created): the width or spacing
    is not a multiple of the manufacturing grid; the layer already had a
    rule.

    Spacing tables in a LEF58 PROPERTY, end-of-line, cut and voltage
    spacing rules are not read.

OPTIONS
    -layer <layer>
        Routing layer name, or its handle (layer:<name>). Required.
    -width <width>
        Wire width in microns. Required.
    -spacing <spacing>
        Spacing in microns kept on each side of the wire. Default: the
        tech spacing for this width (see 'man create_route_rule').
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    route_rule:<layer>
        obj_type, name (the layer), layer, width, spacing, spacing_given
        (true: from -spacing; false: from tech), pitch (width + spacing:
        centre to centre with a parallel wire of the same rule),
        tech_min_width, tech_spacing (what the tech asks for this width)
    get_db route_rules lists all rules.

RETURN VALUE
    The rule handle, route_rule:<layer>.

EXAMPLES
    htree> create_route_rule -layer H2 -width 0.41
    Route rule for H2: width 0.41, spacing 0.105 on each side (tech, SPACINGTABLE TWOWIDTHS row for width 0.41, minimum-width neighbour), pitch to a parallel wire of this rule 0.515
    route_rule:H2
    htree> create_route_rule -layer IA -width 0.36 -spacing 0.72
    htree> get_db route_rule:IA .pitch
    1.08

ERRORS
    HT4-001  missing -layer or -width, or a width or spacing that is not
             a positive number
    HT4-130  no tech, the layer is not in tech, or it is not a routing
             layer
    HT4-131  width below the layer minimum or above its maximum
    HT4-132  spacing below the tech spacing for this width, or no
             spacing in tech and none given
    HT4-133  WARN: the layer's previous rule was replaced
    HT4-134  WARN: width or spacing not on the manufacturing grid

SEE ALSO
    read_tech, assign_track_for_route, get_db
