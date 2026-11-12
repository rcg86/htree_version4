"""legalize_placement -inst <insts>: put instances on legal placement sites.

    legalize_placement -inst [get_db insts]

Each instance goes to the nearest free site of its cell: a DEF ROW (read_def)
whose site is the cell's LEF SITE and whose orientation is the instance's (N
cells in N rows, FS cells in FS rows), the cell inside the row, at a whole
number of site steps from the row origin, overlapping no other instance. It
looks no farther than one cell width + height from where the instance is;
an instance with no free site there stays (warning). Instances already on a
legal, free site do not move; fixed ones (.place_status fixed) never move.
Each instance's route_pin straps and pin wires move with it; the nets whose
routes it moves off are listed to route again.

Then the spacing of set_place_constraint: two instances closer than their
space_x in x and space_y in y at the same time are moved apart, each along
its spine (a cell of a vertical spine moves in y, of a horizontal one in x,
of a spine bent by move_spine_to_boundary the way its stretch of the path
runs; a cell in no spine the way that needs the shorter move), to the nearest
free site far enough away. A fixed (or cover) instance, or one not in
-inst, never moves: a placed one beside it moves the whole distance; two
placed ones each move about half. Pairs of two fixed cells are reported.
"""

import math

from core import objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import placed_bbox

NAME = "legalize_placement"
SUMMARY = "Place instances on the free legal sites of their cells (DEF rows, LEF SITE)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-inst": "value"}

USAGE = 1
NO_INST = 210
NO_ROWS = 211
NO_SITE = 212
RECONNECT = 213
TOO_CLOSE = 214
PASSES = 20                  # spacing passes: each moves every pair still too close
SEARCH = 200                 # sites / rows tried in a direction for a spaced-out place
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-inst" not in opts:
        raise HtreeError(USAGE, "legalize_placement: -inst is required. Usage: "
                         "legalize_placement -inst <insts>")
    db = session.db
    from core.commands.route_pin import inst_names
    try:
        names = inst_names(session, opts["-inst"])
    except HtreeError as exc:
        raise HtreeError(NO_INST, str(exc).replace("route_pin:", "legalize_placement:"))
    if not db.has_site_rows():
        raise HtreeError(NO_ROWS, "legalize_placement: no placement rows; read_def a DEF "
                         "with ROW statements first")
    out = session.out
    boxes = {r["name"]: objects.inst_bbox(db, r) for r in db.inst_rows()}
    moved, kept, fixed, missed, worst = [], [], [], [], 0.0
    for name in names:
        r = db.inst_row(name)
        if (r["status"] or "placed").lower() in ("fixed", "cover"):
            fixed.append(name)
            continue
        cell = db.lib_cell_row(r["ref_cell"])
        if cell is None or cell["size_x"] is None:
            missed.append(f"{name} (cell without SIZE)")
            continue
        site = cell["site"] if db.site_rows_of(cell["site"]) else None
        others = [b for n, b in boxes.items() if n != name and b is not None]
        spot = _free_site(db, r, cell, site, others)
        if spot is None:
            missed.append(name)
            continue
        x, y = spot
        dx, dy = round(x - r["x"], 6), round(y - r["y"], 6)
        if dx or dy:
            db.move_insts([name], dx, dy, pin_routes=True)
            moved.append(name)
            worst = max(worst, abs(dx) + abs(dy))
        else:
            kept.append(name)
        boxes[name] = objects.inst_bbox(db, db.inst_row(name))
    info(f"legalize_placement: {len(moved)} instance(s) moved onto sites (up to {_num(worst)} "
         f"um), {len(kept)} already legal, {len(fixed)} fixed (not moved)", out)
    if missed:
        warn(NO_SITE, f"no free site of the cell's site and orientation within one cell "
             f"width + height of {' '.join(missed)}; left where they are", out)
    spread = _spread(db, names, boxes, out)
    moved += [n for n in spread if n not in moved]
    touched = _nets_of(db, moved)
    if touched:
        warn(RECONNECT, f"{len(touched)} routed net(s) lost their pin routes' positions; "
             f"route them again: route_net -net {{{' '.join(touched)}}} -rule <rule>", out)
    return tuple(f"inst:{n}" for n in moved)


def _free_site(db, r, cell, site, others):
    """The nearest (x, y) site for instance row r that overlaps none of the
    boxes in others, within one cell width + height; None if there is none."""
    w, h = cell["size_x"], cell["size_y"]
    reach = w + h
    orient = r["orient"] or "N"
    query = "SELECT * FROM site_row WHERE orient = ? AND y BETWEEN ? AND ?" + \
        (" AND site = ?" if site else "")
    args = (orient, r["y"] - reach, r["y"] + reach) + ((site,) if site else ())
    candidates = []
    for row in db.conn.execute(query, args):
        step = row["step_x"] or 0.0
        if step:
            first = row["x"]
            last = row["x"] + row["num_x"] * step - w      # the cell must fit
            if last < first - TOL:
                continue
            k0 = round((r["x"] - first) / step)
            span = int(reach / step) + 1
            for k in range(k0 - span, k0 + span + 1):
                x = first + k * step
                if first - TOL <= x <= last + TOL:
                    candidates.append((abs(x - r["x"]) + abs(row["y"] - r["y"]),
                                       round(x, 6), round(row["y"], 6)))
        else:                                             # a one-site row
            candidates.append((abs(row["x"] - r["x"]) + abs(row["y"] - r["y"]),
                               round(row["x"], 6), round(row["y"], 6)))
    for d, x, y in sorted(set(candidates)):
        if d > reach + TOL:
            break
        box = placed_bbox(w, h, r["orient"], x, y)
        if not any(_overlap(box, o) for o in others):
            return x, y
    return None


def _gaps(a, b):
    """(x gap, y gap) between boxes; negative where they overlap."""
    return max(b[0] - a[2], a[0] - b[2]), max(b[1] - a[3], a[1] - b[3])


def _too_close(a, b, space):
    gx, gy = _gaps(a, b)
    return gx < space[0] - TOL and gy < space[1] - TOL


def _spread(db, names, boxes, out):
    """Move instances apart that are closer than their set_place_constraint
    spacing (see the module doc). Returns the names of those moved."""
    from core.commands.set_place_constraint import spacings
    rules = spacings(db)
    if not rules:
        return []
    rows = {r["name"]: r for r in db.inst_rows()}
    from core.spine_snake import member_axes
    axis_of = member_axes(db)    # inst -> "y" (vertical stretch of its spine) or "x"
    movable = {n for n in names if (rows[n]["status"] or "placed").lower()
               not in ("fixed", "cover")}

    def space(a, b):
        ra, rb = rules.get(rows[a]["ref_cell"]), rules.get(rows[b]["ref_cell"])
        if ra is None and rb is None:
            return None
        ra, rb = ra or (0.0, 0.0), rb or (0.0, 0.0)
        return max(ra[0], rb[0]), max(ra[1], rb[1])

    def pairs():
        ruled = [n for n in boxes if boxes[n] is not None and rules.get(rows[n]["ref_cell"])]
        found, seen = [], set()
        for a in ruled:
            for b, box in boxes.items():
                if b == a or box is None or (b, a) in seen:
                    continue
                sp = space(a, b)
                if _too_close(boxes[a], box, sp):
                    seen.add((a, b))
                    found.append((a, b, sp))
        return found

    first = pairs()
    if not first:
        info(f"legalize_placement: placement constraints met ({len(rules)} cell(s))", out)
        return []
    moved, worst, stuck = [], 0.0, {}
    for _ in range(PASSES):
        todo = pairs()
        if not todo:
            break
        progress = False
        for a, b, sp in todo:
            if not _too_close(boxes[a], boxes[b], sp):
                continue                          # fixed by an earlier move this pass
            movers = [n for n in (a, b) if n in movable]
            if not movers:
                stuck[(a, b)] = "both fixed (or not in -inst)"
                continue
            done = False
            for n in movers:                      # half each when both may move
                other = b if n == a else a
                share = 0.5 if len(movers) == 2 and n == movers[0] else 1.0
                d = _shift(db, n, other, rows, boxes, axis_of, rules, space, share)
                if d is not None:
                    moved.append(n)
                    worst = max(worst, d)
                    done = progress = True
                    if not _too_close(boxes[a], boxes[b], sp):
                        break
            if not done:
                stuck[(a, b)] = "no free site far enough away"
            elif _too_close(boxes[a], boxes[b], sp):
                stuck[(a, b)] = "no free site far enough away"
            else:
                stuck.pop((a, b), None)
        if not progress:
            break
    left = pairs()
    moved = list(dict.fromkeys(moved))
    info(f"legalize_placement: {len(first)} pair(s) closer than set_place_constraint; "
         f"{len(moved)} instance(s) moved apart (up to {_num(round(worst, 6))} um), "
         f"{len(left)} pair(s) left", out)
    if left:
        why = lambda a, b: stuck.get((a, b)) or stuck.get((b, a)) or "no free site far enough away"
        warn(TOO_CLOSE, "still closer than set_place_constraint: " + "; ".join(
            f"{a} {b} (gap x {_num(round(_gaps(boxes[a], boxes[b])[0], 6))} y "
            f"{_num(round(_gaps(boxes[a], boxes[b])[1], 6))}, need {_num(sp[0])} x or "
            f"{_num(sp[1])} y: {why(a, b)})" for a, b, sp in left), out)
    return moved


def _shift(db, name, other, rows, boxes, axis_of, rules, space, share):
    """Move instance name away from other along its axis to the nearest free
    site that is share of the needed distance away or more and too close to
    no third instance. Returns the distance moved, or None."""
    r = rows[name] = db.inst_row(name)
    cell = db.lib_cell_row(r["ref_cell"])
    a, b = boxes[name], boxes[other]
    sp = space(name, other)
    # the move along each axis that clears the pair, away from the other cell
    need = {}
    for axis, k, gap in (("x", 0, sp[0]), ("y", 1, sp[1])):
        up = (a[k] + a[k + 2]) >= (b[k] + b[k + 2])
        dist = (b[k + 2] + gap - a[k]) if up else (a[k + 2] - (b[k] - gap))
        need[axis] = (1 if up else -1, max(dist, 0.0))
    axis = axis_of.get(name) or min(need, key=lambda k: need[k][1])
    sign, dist = need[axis]
    site = cell["site"] if db.site_rows_of(cell["site"]) else None
    others = {n: bx for n, bx in boxes.items() if n != name and bx is not None}
    for x, y in _along(db, r, cell, site, axis, sign, dist * share):
        box = placed_bbox(cell["size_x"], cell["size_y"], r["orient"], x, y)
        if any(_overlap(box, o) for o in others.values()):
            continue
        if any(n != other and space(name, n) and _too_close(box, o, space(name, n))
               for n, o in others.items()):
            continue
        dx, dy = round(x - r["x"], 6), round(y - r["y"], 6)
        db.move_insts([name], dx, dy, pin_routes=True)
        rows[name] = db.inst_row(name)
        boxes[name] = objects.inst_bbox(db, rows[name])
        return abs(dx) + abs(dy)
    return None


def _along(db, r, cell, site, axis, sign, least):
    """Legal (x, y) for instance row r moving along axis in direction sign,
    at least least um away, nearest first: in x, the sites of its row; in
    y, the same x in the rows of its site and orientation above or below."""
    w = cell["size_x"]
    orient = r["orient"] or "N"
    extra = (" AND site = ?",) if site else ("",)
    args = (site,) if site else ()
    if axis == "x":
        query = "SELECT * FROM site_row WHERE orient = ? AND abs(y - ?) < 1e-6" + extra[0]
        found = []
        for row in db.conn.execute(query, (orient, r["y"]) + args):
            step = row["step_x"] or 0.0
            if not step:
                continue
            last = row["x"] + row["num_x"] * step - w
            k0 = (r["x"] + sign * least - row["x"]) / step
            k = math.ceil(k0 - 1e-6) if sign > 0 else math.floor(k0 + 1e-6)
            for i in range(SEARCH):
                x = row["x"] + (k + sign * i) * step
                if row["x"] - TOL <= x <= last + TOL and abs(x - r["x"]) > TOL:
                    found.append((abs(x - r["x"]), round(x, 6), r["y"]))
        return [(x, y) for _, x, y in sorted(found)]
    if sign > 0:
        query = "SELECT * FROM site_row WHERE orient = ? AND y >= ?" + extra[0] + \
            " ORDER BY y LIMIT ?"
        bound = r["y"] + least - TOL
    else:
        query = "SELECT * FROM site_row WHERE orient = ? AND y <= ?" + extra[0] + \
            " ORDER BY y DESC LIMIT ?"
        bound = r["y"] - least + TOL
    found = []
    for row in db.conn.execute(query, (orient, bound) + args + (SEARCH,)):
        step = row["step_x"] or 0.0
        last = row["x"] + (row["num_x"] or 1) * step - w
        on_grid = not step or abs((r["x"] - row["x"]) / step
                                  - round((r["x"] - row["x"]) / step)) < 1e-6
        if row["x"] - TOL <= r["x"] <= last + TOL and on_grid and abs(row["y"] - r["y"]) > TOL:
            found.append((r["x"], round(row["y"], 6)))
    return found


def _overlap(a, b):
    """Sharing area; cells that abut (rounding included) do not overlap."""
    return a[0] < b[2] - TOL and b[0] < a[2] - TOL and a[1] < b[3] - TOL and b[1] < a[3] - TOL


def _nets_of(db, insts):
    """Routed spine nets with a driver or load among insts."""
    moved = set(insts)
    found = []
    for s in db.spine_names():
        for n in db.spine_net_rows(db.spine_row(s)["id"]):
            ends = {n["driver"], *n["loads"].split()}
            if ends & moved and db.net_wire_rows(n["name"]):
                found.append(n["name"])
    return found
