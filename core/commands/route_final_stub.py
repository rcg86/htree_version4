"""route_final_stub -rule <rule> [-stub <stubs>] [-shield] [-shield_nets {l r}]:
route the final stubs of the
built spines: each stub as one straight wire, its full length as create_spine
placed it from the spec, on a signal track.

    route_final_stub -rule rule1
    route_final_stub -rule rule1 -stub {stub1 stub2}

A stub of a vertical spine (spine.orientation) is routed vertically, on the
rule's vertical layer; one of a horizontal spine horizontally, on its
horizontal layer, as wide as the rule width there. The track is the signal
('-') track nearest the stub's centre line that keeps the rule spacing to the
shapes of other nets on that layer over the stub's length; when the nearest
is blocked, the next ones out on either side are tried. The stub wire belongs
to its leaf's net (the net driving the stub) and is stored with it (kind
stub), apart from what route_net stores, so each command replaces only its
own. Where the leaf's route meets the stub wire on the other layer a crossing
box is stored (kind stub_cross).

-shield: as route_net -shield does for the main route, the stub wire gets one
power shield on each side, on the nearest track keeping the rule spacing, the
net of its track (assign_track_for_route), else -shield_nets; cut where it
would come closer than the rule spacing to another shape. Stored with the
stub (kind stub_shield), so delete_route and routing the stub again remove
them with it.
"""

import bisect
import fnmatch

from core import objects, root_attrs
from core.commands.route_net import (Grid, NO_POWER, OFF_TRACKS, SHIELD_NETS, TOL, _along,
                                     _report_short,
                                     _gap, _ia_shapes, _obstacles, _rule_layers, _shields)
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "route_final_stub"
SUMMARY = "Route the spine stubs as straight wires on signal tracks"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-rule": "value", "-stub": "value", "-shield": "flag", "-shield_nets": "value"}

USAGE = 1
NO_STUB = 190
NO_TRACK = 191
NOT_JOINED = 192
BENT = 193
SEARCH = 20                  # tracks tried on each side of the nearest one


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-rule" not in opts:
        raise HtreeError(USAGE, "route_final_stub: -rule is required. Usage: "
                         "route_final_stub -rule <route_rule> [-stub <stubs>]")
    shield = None
    if opts["-shield"] or "-shield_nets" in opts:
        shield = tuple(session.split_list(opts.get("-shield_nets", " ".join(SHIELD_NETS))))
        if len(shield) != 2:
            raise HtreeError(USAGE, f"route_final_stub: -shield_nets takes two nets, left of "
                             f"/ above and right of / below the stub, got "
                             f"'{opts['-shield_nets']}'")
    db = session.db
    objects.require_tech(db)
    stubs = _stubs(session, opts.get("-stub"))
    layers = _rule_layers(db, opts["-rule"].removeprefix("route_rule:"))
    grid = Grid(db, layers)
    out = session.out
    h, v = layers
    info(f"route_final_stub: rule {layers.rule}: vertical stubs on {v.name} (width "
         f"{_num(v.width)}), horizontal ones on {h.name} (width {_num(h.width)}), on signal "
         f"tracks", out)
    done = []
    for spine, stub, net in stubs:
        if _route_stub(db, grid, spine, stub, net, out, shield):
            done.append(f"stub:{spine['name']}/{stub['name']}")
    info(f"route_final_stub: {len(done)} of {len(stubs)} stubs routed", out)
    return tuple(done)


def _stubs(session, text):
    """[(spine row, stub row, leaf net name)] from names, glob patterns or
    stub: handles; every stub of every built spine when text is None."""
    db = session.db
    every = []
    for s in db.spine_names():
        spine = db.spine_row(s)
        nets = {r["loads"]: r["name"] for r in db.spine_net_rows(spine["id"])}
        every += [(spine, r, nets.get(r["name"])) for r in db.spine_stub_rows(spine["id"])]
    if not every:
        raise HtreeError(NO_STUB, "route_final_stub: no spine stubs (create_spine -build)")
    if text is None:
        return every
    found = []
    for word in session.split_list(text):
        if word.startswith("stub:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits = [e for e in every if e[0]["name"] == spine and e[1]["name"] == name]
        else:
            hits = [e for e in every if fnmatch.fnmatchcase(e[1]["name"], word)]
        if not hits:
            raise HtreeError(NO_STUB, f"route_final_stub: no spine stub '{word}' (get_db "
                             f"spines .stubs lists them)")
        found += [e for e in hits if e not in found]
    return found


def _route_stub(db, grid, spine, stub, net, out, shield=None):
    if len(stub["points"].split()) > 4:
        warn(BENT, f"stub {spine['name']}/{stub['name']} runs over a bend of its spine "
             f"(move_spine_to_boundary); bent stubs are not routed yet", out)
        return False
    x1, y1, x2, y2 = (float(c) for c in stub["points"].split())
    vertical = (spine["orientation"] or "").lower() == "vertical"   # the spine's direction
    if abs(x2 - x1) + abs(y2 - y1) > TOL:    # on a bent spine: the way its stretch runs
        vertical = abs(x2 - x1) < TOL
    lay = grid.v if vertical else grid.h
    tracks = grid.all_xs if vertical else grid.all_ys
    centre = x1 if vertical else y1
    lo, hi = (min(y1, y2), max(y1, y2)) if vertical else (min(x1, x2), max(x1, x2))
    label = f"{spine['name']}/{stub['name']}"
    if centre < tracks[0] - TOL or centre > tracks[-1] + TOL:
        warn(OFF_TRACKS, f"stub {label} at {'x' if vertical else 'y'} {_num(centre)} is "
             f"beyond the {lay.name} signal tracks ({_num(tracks[0])} .. "
             f"{_num(tracks[-1])}); not routed", out)
        return False
    along = grid.all_ys if vertical else grid.all_xs     # the tracks it runs across
    if lo < along[0] - TOL or hi > along[-1] + TOL:
        warn(OFF_TRACKS, f"stub {label} runs past the last "
             f"{(grid.h if vertical else grid.v).name} track ({'y' if vertical else 'x'} "
             f"{_num(along[0])} .. {_num(along[-1])}): it is partly outside the die", out)
    shapes = [(layer, r) for layer, r in _obstacles(db, net) if layer == lay.name]
    k = bisect.bisect_left(tracks, centre)
    order = sorted(range(max(0, k - SEARCH), min(len(tracks), k + SEARCH + 1)),
                   key=lambda j: abs(tracks[j] - centre))
    rect = None
    for j in order:              # nearest first, then the next ones out either side
        t = tracks[j]
        cand = ((t - lay.width / 2, lo, t + lay.width / 2, hi) if vertical
                else (lo, t - lay.width / 2, hi, t + lay.width / 2))
        if not any(_gap(cand, r) < lay.spacing - TOL for _, r in shapes):
            rect = cand
            break
    if rect is None:
        warn(NO_TRACK, f"stub {label}: no signal track within {SEARCH} of its centre line "
             f"keeps the {lay.name} spacing {_num(lay.spacing)} to other nets; not routed", out)
        return False
    wires = [("stub", lay.name, rect)]
    other = grid.h if vertical else grid.v      # the leaf route meeting it on the other layer
    joins = []                   # the leaf route overlapping the stub wire
    for r in db.net_wire_rows(net) if net else []:
        if r["kind"] not in ("wire", "extension"):
            continue
        w = tuple(float(c) for c in r["rect"].split())
        box = (max(w[0], rect[0]), max(w[1], rect[1]), min(w[2], rect[2]), min(w[3], rect[3]))
        if box[0] < box[2] - TOL and box[1] < box[3] - TOL:
            joins.append(box)
            if r["layer"] != lay.name:   # on the other layer: a box for the via
                wires.append(("stub_cross", f"{lay.name}/{other.name}", box))
    shields, cut, no_power, short = [], 0.0, [], []
    if shield:                   # one each side, its track's net (as route_net -shield)
        rect_of = lambda r: tuple(float(c) for c in r["rect"].split())
        leaf = db.net_wire_rows(net) if net else []
        own = [("own", r["layer"], rect_of(r)) for r in leaf      # the leaf's signal wires
               if r["kind"] in ("wire", "extension")]
        powered = [(r["shield_net"], r["layer"], rect_of(r)) for r in leaf   # its shields
                   if r["kind"] in ("shield", "shield_ext")]
        found, cut, no_power, short = _shields(
            [("wire", lay.name, rect)] + own, _ia_shapes(db, net) + powered, grid, shield,
            min_length=root_attrs.get(db, "ignore_shield_less_than_routing_length"))
        shields = [("stub_shield", layer, r, power) for _, layer, r, power in found]
        wires += shields
    t = (rect[0] + rect[2]) / 2 if vertical else (rect[1] + rect[3]) / 2
    moved = abs(t - centre)
    db.set_net_wires(net or stub["name"],
                     [(w[0], w[1], " ".join(_num(round(c, 6)) for c in w[2])) + tuple(w[3:])
                      for w in wires], stub=True)
    info(f"  stub {label} ({net or 'no net'}): {lay.name} {'x' if vertical else 'y'} {_num(t)}"
         f"{f' ({_num(round(moved, 6))} from its centre line)' if moved > TOL else ''}, "
         f"{_num(lo)} .. {_num(hi)} (length {_num(round(hi - lo, 6))})"
         + (f"; meets its leaf route ({len(joins)} overlap(s))" if joins else ""), out)
    for power in dict.fromkeys(w[3] for w in shields):
        mine = [w for w in shields if w[3] == power]
        info(f"    shield {power}: {len(mine)} wire(s), "
             f"{_num(round(sum(_along(w[2]) for w in mine), 3))} um", out)
    _report_short(short, db, out)
    if cut:
        info(f"    shields cut over {_num(round(cut, 3))} um where they would come closer "
             f"than the rule spacing to another shape", out)
    if no_power:
        warn(NO_POWER, f"stub {label}: no shield where the next track is not a power "
             f"track: {'; '.join(no_power)}", out)
    if net and not joins:
        warn(NOT_JOINED, f"stub {label}: the route of {net} does not reach the stub wire "
             f"(route_net -net {net} first, or it ended on another track)", out)
    return True
