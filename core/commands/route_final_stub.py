"""route_final_stub -rule <rule> [-stub <stubs>] [-shield] [-shield_nets {l r}]:
route the final stubs of the built spines: each stub as one straight wire,
its full length as create_spine placed it from the spec, on a signal track.
A stub that lies over a bend of its spine (move_spine_to_boundary) is routed
as one wire a straight piece.

    route_final_stub -rule rule1
    route_final_stub -rule rule1 -stub {stub1 stub2}

A stub of a vertical spine (spine.orientation) is routed vertically, on the
rule's vertical layer; one of a horizontal spine horizontally, on its
horizontal layer, as wide as the rule width there.

One track for the stubs of a centre line (plan_stubs): the stubs of a spine
that lie on one centre line share one track, so a straight spine has one
stub track and a spine with two bends three (the stretch before the bends,
the one between them, the one after). The tracks are chosen for the whole
spine, also when -stub names a few of its stubs. The track is the signal
('-') track nearest the centre line on which every stub of the line keeps
the rule spacing to the shapes of other nets on that layer over its length;
when the nearest is blocked for one of them, the next ones out on either
side are tried, for all of them. A stub that cannot share the track is not
routed. Two stubs that meet end to end on the track (at the middle of a
mirrored spine) each end short by half of what the spacing needs. The design
boundary is a hard limit, as in route_net: a track on which a wire would not
lie inside it is not taken, and a stub that fits on none is not routed. The
stub wire belongs
to its leaf's net (the net driving the stub: its .shield_net) and is stored
under <leaf net>_stub (kind stub, net_wire:<leaf net>_stub/<n>), apart from
what route_net stores, so each command replaces only its own. Where the leaf's route meets the stub wire on the other layer a crossing
box is stored (kind stub_cross).

A bent stub: each straight piece is routed the way it runs, a vertical piece
on the vertical layer and a horizontal one on the horizontal layer, each on
the track of its centre line. The pieces
meet where their tracks cross: each wire runs on to cover the whole crossing,
a box of (vertical width) x (horizontal width), stored as a crossing box
(kind stub_cross) for the via to come, as route_net does at a layer change.

-shield: as route_net -shield does for the main route, the stub wire (each
piece of a bent stub) gets one power shield on each side, on the nearest
track keeping the rule spacing, the net of its track
(assign_track_for_route), else -shield_nets; cut where it would come closer
than the rule spacing to another shape or leave the design boundary. Stored
with the
stub (kind stub_shield), so delete_route and routing the stub again remove
them with it.
"""

import bisect
import fnmatch
import math

from core import objects, root_attrs, route_status, vias
from core.commands.route_net import (Grid, NO_POWER, OFF_TRACKS, OUTSIDE, SHIELD_NETS, TOL,
                                     _along, _box, _report_fenced, _report_short,
                                     _gap, _ia_shapes, _rule_layers, _shields)
from core.db import _num, stub_owner
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.spine_snake import stub_points

NAME = "route_final_stub"
SUMMARY = "Route the spine stubs as straight wires on signal tracks, a wire a piece of a bent stub"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-rule": "value", "-stub": "value", "-shield": "flag", "-shield_nets": "value"}

USAGE = 1
NO_STUB = 190
NO_TRACK = 191
NOT_JOINED = 192
STALE = 193
SEARCH = 20                  # tracks tried on each side of the nearest one


def run(session, argv):
    result = _route(session, argv)
    vias.report_assigned(vias.auto_assign(session.db), NAME, session.out)
    return result


def _route(session, argv):
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
    fixed = db.fixed_nets()
    keys = {id(stub): route_status.stub_key(spine["name"], stub["name"])
            for spine, stub, _ in stubs}
    route_status.skip(NAME, "fixed stub(s)", [f"stub:{spine['name']}/{stub['name']}"
                                              for spine, stub, _ in stubs
                                              if keys[id(stub)] in fixed], session.out)
    stubs = [e for e in stubs if keys[id(e[1])] not in fixed]
    if not stubs:
        return ()
    layers = _rule_layers(db, opts["-rule"].removeprefix("route_rule:"))
    grid = Grid(db, layers)
    out = session.out
    h, v = layers
    info(f"route_final_stub: rule {layers.rule}: vertical stubs on {v.name} (width "
         f"{_num(v.width)}), horizontal ones on {h.name} (width {_num(h.width)}), on signal "
         f"tracks", out)
    routed = set()               # (spine, stub) of the ones routed
    spines = list(dict.fromkeys(spine["name"] for spine, _, _ in stubs))
    for k, name in enumerate(spines):
        mine = [e for e in stubs if e[0]["name"] == name]
        # the stub wires this run still replaces are no obstacle: of the spines to come
        later = {net or stub["name"] for spine, stub, net in stubs
                 if spine["name"] in spines[k + 1:]}
        plan = plan_stubs(db, grid, mine[0][0], later)
        _report_plan(grid, name, plan, out)
        for spine, stub, net in mine:
            if _route_stub(db, grid, spine, stub, net, out, shield, plan):
                routed.add((name, stub["name"]))
        _report_stale(db, grid, name, plan, {n for s, n in routed if s == name}, out)
    done = [f"stub:{spine['name']}/{stub['name']}" for spine, stub, _ in stubs
            if (spine["name"], stub["name"]) in routed]
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


def _runs(grid, spine, stub):
    """([(vertical, centre, start, end)], [note]) of a stub's straight pieces
    in the order of its points: one for a straight stub, one more for every
    bend of its spine it lies over. An end piece no longer than half the
    width of the wire it leaves is inside that wire: it gets none of its own
    (note)."""
    upright = (spine["orientation"] or "").lower() == "vertical"   # the spine's direction
    runs = []
    pts = stub_points(stub["points"])
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        vertical = upright
        if abs(x2 - x1) + abs(y2 - y1) > TOL:    # on a bent spine: the way its stretch runs
            vertical = abs(x2 - x1) < TOL
        runs.append((vertical, x1, y1, y2) if vertical else (vertical, y1, x1, x2))
    notes = []
    for end, k, joins in (("first", 0, 1), ("last", -1, -2)):
        if len(runs) < 2:
            break
        vertical, _, a, b = runs[k]
        lay = grid.h if vertical else grid.v     # the layer of the piece it joins
        if abs(b - a) <= lay.width / 2 + TOL:
            notes.append(f"its {end} {_num(round(abs(b - a), 6))} um, past the bend, are "
                         f"inside the {lay.name} wire: no wire of their own")
            del runs[k]
    return runs, notes


def _piece_rect(grid, runs, ts, i):
    """The wire of piece i on its track ts[i]. Where it meets another piece
    it runs to that piece's track (ts[i - 1], ts[i + 1]) and half that wire's
    width on, so the two cover their whole crossing. None when those tracks
    leave it no length the way it runs."""
    vertical, _, a, b = runs[i]
    lay, other = (grid.v, grid.h) if vertical else (grid.h, grid.v)
    way = b - a
    more_a = more_b = 0.0
    if i > 0:
        a, more_a = ts[i - 1], other.width / 2
    if i < len(runs) - 1:
        b, more_b = ts[i + 1], other.width / 2
    if len(runs) > 1 and (b - a) * (1 if way > 0 else -1) < TOL:
        return None
    lo, hi = (a - more_a, b + more_b) if a <= b else (b - more_b, a + more_a)
    t = ts[i]
    return ((t - lay.width / 2, lo, t + lay.width / 2, hi) if vertical
            else (lo, t - lay.width / 2, hi, t + lay.width / 2))


class StubPlan:
    """Where the stubs of one spine go (plan_stubs): the stubs on one centre
    line share one track."""

    def __init__(self):
        self.runs = {}           # stub -> its straight pieces (_runs), ends drawn back
        self.notes = {}          # stub -> [note] for the report
        self.net = {}            # stub -> its leaf's net (None without one)
        self.lines = []          # (vertical, centre) of every centre line stubs lie on
        self.line = {}           # stub -> the centre line (index) of each piece
        self.shared = {}         # centre line -> its track
        self.tracks = {}         # stub -> the track of each piece; the stubs that fit only
        self.why = {}            # stub without tracks: off | outside | blocked | shared | close
        self.close = {}          # stub left out as 'close' -> the stub it would come close to

    def line_of(self, vertical, centre):
        for k, (upright, c) in enumerate(self.lines):
            if upright == vertical and abs(c - centre) < TOL:
                return k
        self.lines.append((vertical, centre))
        return len(self.lines) - 1

    def rects(self, grid, name):
        """[(layer, wire rect)] of the pieces of a stub that fits, else []."""
        ts = self.tracks.get(name)
        if ts is None:
            return []
        runs = self.runs[name]
        return [(grid.v if run[0] else grid.h, _piece_rect(grid, runs, ts, i))
                for i, run in enumerate(runs)]


def _beyond(grid, runs):
    """(vertical, centre) of the first piece whose centre line is beyond the
    signal tracks of its layer, else None."""
    for vertical, centre, _, _ in runs:
        tracks = grid.all_xs if vertical else grid.all_ys
        if centre < tracks[0] - TOL or centre > tracks[-1] + TOL:
            return vertical, centre
    return None


def _keep_apart(db, grid, plan, names):
    """Stubs that meet end to end on a centre line (the two at the middle of a
    mirrored spine) are on one track: their ends are drawn back, each by half
    of what the layer's spacing needs (up to the manufacturing grid), so the
    two wires keep it. Only an end of a stub is drawn back, not a bend."""
    step = (db.tech_row()["manufacturing_grid"] if db.has_tech() else None) or 0.001
    up = lambda c: round(math.ceil(c / step - 1e-6) * step, 6)
    for line, (vertical, _) in enumerate(plan.lines):
        lay = grid.v if vertical else grid.h
        on = sorted((min(run[2:]), max(run[2:]), name, i) for name in names
                    for i, run in enumerate(plan.runs[name]) if plan.line[name][i] == line)
        for (_, hi, n1, i1), (lo, _, n2, i2) in zip(on, on[1:]):
            need = lay.spacing - (lo - hi)
            if n1 == n2 or need < TOL:
                continue
            ends = [(n, i, k, top) for n, i, top in ((n1, i1, True), (n2, i2, False))
                    for k in (_stub_end(plan.runs[n], i, top),) if k is not None]
            for n, i, k, top in ends:
                cut = up(need / len(ends))
                vertical, centre, a, b = plan.runs[n][i]
                if cut > abs(b - a) - TOL:       # nothing would be left of it
                    continue
                moved = round((a if k == 0 else b) + (-cut if top else cut), 6)
                plan.runs[n][i] = (vertical, centre, moved, b) if k == 0 else \
                    (vertical, centre, a, moved)
                plan.notes[n].append(
                    f"its {'first' if k == 0 else 'last'} {_num(cut)} um are left off: stub "
                    f"{n2 if n == n1 else n1} is on the same track there ({lay.name} spacing "
                    f"{_num(lay.spacing)})")


def _stub_end(runs, i, top):
    """Which end of piece i is its upper (top) or lower one: 0 its start, 1
    its end; None when that end is a bend, not an end of the stub."""
    _, _, a, b = runs[i]
    k = int(b >= a) if top else int(b < a)
    return k if (k == 0 and i == 0) or (k == 1 and i == len(runs) - 1) else None


def _spec_stub_tracks(db, spine, plan, names):
    """{centre line: coordinate} of the lines whose stubs' leaves the spine
    spec gives an output track (track: {output: k}, core/spine_tracks.py):
    track k of the stretch the line lies on."""
    from core import spine_tracks
    kout = {inst: k[1] for inst, k in spine_tracks.cell_tracks(db, spine["name"]).items()
            if k[1]}
    if not kout:
        return {}
    found = spine_tracks.stretches(db, spine["name"])
    leaf = {s["name"]: s["driver"] for s in db.spine_stub_rows(spine["id"])}
    lines = {}
    for name in names:
        k = kout.get(leaf.get(name))
        if not k:
            continue
        for (vertical, centre, a, b), line in zip(plan.runs[name], plan.line[name]):
            point = (centre, (a + b) / 2) if vertical else ((a + b) / 2, centre)
            s = spine_tracks.stretch_at(found, *point)
            if s is not None and s.vertical == vertical and s.coord(k) is not None:
                lines.setdefault(line, s.coord(k))
    return lines


def plan_stubs(db, grid, spine, replaced=(), more=()):
    """The tracks of the stubs of a spine (StubPlan), every stub of it. The
    stubs on one centre line take one track: all the stubs of a straight
    spine, the stubs on one stretch of a bent one, so a spine with two bends
    has three. It is the signal track nearest the centre line, else the next
    ones out on either side (SEARCH each way) (when the spine spec gives the
    leaves an output track, that track only: _spec_stub_tracks), on which every piece's wire
    keeps its layer's spacing to the shapes of other nets and lies inside the
    design boundary. The tracks of all centre lines are chosen together.
    When the stubs cannot all share: one after another, a stub that does not
    fit with the ones before it is left out (.why).

    The stub wires stored of this spine are no obstacle (routed again, they
    go), nor those of the nets in replaced. more: [(layer, rect, net)] of
    shapes not stored yet."""
    plan = StubPlan()
    nets = {r["loads"]: r["name"] for r in db.spine_net_rows(spine["id"])}
    names = []
    for stub in db.spine_stub_rows(spine["id"]):
        name = stub["name"]
        runs, plan.notes[name] = _runs(grid, spine, stub)
        plan.runs[name], plan.net[name] = runs, nets.get(name)
        if _beyond(grid, runs):
            plan.why[name] = "off"
            continue
        plan.line[name] = [plan.line_of(vertical, centre) for vertical, centre, _, _ in runs]
        names.append(name)
    if not names:
        return plan
    _keep_apart(db, grid, plan, names)
    owner = {name: plan.net[name] or name for name in plan.runs}
    gone = set(owner.values()) | set(replaced)
    gone |= {stub_owner(n) for n in gone}        # the stubs' rows: under <net>_stub
    rect = lambda text: tuple(float(c) for c in text.split())
    shapes = [(r["layer"], rect(r["rect"]), None) for r in db.strap_rows()]
    shapes += [(r["layer"], rect(r["rect"]), None) for r in db.pin_wire_rows()]
    shapes += [(r["layer"], rect(r["rect"]), r["net"]) for r in db.net_wire_rows()
               if r["kind"] != "cross"
               and not (r["kind"].startswith("stub") and r["net"] in gone)]
    shapes += list(more)

    cands = []                   # of each centre line: its tracks, the nearest first
    for vertical, centre in plan.lines:
        tracks = grid.all_xs if vertical else grid.all_ys
        k = bisect.bisect_left(tracks, centre)
        cands.append(sorted(tracks[max(0, k - SEARCH):k + SEARCH + 1],
                            key=lambda t: abs(t - centre)))
    for line, x in _spec_stub_tracks(db, spine, plan, names).items():
        cands[line] = [x]        # the spine spec's: its leaves' output track, nothing else
    reach = max(abs(t - centre) for (_, centre), found in zip(plan.lines, cands)
                for t in found) + max(grid.h.width, grid.v.width) + \
        max(grid.h.spacing, grid.v.spacing)
    every = [run for name in names for run in plan.runs[name]]
    xs = [c for vertical, centre, a, b in every for c in ((centre,) if vertical else (a, b))]
    ys = [c for vertical, centre, a, b in every for c in ((a, b) if vertical else (centre,))]
    area = (min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach)
    near = {}                    # layer -> the shapes any of the wires could come close to
    for layer, r, net in shapes:
        if r[0] <= area[2] and r[2] >= area[0] and r[1] <= area[3] and r[3] >= area[1]:
            near.setdefault(layer, []).append((r, net))

    def solve(some, fence):
        """{centre line: track} for the stubs some, None when there is none."""
        order = list(dict.fromkeys(line for name in some for line in plan.line[name]))
        at = {line: k for k, line in enumerate(order)}
        ready = [[] for _ in order]      # the pieces to check once a line has its track:
        held = [set() for _ in order]    # theirs, the piece before's and the piece after's
        for name in some:
            lines = plan.line[name]
            for i in range(len(lines)):
                needs = lines[max(0, i - 1):i + 2]
                last = max(at[line] for line in needs)
                ready[last].append((name, i))
                for line in needs:           # tracks a later choice still depends on
                    for k in range(at[line] + 1, last + 1):
                        held[k].add(line)
        seen, dead = {}, set()

        def clear(name, i, ts):
            lines = plan.line[name]
            key = (name, i) + tuple(ts[line] for line in lines[max(0, i - 1):i + 2])
            if key not in seen:
                runs = plan.runs[name]
                box = _piece_rect(grid, runs, [ts.get(line) for line in lines], i)
                lay = grid.v if runs[i][0] else grid.h
                seen[key] = box is not None and (fence is None or fence.holds(box)) and \
                    not any(net != owner[name] and _gap(box, r) < lay.spacing - TOL
                            for r, net in near.get(lay.name, ()))
            return seen[key]

        def pick(k, ts):
            if k == len(order):
                return dict(ts)
            key = (k,) + tuple(ts[line] for line in sorted(held[k]))
            if key in dead:
                return None
            for t in cands[order[k]]:    # nearest first
                ts[order[k]] = t
                if all(clear(name, i, ts) for name, i in ready[k]):
                    found = pick(k + 1, ts)
                    if found is not None:
                        return found
            ts.pop(order[k], None)
            dead.add(key)
            return None

        return pick(0, {})

    def left_out(name):
        if solve([name], grid.fence) is not None:
            return "shared"
        if grid.fence is not None and solve([name], None) is not None:
            return "outside"
        return "blocked"

    fit, kept = solve(names, grid.fence), list(names)
    if fit is None:              # not all of them: one after another
        kept = []
        for name in names:
            if solve(kept + [name], grid.fence) is not None:
                kept.append(name)
            else:
                plan.why[name] = left_out(name)
        fit = solve(kept, grid.fence) if kept else {}
    while True:                  # two of them closer than the spacing: the later one goes
        plan.shared = fit
        plan.tracks = {name: [fit[line] for line in plan.line[name]] for name in kept}
        wires = [(name, lay, box) for name in kept for lay, box in plan.rects(grid, name)]
        clash = next(((a, b) for k, (a, lay, box) in enumerate(wires)
                      for b, other, r in wires[k + 1:]
                      if a != b and lay is other and _gap(box, r) < lay.spacing - TOL), None)
        if clash is None:
            return plan
        plan.why[clash[1]], plan.close[clash[1]] = "close", clash[0]
        kept.remove(clash[1])
        fit = solve(kept, grid.fence) if kept else {}


def _report_plan(grid, spine, plan, out):
    """One line: the tracks the stubs of the spine share."""
    said = []
    for line, t in plan.shared.items():
        vertical, centre = plan.lines[line]
        lay = grid.v if vertical else grid.h
        count = sum(line in plan.line[name] for name in plan.tracks)
        moved = abs(t - centre)
        said.append(f"{lay.name} {'x' if vertical else 'y'} {_num(t)} ({count} stub(s)"
                    + (f", {_num(round(moved, 6))} from their centre line" if moved > TOL
                       else "") + ")")
    if said:
        info(f"  spine {spine}: {len(plan.tracks)} of {len(plan.runs)} stub(s) on "
             f"{len(said)} track(s), the stubs on one centre line on one track: "
             f"{'; '.join(said)}", out)


def _report_stale(db, grid, spine, plan, routed, out):
    """Warn of the stubs of the spine not routed now whose stored wires are
    not the ones of the plan: on another track, or with other ends."""
    stale = []
    for name in plan.runs:
        if name in routed:
            continue
        have = sorted(tuple(float(c) for c in r["rect"].split())
                      for r in db.stub_wire_rows(plan.net[name] or name) if r["kind"] == "stub")
        want = sorted(box for _, box in plan.rects(grid, name))
        if have and (len(have) != len(want) or
                     any(not _same(a, b) for a, b in zip(have, want))):
            stale.append(name)
    if stale:
        warn(STALE, f"spine {spine}: the wires of stub(s) {' '.join(stale)}, of an earlier "
             f"route_final_stub, are not on the tracks its stubs share now: route them again "
             f"(route_final_stub -stub {{{' '.join(stale)}}}), or remove them (delete_route "
             f"-nets {{{' '.join(f'stub:{spine}/{n}' for n in stale)}}})", out)


def _route_stub(db, grid, spine, stub, net, out, shield=None, plan=None):
    label = f"{spine['name']}/{stub['name']}"
    plan = plan or plan_stubs(db, grid, spine)
    runs, notes = plan.runs[stub["name"]], plan.notes[stub["name"]]
    past = []
    for vertical, centre, a, b in runs:
        lay = grid.v if vertical else grid.h
        tracks = grid.all_xs if vertical else grid.all_ys
        if centre < tracks[0] - TOL or centre > tracks[-1] + TOL:
            warn(OFF_TRACKS, f"stub {label} at {'x' if vertical else 'y'} {_num(centre)} is "
                 f"beyond the {lay.name} signal tracks ({_num(tracks[0])} .. "
                 f"{_num(tracks[-1])}); not routed", out)
            return False
        along = grid.all_ys if vertical else grid.all_xs     # the tracks it runs across
        if min(a, b) < along[0] - TOL or max(a, b) > along[-1] + TOL:
            past.append(f"the last {(grid.h if vertical else grid.v).name} track "
                        f"({'y' if vertical else 'x'} {_num(along[0])} .. {_num(along[-1])})")
    if past:
        warn(OFF_TRACKS, f"stub {label} runs past {' and '.join(dict.fromkeys(past))}: it is "
             f"partly outside the die", out)
    ts = plan.tracks.get(stub["name"])
    why = plan.why.get(stub["name"])
    if ts is None and why == "outside":
        warn(OUTSIDE, f"stub {label}: its wire would not lie inside the design boundary on "
             f"any signal track within {SEARCH} of its centre line; not routed", out)
        return False
    if ts is None and why == "shared":
        warn(NO_TRACK, f"stub {label}: no signal track within {SEARCH} of its centre line "
             f"that it can share with the other stubs of spine {spine['name']} on that line "
             f"keeps the spacing to other nets and lies inside the design boundary; not "
             f"routed", out)
        return False
    if ts is None and why == "close":
        warn(NO_TRACK, f"stub {label}: on the track it shares with stub "
             f"{plan.close[stub['name']]} its wire would come closer than the spacing to "
             f"that stub's; not routed", out)
        return False
    if ts is None:
        lays = dict.fromkeys(grid.v if run[0] else grid.h for run in runs)
        warn(NO_TRACK, f"stub {label}: no signal track within {SEARCH} of its centre line "
             f"keeps the " + " and the ".join(f"{lay.name} spacing {_num(lay.spacing)}"
                                              for lay in lays)
             + " to other nets; not routed", out)
        return False
    pieces = []                  # (layer, wire rect) of each piece
    for i, run in enumerate(runs):
        pieces.append((grid.v if run[0] else grid.h, _piece_rect(grid, runs, ts, i)))
    wires = [("stub", lay.name, rect) for lay, rect in pieces]
    for i in range(len(runs) - 1):               # a bend: the box both wires cover
        x, y = (ts[i], ts[i + 1]) if runs[i][0] else (ts[i + 1], ts[i])
        wires.append(("stub_cross", f"{grid.h.name}/{grid.v.name}",
                      _box(x, y, grid.v.width, grid.h.width)))
    joins = []                   # the leaf route overlapping the stub wire: its wires, and
    leaf_route = [r for r in db.net_wire_rows(net) if r["kind"] in ("wire", "extension")] + \
        [r for r in db.strap_rows() if r["net"] == net] if net else []     # its straps
    for r in leaf_route:         # (a route lengthens a strap: no extension piece)
        w = tuple(float(c) for c in r["rect"].split())
        for lay, rect in pieces:
            box = (max(w[0], rect[0]), max(w[1], rect[1]),
                   min(w[2], rect[2]), min(w[3], rect[3]))
            if box[0] < box[2] - TOL and box[1] < box[3] - TOL:
                joins.append(box)
                other = grid.h if lay is grid.v else grid.v
                if r["layer"] != lay.name and not any(     # on the other layer: a box for
                        kind == "stub_cross" and _same(b, box)       # the via, once
                        for kind, _, b in wires):
                    wires.append(("stub_cross", f"{lay.name}/{other.name}", box))
    shields, cut, no_power, short, fenced = [], 0.0, [], [], 0.0
    if shield:                   # one each side, its track's net (as route_net -shield)
        rect_of = lambda r: tuple(float(c) for c in r["rect"].split())
        leaf = db.net_wire_rows(net) if net else []
        own = [("own", r["layer"], rect_of(r)) for r in leaf      # the leaf's signal wires
               if r["kind"] in ("wire", "extension")] + \
            [("own", layer, r) for layer, r in db.stretch_pieces(net, ("extension",))]
        powered = [(r["shield_net"], r["layer"], rect_of(r)) for r in leaf   # its shields
                   if r["kind"] in ("shield", "shield_ext")]
        found, cut, no_power, short, fenced = _shields(
            [("wire", lay.name, rect) for lay, rect in pieces] + own,
            _ia_shapes(db, net) + powered, grid, shield,
            min_length=root_attrs.get(db, "ignore_shield_less_than_routing_length"))
        shields = [("stub_shield", layer, r, power) for _, layer, r, power in found]
        wires += shields
    db.set_net_wires(net or stub["name"],
                     [(w[0], w[1], " ".join(_num(round(c, 6)) for c in w[2])) + tuple(w[3:])
                      for w in wires], stub=True)
    lines = []                   # a piece: its layer and track, and its centre line's ends
    for i, ((vertical, centre, a, b), t) in enumerate(zip(runs, ts)):
        lay = grid.v if vertical else grid.h
        a, b = (ts[i - 1] if i else a), (ts[i + 1] if i < len(runs) - 1 else b)
        lo, hi = min(a, b), max(a, b)
        moved = abs(t - centre)
        lines.append(f"{lay.name} {'x' if vertical else 'y'} {_num(t)}"
                     f"{f' ({_num(round(moved, 6))} from its centre line)' if moved > TOL else ''}"
                     f", {_num(lo)} .. {_num(hi)} (length {_num(round(hi - lo, 6))})")
    met = f"; meets its leaf route ({len(joins)} overlap(s))" if joins else ""
    if len(runs) == 1:
        info(f"  stub {label} ({net or 'no net'}): {lines[0]}{met}", out)
    else:
        total = sum(abs((ts[i + 1] if i < len(runs) - 1 else b) - (ts[i - 1] if i else a))
                    for i, (_, _, a, b) in enumerate(runs))
        pts = stub_points(stub["points"])
        more = total - sum(abs(q[0] - p[0]) + abs(q[1] - p[1]) for p, q in zip(pts, pts[1:]))
        change = ""              # pieces off their centre lines: the ones they meet end elsewhere
        if abs(more) > TOL:
            change = (f", {_num(round(abs(more), 6))} {'more' if more > 0 else 'less'} than "
                      f"the stub's {_num(round(total - more, 6))}")
        info(f"  stub {label} ({net or 'no net'}): {len(runs)} pieces round "
             f"{len(runs) - 1} bend(s) (length {_num(round(total, 6))}{change}){met}", out)
        for line in lines:
            info(f"    {line}", out)
    for note in notes:
        info(f"    {note}", out)
    for power in dict.fromkeys(w[3] for w in shields):
        mine = [w for w in shields if w[3] == power]
        info(f"    shield {power}: {len(mine)} wire(s), "
             f"{_num(round(sum(_along(w[2]) for w in mine), 3))} um", out)
    _report_short(short, db, out)
    if cut:
        info(f"    shields cut over {_num(round(cut, 3))} um where they would come closer "
             f"than the rule spacing to another shape", out)
    _report_fenced(fenced, out)
    if no_power:
        warn(NO_POWER, f"stub {label}: no shield where the next track is not a power "
             f"track: {'; '.join(no_power)}", out)
    if net and not joins:
        routed = any(not r["kind"].startswith("stub") for r in db.net_wire_rows(net))
        warn(NOT_JOINED, f"stub {label}: the route of {net} does not reach the stub wire "
             + (f"(it ended on another track: route_net -net {net} again, it then ends on "
                f"the stub wire, and route_final_stub -stub {stub['name']} again)" if routed
                else f"(route_net -net {net} first, or it ended on another track)"), out)
    return True


def _same(a, b):
    return all(abs(p - q) < TOL for p, q in zip(a, b))
