NAME
    set_db - set an attribute on objects in the database, or a root
    attribute

SYNOPSIS
    set_db <objects> <.attr> <value>
    set_db <root_attr> <value>

DESCRIPTION
    Sets an attribute on every object in <objects>, a handle or a Tcl
    list of handles such as the result of get_db. The leading dot on the
    attribute is optional. Every object and the value are checked first;
    if one check fails, nothing is changed.

    Settable attributes:
      spine_net .route_rule   the route rule the net is routed with: a
                              rule name or handle from create_route_rule,
                              or 'default' to go back to the built-in
                              rule (tech minimum width and its spacing on
                              every routing layer)
      inst .place_status      placed (default), fixed or cover (any case);
                              .status is the same attribute. write_def
                              writes it as + PLACED / + FIXED / + COVER,
                              write_logical as set_db .place_status

    A net without a rule set uses route_rule:default. The rule is kept
    by net name, so a net rebuilt with the same name keeps it; write_db
    saves it. route_net sets it to the rule it routes with.

    Root attributes (two arguments) are settings that change how the
    commands work. get_db <root_attr> reads one; get_db root_attributes
    lists them all with their values and defaults. A value of 'default'
    goes back to the default. write_db saves them.
      ignore_shield_less_than_routing_length   (um, >= 0)
                              route_net -shield and route_final_stub
                              -shield give no shields to a signal wire
                              piece shorter than this. Default: the
                              spine spec's placement.deviation (the
                              built spine's, else the first spec read),
                              else 10.
      route_auto_via_insertion_during_stretch  (whole number, >= 0)
                              stretch_wire (Tools > Stretch) adds a via
                              where the stretched wire newly crosses a
                              wire of its net at most this many routing
                              layers away: 1 the next layer (IA-IB), 3
                              H2-IA over G1 and G2, 0 none. Default 1.

OPTIONS
    <objects>
        Object handles, e.g. [get_db nets *L4*].
    <.attr>
        The attribute to set, e.g. .route_rule.
    <value>
        The new value.
    <root_attr>
        A root attribute, e.g. ignore_shield_less_than_routing_length.
    -help
        Print the definition, usage, options and an example of the command.

RETURN VALUE
    The objects that were set; for a root attribute, its value now.

EXAMPLES
    htree> set_db [get_db nets *L4*] .route_rule rule1
    htree> get_db nets .route_rule.name
    htree> set_db [get_db nets *L4*] .route_rule default
    htree> set_db [get_db insts] .place_status fixed
    htree> set_db ignore_shield_less_than_routing_length 20
    set_db: ignore_shield_less_than_routing_length = 20
    htree> set_db ignore_shield_less_than_routing_length default
    set_db: ignore_shield_less_than_routing_length = 10 (default)

ERRORS
    HT4-001  not 2 or 3 arguments, a word that is not a handle, or no
             such root attribute
    HT4-022  an object does not exist
    HT4-140  the attribute cannot be set on that object type
    HT4-141  the value is not valid (e.g. no such route rule, a negative
             length)
    HT4-142  WARN: no objects given, nothing set

SEE ALSO
    get_db, create_route_rule
