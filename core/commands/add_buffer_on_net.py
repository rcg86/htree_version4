"""add_buffer_on_net -net <nets> -ref_cell <lib_cell> -distance <um>
[-first_distance <um>] [-last_distance <um>] [-name <suffix>]: put buffers
on nets, at even distances along their centre lines.

    add_buffer_on_net -net sp_L1_inv1_Y -ref_cell INV_RP -first_distance 30 -distance 100

A net is followed from its driver along the centre lines create_spine
planned for it. They branch where the net has loads in more than one
direction, so the distances are measured down every branch:

    first, first + distance, first + 2 x distance, ...   um from the driver
                                    (first is -first_distance, else -distance)

A buffer goes on each of these points that lies before the last load of its
branch. With -last_distance, each load also gets a last buffer: on the net,
at the first point back from the load where the output pin of the buffer is
that far, in x plus y, from the input pin of the load. No buffer of the row
above comes after the last of them.

Each buffer is an instance of -ref_cell centred on its point, a member of
the spine (it moves with it), and drives a new spine net with the part of
the centre lines behind it: the next buffers and the loads up to them. The
buffers are then put on placement sites by legalize_placement.

The nets of the leaves (their load is a stub) are left as they are.

A net of no spine (net:<name>: of a port, or one connect_pin made) has no
centre lines, so it gets a trunk with branches from its driver, an input port
or an output pin, to its input pins (tree). The pins of spine cells are pins
as any other. Its buffers are instances of no spine, connected as connect_pin
connects.
"""

import fnmatch
import heapq
import math

from core import netlist, objects
from core.commands.write_def import cell_pin
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import placed_bbox, placed_points, placer, rect_in_polygon
from core.spine_snake import Snake, SnakeError

NAME = "add_buffer_on_net"
SUMMARY = "Put buffers on nets at even distances along their centre lines"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-net": "value", "-ref_cell": "value", "-distance": "value",
           "-first_distance": "value", "-last_distance": "value", "-name": "value",
           "-spec": "value"}

USAGE = 1
NO_NET = 256
BAD_CELL = 257
ROUTED = 258
SKIPPED = 259
BAD_ROUTE = 260
OVERLAP = 261
OUTSIDE = 262
TOO_MANY = 263
NOT_LEGAL = 264
LIMIT = 500                  # buffers on one net: more is taken for a wrong -distance
LEVEL = "buffer"             # the level of a buffer among the members of its spine
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    missing = [o for o in ("-net", "-ref_cell", "-distance") if o not in opts]
    if missing:
        raise HtreeError(USAGE, f"add_buffer_on_net: {' and '.join(missing)} required. Usage: "
                         f"add_buffer_on_net -net <nets> -ref_cell <lib_cell> -distance <um> "
                         f"[-first_distance <um>] [-last_distance <um>] [-name <suffix>]")
    step = _um(opts, "-distance")
    first = _um(opts, "-first_distance") if "-first_distance" in opts else step
    last = _um(opts, "-last_distance") if "-last_distance" in opts else None
    suffix = opts.get("-name", "buf")
    if not suffix or "/" in suffix or any(c.isspace() for c in suffix):
        raise HtreeError(USAGE, f"add_buffer_on_net: -name '{suffix}' must not be empty or "
                         f"contain '/' or spaces")
    db = session.db
    out = session.out
    objects.require_library(db)
    ref = opts["-ref_cell"].removeprefix("lib_cell:")
    cell = db.lib_cell_row(ref)
    if cell is None:
        raise HtreeError(BAD_CELL, f"add_buffer_on_net: lib cell '{ref}' is not in the library "
                         f"(read_lef); cells: {' '.join(db.lib_cell_names())}")
    pin_in, pin_out = cell_pin(db, ref, "in"), cell_pin(db, ref, "out")
    if cell["size_x"] is None or not pin_in or not pin_out:
        raise HtreeError(BAD_CELL, f"add_buffer_on_net: lib cell {ref} needs a SIZE, a signal "
                         f"input pin and a signal output pin in its LEF")
    nets, plain, leaves = _nets(session, opts["-net"])
    if leaves:
        warn(SKIPPED, f"add_buffer_on_net: {len(leaves)} net(s) of a leaf left as they are "
             f"(their load is a stub: this command does not buffer the stub nets): "
             f"{' '.join(leaves)}", out)
    plain = [n for n in (_plain(db, name, out) for name in plain) if n is not None]
    routed = [row["name"] for _, row in nets if netlist.routed(db, row["name"])]
    if routed:
        raise HtreeError(ROUTED, f"add_buffer_on_net: routed spine net(s) {' '.join(routed)}: "
                         f"buffers on the routes of a spine's nets are not made yet (only on "
                         f"routed nets of no spine). Remove the routing first: delete_route "
                         f"-nets {{{' '.join(routed)}}}")
    on_route = [n for n in plain if netlist.routed(db, n.row["name"])]
    plain = [n for n in plain if n not in on_route]
    if on_route and last is not None:
        raise HtreeError(USAGE, f"add_buffer_on_net: -last_distance is not taken on routed "
                         f"nets yet ({' '.join(n.row['name'] for n in on_route)})")
    routed_made = []
    for net in on_route:                 # along the wires, cut and routed again
        routed_made += _on_route(session, net, cell, ref, pin_in, pin_out, first, step,
                                 opts.get("-name", f"{net.prefix}_buf"), opts.get("-spec"))
    if on_route and not nets and not plain:
        return tuple(f"inst:{n}" for n in routed_made)

    # everything is planned before anything is stored
    grid = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    snap = (lambda v: round(round(v / grid) * grid, 6)) if grid else (lambda v: round(v, 6))
    w, h = cell["size_x"], cell["size_y"]
    taken = set(db.inst_names())
    net_names = set(netlist.spine_nets(db)) | set(netlist.roots(db).values())
    net_names |= {r["net"] for r in db.connection_rows() if r["net"]}
    snakes, plans, none = {}, [], []
    insts, members, new_nets, cut, moved, links, made = [], [], [], [], [], [], []
    for spine, row in nets:
        if spine["name"] not in snakes:
            try:
                snakes[spine["name"]] = Snake(db, spine["name"], limits=False)
            except SnakeError as exc:
                raise HtreeError(BAD_ROUTE, f"add_buffer_on_net: {exc}")
        snake = snakes[spine["name"]]
        orient = db.inst_row(row["driver"])["orient"] or "N"
        top, bufs = _plan(db, snake, row, first, step, last,
                          _pin_offset(db, cell, pin_out, orient))
        if not bufs:
            none.append(f"{row['name']} ({_num(round(_far(top), 3))} um to its farthest load)")
            continue
        if len(bufs) > LIMIT:
            raise HtreeError(TOO_MANY, f"add_buffer_on_net: {len(bufs)} buffers on net "
                             f"{row['name']}, more than {LIMIT}: check -distance "
                             f"({_num(step)} um)")
        _name(db, bufs, row["driver"], suffix, pin_out, taken, net_names)
        top.name, top.net = row["driver"], row["name"]
        for b in bufs:
            cx, cy = snake.place(*b.at)
            x, y = snap(cx - w / 2), snap(cy - h / 2)
            insts.append((b.name, ref, x, y, orient))
            members.append((spine["id"], b.name, LEVEL, ref, b.parent.name) + b.at)
            new_nets.append((spine["id"], b.net, b.name, _loads(b), row["grp"],
                             _length(b)) + (0.0,) + _routes(snake, b))
            moved += [(key[1], b.net, f"{b.name}/{pin_out}")
                      for key, _ in b.loads if isinstance(key, tuple)]
        cut.append((row["id"], _loads(top), _length(top)) + _routes(snake, top))
        plans.append((row, top, bufs))
    for net in plain:                    # of no spine: instances and connections
        row = net.row
        top, bufs = _plan_net(db, net, first, step, last,
                              _pin_offset(db, cell, pin_out, net.orient))
        if not bufs:
            none.append(f"{row['name']} ({_num(round(_far(top), 3))} um to its farthest load)")
            continue
        if len(bufs) > LIMIT:
            raise HtreeError(TOO_MANY, f"add_buffer_on_net: {len(bufs)} buffers on net "
                             f"{row['name']}, more than {LIMIT}: check -distance "
                             f"({_num(step)} um)")
        _name(db, bufs, net.prefix, suffix, pin_out, taken, net_names)
        top.name, top.net, top.key = row["driver"], row["name"], net.driver.key
        for b in bufs:
            b.key = f"{b.name}/{pin_out}"
            insts.append((b.name, ref, snap(b.at[0] - w / 2), snap(b.at[1] - h / 2), net.orient))
            links.append((b.name, pin_in, b.parent.net, b.parent.key))
            links += [(net.loads[key].inst, net.loads[key].pin, b.net, b.key)
                      for key, _ in b.loads]
            made.append(b.net)
        plans.append((row, top, bufs))
    if none:
        warn(SKIPPED, f"add_buffer_on_net: no buffer on {' ; '.join(none)}: the first would be "
             f"{_num(first)} um from the driver"
             + (f", the last {_num(last)} um from the pin of a load" if last else ""), out)
    if not plans:
        return tuple(f"inst:{n}" for n in routed_made)

    info(f"add_buffer_on_net: {ref} every {_num(step)} um, the first {_num(first)} um from "
         f"the driver" + (f", the last {_num(last)} um from the pin of each load (x + y, "
                          f"from the output pin of the buffer)" if last else ""), out)
    db.add_net_buffers(insts, members, new_nets, cut, moved, links)
    names = [i[0] for i in insts]
    legal = db.has_site_rows()
    if legal:
        from core.commands import legalize_placement
        try:
            legalize_placement.run(session, ["-inst", " ".join(names)])
        except HtreeError as exc:
            legal = False
            warn(NOT_LEGAL, f"add_buffer_on_net: the buffers are made, but not put on sites: "
                 f"{exc}", out)
    else:
        warn(NOT_LEGAL, "add_buffer_on_net: no placement rows (read_def a DEF with ROW "
             "statements), so the buffers are on the manufacturing grid, not on sites: run "
             "legalize_placement on them once the rows are read", out)
    for row, top, bufs in plans:
        _report(db, row, top, bufs, last, pin_out, out)
    _check_place(db, names, out)
    done = [row["name"] for row, _, _ in plans if "id" in row.keys()] + [n[1] for n in new_nets]
    rest = [n.row["name"] for n in plain if any(row is n.row for row, _, _ in plans)] + made
    info(f"Added {len(insts)} buffer(s) on {len(plans)} net(s), now {len(done) + len(rest)} "
         f"nets. Next: " + ("" if legal else "legalize_placement, ") + "route_pin for the buffers"
         + f", then route_net -net {{{' '.join(done + rest)}}} -rule <rule>", out)
    return tuple(f"inst:{n}" for n in routed_made + names)


def _on_route(session, net, cell, ref, pin_in, pin_out, first, step, prefix, spec):
    """Buffers on a routed net of no spine (core/buffer_route.py): placed
    under the route every step um along it, the wires cut there and the
    pieces put on the buffers' nets, then route_pin on the buffers and
    route_net on the nets, every piece held as it is. Returns the names of
    the buffers."""
    from core import auto_via, buffer_route as br
    from core.commands import legalize_placement, route_net, route_pin
    db, out = session.db, session.out
    name = net.row["name"]
    rule = db.net_route_rule(name)
    if rule is None:
        raise HtreeError(ROUTED, f"add_buffer_on_net: net {name} has wires but no route rule "
                         f"(route_net sets it): route it with route_net first")
    grid = route_net.Grid(db, route_net._rule_layers(db, rule))
    lines, adj, bufs, top_loads = br.plan(db, name, net, cell, pin_in, pin_out, grid, first,
                                          step, out)
    if not bufs:
        warn(SKIPPED, f"add_buffer_on_net: no buffer on {name}: no point {_num(first)} + k x "
             f"{_num(step)} um along its route lies before its last load", out)
        return []
    if len(bufs) > LIMIT:
        raise HtreeError(TOO_MANY, f"add_buffer_on_net: {len(bufs)} buffers on net {name}, "
                         f"more than {LIMIT}: check -distance ({_num(step)} um)")
    grid_um = db.tech_row()["manufacturing_grid"] if db.has_tech() else None
    snap = (lambda v: round(round(v / grid_um) * grid_um, 6)) if grid_um else \
        (lambda v: round(v, 6))
    w, h = cell["size_x"], cell["size_y"]
    # under the route, clear of the other cells and their pin routes by the rule spacing
    gap_um = max(grid.h.spacing, grid.v.spacing)
    taken = [box for box in (br.footprint(db, r) for r in db.inst_rows()) if box]
    ml, mb, mr, mt = br.margins(db, ref)
    box_at = lambda x, y: (x - w / 2 - ml - gap_um, y - h / 2 - mb - gap_um,
                           x + w / 2 + mr + gap_um, y + h / 2 + mt + gap_um)
    strap_layer = next((s["layer"] for r in db.inst_rows() if r["ref_cell"] == ref
                        for s in db.strap_rows(r["name"])), grid.h.name)
    wires = [(r, br._rect(r)) for r in db.net_wire_rows() if r["layer"] == strap_layer]
    slid, stuck = [], []
    for b in list(bufs):                 # in order from the driver
        line = b.line                    # the wires on the straps' layer but its own
        others = [box for r, box in wires if not (
            r["net"] == name and r["layer"] == line.row["layer"] and abs(
                ((box[1] + box[3]) if line.horizontal else (box[0] + box[2])) / 2 - line.c) < TOL)]
        if not br.free_spot(b, box_at, taken + others, step):
            stuck.append(f"{_num(round(b.dist, 3))} um ({{{_num(round(b.point[0], 3))} "
                         f"{_num(round(b.point[1], 3))}}})")
            br.drop(b, bufs, lines, top_loads)
            continue
        if b.slid:
            slid.append(b)
        x1, y1, x2, y2 = box_at(*b.point)     # its own footprint, without the spacing
        taken.append((x1 + gap_um, y1 + gap_um, x2 - gap_um, y2 - gap_um))
    if stuck:
        warn(OVERLAP, f"add_buffer_on_net: {name}: {len(stuck)} buffer(s) not made: no place "
             f"within {_num(step / 2)} um along that branch of the route clear of the cells "
             f"under it and their pin routes, at {', '.join(stuck)} from the driver; their "
             f"loads stay on the net before them", out)
    if not bufs:
        return []
    names_in_use = set(db.inst_names())
    net_names = set(netlist.spine_nets(db)) | set(netlist.roots(db).values())
    net_names |= {r["net"] for r in db.connection_rows() if r["net"]}
    n = 0
    for b in bufs:                       # numbered from the driver
        n += 1
        while _used(db, f"{prefix}_{n}", pin_out, names_in_use, net_names):
            n += 1
        b.name, b.net = f"{prefix}_{n}", f"{prefix}_{n}_{pin_out}"
    if slid:
        info(f"  {name}: buffers moved along the route, off the cells under it (um, + is "
             f"away from the driver): "
             + ", ".join(f"{b.name} {_num(round(b.slid, 3))}" for b in slid), out)
    up_net = lambda b: name if b.up is None else b.up.net
    up_key = lambda b: net.driver.key if b.up is None else f"{b.up.name}/{pin_out}"
    insts, links = [], []
    for b in bufs:
        orient = br.orient_for(db, cell, pin_in, pin_out, b.upstream, _pin_offset)
        insts.append((b.name, ref, snap(b.point[0] - w / 2), snap(b.point[1] - h / 2), orient))
        links.append((b.name, pin_in, up_net(b), up_key(b)))
        links += [(net.loads[key].inst, net.loads[key].pin, b.net, f"{b.name}/{pin_out}")
                  for key in b.loads]
    shielded = any(r["kind"] == "shield" for r in db.net_wire_rows(name))
    db.add_net_buffers(insts, [], [], [], [], links)
    names = [b.name for b in bufs]
    if db.has_site_rows():
        legalize_placement.run(session, ["-inst", " ".join(names)])
    route_pin.run(session, ["-inst", " ".join(names)] + (["-spec", spec] if spec else []))

    # cut the wires: each buffer's gap on every wire of its line
    gaps = {id(line): [] for line in lines}
    for b in bufs:
        g = br.gap(db, b, grid)
        for line in lines:
            if line.horizontal == b.line.horizontal and abs(line.c - b.line.c) < TOL and \
                    line.row["layer"] == b.line.row["layer"]:
                gaps[id(line)].append(g)
        turns = br.junctions_in(adj, b.line, *g)
        if turns:
            warn(OVERLAP, f"add_buffer_on_net: {b.name} is cut out of {name} where its route "
                 f"turns or branches ({' '.join(f'{{{_num(x)} {_num(y)}}}' for x, y in turns)}): "
                 f"route_net joins the pieces again", out)
    old = [line.row for line in lines]
    was_fixed = {r["id"] for r in old if r["status"] == "fixed"}
    new_rows = []                        # (net, rect text, keep fixed)
    for line in lines:
        for p1, p2, lab in br.pieces(line, gaps[id(line)]):
            new_rows.append((name if lab is None else lab.net, line.row["layer"],
                             br.text(br.piece_rect(line, p1, p2)), line.row["id"] in was_fixed))
    db.delete_wires([("net_wire", r["id"]) for r in old])
    auto_via.drop(db, [f"net_wire:{name}/{r['seq']}" for r in old])
    made = db.add_net_wires([(n_, "wire", layer, rect, None, None)
                             for n_, layer, rect, _ in new_rows])
    ids = [db.net_wire_row(n_, seq)["id"] for n_, seq in made]
    for k in ids:                        # held as they are while route_net joins them
        db.set_wire_fixed(k, True)
    nets = [name] + [b.net for b in bufs]
    info(f"add_buffer_on_net: {name}: {len(bufs)} buffer(s) along its route, its {len(old)} "
         f"wire(s) cut into {len(made)} piece(s) on {len(nets)} net(s); route_net joins them "
         f"to the pins", out)
    try:
        route_net.run(session, ["-net", " ".join(nets), "-rule", rule]
                      + (["-shield"] if shielded else []))
    finally:
        for k, (_, _, _, keep) in zip(ids, new_rows):
            if not keep:
                db.set_wire_fixed(k, False)
    _report_route(db, name, bufs, top_loads, pin_out, out)
    _check_place(db, names, out)
    return names


def _report_route(db, name, bufs, top_loads, pin_out, out):
    width = max(len(b.name) for b in bufs)
    info(f"  {name}: {len(bufs)} buffer(s) along its route", out)
    info(f"    {'Buffer':<{width}}  {'From driver':>11}  Centre               Input net -> "
         f"output net", out)
    for b in bufs:
        box = objects.inst_bbox(db, db.inst_row(b.name))
        centre = f"{{{_num(round((box[0] + box[2]) / 2, 3))} {_num(round((box[1] + box[3]) / 2, 3))}}}"
        info(f"    {b.name:<{width}}  {_num(round(b.dist, 3)):>11}  {centre:<19}  "
             f"{name if b.up is None else b.up.net} -> {b.net}", out)
    for key in top_loads:
        info(f"    load {key}: on {name}, before the first buffer", out)
    for b in bufs:
        for key in b.loads:
            info(f"    load {key}: on {b.net}, behind {b.name}", out)


def _um(opts, name):
    try:
        value = float(opts[name])
    except ValueError:
        value = None
    if value is None or not math.isfinite(value) or value <= 0:
        raise HtreeError(USAGE, f"add_buffer_on_net: {name} must be a distance in um above 0, "
                         f"got '{opts[name]}'")
    return value


def _nets(session, text):
    """([(spine row, spine_net row)], [names of nets of no spine], [names of
    leaf nets left out]) from names, glob patterns or spine_net: and net:
    handles."""
    db = session.db
    every, leaf = [], set()
    for s in db.spine_names():
        spine = db.spine_row(s)
        stubs = {r["name"] for r in db.spine_stub_rows(spine["id"])}
        for r in db.spine_net_rows(spine["id"]):
            every.append((spine, r))
            if stubs & set(r["loads"].split()):
                leaf.add(r["id"])
    spine_names = {r["name"] for _, r in every}
    others = [n for n in netlist.by_net(db) if n not in spine_names]    # with a pin on them
    found, plain = [], []
    for word in session.split_list(text):
        hits, more = [], []
        if word.startswith("spine_net:"):
            spine, _, name = word.partition(":")[2].partition("/")
            hits = [(s, r) for s, r in every if s["name"] == spine and r["name"] == name]
        elif word.startswith("net:"):
            more = [n for n in others if n == word[4:]]
        else:
            hits = [(s, r) for s, r in every if fnmatch.fnmatchcase(r["name"], word)]
            more = [n for n in others if fnmatch.fnmatchcase(n, word)]
        name = word.removeprefix("net:")
        if not hits and not more and name not in spine_names and db.has_design() and \
                db.port_of_net(name) is not None:
            more = [name]                # the net of a port, nothing on it yet
        if not hits and not more:
            raise HtreeError(NO_NET, f"add_buffer_on_net: no net '{word}' (the nets of a "
                             f"built spine: get_db spine:<name> .spine_nets; the net of a "
                             f"pin: get_db pin:<inst>/<pin> .net)")
        found += [h for h in hits if h not in found]
        plain += [n for n in more if n not in plain]
    return ([(s, r) for s, r in found if r["id"] not in leaf], plain,
            [r["name"] for _, r in found if r["id"] in leaf])


def _name(db, bufs, prefix, suffix, pin_out, taken, nets):
    """Name the buffers of a net <prefix>_<suffix><n>, with the first numbers
    that are free, and their nets."""
    n = 0
    for b in bufs:
        n += 1
        while _used(db, f"{prefix}_{suffix}{n}", pin_out, taken, nets):
            n += 1
        b.name = f"{prefix}_{suffix}{n}"
        b.net = f"{b.name}_{pin_out}"
        taken.add(b.name)
        nets.add(b.net)


def _used(db, name, pin_out, insts, nets):
    """The buffer name, or the name of its net, is in use."""
    net = f"{name}_{pin_out}"
    return name in insts or net in nets or \
        (db.has_design() and db.port_of_net(net) is not None)


# -- the net as a tree: on the straight spine, (um along it, um across it) -----------

class Piece:
    """The part of a net behind one driver: the driver of the net, or a
    buffer at the point `at`, `dist` um from the driver along the net."""

    def __init__(self, at=None, dist=0.0, parent=None):
        self.at, self.dist, self.parent = at, dist, parent
        self.depth = 0 if parent is None else parent.depth + 1    # buffers before it
        self.segs = []               # ((along, across), (along, across)) centre lines
        self.loads = []              # (name, um from the driver of the net)
        self.pieces = []             # the buffers this one drives


def split(segs, root, loads, first, step, last=None, pins=None, lines=None):
    """Cut a net at its buffer points. segs: its centre lines ((along,
    across), (along, across)), each along or across the spine; root: the
    point of its driver; loads: {name: point}. Points off the lines count
    from the nearest point on them. Returns (the piece of the driver, the
    buffers in order: down each branch in turn). ValueError when a load
    cannot be reached along the lines.

    last: the Manhattan distance from the last buffer before a load to the
    point of the load in pins (default: loads), measured where lines(u, v)
    puts the stretch of a centre line from u to v, as [(point, point)]
    (default: where it is). The piece of the driver gets .missed, [(load,
    'near' | 'far')]: the loads without such a buffer, as the driver is
    nearer than last or the net does not come that near the point."""
    segs = [s for s in segs if _len(*s) > TOL]
    if any(abs(a[0] - b[0]) > TOL and abs(a[1] - b[1]) > TOL for a, b in segs):
        raise ValueError("a centre line that runs neither along nor across the spine")
    if not segs:
        raise ValueError("no centre lines")
    on_lines = lambda p: _key(min((_nearest(s, p) for s in segs), key=lambda q: _len(p, q)))
    root = on_lines(root)
    at = {}                          # node: the loads there
    for name, p in loads.items():
        at.setdefault(on_lines(p), []).append(name)
    nodes = {root, *at} | {_key(p) for s in segs for p in s}
    for i, s in enumerate(segs):     # where two lines cross
        for t in segs[i + 1:]:
            for p in ((s[0][0], t[0][1]), (t[0][0], s[0][1])):
                if _on(s, p) and _on(t, p):
                    nodes.add(_key(p))
    edges = {}
    for s in segs:
        axis = 0 if abs(s[0][1] - s[1][1]) < TOL else 1
        on = sorted((n for n in nodes if _on(s, n)), key=lambda n: n[axis])
        for a, b in zip(on, on[1:]):
            edges.setdefault(a, set()).add(b)
            edges.setdefault(b, set()).add(a)

    dist, parent, heap = {root: 0.0}, {}, [(0.0, root)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u] + TOL:
            continue
        for v in edges.get(u, ()):
            if d + _len(u, v) < dist.get(v, math.inf) - TOL:
                dist[v], parent[v] = d + _len(u, v), u
                heapq.heappush(heap, (dist[v], v))
    lost = [str(name) for node, names in at.items() if node not in dist for name in names]
    if lost:
        raise ValueError(f"no centre line leads from the driver to {' '.join(lost)}")
    children = {}
    for v in sorted(parent):
        children.setdefault(parent[v], []).append(v)
    top, bufs = Piece(), []
    top.missed = []
    ends = {}                        # node: (the row ends before, the last buffer) of its loads
    for node, names in at.items():
        way = _way(node, parent, dist, lines or (lambda u, v: [(u, v)])) if last else []
        for name in names:
            cut = _reach(way, (pins or loads)[name], last) if last else None
            if cut is not None and cut > dist[node] - 10 * TOL:
                cut = None
            stop = dist[node] if cut is None else cut
            if last and not cut:
                top.missed.append((name, "far" if cut is None else "near"))
                if cut is not None:          # none within last um along the net either
                    stop = max(0.0, dist[node] - last)
            ends.setdefault(node, []).append((stop, cut or None))
    below = {}                       # node: the ends of the loads at and behind it

    def gather(u):
        below[u] = list(ends.get(u, ()))
        for v in children.get(u, ()):
            below[u] += gather(v)
        return below[u]

    gather(root)
    top.loads += [(name, 0.0) for name in at.get(root, ())]

    def walk(u, piece):
        for v in children.get(u, ()):
            cur, a = piece, u
            here = [(name, dist[v]) for name in at.get(v, ())]
            for c in _cuts(dist[u], dist[v], below[v], first, step):
                if c > dist[v] - TOL:        # on the node: its loads are before the buffer
                    p = v
                    cur.loads += here
                    here = []
                else:
                    t = (c - dist[u]) / (dist[v] - dist[u])
                    p = _key((u[0] + t * (v[0] - u[0]), u[1] + t * (v[1] - u[1])))
                cur.segs.append((a, p))
                buf = Piece(p, c, cur)
                cur.pieces.append(buf)
                bufs.append(buf)
                cur, a = buf, p
            if a != v:
                cur.segs.append((a, v))
            cur.loads += here
            walk(v, cur)

    walk(root, top)
    for piece in [top] + bufs:           # each line from its end nearer to the piece's driver
        start = piece.at or root
        piece.segs = [s if _len(start, s[0]) <= _len(start, s[1]) + TOL else s[::-1]
                      for s in _merge(piece.segs)]
    return top, bufs


def _cuts(lo, hi, below, first, step):
    """The buffer distances d, lo < d <= hi, on a stretch of a net. below:
    (the row of buffers ends before this distance, the distance of its last
    buffer or None) of each load at and behind the end of the stretch."""
    if not below:
        return []
    end = max(stop for stop, _ in below)     # the last buffer is before this, or on it
    found = []
    k = max(0, math.floor((lo - first) / step))
    while first + k * step <= min(hi, end - 2 * TOL) + TOL:
        if first + k * step > lo + TOL:
            found.append(first + k * step)
        k += 1
    found += [c for _, c in below if c is not None and lo + TOL < c <= hi + TOL]
    cuts = []
    for c in sorted(found):
        if not cuts or c > cuts[-1] + 10 * TOL:
            cuts.append(c)
    return cuts


def _way(node, parent, dist, lines):
    """The way back from a node to the driver: [(a, b, um from the driver
    along the net at a, at b)], the straight lines lines() gives, a first."""
    way = []
    v = node
    while v in parent:
        u = parent[v]
        parts = [(b, a) for a, b in reversed(lines(u, v))]
        total = sum(_len(a, b) for a, b in parts) or 1.0
        run = 0.0
        for a, b in parts:
            d = dist[v] - (dist[v] - dist[u]) * run / total
            run += _len(a, b)
            way.append((a, b, d, dist[v] - (dist[v] - dist[u]) * run / total))
        v = u
    return way


def _reach(way, target, last):
    """Going back from a load along way (_way): the um from the driver of
    the first point that is last um from target, in x plus y. None when the
    way starts that far from it or farther, 0.0 when all of it is nearer."""
    if not way:
        return 0.0
    if _len(way[0][0], target) > last - TOL:
        return None
    for a, b, da, db in way:
        at = lambda t: (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        ts = {0.0, 1.0}              # the distance is linear between these
        for k in (0, 1):
            if abs(b[k] - a[k]) > TOL and 0 < (target[k] - a[k]) / (b[k] - a[k]) < 1:
                ts.add((target[k] - a[k]) / (b[k] - a[k]))
        ts = sorted(ts)
        for t1, t2 in zip(ts, ts[1:]):
            g1, g2 = _len(at(t1), target), _len(at(t2), target)
            if g2 >= last - TOL:
                t = t2 if g2 - g1 < TOL else t1 + (t2 - t1) * (last - g1) / (g2 - g1)
                return da + min(max(t, t1), t2) * (db - da)
    return 0.0


def _merge(segs):
    """Centre lines that continue each other, as one."""
    runs = {}
    for a, b in segs:
        axis = 0 if abs(a[1] - b[1]) < TOL else 1          # the coordinate that runs
        runs.setdefault((axis, a[1 - axis]), []).append(sorted((a[axis], b[axis])))
    found = []
    for (axis, fixed), spans in runs.items():
        spans.sort()
        joined = [spans[0]]
        for lo, hi in spans[1:]:
            if lo <= joined[-1][1] + TOL:
                joined[-1][1] = max(joined[-1][1], hi)
            else:
                joined.append([lo, hi])
        found += [((lo, fixed), (hi, fixed)) if axis == 0 else ((fixed, lo), (fixed, hi))
                  for lo, hi in joined]
    return found


def _key(p):
    return round(p[0], 6), round(p[1], 6)


def _len(a, b):
    return abs(b[0] - a[0]) + abs(b[1] - a[1])


def _on(seg, p):
    """p is on the line seg (which runs along one axis)."""
    (x1, y1), (x2, y2) = seg
    return min(x1, x2) - TOL <= p[0] <= max(x1, x2) + TOL and \
        min(y1, y2) - TOL <= p[1] <= max(y1, y2) + TOL


def _nearest(seg, p):
    """The point of the line seg nearest to p."""
    (x1, y1), (x2, y2) = seg
    return (min(max(p[0], min(x1, x2)), max(x1, x2)), min(max(p[1], min(y1, y2)), max(y1, y2)))


# -- a net of the database ---------------------------------------------------------------

def _plan(db, snake, row, first, step, last, out_pin):
    """split() for a spine_net row. The loads are its instances, and the
    connect_pin rows on it as ('connection', id, '<inst>/<pin>'). The last
    distance is measured in the layout, from the output pin of a buffer
    (out_pin: where it is from the centre of the buffer) to the input pin of
    the load. The piece of the driver gets .pins: {load: its pin (x, y)}."""
    segs = [(tuple(v[:2]), tuple(v[2:])) for v in
            ([float(c) for c in seg.split()] for seg in (row["ref_route"] or "").split(";")
             if seg)]
    if not segs:
        raise HtreeError(BAD_ROUTE, f"add_buffer_on_net: net {row['name']} has no centre lines "
                         f"on the straight spine; build its spine again (create_spine -build)")
    cells = {inst: (along, across) for inst, along, across in snake.members}

    def spot(inst):
        if inst in cells:
            return cells[inst]
        r = db.inst_row(inst)
        box = objects.inst_bbox(db, r) if r is not None else None
        if box is None:
            raise HtreeError(BAD_ROUTE, f"add_buffer_on_net: net {row['name']}: '{inst}' is "
                             f"no placed instance")
        return _on_spine(snake, segs, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))

    try:
        loads, pins = {}, {}
        for inst in row["loads"].split():
            loads[inst] = spot(inst)
            pins[inst] = _pin_centre(db, inst, netlist.signal_pin(db, inst, "in"))
        for r in db.connection_rows():
            if r["net"] == row["name"]:
                key = "connection", r["id"], f"{r['inst']}/{r['pin']}"
                loads[key] = spot(r["inst"])
                pins[key] = _pin_centre(db, r["inst"], r["pin"])
        top, bufs = split(segs, spot(row["driver"]), loads, first, step, last,
                          {k: (x - out_pin[0], y - out_pin[1]) for k, (x, y) in pins.items()},
                          lambda u, v: snake.seg_lines(u + v))
    except ValueError as exc:
        raise HtreeError(BAD_ROUTE, f"add_buffer_on_net: net {row['name']}: {exc}")
    top.pins = pins
    return top, bufs


_pin_centre = objects.pin_centre


# -- a net of no spine: of a port, or one connect_pin made -------------------------------

class Plain:
    """A net of no spine. driver: its End; loads: {'<inst>/<pin>': End} of
    its input pins; root, pins: where they are; row: what _report reads of a
    spine_net row."""

    def __init__(self, db, name, driver, loads, root):
        self.driver, self.root = driver, root
        self.loads = {e.text: e for e in loads}
        self.pins = {e.text: _pin_centre(db, e.inst, e.pin) for e in loads}
        port = driver.kind == "port"
        self.prefix = driver.pin if port else driver.inst       # of the buffer names
        # a port has no orientation a cell can take: that of the first load
        self.orient = db.inst_row(loads[0].inst if port else driver.inst)["orient"] or "N"
        self.row = {"name": name, "driver": driver.text, "detour": 0,
                    "grp": "the net of a port" if port else "a net of no spine",
                    "length": round(sum(_len(a, b) for a, b in tree(root, self.pins.values())),
                                    6)}


def _plain(db, name, out):
    """The Plain of a net of no spine; None, with a warning, for a net
    without one driver that is somewhere, or without an input pin."""
    ends = netlist.ends(db, name)
    drivers = [e for e in ends if e.drives]
    loads = [e for e in ends if e.is_load]
    root = None
    if len(drivers) == 1:
        d = drivers[0]
        root = objects.port_centre(db, d.pin) if d.kind == "port" else \
            _pin_centre(db, d.inst, d.pin)
    if len(drivers) != 1:
        why = f"it has {len(drivers) or 'no'} driver{'s' if len(drivers) > 1 else ''} (an " \
              f"output pin of an instance or an input port of the design)"
    elif not loads:
        why = f"no input pin of an instance is on it (connect_pin -from {drivers[0].key} " \
              f"-to <pins>)"
    elif root is None:
        why = f"{drivers[0].text} has no shapes and no location (DEF PINS)"
    else:
        return Plain(db, name, drivers[0], loads, root)
    warn(SKIPPED, f"add_buffer_on_net: net {name} left as it is: {why}", out)
    return None


def tree(root, pins):
    """Centre lines [((x, y), (x, y))] for a net that has none, from the
    point of its driver to the points of its pins: a trunk along x or y,
    whichever they are spread over more, at the middle one of the pins across
    it (the lower of two), and a line straight across to it from the driver
    and from every pin beside it."""
    pins = list(pins)
    pts = [root] + pins
    spread = [max(p[k] for p in pts) - min(p[k] for p in pts) for k in (0, 1)]
    axis = 0 if spread[0] >= spread[1] else 1
    across = sorted(p[1 - axis] for p in pins)
    mid = across[(len(across) - 1) // 2]
    on = lambda p: (p[0], mid) if axis == 0 else (mid, p[1])
    segs = [(on(min(pts, key=lambda p: p[axis])), on(max(pts, key=lambda p: p[axis])))]
    return segs + [(p, on(p)) for p in dict.fromkeys(pts) if abs(p[1 - axis] - mid) > TOL]


def _plan_net(db, net, first, step, last, out_pin):
    """split() for a Plain, on tree(), in the layout. The piece of the driver
    gets .pins as _plan gives them."""
    try:
        top, bufs = split(tree(net.root, net.pins.values()), net.root, net.pins, first, step,
                          last, {k: (x - out_pin[0], y - out_pin[1])
                                 for k, (x, y) in net.pins.items()})
    except ValueError as exc:
        raise HtreeError(BAD_ROUTE, f"add_buffer_on_net: net {net.row['name']}: {exc}")
    top.pins = net.pins
    return top, bufs


def _pin_offset(db, cell, pin, orient):
    """Where the centre of a pin of a lib cell is from the centre of the
    cell, placed in orient."""
    place = placer(cell["size_x"], cell["size_y"], orient, 0.0, 0.0)
    pts = [v for p, _, _, text in db.lib_cell_shapes(cell["name"]) if p == pin
           for v in placed_points([float(c) for c in text.split()], place)]
    if not pts:
        return 0.0, 0.0
    box = placed_bbox(cell["size_x"], cell["size_y"], orient, 0.0, 0.0)
    return ((min(pts[0::2]) + max(pts[0::2])) / 2 - (box[0] + box[2]) / 2,
            (min(pts[1::2]) + max(pts[1::2])) / 2 - (box[1] + box[3]) / 2)


def _on_spine(snake, segs, p):
    """The point of the centre lines nearest to (x, y), on the straight spine."""
    best = None
    for (a1, c1), (a2, c2) in segs:
        lines = snake.seg_lines((a1, c1, a2, c2))
        total = sum(_len(a, b) for a, b in lines)
        run = 0.0
        for a, b in lines:
            q = _nearest((a, b), p)
            if best is None or _len(p, q) < best[0] - TOL:
                t = (run + _len(a, q)) / total
                best = (_len(p, q), (a1 + t * (a2 - a1), c1 + t * (c2 - c1)))
            run += _len(a, b)
    if best is None:
        raise ValueError("no centre lines")
    return best[1]


def _far(piece):
    """um from the driver to the farthest load behind a piece."""
    return max([d for _, d in piece.loads] + [_far(p) for p in piece.pieces] + [0.0])


def _loads(piece):
    """The loads text of the net of a piece: its instances, then its buffers."""
    return " ".join([n for n, _ in piece.loads if not isinstance(n, tuple)]
                    + [p.name for p in piece.pieces])


def _length(piece):
    return round(sum(_len(a, b) for a, b in piece.segs), 6)


def _routes(snake, piece):
    """(route, ref_route) of the net of a piece, as spine_net has them."""
    text = lambda values: " ".join(_num(round(v, 6)) for v in values)
    return (";".join(text(a + b) for s in piece.segs for a, b in snake.seg_lines(s[0] + s[1])),
            ";".join(text(a + b) for a, b in piece.segs))


def _report(db, row, top, bufs, last, pin_out, out):
    """The buffers of a net where they are now, and what each load is behind."""
    info(f"  {row['name']} ({row['grp']}, {_num(row['length'])} um, driver {row['driver']}): "
         f"{len(bufs)} buffer(s)", out)
    if row["detour"]:
        info(f"    its detour of {_num(row['detour'])} um is not drawn: not counted", out)
    width = max(len(b.name) for b in bufs)
    info(f"    {'Buffer':<{width}}  {'From driver':>11}  {'After':>9}  Centre", out)
    for b in bufs:
        box = objects.inst_bbox(db, db.inst_row(b.name))
        info(f"    {b.name:<{width}}  {_num(round(b.dist, 3)):>11}  "
             f"{_num(round(b.dist - b.parent.dist, 3)):>9}  "
             f"{{{_num(round((box[0] + box[2]) / 2, 3))} {_num(round((box[1] + box[3]) / 2, 3))}}}",
             out)
    odd = False
    for piece in [top] + bufs:
        for key, d in piece.loads:
            name = key if not isinstance(key, tuple) else f"{key[2]} (connect_pin)"
            odd = odd or piece.depth % 2 == 1
            gap = ""
            if last and piece is not top:        # as placed: from pin to pin
                gap = _len(_pin_centre(db, piece.name, pin_out), top.pins[key])
                gap = f", {_num(round(gap, 3))} um from its pin to the pin of the load"
            info(f"    load {name}: behind {piece.depth} buffer(s), "
                 f"{_num(round(d - piece.dist, 3))} um after {piece.name}{gap}", out)
    for key, why in top.missed:
        name = key if not isinstance(key, tuple) else f"{key[2]} (connect_pin)"
        info(f"    no buffer {_num(last)} um from the pin of {name}: "
             + ("the driver of the net is nearer" if why == "near" else
                "the net does not come that near the pin"), out)
    if odd:
        info("    an odd number of inverting cells before a load inverts its signal", out)


def _check_place(db, names, out, cmd=NAME):
    """Warn about buffers (instances, as placed) over another instance or
    outside the boundary."""
    boxes = {r["name"]: objects.inst_bbox(db, r) for r in db.inst_rows()}
    over, seen = [], set()
    for n in names:
        a = boxes[n]
        seen.add(n)
        over += [f"{n} and {other}" for other, b in boxes.items()
                 if b and other not in seen and a[0] < b[2] - TOL and b[0] < a[2] - TOL
                 and a[1] < b[3] - TOL and b[1] < a[3] - TOL]
    if over:
        warn(OVERLAP, f"{cmd}: {len(over)} overlap(s): {' ; '.join(over)}. "
             + ("No free site was near enough: move one of the two (move_obj)"
                if db.has_site_rows() else "legalize_placement moves cells onto free sites"),
             out)
    if db.has_design() and db.design_row()["boundary"]:
        boundary = [float(v) for v in db.design_row()["boundary"].split()]
        outside = [n for n in names if not rect_in_polygon(boxes[n], boundary)]
        if outside:
            warn(OUTSIDE, f"{cmd}: not inside the design boundary: "
                 f"{' '.join(outside)}", out)
