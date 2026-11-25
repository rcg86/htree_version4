"""legalize_placement -inst <insts>: put instances on legal placement sites.

    legalize_placement -inst [get_db insts]

Each instance goes to the nearest free site of its cell: a DEF ROW (read_def)
whose site is the cell's LEF SITE and whose orientation is the instance's (N
and FN cells in N rows, FS and S cells in FS rows: FN and S are N and FS
mirrored about the y axis), the cell inside the row, at a whole
number of site steps from the row origin, overlapping no other instance,
and inside the design boundary when a free site there is near enough. It
looks no farther than one cell width + height from where the instance is;
an instance with no free site there stays (warning). Instances already on a
legal, free site do not move; fixed ones (.place_status fixed) never move.
Each instance's route_pin straps and pin wires move with it; the nets whose
routes it moves off are listed to route again.

The orientation for pin access (not with -keep_orientation). A cell whose
signal runs up or down (its input net's driver below it and its output's
loads above, or the other way: more in y than in x) is put in the
orientation, N or FS (flipped about the x axis), that has its input pin on
the side the signal comes from: route_pin then gives the input the strap on
that side, so the net coming in and the net going out can pass the cell on
one track (route_net). A cell whose pins are as high in both is left as it
is. A cell that changes orientation goes on a site of the new one (an FS row
for FS); its pin routes would be upside down, so they are removed and, once
every instance is placed, made again (route_pin.rebuild): straps, pin wires
and pin vias, with the spec route_pin last routed the instance with. One
routed before specs were kept (an older database) is said: run route_pin
on it.

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
from core.placement import placed_bbox, rect_in_polygon, row_orient

NAME = "legalize_placement"
SUMMARY = "Place instances on the free legal sites of their cells (DEF rows, LEF SITE)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-inst": "value", "-keep_orientation": "flag"}

USAGE = 1
NO_INST = 210
NO_ROWS = 211
NO_SITE = 212
RECONNECT = 213
TOO_CLOSE = 214
NO_ACCESS = 288
OFF_TRACKS = 289
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
    moved, kept, fixed, missed, flipped, worst = [], [], [], [], [], 0.0
    had = set()                          # turned instances that had pin routes
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
        orient = r["orient"] or "N"
        want = None if opts["-keep_orientation"] else _access_orient(db, name, cell, orient)
        spot = None
        if want is not None and want != orient:
            spot = _free_site(db, r, cell, site, others, want)
            if spot is not None:                  # flipped: its pin routes are upside down
                db.set_inst_orient(name, want)
                if db.strap_rows(name):           # made again once all are placed
                    had.add(name)
                db.set_straps(name, [])
                flipped.append(f"{name} {orient} -> {want}")
        if spot is None:
            spot = _free_site(db, r, cell, site, others, wide=True)
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
    info(f"legalize_placement: {len(moved)} instance(s) moved onto sites (up to {_num(round(worst, 6))} "
         f"um), {len(kept)} already legal, {len(fixed)} fixed (not moved)", out)
    if missed:
        warn(NO_SITE, f"no free site of the cell's site and orientation within {WIDE[-1]} "
             f"cell widths + heights of {' '.join(missed)}; left where they are", out)
    slid, far = _slide_to_tracks(db, names, boxes)
    moved += [n for n, _ in slid if n not in moved]
    if slid:
        info(f"  {len(slid)} instance(s) moved across their spine so their straps reach the "
             f"tracks of the spine spec (track: input / output): "
             + ", ".join(f"{n} {_num(d)}" for n, d in slid), out)
    if far:
        warn(OFF_TRACKS, f"legalize_placement: {len(far)} instance(s) cannot reach the tracks "
             f"of the spine spec: " + "; ".join(far), out)
    spread = _spread(db, names, boxes, out)
    moved += [n for n in spread if n not in moved]
    if spread and not opts["-keep_orientation"]:   # moved apart: turned the way they face now
        again = _turn(db, spread, boxes, flipped, had)
        if again:
            moved += [n for n in again if n not in moved]
            moved += [n for n in _spread(db, names, boxes, out) if n not in moved]
    if flipped:                  # their pin routes made again, the way route_pin made them
        turned = list(dict.fromkeys(f.split()[0] for f in flipped))
        info(f"  {len(flipped)} instance(s) turned so the input pin faces the incoming net: "
             f"{', '.join(flipped)}; their pin routes (straps, pin wires, vias) made again "
             f"in the new orientation", out)
        from core.commands import route_pin
        done, unknown = route_pin.rebuild(session, [n for n in turned if n in had])
        if done:
            info(f"  pin routes made again with the spec route_pin used: {' '.join(done)}", out)
        if unknown:
            warn(RECONNECT, f"legalize_placement: no pin routing spec kept for "
                 f"{' '.join(unknown)} (routed before specs were kept): their pin routes are "
                 f"removed; route_pin -inst {{{' '.join(unknown)}}} -spec <yaml>", out)
    touched = _nets_of(db, moved)
    if touched:
        warn(RECONNECT, f"{len(touched)} routed net(s) lost their pin routes' positions; "
             f"route them again: route_net -net {{{' '.join(touched)}}} -rule <rule>", out)
    _pin_access(db, names, touched, out)
    return tuple(f"inst:{n}" for n in moved)


def _pin_access(db, names, touched, out):
    """Report the signal pins of names route_net cannot reach (core/pin_access.py)."""
    from core import pin_access
    rows = pin_access.check(db, names, ignore=touched)
    if rows is None:
        info("legalize_placement: pin access not checked: no track assignment numbered in x "
             "(assign_track_for_route)", out)
    elif rows:
        warn(NO_ACCESS, f"legalize_placement: {len(rows)} signal pin(s) with no track route_net "
             f"can reach them on (the nets to route again are not counted as in the way):", out)
        for line in pin_access.report(rows):
            info(line, out)
    else:
        info(f"legalize_placement: pin access: every signal pin of the {len(names)} "
             f"instance(s) has a track to be reached on", out)


def _slide_to_tracks(db, names, boxes):
    """Move the cells of names that the spine spec gives tracks (track:
    {input, output}, core/spine_tracks.py) across their stretch of the spine,
    on whole sites of their row, the least distance that puts both tracks in
    their straps' reach (max_extension each side, as wide as the rule's
    wires), overlapping no other cell. Returns ([(name, dx)], [why not])."""
    from core import pin_access, spine_tracks
    wanted = set(names)
    slid, far = [], []
    reach_default = next((r["max_extension"] for r in db.strap_rows()
                          if r["max_extension"] is not None), 3.0)
    for spine in db.spine_names():
        for name, (st, cin, cout, kin, kout) in spine_tracks.placed(db, spine).items():
            if name not in wanted:
                continue
            missing = [f"{what} {k}" for what, k, c in (("input", kin, cin), ("output", kout, cout))
                       if k and c is None]
            if missing:
                far.append(f"{name}: no track {' and '.join(missing)} past the spine's location "
                           f"on {st.layer}")
                continue
            if not st.vertical:
                continue                          # a track along y: a hop reaches it
            r = db.inst_row(name)
            if (r["status"] or "placed").lower() in ("fixed", "cover"):
                continue
            cell = db.lib_cell_row(r["ref_cell"])
            coords = [c for c in (cin, cout) if c is not None]
            width = pin_access._rule(db, None, st.layer)[0]
            reach = max((s["max_extension"] or 0.0 for s in db.strap_rows(name)),
                        default=reach_default)
            box = objects.inst_bbox(db, r)
            lo = max(coords) + width / 2 - cell["size_x"] - reach    # where the cell may start
            hi = min(coords) - width / 2 + reach
            if lo - TOL <= box[0] <= hi + TOL:
                continue
            if lo > hi + TOL:
                far.append(f"{name}: its tracks x {' and '.join(_num(c) for c in coords)} are "
                           f"farther apart than its straps reach")
                continue
            spot = _site_between(db, r, cell, lo, hi, [b for n, b in boxes.items()
                                                       if n != name and b is not None])
            if spot is None:
                far.append(f"{name}: no free site between x {_num(round(lo, 3))} and "
                           f"{_num(round(hi, 3))} (to reach x {' and '.join(_num(c) for c in coords)})")
                continue
            dx = round(spot - r["x"], 6)
            db.move_insts([name], dx, 0.0, pin_routes=True)
            boxes[name] = objects.inst_bbox(db, db.inst_row(name))
            slid.append((name, dx))
    return slid, far


def _site_between(db, r, cell, lo, hi, others):
    """The x of the free site in r's row (its site and orientation) nearest
    r's x with the cell starting between lo and hi; None if there is none."""
    site = cell["site"] if db.site_rows_of(cell["site"]) else None
    query = "SELECT * FROM site_row WHERE orient = ? AND abs(y - ?) < 1e-6" + \
        (" AND site = ?" if site else "")
    args = (row_orient(r["orient"]), r["y"]) + ((site,) if site else ())
    best = None
    for row in db.conn.execute(query, args):
        step = row["step_x"] or 0.0
        if not step:
            continue
        first = row["x"]
        last = row["x"] + row["num_x"] * step - cell["size_x"]
        k1, k2 = math.ceil((max(lo, first) - first) / step - TOL), \
            math.floor((min(hi, last) - first) / step + TOL)
        for k in sorted(range(k1, k2 + 1), key=lambda k: abs(first + k * step - r["x"])):
            x = round(first + k * step, 6)
            box = placed_bbox(cell["size_x"], cell["size_y"], r["orient"], x, r["y"])
            if not any(_overlap(box, o) for o in others):
                if best is None or abs(x - r["x"]) < abs(best - r["x"]):
                    best = x
                break
    return best


def _turn(db, names, boxes, flipped, had):
    """Turn those of names whose input no longer faces its net (after the
    spacing moved them) onto the nearest free site of the new orientation.
    Returns the names turned; appends to flipped."""
    done = []
    for name in names:
        r = db.inst_row(name)
        if (r["status"] or "placed").lower() in ("fixed", "cover"):
            continue
        cell = db.lib_cell_row(r["ref_cell"])
        orient = r["orient"] or "N"
        want = _access_orient(db, name, cell, orient)
        if want is None or want == orient:
            continue
        site = cell["site"] if db.site_rows_of(cell["site"]) else None
        others = [b for n, b in boxes.items() if n != name and b is not None]
        spot = _free_site(db, r, cell, site, others, want)
        if spot is None:
            continue
        db.set_inst_orient(name, want)
        if db.strap_rows(name):
            had.add(name)
        db.set_straps(name, [])
        db.move_insts([name], round(spot[0] - r["x"], 6), round(spot[1] - r["y"], 6))
        boxes[name] = objects.inst_bbox(db, db.inst_row(name))
        flipped.append(f"{name} {orient} -> {want}")
        done.append(name)
    return done


def _access_orient(db, name, cell, orient):
    """N or FS: the orientation that puts the cell's input pin on the side
    its signal comes from: above or below the cell, where the driver of its
    input net is (farther in y than in x, by more than the cell's height).
    None when it comes from beside the cell, has no driver, or the pins are
    as high in both orientations."""
    from core import netlist
    from core.commands.add_buffer_on_net import _pin_offset
    from core.commands.write_def import cell_pin
    pin_in, pin_out = cell_pin(db, cell["name"], "in"), cell_pin(db, cell["name"], "out")
    if not pin_in or not pin_out or orient not in ("N", "FS"):
        return None
    pins = netlist.pins(db).get(name, {})
    centre = lambda inst: _centre(objects.inst_bbox(db, db.inst_row(inst)))
    source = None
    if pins.get(pin_in):
        for e in netlist.ends(db, pins[pin_in]):
            if e.drives:
                source = objects.port_centre(db, e.pin) if e.kind == "port" else centre(e.inst)
    here = _centre(objects.inst_bbox(db, db.inst_row(name)))
    if source is None or abs(source[1] - here[1]) <= abs(source[0] - here[0]) + cell["size_y"]:
        return None                               # comes from beside it: no matter
    side = 1 if source[1] > here[1] else -1       # from above: the input the higher pin
    for want in ("N", "FS"):
        rise = _pin_offset(db, cell, pin_in, want)[1] - _pin_offset(db, cell, pin_out, want)[1]
        if rise * side > TOL:                     # the input on the side it comes from
            return want
    return None


def _centre(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


WIDE = (1, 2, 4, 8, 16, 32)  # how far a crowded cell looks, in cell widths + heights


def _free_site(db, r, cell, site, others, orient=None, wide=False):
    """The nearest (x, y) site for instance row r that overlaps none of the
    boxes in others, within one cell width + height (wide: then two, four
    ... up to WIDE[-1] of them, until one is free: a cell on a crowded spot,
    another on it already); None if there is none.
    orient: look in the rows of that orientation, not r's.
    A site with the cell inside the design boundary comes before a nearer
    one where it is not: a row can be lower than the cell, so a cell in a
    row at the edge of the die may reach across it."""
    for k in (WIDE if wide else WIDE[:1]):
        spot = _free_site_within(db, r, cell, site, others, orient,
                                 k * (cell["size_x"] + cell["size_y"]))
        if spot is not None:
            return spot
    return None


def _free_site_within(db, r, cell, site, others, orient, reach):
    w, h = cell["size_x"], cell["size_y"]
    orient = orient or r["orient"] or "N"
    query = "SELECT * FROM site_row WHERE orient = ? AND y BETWEEN ? AND ?" + \
        (" AND site = ?" if site else "")
    args = (row_orient(orient), r["y"] - reach, r["y"] + reach) + ((site,) if site else ())
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
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()] \
        if db.has_design() else []
    across = None                # the nearest free site, the cell not inside the boundary
    for d, x, y in sorted(set(candidates)):
        if d > reach + TOL:
            break
        box = placed_bbox(w, h, orient, x, y)
        if any(_overlap(box, o) for o in others):
            continue
        if not boundary or rect_in_polygon(box, boundary):
            return x, y
        if across is None:
            across = x, y
    return across


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
        for row in db.conn.execute(query, (row_orient(orient), r["y"]) + args):
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
    for row in db.conn.execute(query, (row_orient(orient), bound) + args + (SEARCH,)):
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
    """Routed nets (of a spine, or of none) with a driver or load among insts."""
    from core import netlist
    moved = set(insts)
    found = []
    for s in db.spine_names():
        for n in db.spine_net_rows(db.spine_row(s)["id"]):
            ends = {n["driver"], *n["loads"].split()}
            if ends & moved and db.net_wire_rows(n["name"]):
                found.append(n["name"])
    for name in netlist.plain_nets(db):
        if {inst for inst, _ in netlist.by_net(db)[name]} & moved and db.net_wire_rows(name):
            found.append(name)
    return found
