"""create_route_rule -name <rule> -layer <layers> -width <w> [-spacing <s>] [-append]:
a named route rule; per layer, the wire width and the spacing kept on the left
and right side of a route.

    create_route_rule -name rule1 -layer H2 -width 0.41
    create_route_rule -name rule1 -layer H1 -width 0.35 -append
    create_route_rule -name rule2 -layer {IA IB} -width 0.72 -spacing 0.72

The rule 'default' is built in: on every routing layer, the tech minimum width
and the tech spacing for it. Nets use it until set_db gives them another rule.

Without -append the rule is created, or replaced by this one layer. With
-append the layer is added to an existing rule (or replaces that layer's
entry in it). Without -spacing, the tech spacing for a wire of this width.
"""

from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "create_route_rule"
SUMMARY = "Create a named route rule: per layer, wire width and spacing on each side"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-name": "value", "-layer": "value", "-width": "value", "-spacing": "value",
           "-append": "flag"}

USAGE = 1
NO_LAYER = 130
BAD_WIDTH = 131
BAD_SPACING = 132
REPLACED = 133
OFF_GRID = 134
NO_RULE = 135
RESERVED = 136
DEFAULT = "default"
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-name" not in opts or "-layer" not in opts or "-width" not in opts:
        raise HtreeError(USAGE, "create_route_rule: -name, -layer and -width are required. "
                         "Usage: create_route_rule -name <rule> -layer <layers> -width <width> "
                         "[-spacing <spacing>] [-append]")
    name = opts["-name"].removeprefix("route_rule:")
    if not name or any(ch in name for ch in "/ \t{}"):
        raise HtreeError(USAGE, f"create_route_rule: -name '{opts['-name']}' must be a "
                         f"non-empty name without '/', spaces or braces")
    if name == DEFAULT:
        raise HtreeError(RESERVED, f"create_route_rule: '{DEFAULT}' is the built-in rule "
                         f"(tech minimum width and its spacing on every routing layer); "
                         f"give another -name")
    append = opts["-append"]
    width = _positive(opts["-width"], "-width")
    spacing = _positive(opts["-spacing"], "-spacing") if "-spacing" in opts else None

    db = session.db
    if not db.has_tech():
        raise HtreeError(NO_LAYER, "create_route_rule: no tech data; run read_tech first")
    layers = [w.removeprefix("layer:") for w in opts["-layer"].replace(",", " ").split()]
    if not layers:
        raise HtreeError(USAGE, "create_route_rule: -layer names no layer")
    layers = list(dict.fromkeys(layers))
    if append and not db.route_rule_layers(name):
        raise HtreeError(NO_RULE, f"create_route_rule: -append needs an existing rule; there "
                         f"is no route rule '{name}' (rules: "
                         f"{' '.join(db.route_rule_names()) or 'none'}). Create it without "
                         f"-append first")
    # every layer is checked before the rule is changed
    entries = [(layer,) + _layer_entry(db, layer, width, spacing) for layer in layers]

    out = session.out
    grid = db.tech_row()["manufacturing_grid"]
    if grid:
        values = [("width", width)] + [("spacing", v) for v in dict.fromkeys(
            e[1] for e in entries)]
        for what, value in values:
            if abs(value / grid - round(value / grid)) > TOL:
                warn(OFF_GRID, f"{what} {_num(value)} is not a multiple of the manufacturing "
                     f"grid {_num(grid)}", out)
    for k, (layer, layer_spacing, given, source) in enumerate(entries):
        first_replaces = k == 0 and not append     # later layers join the new rule
        replaced = db.set_route_rule(name, layer, width, layer_spacing, given,
                                     not first_replaces)
        if not first_replaces and replaced:
            warn(REPLACED, f"replacing the {layer} entry of route rule {name}", out)
        elif replaced:
            warn(REPLACED, f"replacing route rule {name} (layers {' '.join(replaced)}); use "
                 f"-append to add a layer to it", out)
        how = "given" if given else f"tech, {source}"
        info(f"Route rule {name}, {layer}: width {_num(width)}, spacing {_num(layer_spacing)} "
             f"on each side ({how}), pitch to a parallel wire of this rule "
             f"{_num(round(width + layer_spacing, 6))}", out)
    info(f"  route rule {name} layers: {' '.join(db.route_rule_layers(name))}", out)
    return f"route_rule:{name}"


def _layer_entry(db, layer, width, spacing):
    """(spacing, given, source) of one layer of a rule, or an error: the layer
    must be a tech routing layer, width within its limits, spacing (given, or
    from tech when None) not below the tech spacing."""
    row = db.layer_row(layer)
    if row is None:
        raise HtreeError(NO_LAYER, f"create_route_rule: layer '{layer}' is not in tech "
                         f"(tech layers: {' '.join(db.layer_names())})")
    if (row["type"] or "").lower() != "routing":
        raise HtreeError(NO_LAYER, f"create_route_rule: layer {layer} is a "
                         f"{row['type'] or 'untyped'} layer, not a routing layer")
    min_width = tech_min_width(row)
    if min_width is not None and width < min_width - TOL:
        raise HtreeError(BAD_WIDTH, f"create_route_rule: width {_num(width)} is below the "
                         f"{layer} minimum width {_num(min_width)}")
    if row["max_width"] is not None and width > row["max_width"] + TOL:
        raise HtreeError(BAD_WIDTH, f"create_route_rule: width {_num(width)} is above the "
                         f"{layer} maximum width {_num(row['max_width'])}")
    needed, source = tech_spacing(db, row, width)
    if spacing is None:
        if needed is None:
            raise HtreeError(BAD_SPACING, f"create_route_rule: tech has no spacing rule for "
                             f"{layer}; give -spacing")
        return needed, False, source
    if needed is not None and spacing < needed - TOL:
        raise HtreeError(BAD_SPACING, f"create_route_rule: spacing {_num(spacing)} is "
                         f"below the {layer} tech spacing {_num(needed)} for a "
                         f"{_num(width)} wide wire ({source})")
    return spacing, True, source


def _positive(text, option):
    try:
        value = float(text)
    except ValueError:
        value = None
    if value is None or value <= 0:
        raise HtreeError(USAGE, f"create_route_rule: {option} must be a positive number in "
                         f"microns, got '{text}'")
    return value


def default_layers(db):
    """Routing layers of the tech, the layers of the default rule."""
    if not db.has_tech():
        return []
    return [n for n in db.layer_names()
            if (db.layer_row(n)["type"] or "").lower() == "routing"]


def default_layer_rule(db, layer):
    """The default rule on a routing layer, shaped like a route_rule row:
    tech minimum width, and the tech spacing for that width (None if the
    tech has none). None if the layer is not a routing layer."""
    if layer not in default_layers(db):
        return None
    row = db.layer_row(layer)
    width = tech_min_width(row)
    spacing = tech_spacing(db, row, width)[0] if width is not None else None
    return {"layer": layer, "width": width, "spacing": spacing, "spacing_given": "false"}


def tech_min_width(row):
    values = [v for v in (row["width"], row["min_width"]) if v is not None]
    return max(values) if values else None


def tech_spacing(db, row, width):
    """(spacing, source text) that the tech asks of a wire of this width next to a
    minimum-width wire, or (None, None) if the layer has no spacing rule.

    SPACINGTABLE TWOWIDTHS: the row for this width, first column (a minimum-width
    neighbour). SPACINGTABLE PARALLELRUNLENGTH: the row for this width, last
    column (the longest parallel run). PRL conditions are not applied, which
    is the safe side. The plain SPACING value is a floor under both."""
    found = []
    if row["min_spacing"] is not None:
        found.append((row["min_spacing"], "SPACING"))
    for stmt in db.layer_extra(row["id"]):
        words = stmt.replace(";", " ").split()
        if not words or words[0].upper() != "SPACINGTABLE":
            continue
        rows = _table_rows(words)
        if not rows:
            continue
        kind, values = None, None
        for row_width, row_values in rows:
            if row_width <= width + TOL:
                values = row_values
        if values:
            kind = words[1].upper() if len(words) > 1 else ""
            if kind == "TWOWIDTHS":
                found.append((values[0], f"SPACINGTABLE TWOWIDTHS row for width "
                                         f"{_num(width)}, minimum-width neighbour"))
            else:
                found.append((values[-1], f"SPACINGTABLE row for width {_num(width)}, "
                                          f"longest parallel run"))
    if not found:
        return None, None
    return max(found, key=lambda f: f[0])


def _table_rows(words):
    """[(width, [spacing, ...])] from a SPACINGTABLE statement's words."""
    rows = []
    i = 0
    while i < len(words):
        if words[i].upper() != "WIDTH" or i + 1 >= len(words):
            i += 1
            continue
        try:
            row_width = float(words[i + 1])
        except ValueError:
            return []
        i += 2
        if i < len(words) and words[i].upper() == "PRL":
            i += 2
        values = []
        while i < len(words) and words[i].upper() != "WIDTH":
            try:
                values.append(float(words[i]))
            except ValueError:
                return []
            i += 1
        rows.append((row_width, values))
    return rows
