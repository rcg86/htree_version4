"""create_route_rule -layer <layer> -width <w> [-spacing <s>]: the wire width and
the spacing kept on the left and right side of a route on a layer.

    create_route_rule -layer H2 -width 0.41
    create_route_rule -layer IA -width 0.36 -spacing 0.72

One rule per layer; a new rule for the same layer replaces the old one.
Without -spacing, the rule takes the tech spacing for a wire of this width.
"""

from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "create_route_rule"
SUMMARY = "Set the wire width and the spacing on each side for routes on a layer"

USAGE = 1
NO_LAYER = 130
BAD_WIDTH = 131
BAD_SPACING = 132
REPLACED = 133
OFF_GRID = 134
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, {"-layer": "value", "-width": "value",
                                         "-spacing": "value"})
    if "-layer" not in opts or "-width" not in opts:
        raise HtreeError(USAGE, "create_route_rule: -layer and -width are required. Usage: "
                         "create_route_rule -layer <layer> -width <width> [-spacing <spacing>]")
    width = _positive(opts["-width"], "-width")
    spacing = _positive(opts["-spacing"], "-spacing") if "-spacing" in opts else None

    db = session.db
    layer = opts["-layer"].removeprefix("layer:")
    if not db.has_tech():
        raise HtreeError(NO_LAYER, "create_route_rule: no tech data; run read_tech first")
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
        spacing, given = needed, False
    else:
        if needed is not None and spacing < needed - TOL:
            raise HtreeError(BAD_SPACING, f"create_route_rule: spacing {_num(spacing)} is "
                             f"below the {layer} tech spacing {_num(needed)} for a "
                             f"{_num(width)} wide wire ({source})")
        given = True

    out = session.out
    grid = db.tech_row()["manufacturing_grid"]
    if grid:
        for what, value in (("width", width), ("spacing", spacing)):
            if abs(value / grid - round(value / grid)) > TOL:
                warn(OFF_GRID, f"{what} {_num(value)} is not a multiple of the manufacturing "
                     f"grid {_num(grid)}", out)
    if db.set_route_rule(layer, width, spacing, given):
        warn(REPLACED, f"replacing the previous route rule of {layer}", out)

    how = "given" if given else f"tech, {source}"
    info(f"Route rule for {layer}: width {_num(width)}, spacing {_num(spacing)} on each side "
         f"({how}), pitch to a parallel wire of this rule {_num(round(width + spacing, 6))}", out)
    return f"route_rule:{layer}"


def _positive(text, option):
    try:
        value = float(text)
    except ValueError:
        value = None
    if value is None or value <= 0:
        raise HtreeError(USAGE, f"create_route_rule: {option} must be a positive number in "
                         f"microns, got '{text}'")
    return value


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
