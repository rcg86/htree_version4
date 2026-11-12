NAME
    create_route_rule - create a named route rule: per layer, the wire width and the spacing on each side

SYNOPSIS
    create_route_rule -name <rule> -layer <layers> -width <width> [-spacing <spacing>] [-append]

DESCRIPTION
    Creates a named route rule that says how routes are drawn on each
    of its layers: the wire width, and the spacing kept clear on the
    left and on the right side of the wire. One command sets one layer;
    -append adds more layers to the same rule.

    Without -append, the rule is created with this one layer. If a rule
    of that name already exists, it is replaced, all its layers
    included (with a warning). With -append, the layer is added to an
    existing rule; if the rule already has the layer, that layer's
    entry is replaced in place (with a warning). -append on a rule that
    does not exist is an error, so a mistyped name is caught.

    The rule 'default' is built in and cannot be created: on every
    routing layer, the tech minimum width (the larger of WIDTH and
    MINWIDTH) and the tech spacing for that width. Every net uses it
    until 'set_db <nets> .route_rule <rule>' gives it another rule.

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
    given spacing is at least the tech spacing for this width; with
    -append, the rule exists. A failed check leaves the rule unchanged.

    Checks (warnings, the rule is still created): the width or spacing
    is not a multiple of the manufacturing grid; an existing rule (or,
    with -append, the rule's entry for this layer) was replaced.

    Spacing tables in a LEF58 PROPERTY, end-of-line, cut and voltage
    spacing rules are not read.

OPTIONS
    -name <rule>
        Name of the rule, or its handle (route_rule:<rule>). No '/',
        spaces or braces. Required.
    -layer <layers>
        Routing layer names or handles (layer:<name>), one or a list:
        {IA IB} or IA,IB. Every layer gets the same -width and -spacing
        (without -spacing, each layer's own tech spacing). All layers are
        checked before the rule changes. Without -append the rule becomes
        exactly these layers; with -append they are added to it (a layer
        already in the rule has its entry replaced). Required.
    -width <width>
        Wire width in microns. Required.
    -spacing <spacing>
        Spacing in microns kept on each side of the wire. Default: the
        tech spacing for this width (see 'man create_route_rule').
    -append
        Add the layer to the existing rule -name instead of replacing
        the rule.
    -help
        Print the definition, usage, options and an example of the command.

OBJECTS AND ATTRIBUTES
    route_rule:<rule>
        obj_type, name, layers (layer handles, in the order they were
        added), route_rule_layers
    route_rule_layer:<rule>/<layer>
        obj_type, name (the layer), layer (handle), width, spacing,
        spacing_given (true: from -spacing; false: from tech), pitch
        (width + spacing: centre to centre with a parallel wire of the
        same rule), tech_min_width, tech_spacing (what the tech asks for
        this width), route_rule
    get_db route_rules lists all rules, route_rule:default first.

RETURN VALUE
    The rule handle, route_rule:<rule>.

EXAMPLES
    htree> create_route_rule -name rule1 -layer H2 -width 0.41
    Route rule rule1, H2: width 0.41, spacing 0.105 on each side (tech, SPACINGTABLE TWOWIDTHS row for width 0.41, minimum-width neighbour), pitch to a parallel wire of this rule 0.515; layers H2
    route_rule:rule1
    htree> create_route_rule -name rule1 -layer H1 -width 0.35 -append
    htree> get_db route_rule:rule1 .layers.name
    H2 H1
    htree> get_db route_rule_layer:rule1/H2 .pitch
    0.515
    htree> create_route_rule -name rule2 -layer IA -width 0.36 -spacing 0.72
    htree> create_route_rule -name rule3 -layer {IA IB} -width 0.72 -spacing 0.72
    Route rule rule3, IA: width 0.72, spacing 0.72 on each side (given), pitch to a parallel wire of this rule 1.44
    Route rule rule3, IB: width 0.72, spacing 0.72 on each side (given), pitch to a parallel wire of this rule 1.44
      route rule rule3 layers: IA IB

ERRORS
    HT4-001  missing -name, -layer or -width, an empty -layer list, a
             bad rule name, or a
             width or spacing that is not a positive number
    HT4-130  no tech, the layer is not in tech, or it is not a routing
             layer
    HT4-131  width below the layer minimum or above its maximum
    HT4-132  spacing below the tech spacing for this width, or no
             spacing in tech and none given
    HT4-133  WARN: an existing rule, or with -append the rule's entry
             for this layer, was replaced
    HT4-134  WARN: width or spacing not on the manufacturing grid
    HT4-135  -append on a rule that does not exist
    HT4-136  -name default: the built-in rule cannot be created

SEE ALSO
    read_tech, set_db, assign_track_for_route, get_db
