"""move_obj -direction <up|down|left|right> -distance <um> [-legal] <objects>:
move spines (with everything they own) or instances (alone).

    move_obj -direction up -distance 14.4 -legal [get_db spines .name]
    move_obj -direction left -distance 2 [get_db insts *L7*]

A spine moves whole: its location, instances, their route_pin straps and pin
wires, stubs, net centre lines and all the routed wires of its nets and stubs
(extensions, crossing boxes, shields). An instance moves alone: its pin routes
and the routes to it stay, so a warning says to route them again.

-legal: nets snap to tracks, instances to sites. A spine moves by the
distance rounded to a whole number of track-pattern periods of the layers its
routes use across the move (at least one), so its wires stay on their tracks;
then each of its instances, with its pin routes, snaps to the nearest site
(DEF ROW) of its orientation. A lone instance snaps to the nearest site from
where the distance takes it. Without DEF rows: the manufacturing grid.
"""

import fnmatch
import math

from core import objects
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import rect_in_polygon, rects_overlap

NAME = "move_obj"
SUMMARY = "Move spines (with their routing) or instances by a distance"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-direction": "value", "-distance": "value", "-legal": "flag"}

USAGE = 1
NO_OBJ = 200
OFF_TRACK = 201
LEFT_BEHIND = 202
OUTSIDE = 203
OVERLAP = 204
NO_SITE = 205
RECONNECT = 206
DIRECTIONS = {"up": (0, 1), "down": (0, -1), "right": (1, 0), "left": (-1, 0),
              "+y": (0, 1), "-y": (0, -1), "+x": (1, 0), "-x": (-1, 0)}
TOL = 1e-6


def run(session, argv):
    opts, pos = parse_options(NAME, argv, OPTIONS, max_positionals=100000)
    usage = ("Usage: move_obj -direction <up|down|left|right> -distance <um> [-legal] "
             "<spines or insts>")
    if "-direction" not in opts or "-distance" not in opts or not pos:
        raise HtreeError(USAGE, f"move_obj: -direction, -distance and the objects are "
                         f"required. {usage}")
    direction = DIRECTIONS.get(opts["-direction"].lower())
    if direction is None:
        raise HtreeError(USAGE, f"move_obj: -direction must be one of "
                         f"{' '.join(DIRECTIONS)}, got '{opts['-direction']}'")
    try:
        distance = float(opts["-distance"])
    except ValueError:
        distance = -1.0
    if distance <= 0:
        raise HtreeError(USAGE, f"move_obj: -distance must be a positive number of microns, "
                         f"got '{opts['-distance']}'")
    db = session.db
    spines, insts = _objects(session, pos)
    out = session.out
    axis = 0 if direction[0] else 1          # 0: x, 1: y
    moved = []
    if spines:
        step = _spine_step(db, spines, axis) if opts["-legal"] else None
        d = _legal(distance, step, out, "spine") if step else distance
        dx, dy = direction[0] * d, direction[1] * d
        for name in spines:
            spine_insts, nets = db.move_spine(name, dx, dy)
            info(f"Moved spine:{name} {_num(d)} {opts['-direction']}: {len(spine_insts)} "
                 f"instances, {len(nets)} nets with their routing, stubs and pin routes", out)
            moved.append(f"spine:{name}")
            if opts["-legal"]:               # nets on tracks; now instances on sites
                shifted = _snap_to_sites(db, spine_insts, out, pin_routes=True)
                touched = sorted({r["name"] for r in db.spine_net_rows(
                    db.spine_row(name)["id"]) for i in shifted
                    if i == r["driver"] or i in r["loads"].split()})
                if touched:
                    warn(RECONNECT, f"spine {name}: {len(shifted)} instance(s) moved onto "
                         f"sites with their pin routes, off the routes of {len(touched)} "
                         f"net(s) by up to the site and row pitch; route them again: "
                         f"route_net -net {{{' '.join(touched)}}} -rule <rule>", out)
            else:
                _check_tracks(db, nets, axis, d, out, name)
            _check_place(db, spine_insts, set(spine_insts), out)
    if insts:
        dx, dy = direction[0] * distance, direction[1] * distance
        db.move_insts(insts, dx, dy)
        info(f"Moved {len(insts)} instance(s) {_num(distance)} {opts['-direction']}: "
             f"{' '.join(insts)}", out)
        if opts["-legal"]:
            _snap_to_sites(db, insts, out)
        moved += [f"inst:{n}" for n in insts]
        behind = [n for n in insts if db.strap_rows(n) or _in_spine(db, n)]
        if behind:
            warn(LEFT_BEHIND, f"only the instances moved; the pin routes, spine geometry and "
                 f"routes of {' '.join(behind)} stay where they were (route_pin and route_net "
                 f"them again, or move the whole spine)", out)
        _check_place(db, insts, set(insts), out)
    return tuple(moved)


def _objects(session, words):
    """(spine names, inst names): spine: and inst: handles, or names and glob
    patterns, a spine's name first."""
    db = session.db
    spine_names, inst_names = db.spine_names(), db.inst_names()
    spines, insts = [], []
    for word in (w for arg in words for w in session.split_list(arg)):
        if word.startswith("spine:"):
            hits_s, hits_i = [n for n in spine_names if n == word[6:]], []
        elif word.startswith("inst:"):
            hits_s, hits_i = [], [n for n in inst_names if n == word[5:]]
        else:
            hits_s = [n for n in spine_names if fnmatch.fnmatchcase(n, word)]
            hits_i = [] if hits_s else [n for n in inst_names if fnmatch.fnmatchcase(n, word)]
        if not hits_s and not hits_i:
            raise HtreeError(NO_OBJ, f"move_obj: no spine or instance '{word}' (get_db spines, "
                             f"get_db insts)")
        spines += [n for n in hits_s if n not in spines]
        insts += [n for n in hits_i if n not in insts]
    in_spines = {m["inst"] for s in spines for m in db.spine_members(db.spine_row(s)["id"])}
    return spines, [n for n in insts if n not in in_spines]   # those move with their spine


def _in_spine(db, inst):
    return any(m["inst"] == inst for s in db.spine_names()
               for m in db.spine_members(db.spine_row(s)["id"]))


def _spine_step(db, spines, axis):
    """The legal step of a spine move along axis: the least common multiple of
    the track-pattern periods (pitch x pattern length; the pitch alone with no
    assignment) of the layers its routes use whose tracks run across the move,
    and of the manufacturing grid."""
    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    unit = grid or 0.001
    direction = "x" if axis == 0 else "y"
    layers = {r["layer"] for s in spines for n in db.spine_net_rows(db.spine_row(s)["id"])
              for r in db.net_wire_rows(n["name"]) if "/" not in r["layer"]}
    step = 1
    for layer in layers:
        pos = db.track_positions(layer, direction)
        if len(pos) < 2:
            continue
        period = pos[1] - pos[0]
        row = db.track_assignment_row(layer)
        if row is not None and row["direction"] == direction:
            period *= len(row["pattern"].split())
        n = int(round(period / unit))
        step = step * n // math.gcd(step, n)
    return step * unit


def _snap_to_sites(db, insts, out, pin_routes=False):
    """Move each instance to the nearest placement site of its orientation
    (DEF ROW); without rows, to the manufacturing grid. Returns the names of
    those that moved."""
    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    rows = db.has_site_rows()
    if not rows:
        warn(NO_SITE, "no DEF rows (read_def): instances snap to the manufacturing grid "
             "only", out)
    shifted, worst, missed = [], 0.0, []
    for name in insts:
        r = db.inst_row(name)
        cell = db.lib_cell_row(r["ref_cell"])
        if rows:
            site = db.legal_site(r["x"], r["y"], cell["size_x"], r["orient"] or "N",
                                 cell["site"] if db.site_rows_of(cell["site"]) else None)
            reach = cell["size_x"] + cell["size_y"]     # a snap, not a relocation
            if site is None or abs(site[0] - r["x"]) + abs(site[1] - r["y"]) > reach:
                missed.append(name)
                continue
            x, y = site[0], site[1]
        elif grid:
            x, y = (round(round(v / grid) * grid, 6) for v in (r["x"], r["y"]))
        else:
            continue
        dx, dy = round(x - r["x"], 6), round(y - r["y"], 6)
        if dx or dy:
            db.move_insts([name], dx, dy, pin_routes)
            shifted.append(name)
            worst = max(worst, abs(dx) + abs(dy))
    if shifted:
        info(f"  -legal: {len(shifted)} instance(s) snapped to "
             f"{'sites' if rows else 'the grid'} (up to {_num(worst)} um)"
             + (", with their pin routes" if pin_routes else ""), out)
    if missed:
        warn(NO_SITE, f"no site of their cell's site and orientation within one cell width "
             f"+ height of {' '.join(missed)} (outside the rows?); left where the move put "
             f"them", out)
    return shifted


def _legal(distance, step, out, what):
    d = max(1, round(distance / step)) * step
    d = round(d, 6)
    if abs(d - distance) > TOL:
        info(f"  -legal: distance {_num(distance)} rounded to {_num(d)} (the {what} step is "
             f"{_num(round(step, 6))})", out)
    return d


def _check_tracks(db, nets, axis, d, out, name):
    """Without -legal: warn when the routes left their tracks."""
    direction = "x" if axis == 0 else "y"
    off = []
    for layer in {r["layer"] for n in nets for r in db.net_wire_rows(n) if "/" not in r["layer"]}:
        pos = db.track_positions(layer, direction)
        if len(pos) >= 2:
            step = pos[1] - pos[0]
            if abs(d / step - round(d / step)) > 1e-6:
                off.append(f"{layer} (pitch {_num(step)})")
    if off:
        warn(OFF_TRACK, f"spine {name} moved {_num(d)}: its routes on {', '.join(off)} are off "
             f"their tracks now; use -legal to move by whole track periods", out)


def _check_place(db, names, moving, out):
    boundary = None
    if db.has_design() and db.design_row()["boundary"]:
        boundary = [float(v) for v in db.design_row()["boundary"].split()]
    outside = []
    for name in names:
        box = objects.inst_bbox(db, db.inst_row(name))
        if box is None:
            continue
        if boundary and not rect_in_polygon(box, boundary):
            outside.append(name)
        for other in db.inst_rows():
            if other["name"] in moving:
                continue
            other_box = objects.inst_bbox(db, other)
            if other_box and rects_overlap(box, other_box):
                warn(OVERLAP, f"{name} overlaps instance {other['name']}", out)
    if outside:
        more = f" and {len(outside) - 10} more" if len(outside) > 10 else ""
        warn(OUTSIDE, f"{len(outside)} instance(s) not inside the design boundary: "
             f"{' '.join(outside[:10])}{more}", out)
