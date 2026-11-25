"""Pin access: can route_net reach each signal pin of a cell?

A signal pin is reached on its route_pin strap, from a vertical signal track
(the '-' tracks of the track assignment of a layer numbered in x, IB) that
the strap covers or reaches by extending at most its max_extension: at the
crossing of that track with the horizontal signal track nearest the strap,
or the one on the strap's other side. A track is of no use to the pin when
  - the wire there (as wide as the rule's) is not inside the design,
  - a wire of another net on the vertical layer is closer than the rule
    spacing to the wire down to the strap, at both of those crossings, or
  - the strap's extension to it on its layer would come closer than the
    tech spacing (route_net's for strap extensions) to a strap or wire of
    another net (another cell's straps).
A pin of a cell the spine spec gives tracks (track: {input, output},
core/spine_tracks.py) has its track only. A pin with no track of use cannot
be connected. Before route_pin the strap
is taken as the cell's width at the cell's height, reaching as far as
route_pin's straps do (another cell's max_extension, or route_pin's
default). The wires of the nets in `ignore` (to be routed again) are not
looked at.
"""

import bisect

from core import netlist, objects
from core.commands.route_net import strap_spacing
from core.db import _num, base_rect
from core.placement import rect_in_polygon

TOL = 1e-6


def _rect(r):
    return tuple(float(c) for c in r["rect"].split())


def _signal_tracks(db, axis):
    """{layer: [coordinates of its '-' tracks]} of the layers whose track
    assignment numbers the tracks in axis."""
    found = {}
    for layer in db.track_assignment_layers():
        row = db.track_assignment_row(layer)
        if row["direction"] != axis:
            continue
        pattern = row["pattern"].split()
        found[layer] = [c for k, c in enumerate(db.track_positions(layer, axis))
                        if pattern[k % len(pattern)] == "-"]
    return found


def _rule(db, net, layer):
    """(width, spacing) of the rule net is routed with on layer, else of any
    rule with the layer, else the layer's width and spacing in the tech."""
    for name in ([db.net_route_rule(net)] if net else []) + db.route_rule_names():
        row = db.route_rule_layer_row(name, layer) if name else None
        if row is not None:
            return row["width"], row["spacing"]
    tech = db.layer_row(layer) if db.has_tech() else None     # no rule yet: the layer's own
    return ((tech["width"] or 0.0, tech["min_spacing"] or 0.0) if tech is not None
            else (0.0, 0.0))


def _near(a, b, gap):
    return a[0] < b[2] + gap - TOL and b[0] < a[2] + gap - TOL and \
        a[1] < b[3] + gap - TOL and b[1] < a[3] + gap - TOL


def check(db, insts, ignore=()):
    """[(inst, pin, strap text, [(x, why)])] of the signal pins of insts
    with no track of use (see the module docstring); [] when every one has
    one. None when the design has no track assignment numbered in x."""
    vertical = _signal_tracks(db, "x")
    horizontal = _signal_tracks(db, "y")
    if not vertical:
        return None
    vlayer = next(iter(vertical))
    xs = vertical[vlayer]
    ys = next(iter(horizontal.values()), [])
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()] \
        if db.has_design() else []
    ignore = set(ignore)
    wires = [(r["shield_net"] or r["net"], r["layer"], _rect(r)) for r in db.net_wire_rows()
             if "/" not in r["layer"] and r["net"] not in ignore]   # a shield: its power net
    straps = [(r["net"], r["layer"], _rect(r), r["inst"]) for r in db.strap_rows()]
    reach_default = next((r["max_extension"] for r in db.strap_rows()
                          if r["max_extension"] is not None), 3.0)
    pins_of = netlist.pins(db)
    from core import spine_tracks
    assigned = {}                        # (inst, in | out) -> (x, k): the spine spec's track
    for spine in db.spine_names():
        for inst, (st, cin, cout, kin, kout) in spine_tracks.placed(db, spine).items():
            if st.vertical and st.layer == vlayer:
                assigned[inst, "in"], assigned[inst, "out"] = (cin, kin), (cout, kout)
    found = []
    for name in insts:
        row = db.inst_row(name)
        cell = db.lib_cell_row(row["ref_cell"])
        box = objects.inst_bbox(db, row)
        if cell is None or box is None:
            continue
        nets = pins_of.get(name, {})
        for pin in db.lib_pin_names(cell["id"]):
            lp = db.lib_pin_row(cell["name"], pin)
            if (lp["use"] or "signal").lower() != "signal" or \
                    not (lp["direction"] or "").lower().startswith(("in", "out")):
                continue
            net = nets.get(pin)
            wire = db.pin_wire_row(name, pin)
            if net is None and wire is None:
                continue                          # on no net: nothing to reach it for
            if wire is not None and wire["strap"] is None:
                continue                          # reached from the side on its own track
            strap = db.strap_row(name, wire["strap"]) if wire is not None else None
            if strap is not None:
                sx1, sy1, sx2, sy2 = base_rect(strap)     # its reach is from route_pin's
                reach, slayer = strap["max_extension"] or 0.0, strap["layer"]
                where = f"strap {wire['strap']}, y {_num(round((sy1 + sy2) / 2, 3))}"
            else:
                sx1, sy1, sx2, sy2 = box
                reach, slayer = reach_default, next(iter(horizontal), vlayer)
                where = "no strap yet: the cell"
            width, spacing = _rule(db, net, vlayer)
            mine = {net, strap["net"] if strap is not None else None} - {None}
            centre = (sy1 + sy2) / 2
            k = bisect.bisect_left(ys, centre)
            taps = [ys[j] for j in range(max(0, k - 1), min(len(ys), k + 1))] or [centre]
            why_not = []
            usable = False
            spec = assigned.get((name, "in" if lp["direction"].lower().startswith("in")
                                 else "out"))
            for x in ([spec[0]] if spec and spec[0] is not None else xs):
                if x - width / 2 < sx1 - reach - TOL or x + width / 2 > sx2 + reach + TOL:
                    if spec and spec[0] is not None:
                        why_not.append((x, f"track {spec[1]} of the spine spec, out of the "
                                           f"strap's reach"))
                    continue                      # out of the strap's reach
                if boundary and not rect_in_polygon(
                        (x - width / 2, sy1, x + width / 2, sy2), boundary):
                    why_not.append((x, "outside the design"))
                    continue
                if x - width / 2 < sx1 or x + width / 2 > sx2:   # the strap extended to it
                    ext = (min(sx1, x - width / 2), sy1, max(sx2, x + width / 2), sy2)
                    gap = strap_spacing(db, slayer, sy2 - sy1)     # as route_net extends it
                    hit = next((f"strap:{i}/{n}" if i else n for n, layer, r, i in
                                [(n, l, r, i) for n, l, r, i in straps if i != name]
                                + [(n, l, r, None) for n, l, r in wires]
                                if layer == slayer and n not in mine
                                and _near(ext, r, gap)), None)
                    if hit:
                        why_not.append((x, f"the strap's extension to it meets {hit}"))
                        continue
                blocking = None
                for ty in taps:
                    drop = (x - width / 2, min(ty - width / 2, sy1), x + width / 2,
                            max(ty + width / 2, sy2))
                    blocking = next((n for n, layer, r in wires
                                     if layer == vlayer and n not in mine
                                     and _near(drop, r, spacing)), None)
                    if blocking is None:
                        break
                if blocking is not None:
                    why_not.append((x, f"taken by {blocking}"))
                    continue
                usable = True
                break
            if not usable:
                found.append((name, pin, where, why_not))
    return found


def report(rows):
    """Text lines of check's rows."""
    lines = []
    for inst, pin, where, why in rows:
        reasons = "; ".join(f"x {_num(x)} {text}" for x, text in why) or \
            "no signal track within the strap's reach"
        lines.append(f"    {inst}/{pin} ({where}): {reasons}")
    return lines
