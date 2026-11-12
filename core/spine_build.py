"""Spine placement for create_spine. Pure: no database, no Tcl, no Qt.

A spine grows from its location: up for a vertical spine, right for a
horizontal one. The root cell sits placement.origin (default 0) from the
location, along the spine. Positions use two coordinates:
    s    along the spine, 0 at the root cell
    col  the column: level i of the spec is column i (L1 = 0); the stubs are
         one column beyond the last level. Columns are level_pitch apart, on
         the side given by the build direction.

Fixed: the root (L1_inv1) at s = 0, every leaf at the middle (tap) of its
stub, and every cell with a location (cell key 'location') at its driver's
s + location. The stubs lie end to end from s = 0 with stub_gap between
them and share the span equally. Every other cell keeps its column and
moves only along the spine. A linear program places them to keep every net within
max_drive_length + deviation and the nets of each level within deviation of
each other, using the least wire; the leftovers become warnings. When the
cell size is known, a cell driven from its own column sits at least one
cell length further along than its driver, and overlapping cells are
reported.

Net length is the wire drawn once: level_pitch per column crossed, plus one
trunk per load column running from the driver's s to its farthest load in
that column (shared wire counted once), plus any detour. A leaf's net is
level_pitch plus its whole stub.
"""

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TOL = 1e-3                 # um, for every comparison (the spec's 0.001)
MAX_ORDERINGS = 4096       # stub orders tried; more falls back to two
PENALTY = 1000.0           # LP weight of an um over a limit, against an um of wire
OVERLAP_PENALTY = 100 * PENALTY   # cells on top of each other are worse than a long net
LONGEST_WEIGHT = 0.01      # tie-break: among equal wire, keep the longest net short


class SpineError(Exception):
    pass


@dataclass
class SpecCell:
    level: str
    name: str
    input: Optional[str]
    output: Optional[str]
    location: Optional[float] = None  # along the spine from the driver (+ up / right)


@dataclass
class SpecData:
    """The spine_spec fields create_spine uses."""
    name: str
    orientation: Optional[str]
    span: Optional[float]
    level_pitch: Optional[float]
    max_drive: Optional[float]
    gap: Optional[float]
    deviation: Optional[float]
    root_net: Optional[str]
    tap: Optional[str]
    stub_count: Optional[int]
    levels: List[str]
    cells: List[SpecCell]
    origin: Optional[float] = None   # along the spine from the location to the root


@dataclass
class Cell:
    key: str                         # <level>/<cell>, as in the YAML
    level: str
    col: int
    name: str
    inst: str                        # <spine>_<level>_<cell>
    driver: Optional[str] = None     # key of the driving cell; None for the root
    loads: List[str] = field(default_factory=list)
    stub: Optional[str] = None       # stub name for a leaf
    s: float = 0.0
    depth: int = 1                   # inverters from the root, the root counted
    location: Optional[float] = None  # fixed offset from the driver's s, if given

    @property
    def dummy(self):
        return not self.loads and self.stub is None


@dataclass
class Stub:
    name: str
    lo: float
    hi: float
    driver: str = ""                 # key of its leaf

    @property
    def tap(self):
        return (self.lo + self.hi) / 2


@dataclass
class Net:
    name: str
    driver: str                      # cell key
    loads: List[str]                 # cell keys, or the stub name for a leaf
    group: str                       # L1-L2, L2-L3, ..., L4-stubs
    length: float = 0.0
    detour: float = 0.0
    segments: List[Tuple[int, float, int, float]] = field(default_factory=list)
    # (col, s, col, s) centre lines, stub not included


@dataclass
class Plan:
    name: str                        # the spine (instance prefix)
    orientation: str
    direction: int                   # +1 or -1: side the columns step to
    x0: float
    y0: float
    pitch: float
    deviation: float
    max_drive: float
    span: float
    gap: float
    levels: List[str]
    cells: Dict[str, Cell]
    stubs: List[Stub]                # bottom (or left) first
    nets: List[Net] = field(default_factory=list)
    cell_size: Optional[Tuple[float, float]] = None   # (along, across) the spine
    warnings: List[Tuple[str, str]] = field(default_factory=list)   # (kind, text)
    groups: List[Tuple[str, List[str]]] = field(default_factory=list)  # (label, net names)
    spec: str = ""                   # the spine spec it was placed from
    origin: float = 0.0              # along the spine from (x0, y0) to the root
    sign: int = 1                    # -1: the mirrored copy, growing down (or left)

    @property
    def limit(self):
        return self.max_drive + self.deviation

    @property
    def stub_col(self):
        return len(self.levels)

    @property
    def stub_length(self):
        return self.stubs[0].hi - self.stubs[0].lo

    def point(self, col, s):
        """Absolute (x, y) of a column and an along-spine position."""
        across = col * self.pitch * self.direction
        along = self.sign * (self.origin + s)
        if self.orientation == "vertical":
            return self.x0 + across, self.y0 + along
        return self.x0 + along, self.y0 + across

    def net_of(self, key) -> Optional[Net]:
        return next((n for n in self.nets if n.driver == key), None)


DIRECTIONS = {"vertical": {"+x": 1, "-x": -1}, "horizontal": {"+y": 1, "-y": -1}}


def plan(spec: SpecData, prefix: str, location, build_direction: Optional[str] = None,
         cell_size: Optional[Tuple[float, float]] = None) -> Plan:
    """Place a spine; raises SpineError when the spec cannot be built at all.
    cell_size: the inverter's (x, y) size, if known."""
    orientation = (spec.orientation or "").lower()
    if orientation not in DIRECTIONS:
        raise SpineError(f"spine.orientation must be vertical or horizontal, "
                         f"got '{spec.orientation}'")
    choices = DIRECTIONS[orientation]
    build_direction = build_direction or next(iter(choices))
    if build_direction not in choices:
        raise SpineError(f"a {orientation} spine builds toward {' or '.join(choices)}, "
                         f"not '{build_direction}'")
    for value, what in ((spec.span, "spine.span"), (spec.level_pitch, "placement.level_pitch"),
                        (spec.max_drive, "constraints.max_drive_length")):
        if value is None or value <= 0:
            raise SpineError(f"{what} must be a positive number, got "
                             f"{'nothing' if value is None else value}")
    gap = spec.gap if spec.gap is not None else 0.0
    deviation = spec.deviation if spec.deviation is not None else 0.0
    origin = spec.origin if spec.origin is not None else 0.0
    if gap < 0 or deviation < 0 or origin < 0:
        raise SpineError("stubs.gap, placement.deviation and placement.origin must not be "
                         "negative")
    if spec.tap not in (None, "center"):
        raise SpineError(f"stubs.tap '{spec.tap}' is not supported; leaves drive their "
                         f"stub at the center")

    cells, root = _tree(spec, prefix)
    leaves = [c for c in cells.values() if c.stub is not None]
    if spec.stub_count is not None and spec.stub_count != len(leaves):
        raise SpineError(f"stubs.count is {spec.stub_count} but {len(leaves)} cells "
                         f"drive a stub")
    n = len(leaves)
    length = (spec.span - (n - 1) * gap) / n
    if length <= TOL:
        raise SpineError(f"{n} stubs with gap {gap} do not fit in span {spec.span}")
    if cell_size is not None:          # (along, across) the spine
        cell_size = (cell_size[1], cell_size[0]) if orientation == "vertical" else cell_size

    best = None
    for order in _leaf_orders(cells, root):
        candidate = _place(spec, prefix, location, orientation, choices[build_direction],
                           gap, deviation, cells, order, length, cell_size)
        key = (round(candidate[1], 3), round(candidate[2], 3))
        if best is None or key < best[0]:
            best = (key, candidate[0])
    result = best[1]
    result.origin = origin
    _check(result)
    return result


MIRROR = "_mirror"         # suffix of the mirrored copy's prefix and stub names


def mirrored(p: Plan) -> Plan:
    """The plan reflected across the location, through the axis across the
    spine: below it for a vertical spine, left of it for a horizontal one.
    The same cells, stubs and nets (same s, same lengths), renamed: instances
    <spine>_mirror_<level>_<cell>, stubs <stub>_mirror. Warnings are not
    copied (they are the same as the original's)."""
    prefix = p.name + MIRROR

    def inst(name):
        return prefix + name[len(p.name):]

    cells = {k: Cell(**{**vars(c), "loads": list(c.loads), "inst": inst(c.inst),
                        "stub": None if c.stub is None else c.stub + MIRROR})
             for k, c in p.cells.items()}
    stubs = [Stub(s.name + MIRROR, s.lo, s.hi, s.driver) for s in p.stubs]
    nets = [Net(inst(n.name), n.driver,
                [l + MIRROR for l in n.loads] if n.loads[0] not in p.cells else list(n.loads),
                n.group, n.length, n.detour, list(n.segments)) for n in p.nets]
    return Plan(prefix, p.orientation, p.direction, p.x0, p.y0, p.pitch, p.deviation,
                p.max_drive, p.span, p.gap, p.levels, cells, stubs, nets, p.cell_size, [],
                [(label, [inst(n) for n in names]) for label, names in p.groups],
                p.spec, p.origin, -p.sign)


def mirror_overlaps(p: Plan, m: Plan, shown=10):
    """Cell pairs of a plan and its mirror closer than the cell size (the
    roots are 2 x origin apart); appends an overlap warning to p."""
    along = p.cell_size[0] if p.cell_size else 0.0
    across = p.cell_size[1] if p.cell_size else 0.0
    pairs = []
    for a in p.cells.values():
        for b in m.cells.values():
            dcol = abs(a.col - b.col)
            if dcol > 1 or (dcol == 1 and p.pitch >= across - TOL):
                continue
            ds = abs((p.origin + a.s) + (m.origin + b.s))
            if ds < along - TOL or (along == 0 and dcol == 0 and ds < TOL):
                pairs.append(f"{a.inst}-{b.inst}")
    if pairs:
        more = f" and {len(pairs) - shown} more" if len(pairs) > shown else ""
        p.warnings.append(("overlap", f"{len(pairs)} cell pair(s) of the spine and its mirror "
                           f"closer than the cell size ({_n(round(along, 6))} along the "
                           f"spine; placement.origin {_n(p.origin)} puts the roots "
                           f"{_n(2 * p.origin)} apart): {' '.join(pairs[:shown])}{more}"))


def _tree(spec, prefix):
    """Cells keyed <level>/<cell>, with drivers, loads, columns and depths."""
    if not spec.levels or not spec.cells:
        raise SpineError("the spec has no levels or cells")
    col = {level: i for i, level in enumerate(spec.levels)}
    cells = {}
    for c in spec.cells:
        key = f"{c.level}/{c.name}"
        cells[key] = Cell(key, c.level, col[c.level], c.name, f"{prefix}_{c.level}_{c.name}",
                          stub=c.output, location=c.location)
    root_net = spec.root_net or "net"
    roots = []
    for c in spec.cells:
        key = f"{c.level}/{c.name}"
        if c.input is None:
            raise SpineError(f"{key} has no input")
        if c.input == root_net:
            roots.append(key)
            continue
        parts = c.input.split("/")
        driver = "/".join(parts[:2]) if len(parts) == 3 and parts[2] == "Y" else None
        if driver not in cells:
            raise SpineError(f"{key}: input '{c.input}' is neither the root net "
                             f"'{root_net}' nor <level>/<cell>/Y of a cell in the spec")
        if driver == key:
            raise SpineError(f"{key} drives its own input")
        cells[key].driver = driver
        cells[driver].loads.append(key)
    if len(roots) != 1:
        raise SpineError(f"exactly one cell must take the root net '{root_net}' as its "
                         f"input; found {len(roots)}: {' '.join(roots) or 'none'}")
    root = roots[0]
    if cells[root].location is not None:
        raise SpineError(f"{root} is the root: it sits at -location, so it cannot have a "
                         f"location")
    for c in cells.values():
        if c.location is not None and c.stub is not None:
            raise SpineError(f"{c.key} drives {c.stub}: it sits at the middle of its stub, "
                             f"so it cannot have a location")
    stubs = [c.stub for c in cells.values() if c.stub is not None]
    if not stubs:
        raise SpineError("no cell drives a stub (output: <stub name>)")
    dup = sorted({s for s in stubs if stubs.count(s) > 1})
    if dup:
        raise SpineError(f"stub {' '.join(dup)} is driven by more than one cell")
    for c in cells.values():
        if c.stub is not None and c.loads:
            raise SpineError(f"{c.key} drives stub {c.stub} and cells "
                             f"{' '.join(c.loads)}; a leaf drives only its stub")
    seen, todo = {root}, [root]
    while todo:
        key = todo.pop()
        for load in cells[key].loads:
            cells[load].depth = cells[key].depth + 1
            seen.add(load)
            todo.append(load)
    lost = [k for k in cells if k not in seen]
    if lost:
        raise SpineError(f"not connected to the root {root} (a loop?): {' '.join(lost)}")
    return cells, root


def _leaf_orders(cells, root):
    """Leaf orders (bottom to top) where every cell's leaves stay together: the
    stub order is free, but nets must not cross. Tries each order of every
    cell's loads, or only the YAML order and its mirror when there are too many."""
    def has_leaves(key):
        c = cells[key]
        return c.stub is not None or any(has_leaves(l) for l in c.loads)

    branching = {k: [l for l in c.loads if has_leaves(l)] for k, c in cells.items()}
    nodes = [k for k, loads in branching.items() if len(loads) > 1]
    count = 1
    for k in nodes:
        for i in range(2, len(branching[k]) + 1):
            count *= i
    def walk(key, choice):
        c = cells[key]
        if c.stub is not None:
            return [key]
        loads = choice.get(key, branching[key])
        return [leaf for l in loads for leaf in walk(l, choice)]

    if count > MAX_ORDERINGS:
        first = walk(root, {})
        return [first, first[::-1]]
    orders = []
    for combo in itertools.product(*(itertools.permutations(branching[k]) for k in nodes)):
        orders.append(walk(root, dict(zip(nodes, combo))))
    return orders


def _place(spec, prefix, location, orientation, direction, gap, deviation, cells, order,
           length, cell_size):
    """Solve one stub order. Returns (Plan, penalty, wire)."""
    from scipy.optimize import linprog

    levels = list(spec.levels)
    cells = {k: Cell(**{**vars(c), "loads": list(c.loads)}) for k, c in cells.items()}
    stubs = []
    for i, key in enumerate(order):
        lo = i * (length + gap)
        stubs.append(Stub(cells[key].stub, lo, lo + length, key))
        cells[key].s = lo + length / 2
    p = Plan(prefix, orientation, direction, float(location[0]), float(location[1]),
             spec.level_pitch, deviation, spec.max_drive, spec.span, gap, levels, cells, stubs,
             cell_size=cell_size, spec=spec.name)
    stub_col = p.stub_col

    # s of each cell: a constant (root, leaves) or an LP variable; a cell with
    # a location is its driver's s + location (a constant when the driver is
    # one); a dummy (no loads, no stub) sits at its driver's s.
    s_of, tied, bounds = {}, [], []      # tied: (cell, driver, location)
    for key in _top_down(cells):
        c = cells[key]
        if c.driver is None or c.stub is not None:
            s_of[key] = ("const", c.s)
        elif c.location is not None and s_of[c.driver][0] == "const":
            s_of[key] = ("const", s_of[c.driver][1] + c.location)
        elif c.location is not None:     # free of the span: the driver decides
            s_of[key] = ("var", len(bounds))
            bounds.append((None, None))
            tied.append((key, c.driver, c.location))
        elif c.dummy:
            s_of[key] = s_of[c.driver]
        else:
            s_of[key] = ("var", len(bounds))
            bounds.append((0.0, p.span))
    nvar = len(bounds)
    rows, rhs = [], []

    def new_var(lo=None, hi=None):
        nonlocal nvar
        bounds.append((lo, hi))
        nvar += 1
        return nvar - 1

    def add_row(terms, const_terms, limit):
        """sum(coef * var) + sum(coef * s_const) <= limit."""
        row = {}
        for coef, ref in terms:
            row[ref] = row.get(ref, 0.0) + coef
        rows.append(row)
        rhs.append(limit - sum(const_terms))

    def s_term(key, coef):
        kind, value = s_of[key]
        return ([(coef, value)], []) if kind == "var" else ([], [coef * value])

    for key, driver, location in tied:   # s - s_driver = location
        t1, k1 = s_term(key, 1.0)
        t2, k2 = s_term(driver, -1.0)
        add_row(t1 + t2, k1 + k2, location)
        add_row([(-c, v) for c, v in t1 + t2], [-k for k in k1 + k2], -location)

    nets, net_len = [], {}               # net_len: name -> (const, [(coef, var)])
    for key in _top_down(cells):
        c = cells[key]
        if c.dummy:
            continue
        group = (f"{c.level}-{levels[c.col + 1]}" if c.col + 1 < len(levels)
                 else f"{c.level}-stubs")
        net = Net(f"{c.inst}_Y", key, [c.stub] if c.stub else list(c.loads), group)
        nets.append(net)
        if c.stub is not None:
            net_len[net.name] = (spec.level_pitch * (stub_col - c.col) + length, [])
            continue
        cols = sorted({cells[l].col for l in c.loads})
        const = spec.level_pitch * max(0, max(cols) - c.col)
        terms = []
        for col in cols:
            hi, lo = new_var(), new_var()
            for member in [key] + [l for l in c.loads if cells[l].col == col]:
                t, k = s_term(member, 1.0)              # s - hi <= 0
                add_row(t + [(-1.0, hi)], k, 0.0)
                t, k = s_term(member, -1.0)             # lo - s <= 0
                add_row(t + [(1.0, lo)], k, 0.0)
            terms += [(1.0, hi), (-1.0, lo)]
        net_len[net.name] = (const, terms)

    penalties, spacing, wire = [], [], []
    if cell_size is not None:          # same-column load: one cell further along
        for key, c in cells.items():
            d = c.driver
            if (d is None or cells[d].col != c.col or s_of[key] == s_of[d]
                    or c.location is not None):  # a given location wins
                continue
            slack = new_var(0.0)       # soft, so a fixed pair cannot make it infeasible
            t1, k1 = s_term(d, 1.0)
            t2, k2 = s_term(key, -1.0)
            add_row(t1 + t2 + [(-1.0, slack)], k1 + k2, -cell_size[0])
            spacing.append(slack)
    for net in nets:
        const, terms = net_len[net.name]
        wire += terms
        if terms:                                       # length - over <= limit
            over = new_var(0.0)
            add_row(terms + [(-1.0, over)], [const], p.limit)
            penalties.append(over)
    longest = new_var()
    for net in nets:
        const, terms = net_len[net.name]
        if terms:                                       # length <= longest
            add_row(terms + [(-1.0, longest)], [const], 0.0)
    groups = {}
    for net in nets:
        groups.setdefault(net.group, []).append(net.name)
    for label, names in groups.items():
        if all(not net_len[n][1] for n in names):       # all fixed: nothing to place
            continue
        gmax, gmin, excess = new_var(), new_var(), new_var(0.0)
        for name in names:
            const, terms = net_len[name]
            add_row(terms + [(-1.0, gmax)], [const], 0.0)          # length <= gmax
            add_row([(-c, v) for c, v in terms] + [(1.0, gmin)], [-const], 0.0)
        add_row([(1.0, gmax), (-1.0, gmin), (-1.0, excess)], [], deviation)
        penalties.append(excess)

    x = [0.0] * nvar
    if nvar:
        import numpy as np
        cost = np.zeros(nvar)
        for coef, v in wire:
            cost[v] += coef
        for v in penalties:
            cost[v] += PENALTY
        for v in spacing:
            cost[v] += OVERLAP_PENALTY
        cost[longest] += LONGEST_WEIGHT
        a = np.zeros((len(rows), nvar))
        for i, row in enumerate(rows):
            for v, coef in row.items():
                a[i, v] = coef
        res = linprog(cost, A_ub=a if rows else None, b_ub=np.array(rhs) if rows else None,
                      bounds=bounds, method="highs")
        if res.status != 0:
            raise SpineError(f"placement LP failed: {res.message}")
        x = [float(v) for v in res.x]

    for key, (kind, value) in s_of.items():
        cells[key].s = round(float(value if kind == "const" else x[value]), 6)
    for net in nets:
        const, terms = net_len[net.name]
        net.length = round(const + sum(coef * x[v] for coef, v in terms), 6)
        net.segments, drawn = _segments(p, cells[net.driver], cells)
        net.detour = max(0.0, round(net.length - drawn, 6))
        if net.detour < TOL:
            net.detour = 0.0
    p.nets = nets
    p.groups = list(groups.items())
    penalty = sum(x[v] for v in penalties) + 100 * sum(x[v] for v in spacing)
    return p, penalty, sum(n.length for n in nets)


def _top_down(cells):
    """Cell keys with every driver before its loads."""
    root = next(k for k, c in cells.items() if c.driver is None)
    order, todo = [], [root]
    while todo:
        key = todo.pop(0)
        order.append(key)
        todo += cells[key].loads
    return order


def _segments(p, c, cells):
    """Centre lines of a cell's net and their length (detour not drawn)."""
    if c.stub is not None:
        stub = next(s for s in p.stubs if s.name == c.stub)
        return [(c.col, c.s, p.stub_col, c.s)], p.pitch * (p.stub_col - c.col) + stub.hi - stub.lo
    segs, total = [], 0.0
    cols = sorted({cells[l].col for l in c.loads})
    if max(cols) > c.col:
        segs.append((c.col, c.s, max(cols), c.s))
        total += p.pitch * (max(cols) - c.col)
    for col in cols:
        ss = [c.s] + [cells[l].s for l in c.loads if cells[l].col == col]
        if max(ss) - min(ss) > 0:
            segs.append((col, min(ss), col, max(ss)))
            total += max(ss) - min(ss)
    return segs, total


def _check(p):
    """Warnings: nets over the limit, levels out of balance, unequal inverter
    counts, cells that drive nothing."""
    for net in p.nets:
        if net.length > p.limit + TOL:
            p.warnings.append(("over", f"net {net.name} ({net.group}) is {net.length:.3f} um, "
                               f"over max_drive_length {_n(p.max_drive)} + deviation "
                               f"{_n(p.deviation)} = {_n(p.limit)} by "
                               f"{net.length - p.limit:.3f} um"))
    by_name = {n.name: n for n in p.nets}
    for label, names in p.groups:
        lengths = [by_name[n].length for n in names]
        if max(lengths) - min(lengths) > p.deviation + TOL:
            p.warnings.append(("spread", f"{label} nets range from {min(lengths):.3f} to "
                               f"{max(lengths):.3f} um: spread {max(lengths) - min(lengths):.3f}"
                               f" is over deviation {_n(p.deviation)}"))
    depths = {}
    for c in p.cells.values():
        if c.stub is not None:
            depths.setdefault(c.depth, []).append(c.stub)
    if len(depths) > 1:
        parts = [f"{' '.join(sorted(stubs))} through {d} inverters"
                 for d, stubs in sorted(depths.items())]
        p.warnings.append(("depth", "stubs are reached through different numbers of "
                           "inverters (different delay; opposite clock polarity when odd "
                           "and even): " + "; ".join(parts)))
    _check_overlaps(p)
    for c in p.cells.values():
        if c.dummy:
            where = ("placed at its driver's position" if c.location is None else
                     f"placed {_n(c.location)} um from its driver")
            p.warnings.append(("dummy", f"{c.key} ({c.inst}) drives nothing: no loads and "
                               f"no stub; {where}"))


def _check_overlaps(p, shown=10):
    """Cells closer than one cell length along the spine, in the same column
    or (when level_pitch is under the cell width) in neighbouring columns."""
    along = p.cell_size[0] if p.cell_size else 0.0
    across = p.cell_size[1] if p.cell_size else 0.0
    cells = list(p.cells.values())
    pairs = []
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            dcol = abs(a.col - b.col)
            if dcol > 1 or (dcol == 1 and p.pitch >= across - TOL):
                continue
            ds = abs(a.s - b.s)
            if ds < along - TOL or (along == 0 and dcol == 0 and ds < TOL):
                pairs.append(f"{a.key}-{b.key}")
    if pairs:
        what = (f"closer than the cell size ({_n(round(along, 6))} along the spine, "
                f"{_n(round(across, 6))} across, level_pitch {_n(p.pitch)})"
                if p.cell_size else "at the same position (no cell given: size unknown)")
        more = f" and {len(pairs) - shown} more" if len(pairs) > shown else ""
        p.warnings.append(("overlap", f"{len(pairs)} cell pair(s) {what}: "
                           f"{' '.join(pairs[:shown])}{more}"))


def _n(v):
    text = repr(float(v))
    return text[:-2] if text.endswith(".0") else text
