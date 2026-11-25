"""create_buffer_tree -from <input port> -inverter_ref <lib_cell> [-buffer_ref
<lib_cell>] -distance <um> [-name <prefix>]: drive the sinks of an input
port's net through a tree of inverters, keeping their polarity.

    create_buffer_tree -from [get_db ports clk] -inverter_ref INV_RP \
        -buffer_ref BUF_RP -distance 100 -name clk_tree

The sinks are the input pins on the port's net. -topology fishbone (the
default): a tree of the least total way, a trunk and a rib off it to each
sink (build_fishbone), so the fewest inverters. -topology shortest: a
shortest-path rectilinear tree from the port to them that shares its trunk as far as it
can and branches as late as it can (a rectilinear Steiner arborescence,
the merge heuristic of Rao et al.): every sink is reached the shortest way
(x + y), and two sinks share the way to the point both go through. When that
tree leaves the design boundary (an L- or comb-shaped die), the shortest
ways inside it instead, down the middle of the die's arms (build_tree_inside). Along it,
from the port, an inverter every -distance um (on a shared part, one for all
the sinks past it). Polarity: every sink must see an even number of
inversions. A sink whose way has an odd number gets its last cell changed
to a buffer (-buffer_ref) when that cell drives sinks only; when it drives
further cells too, or no -buffer_ref is given, one more inverter just
before the sink. The first cell is at the
port, so the port drives one cell; a sink nearer the port than -distance is
driven by it.

Even counts from the port to each end. The ends are those all_fanout
finds from the port before the tree is made; a sink's cell and the cells
after it may invert already (an odd count): the tree then gives that sink
an odd number, so the count from the port to the end is even. The
cells are what the user says they are: -inverter_ref an inverter,
-buffer_ref a buffer (kept, so all_fanout counts them the same). A sink
whose ends differ (one odd, one even) cannot have all of them even: a
warning, and the tree makes its own count even.

Each cell (<prefix>_<n>, a plain instance) is placed with its input pin on
the tree, oriented N, and put on a site (legalize_placement). Its input
goes on the net of the cell before it (the port's net for the first), its
output drives <prefix>_<n>_<output pin>. Only the netlist and placement
change (write_logical, get_db pin .net): route_pin and route_net next.
"""

import math

from core import netlist, objects
from core.commands.add_buffer_on_net import BAD_CELL, _check_place, _pin_offset
from core.commands.connect_pin import warn_routed
from core.commands.write_def import cell_pin
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import placed_bbox, rect_in_polygon

NAME = "create_buffer_tree"
SUMMARY = "Drive the sinks of an input port through a tree of inverters (polarity kept)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-inverter_ref": "value", "-buffer_ref": "value",
           "-distance": "value", "-name": "value", "-topology": "value"}
TOPOLOGIES = ("fishbone", "shortest")
USAGE = "create_buffer_tree -from <input port> -inverter_ref <lib_cell> [-buffer_ref " \
        "<lib_cell>] -distance <um> [-name <prefix>] [-topology fishbone|shortest]"

MIDDLE = 1.0                 # build_tree_inside: a way off the middle of the arms costs
                             # this much more per um, so the ways share one trunk there
NOT_INPUT = 302
NO_SINKS = 303
NOT_LEGAL = 304
TOL = 1e-6


class Node:
    """A point of the tree (model x, y): its children, and the sink there
    (an End) when it is one."""

    def __init__(self, x, y, sink=None):
        self.x, self.y, self.sink, self.kids = x, y, sink, []


def build_tree(root, sinks):
    """The rectilinear Steiner arborescence of sinks [(x, y, End)] from root
    (x, y): a Node tree whose every root-to-sink way is a shortest one (x +
    y), the ways merged as far from the root as they can be. Per quadrant
    round the root, the pair of points whose merge point (the corner of
    the box they share nearest to them, away from the root) is farthest
    from the root is merged first."""
    rx, ry = root
    top = Node(rx, ry)
    quads = {}
    for x, y, end in sinks:
        if abs(x - rx) < TOL and abs(y - ry) < TOL:
            top.kids.append(Node(x, y, end))
            continue
        quads.setdefault((x >= rx, y >= ry), []).append(Node(x, y, end))
    for (east, north), nodes in quads.items():
        sx, sy = (1 if east else -1), (1 if north else -1)
        # in the quadrant's own frame: coordinates >= 0 from the root
        pts = [(abs(n.x - rx), abs(n.y - ry), n) for n in nodes]
        while len(pts) > 1:
            best = None
            for a in range(len(pts)):
                for b in range(a + 1, len(pts)):
                    mx, my = min(pts[a][0], pts[b][0]), min(pts[a][1], pts[b][1])
                    if best is None or mx + my > best[0]:
                        best = (mx + my, a, b, mx, my)
            _, a, b, mx, my = best
            merged = Node(rx + sx * mx, ry + sy * my)
            for k in (a, b):
                p = pts[k]
                if abs(p[0] - mx) < TOL and abs(p[1] - my) < TOL and p[2].sink is None:
                    merged.kids += p[2].kids              # a branch point there: one node
                else:
                    merged.kids.append(p[2])
            pts = [p for k, p in enumerate(pts) if k not in (a, b)] + [(mx, my, merged)]
        top.kids.append(pts[0][2])
    return top


def _tree_inside(top, fence):
    """Does every way of the tree (the L of each node to its kid) lie inside
    the design boundary (route_net's Fence)."""
    def ok(node):
        for kid in node.kids:
            for (x1, y1), (x2, y2) in _segments(node, kid):
                if not fence.holds((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))):
                    return False
            if not ok(kid):
                return False
        return True
    return ok(top)


def build_tree_inside(root, sinks, boundary):
    """A tree like build_tree whose ways stay inside the design boundary (a
    rectilinear polygon): the shortest ways from the root to each sink on a
    grid of the lines through the root, the sinks and the middle of each
    band of the boundary (between two of its x, or two of its y), a grid
    line used only where it is inside. A way off the middle of the arms
    costs MIDDLE more per um, so the ways go to the middle of the arm and
    run down it, sharing that trunk (the shortest-path tree of those
    costs), not beside it along the die's edge. Returns (Node tree, [sink End
    that no way inside reaches])."""
    import heapq
    from core.commands.route_net import Fence
    fence = Fence(boundary)
    bx, by = sorted(set(boundary[0::2])), sorted(set(boundary[1::2]))
    mid_x = {(a + b) / 2 for a, b in zip(bx, bx[1:])}
    mid_y = {(a + b) / 2 for a, b in zip(by, by[1:])}
    xs = sorted({root[0]} | {x for x, _, _ in sinks} | mid_x)
    ys = sorted({root[1]} | {y for _, y, _ in sinks} | mid_y)

    def inside(a, b):
        return fence.holds((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
    # Dijkstra over the grid crossings that are inside, from the root
    start = (root[0], root[1])
    dist, parent, heap = {start: 0.0}, {}, [(0.0, start)]
    ix = {x: k for k, x in enumerate(xs)}
    iy = {y: k for k, y in enumerate(ys)}
    while heap:
        d, (x, y) = heapq.heappop(heap)
        if d > dist.get((x, y), math.inf) + TOL:
            continue
        i, j = ix[x], iy[y]
        for ni, nj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            nxt = (xs[ni], ys[nj])
            if not inside((x, y), nxt):
                continue
            # off the middle of the arms (along the root's or a sink's line, which
            # may run by the edge of the die) dearer: the ways go to the middle and
            # share the trunk there, not run beside it
            off = (nxt[1] not in mid_y) if ni != i else (nxt[0] not in mid_x)
            nd = d + (abs(nxt[0] - x) + abs(nxt[1] - y)) * (1 + MIDDLE * off)
            if nd < dist.get(nxt, math.inf) - TOL:
                dist[nxt], parent[nxt] = nd, (x, y)
                heapq.heappush(heap, (nd, nxt))
    top = Node(*start)
    nodes, lost = {start: top}, []

    def node(p):                         # the tree's node at p, with its way back to the root
        if p not in nodes:
            nodes[p] = Node(*p)
            node(parent[p]).kids.append(nodes[p])
        return nodes[p]
    for x, y, end in sinks:
        if (x, y) not in dist:
            lost.append(end)
            continue
        node((x, y)).kids.append(Node(x, y, end))
    return top, lost


def build_fishbone(root, sinks, boundary=None):
    """A tree of the least total length the grid allows (fewest inverters),
    a fishbone: the trunk the sinks share, a rib off it to each. Grown from
    the root: each time, the sink nearest the tree so far (by the shortest
    way inside the boundary, the tree itself free to reach) is joined to it
    by that way (the shortest-path heuristic for Steiner trees). The grid:
    the lines through the root, the sinks and, with a boundary, the middle
    of each of its bands; with a boundary a line is used only where it is
    inside. Of ways as long, the one down the middle of the die's arms,
    then the one nearest the sinks not joined yet (summed over its points),
    so the next can branch off it: the trunk.
    Returns (Node tree, [sink End no way inside reaches])."""
    import heapq
    fence = None
    mid_x = mid_y = set()
    if boundary:
        from core.commands.route_net import Fence
        fence = Fence(boundary)
        bx, by = sorted(set(boundary[0::2])), sorted(set(boundary[1::2]))
        mid_x = {(a + b) / 2 for a, b in zip(bx, bx[1:])}
        mid_y = {(a + b) / 2 for a, b in zip(by, by[1:])}
    xs = sorted({root[0]} | {x for x, _, _ in sinks} | mid_x)
    ys = sorted({root[1]} | {y for _, y, _ in sinks} | mid_y)
    ix = {x: k for k, x in enumerate(xs)}
    iy = {y: k for k, y in enumerate(ys)}
    open_edge = {}

    def step_ok(a, b):
        key = (a, b) if a <= b else (b, a)
        if key not in open_edge:
            open_edge[key] = fence is None or fence.holds(
                (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
        return open_edge[key]

    start = (root[0], root[1])
    top = Node(*start)
    nodes = {start: top}                 # grid point -> its Node in the tree
    todo = {(x, y) for x, y, _ in sinks}
    lost = set()
    while todo - lost:
        # Dijkstra from every point of the tree at once; a way's cost: (its length,
        # its length off the middle of the arms, how far its points are from the
        # sinks still to join)
        left = list(todo - set(nodes))
        near = lambda p: sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in left)  # noqa
        zero = (0.0, 0.0, 0.0)
        dist = {p: zero for p in nodes}
        parent, heap = {}, [(zero, p) for p in nodes]
        heapq.heapify(heap)
        hit = None
        while heap:
            d, (x, y) = heapq.heappop(heap)
            if d != dist.get((x, y)):
                continue
            if (x, y) in todo and (x, y) not in nodes and (x, y) not in lost:
                hit = (x, y)
                break
            i, j = ix[x], iy[y]
            for ni, nj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                    continue
                nxt = (xs[ni], ys[nj])
                if nxt in nodes or not step_ok((x, y), nxt):
                    continue
                off = (nxt[1] not in mid_y) if ni != i else (nxt[0] not in mid_x)
                length = abs(nxt[0] - x) + abs(nxt[1] - y)
                nd = (round(d[0] + length, 6), round(d[1] + length * off, 6), d[2] + near(nxt))
                if nxt not in dist or nd < dist[nxt]:
                    dist[nxt], parent[nxt] = nd, (x, y)
                    heapq.heappush(heap, (nd, nxt))
        if hit is None:                  # the rest: no way inside reaches them
            lost |= todo - set(nodes)
            break
        way = [hit]
        while way[-1] not in nodes:
            way.append(parent[way[-1]])
        for p, q in zip(way[-1:0:-1], way[-2::-1]):    # from the tree out to the sink
            nodes[q] = Node(*q)
            nodes[p].kids.append(nodes[q])
        todo.discard(hit)
    for x, y, end in sinks:
        if (x, y) in nodes:
            nodes[(x, y)].kids.append(Node(x, y, end))
    return top, [end for x, y, end in sinks if (x, y) not in nodes]


def tree_length(top):
    """The total way of a Node tree (x + y of each L)."""
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for node in _nodes(top)
               for kid in node.kids for a, b in _segments(node, kid))


def _nodes(node):
    yield node
    for kid in node.kids:
        yield from _nodes(kid)


def _segments(a, b):
    """The L way from node a to node b: along x first, then y."""
    corner = (b.x, a.y)
    return [((a.x, a.y), corner), (corner, (b.x, b.y))]


class Stage:
    """A cell of the tree: its point (where its input pin goes), parent
    Stage (None: the port), kind (inverter | buffer), the sinks it drives
    directly [End] and the stages it drives."""

    def __init__(self, point, parent):
        self.point, self.parent, self.kind = point, parent, "inverter"
        self.sinks, self.kids, self.name = [], [], None

    def depth(self):
        n, s = 0, self
        while s is not None:
            n += s.kind == "inverter"
            s = s.parent
        return n


def place_stages(top, step, root_cell=True):
    """The Stages along the tree: with root_cell the first at the root (the
    port drives that one cell only), then walking the tree, one every step
    um of way; a sink is driven by the last stage before it. Returns
    ([Stage], {sink End: Stage or None (the port)})."""
    stages, driver = [], {}
    first = None
    if root_cell:
        first = Stage((top.x, top.y), None)
        stages.append(first)

    def walk(node, since, last):
        if node.sink is not None:
            driver[node.sink] = last
            if last is not None:
                last.sinks.append(node.sink)
        for kid in node.kids:
            run, at = since, last
            for (x1, y1), (x2, y2) in _segments(node, kid):
                length = abs(x2 - x1) + abs(y2 - y1)
                done = 0.0
                while run + (length - done) >= step - TOL and length > TOL:
                    done += step - run
                    f = done / length
                    s = Stage((x1 + (x2 - x1) * f, y1 + (y2 - y1) * f), at)
                    if at is not None:
                        at.kids.append(s)
                    stages.append(s)
                    at, run = s, 0.0
                run += length - done
            walk(kid, run, at)

    walk(top, 0.0, first)
    return stages, driver


def fix_polarity(stages, driver, after=None, buffers=True):
    """Even inversions from the port to every end: a sink whose count to
    it, plus after[sink] (the inverters past the sink, 0 when not given),
    is odd gets its last cell made a buffer when that cell drives sinks only
    and all of them are odd, else one more inverter just before it (on the
    port's net for a sink the port drives). buffers False (no -buffer_ref):
    never a buffer, the inverter always. Returns the Stages added."""
    after = after or {}

    def odd(sink, last):
        return ((last.depth() if last is not None else 0) + after.get(sink, 0)) % 2

    for s in stages if buffers else ():
        if not s.kids and s.kind == "inverter" and s.sinks and \
                all(odd(sink, s) for sink in s.sinks):
            s.kind = "buffer"
    added = []
    for sink, last in list(driver.items()):
        if not odd(sink, last):
            continue
        s = Stage(None, last)            # just before the sink: placed at it
        s.sinks.append(sink)
        if last is not None:
            last.sinks.remove(sink)
            last.kids.append(s)
        driver[sink] = s
        added.append(s)
    return added


def inverters_after(db, port, sinks):
    """({sink End: 0 | 1}, {sink End: (fewest, most)}): the inverters from
    each sink (its cell included) to the ends all_fanout finds from the
    port; 0 | 1 the parity when every end agrees, else 0 (and the sink in
    the second dict with fewest and most differing in parity)."""
    from core.commands import all_fanout
    kinds = db.cell_kinds()
    seen = {}
    for path in all_fanout.paths(db, port):
        if len(path) > 1:
            seen.setdefault(path[1], []).append(all_fanout.count(db, path, kinds)[2])
    parity, counts = {}, {}
    for _, _, e in sinks:
        got = seen.get(e, [0])
        counts[e] = (min(got), max(got))
        parity[e] = got[0] % 2 if len({n % 2 for n in got}) == 1 else 0
    return parity, counts


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    missing = [o for o in ("-from", "-inverter_ref", "-distance") if o not in opts]
    if missing:
        raise HtreeError(1, f"{NAME}: {' '.join(missing)} required. Usage: {USAGE}")
    words = session.split_list(opts["-from"])
    if len(words) != 1:
        raise HtreeError(1, f"{NAME}: -from takes one input port. Usage: {USAGE}")
    port = netlist.resolve(db, words[0], NAME)
    if port.kind != "port" or port.direction != "in":
        raise HtreeError(NOT_INPUT, f"{NAME}: -from {port.text} is not an input port of the "
                         f"design: the tree is driven from one")
    try:
        step = float(opts["-distance"])
    except ValueError:
        step = -1.0
    if not math.isfinite(step) or step <= 0:
        raise HtreeError(1, f"{NAME}: -distance must be a distance in um above 0, got "
                         f"'{opts['-distance']}'")
    topology = opts.get("-topology", "fishbone").lower()
    if topology not in TOPOLOGIES:
        raise HtreeError(1, f"{NAME}: -topology takes {' or '.join(TOPOLOGIES)}, got "
                         f"'{opts['-topology']}'")
    prefix = opts.get("-name", f"{port.pin}_tree")
    if not prefix or "/" in prefix or any(c.isspace() for c in prefix):
        raise HtreeError(1, f"{NAME}: -name '{prefix}' must not be empty or contain '/' or "
                         f"spaces")
    cells = {}
    for option in [o for o in ("-inverter_ref", "-buffer_ref") if o in opts]:
        ref = opts[option].removeprefix("lib_cell:")
        row = db.lib_cell_row(ref)
        if row is None:
            raise HtreeError(BAD_CELL, f"{NAME}: {option} '{ref}' is not in the library "
                             f"(read_lef)")
        pin_in, pin_out = cell_pin(db, ref, "in"), cell_pin(db, ref, "out")
        if row["size_x"] is None or not pin_in or not pin_out:
            raise HtreeError(BAD_CELL, f"{NAME}: {option} {ref} needs a SIZE, a signal input "
                             f"pin and a signal output pin in its LEF")
        cells["inverter" if option == "-inverter_ref" else "buffer"] = (row, pin_in, pin_out)
    for kind in ("buffer", "inverter"):  # one cell given as both: an inverter
        if kind in cells:
            db.set_cell_kind(cells[kind][0]["name"], kind)
    root = objects.port_centre(db, port.pin)
    if root is None:
        raise HtreeError(NOT_INPUT, f"{NAME}: port {port.pin} has no shapes and no location "
                         f"(DEF PINS): where the tree starts is not known")
    net = netlist.port_net(db, port.pin)
    sinks = []
    for e in netlist.ends(db, net):
        if e.is_load:
            p = objects.pin_centre(db, e.inst, e.pin)
            if p is not None:
                sinks.append((p[0], p[1], e))
    if not sinks:
        raise HtreeError(NO_SINKS, f"{NAME}: no input pin is on net {net} of port {port.pin}")

    after, after_counts = inverters_after(db, port, sinks)
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()]
    inside_ways = False
    if topology == "fishbone":
        top, lost = build_fishbone(root, sinks, boundary or None)
        if lost:
            raise HtreeError(NO_SINKS, f"{NAME}: no way inside the design boundary from "
                             f"port {port.pin} to " + " ".join(e.text for e in lost))
    else:
        top = build_tree(root, sinks)
    if boundary and topology == "shortest":
        from core.commands.route_net import Fence
        if not _tree_inside(top, Fence(boundary)):
            # the shortest ways leave the die (an L- or comb-shaped one): ways inside it
            top, lost = build_tree_inside(root, sinks, boundary)
            inside_ways = True
            if lost:
                raise HtreeError(NO_SINKS, f"{NAME}: no way inside the design boundary from "
                                 f"port {port.pin} to " + " ".join(e.text for e in lost))
    stages, driver = place_stages(top, step)
    added = fix_polarity(stages, driver, after, buffers="buffer" in cells)
    for s in added:                      # one more inverter: at its sink
        e = s.sinks[0]
        s.point = objects.pin_centre(db, e.inst, e.pin)
    stages += added

    taken = set(db.inst_names())
    nets = {r["net"] for r in db.connection_rows() if r["net"]} | set(netlist.spine_nets(db))
    k = 0
    rows = []
    for s in stages:
        while True:
            k += 1
            name = f"{prefix}_{k}"
            if name not in taken and f"{name}_{cells[s.kind][2]}" not in nets:
                break
        s.name = name
        taken.add(name)
        cell, pin_in, _ = cells[s.kind]
        off = _pin_offset(db, cell, pin_in, "N")
        x = round(s.point[0] - off[0] - cell["size_x"] / 2, 6)
        y = round(s.point[1] - off[1] - cell["size_y"] / 2, 6)
        if boundary and s is stages[0]:  # the cell at the port, on the die edge: moved in
            box = placed_bbox(cell["size_x"], cell["size_y"], "N", x, y)
            x += max(min(boundary[0::2]) - box[0], 0) - max(box[2] - max(boundary[0::2]), 0)
            y += max(min(boundary[1::2]) - box[1], 0) - max(box[3] - max(boundary[1::2]), 0)
            x, y = round(x, 6), round(y, 6)
        if boundary and not rect_in_polygon(placed_bbox(cell["size_x"], cell["size_y"], "N",
                                                         x, y), boundary):
            warn(NOT_LEGAL, f"{NAME}: {name} at {{{_num(x)} {_num(y)}}} is not inside the "
                 f"design boundary", out)
        rows.append((name, cell["name"], x, y, "N"))
    db.add_net_buffers(rows, [], [], [], [])
    port_end = port
    stale = {}
    with db.conn:
        for s in stages:                 # each cell: its input on the net before it
            _, pin_in, _ = cells[s.kind]
            if s.parent is None:
                netlist.connect_load(db, s.name, pin_in, net, port_end)
            else:
                p_out = cells[s.parent.kind][2]
                netlist.connect_load(db, s.name, pin_in, f"{s.parent.name}_{p_out}",
                                     netlist.End("pin", s.parent.name, p_out, "out"))
        for sink, s in driver.items():   # each sink: on the net of its last cell
            if s is None:
                continue
            p_out = cells[s.kind][2]
            if netlist.pin_net(db, sink.inst, sink.pin) is not None:
                netlist.disconnect_load(db, sink.inst, sink.pin)
            netlist.connect_load(db, sink.inst, sink.pin, f"{s.name}_{p_out}",
                                 netlist.End("pin", s.name, p_out, "out"))
            stale.setdefault(net, []).append(sink.text)
    legal = _legalize(session, [s.name for s in stages])

    inv = sum(1 for s in stages if s.kind == "inverter")
    info(f"{NAME}: port {port.pin} (net {net}) -> {len(sinks)} sink(s): {len(stages)} cell(s), "
         f"{inv} inverter(s) ({cells['inverter'][0]['name']}), {len(stages) - inv} buffer(s)"
         + (f" ({cells['buffer'][0]['name']})" if "buffer" in cells else " (no -buffer_ref)")
         + f", one every {_num(step)} um of the tree", out)
    info(f"  {topology} tree: {_num(round(tree_length(top), 3))} um of way in all"
         + (", a trunk the sinks share and a rib off it to each (the least way, the fewest "
            "inverters)" if topology == "fishbone" else
            ", each sink the shortest way from the port"), out)
    if inside_ways:
        info(f"  the shortest ways leave the design boundary: the tree takes the shortest "
             f"ways inside it, down the middle of its arms", out)
    if added:
        info(f"  one more inverter before {len(added)} sink(s) to keep their polarity: "
             + " ".join(s.name for s in added), out)
    head = ("Sink", "Way", "Inverters", "Buffers", "Inverters after", "Last cell")
    table = []
    for x, y, e in sinks:
        chain = []
        s = driver.get(e)
        while s is not None:
            chain.append(s)
            s = s.parent
        way = abs(x - root[0]) + abs(y - root[1])
        lo, hi = after_counts[e]
        table.append((e.text, _num(round(way, 3)), str(sum(c.kind == "inverter" for c in chain)),
                      str(sum(c.kind == "buffer" for c in chain)),
                      str(lo) if lo == hi else f"{lo} .. {hi}",
                      chain[0].name if chain else "- (on the port's net)"))
    wide = [max(len(h), *(len(r[i]) for r in table)) for i, h in enumerate(head)]
    for r in [head] + table:
        info("  " + "  ".join(c.ljust(w) for c, w in zip(r, wide)).rstrip(), out)
    mixed = [e.text for e, (lo, hi) in after_counts.items() if (hi - lo) % 2]
    if mixed:
        warn(NOT_LEGAL, f"{NAME}: the ends past {' '.join(mixed)} see odd and even numbers of "
             f"inverters: the tree cannot make them all even", out)
    if any((int(r[2]) + after[e]) % 2 for r, (_, _, e) in zip(table, sinks)):
        warn(NOT_LEGAL, f"{NAME}: a sink sees an odd number of inverters from the port", out)
    _check_place(db, [s.name for s in stages], out, NAME)
    warn_routed(db, stale, NAME, out)
    info("  netlist and placement only: " + ("" if legal else "legalize_placement, ")
         + f"route_pin -inst {{{prefix}_*}}, route_net next", out)
    return tuple(s.name for s in stages)


def _legalize(session, names):
    if not names:
        return True
    out = session.out
    if not session.db.has_site_rows():
        warn(NOT_LEGAL, f"{NAME}: no placement rows (read_def a DEF with ROW statements), so "
             f"the cells are on the tree, not on sites: run legalize_placement once the rows "
             f"are read", out)
        return False
    from core.commands import legalize_placement
    try:
        legalize_placement.run(session, ["-inst", " ".join(names)])
    except HtreeError as exc:
        warn(NOT_LEGAL, f"{NAME}: the cells are made, but not put on sites: {exc}", out)
        return False
    return True
