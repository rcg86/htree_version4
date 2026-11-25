"""copy_obj -from <spine> -name <name> [-x_shift <um>] [-y_shift <um>]: copy a
built spine, with everything it owns, as a new spine shifted by x_shift and
y_shift.

    copy_obj -from [get_db spine sp] -name sp2 -x_shift 17.28
    copy_obj -from sp -name sp_low -y_shift -400

The copy is a spine like one create_spine builds: its instances, their
route_pin straps and pin wires, its stubs, the centre lines and routed wires
of its nets (wires, extensions, crossing boxes, shields, stub wires) and the
vias they give, all shifted. Names: <from>_<rest> becomes <name>_<rest>
(sp_L1_inv1 -> sp2_L1_inv1, net sp_L1_inv1_Y -> sp2_L1_inv1_Y); a name that
does not start with <from>_ gets <name>_ in front. Stubs keep their names
(they are named within their spine). The root takes a root net of its own,
<name>_primary_input (its pin routes too), as a spine create_spine built. Each shift snaps to the nearest whole number of the legal step (at
least one when it is not 0): a multiple of the track-pattern period and of the
site step of the cells' rows. Cells, pin routes, routes and vias all move by
that one shift, so nothing is legalized after and every connection holds:
signal wires on signal tracks, shields on their nets' tracks, cells on sites
of their orientation. Cells still off a site (rows that are not regular, or
none there), and anything outside the design or over another instance, are
reported.
"""

import math

from core import netlist
from core.commands import move_obj
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import rect_in_polygon

NAME = "copy_obj"
SUMMARY = "Copy a spine with its cells, pin routes and routing to a new name, shifted"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-from": "value", "-name": "value", "-x_shift": "value", "-y_shift": "value"}

USAGE = 1
NO_SPINE = 280
NAME_TAKEN = 281
SNAPPED = 282
OFF_SITE = 283
ROUTE_OUTSIDE = 284
PORT_DRIVER = 285
TOL = 1e-6


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    usage = "Usage: copy_obj -from <spine> -name <name> [-x_shift <um>] [-y_shift <um>]"
    if "-from" not in opts or "-name" not in opts:
        raise HtreeError(USAGE, f"copy_obj: -from and -name are required. {usage}")
    shift = []
    for key in ("-x_shift", "-y_shift"):
        try:
            shift.append(float(opts.get(key, 0)))
        except ValueError:
            raise HtreeError(USAGE, f"copy_obj: {key} must be a number of microns, got "
                             f"'{opts[key]}'") from None
    db = session.db
    src = _spine(session, opts["-from"])
    out = session.out
    insts = [m["inst"] for m in db.spine_members(db.spine_row(src)["id"])]
    dx, dy = (_snap(db, src, insts, d, axis, key, out)
              for axis, (d, key) in enumerate(zip(shift, ("-x_shift", "-y_shift"))))
    new = opts["-name"]
    if not new or any(c in new for c in " \t/:{}[]$\"\\*?"):
        raise HtreeError(USAGE, f"copy_obj: -name must be a plain name (no blanks, / : "
                         f"or glob characters), got '{new}'")
    spine = db.spine_row(src)
    insts = [m["inst"] for m in db.spine_members(spine["id"])]
    nets = [r["name"] for r in db.spine_net_rows(spine["id"])]
    inst_map = {n: _renamed(n, src, new) for n in insts}
    net_map = {n: _renamed(n, src, new) for n in nets}
    _check_names(session, new, inst_map, net_map)
    port_drivers = [f"{r['inst']}/{r['pin']}" for r in db.connection_rows()
                    if r["inst"] in inst_map and r["driver"] == f"{r['inst']}/{r['pin']}"]
    straps, pin_wires, wires, stretches = db.copy_spine(src, new, inst_map, net_map, dx, dy)
    _root_pin_routes(db, src, new, list(inst_map.values()))
    info(f"Copied spine:{src} to spine:{new} (x {_num(dx)}, y {_num(dy)}): {len(insts)} "
         f"instance(s), {len(nets)} net(s), {straps} strap(s), {pin_wires} pin wire(s), "
         f"{wires} routed shape(s) (wires, crossing boxes, shields, stubs), {stretches} "
         f"strap stretch(es)", out)
    if port_drivers:
        warn(PORT_DRIVER, f"copy_obj: not copied: the connection of {' '.join(port_drivers)} to the net "
             f"of a port (connect_port); a net has one driver", out)
    new_insts = list(inst_map.values())
    _check_sites(db, inst_map, out)
    _check_routes(db, new_insts, list(net_map.values()), out)
    move_obj._check_place(db, new_insts, set(new_insts), out)
    return f"spine:{new}"


def _spine(session, word):
    """The name of the one built spine word gives (a name or spine: handle)."""
    db = session.db
    words = session.split_list(word)
    names = [w[len("spine:"):] if w.startswith("spine:") else w for w in words]
    if len(names) != 1 or names[0] not in db.spine_names():
        what = "one spine" if len(names) != 1 else f"no spine '{names[0]}'"
        raise HtreeError(NO_SPINE, f"copy_obj: -from takes {what}; copy_obj copies built "
                         f"spines only (get_db spines: {' '.join(db.spine_names()) or 'none'})")
    return names[0]


def _root_pin_routes(db, src, new, insts):
    """The copy's root takes a root net of its own: the copied pin routes
    route_pin put on the original's root net go on the copy's, and the
    shapes kept with them that carry that net: route_pin's pieces under the
    pin wires (pg:<inst>) and the vias inserted on the pin routes (auto_via:)."""
    old, now = netlist.root_net(db, db.spine_row(src)), netlist.root_net(db, db.spine_row(new))
    if not old or not now or old == now:
        return
    with db.conn:
        for table in ("strap", "pin_wire"):
            db.conn.executemany(f"UPDATE {table} SET net = ? WHERE inst = ? AND net = ?",
                                [(now, inst, old) for inst in insts])
        own = {f"pg:{inst}" for inst in insts}
        under = tuple(o for inst in insts for o in (
            f"auto_via:pin_wire:{inst}/", f"auto_via:strap:{inst}/", f"auto_via:net_wire:pg:{inst}/"))
        rows = db.conn.execute("SELECT id, net FROM net_wire WHERE shield_net = ?",
                               (old,)).fetchall()
        db.conn.executemany("UPDATE net_wire SET shield_net = ? WHERE id = ?",
                            [(now, r["id"]) for r in rows
                             if r["net"] in own or r["net"].startswith(under)])
    db.netlist = None


def _renamed(name, src, new):
    return new + name[len(src):] if name.startswith(src + "_") else f"{new}_{name}"


def _check_names(session, new, inst_map, net_map):
    db = session.db
    if new in db.spine_names():
        raise HtreeError(NAME_TAKEN, f"copy_obj: there is a spine '{new}' already")
    taken_insts = set(db.inst_names()) & set(inst_map.values())
    taken_nets = (set(netlist.spine_nets(db)) | set(netlist.by_net(db))) & set(net_map.values())
    if taken_insts or taken_nets:
        clash = sorted(taken_insts) + sorted(taken_nets)
        more = f" and {len(clash) - 10} more" if len(clash) > 10 else ""
        raise HtreeError(NAME_TAKEN, f"copy_obj: the copy's names are taken: "
                         f"{' '.join(clash[:10])}{more}; give another -name")


def _snap(db, src, insts, d, axis, what, out):
    """d rounded to the nearest whole number of the legal step along axis, at
    least one step when d is not 0. The legal step is the least common
    multiple of the track-pattern period of the layers whose tracks run across
    it (the spine's route layers and the layers with a track assignment) and
    of the site step of the cells' rows (x: the site width step; y: the row
    pitch, twice that when the rows alternate N / FS). So cells, routes and
    vias move by the same amount and each lands where it is legal: signal
    wires on signal tracks, shields on their nets' tracks, cells on sites of
    their orientation."""
    if not d:
        return 0.0
    unit = (db.tech_row()["manufacturing_grid"] if db.has_tech() else None) or 0.001
    assigned = [r["layer"] for r in db.conn.execute("SELECT layer FROM track_assignment")]
    track = int(round(move_obj._spine_step(db, [src], axis, assigned) / unit))
    site = _site_step(db, insts, axis, unit)
    step = track * site // math.gcd(track, site) * unit
    k = max(1, round(abs(d) / step))
    snapped = round(k * step if d > 0 else -k * step, 6)
    if abs(snapped - d) > TOL:
        parts = f"track period {_num(round(track * unit, 6))}" + \
            (f", site step {_num(round(site * unit, 6))}" if site > 1 else "")
        warn(SNAPPED, f"copy_obj: {what} {_num(d)} snapped to {_num(snapped)}, the nearest "
             f"whole number of the legal step {_num(round(step, 6))} ({parts}): signal wires "
             f"on signal tracks, shields on their nets' tracks, cells on sites", out)
    return snapped


def _site_step(db, insts, axis, unit):
    """The step, in units, that keeps the cells on sites of their orientation:
    the least common multiple over the sites of their cells (those with DEF
    rows) of the site width step (x), or of the row pitch, doubled when the
    neighbouring rows have other orientations (y). 1 without rows."""
    sites = {db.lib_cell_row(db.inst_row(n)["ref_cell"])["site"] for n in insts}
    step = 1
    for site in sorted(s for s in sites if db.site_rows_of(s)):
        if axis == 0:
            values = [r[0] for r in db.conn.execute(
                "SELECT DISTINCT step_x FROM site_row WHERE site = ? AND step_x > 0", (site,))]
        else:
            orients = {}
            for y, orient in db.conn.execute("SELECT y, orient FROM site_row WHERE site = ?",
                                             (site,)):
                orients.setdefault(int(round(y / unit)), set()).add(orient)
            ys = sorted(orients)
            gaps = [b - a for a, b in zip(ys, ys[1:])]
            if not gaps:
                continue
            pitch = min(gaps)
            same = all(orients[a] == orients[b] for a, b in zip(ys, ys[1:]) if b - a == pitch)
            values = [(pitch if same else 2 * pitch) * unit]
        for v in values:
            n = int(round(v / unit))
            step = step * n // math.gcd(step, n)
    return step


def _on_site(db, name):
    r = db.inst_row(name)
    cell = db.lib_cell_row(r["ref_cell"])
    if cell is None or cell["size_x"] is None:
        return True
    site = db.legal_site(r["x"], r["y"], cell["size_x"], r["orient"] or "N",
                         cell["site"] if db.site_rows_of(cell["site"]) else None)
    return site is not None and abs(site[0] - r["x"]) <= TOL and abs(site[1] - r["y"]) <= TOL


def _check_sites(db, inst_map, out):
    """Report the copied cells not on a site of their orientation (they are
    not moved: that would break their connections)."""
    if not db.has_site_rows():
        return
    off = [(old, new) for old, new in inst_map.items() if not _on_site(db, new)]
    if off:
        names = [new for _, new in off]
        more = f" and {len(off) - 10} more" if len(off) > 10 else ""
        was = sum(1 for old, _ in off if not _on_site(db, old))
        why = f"; {was} of them because the original is not on one either" if was else \
            "; the rows there are not like the original's, or there are none"
        warn(OFF_SITE, f"copy_obj: {len(off)} copied instance(s) not on a placement site of "
             f"their orientation, left where the shift put them (their routes go with them)"
             f"{why}: {' '.join(names[:10])}{more}", out)


def _check_routes(db, insts, nets, out):
    """Warn when copied route shapes are not inside the design boundary."""
    if not (db.has_design() and db.design_row()["boundary"]):
        return
    boundary = [float(v) for v in db.design_row()["boundary"].split()]
    owners = [r for n in nets for r in db.net_wire_rows(n)]
    shapes = [r for n in insts for r in db.strap_rows(n)] + owners + \
        [r for n in insts for r in db.conn.execute("SELECT * FROM pin_wire WHERE inst = ?",
                                                  (n,)).fetchall()]
    outside = [r for r in shapes
               if not rect_in_polygon([float(v) for v in r["rect"].split()], boundary)]
    if outside:
        warn(ROUTE_OUTSIDE, f"copy_obj: {len(outside)} copied route shape(s) are not inside "
             f"the design boundary", out)
