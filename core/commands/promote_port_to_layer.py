"""promote_port_to_layer -port <ports> -layer <layer> -width <um>: put ports of
the design on a routing layer, -width wide.

    promote_port_to_layer -port mgt_clk_ctm2_iose_local_clk_25 -layer IB -width 0.72

Each port's shapes (DEF PINS) are replaced by one rectangle on -layer: -width
across the layer's direction (x on a vertical layer, y on a horizontal one),
along it as long as the old shapes were and at least -width; a layer of no
direction gets a -width square. It is centred where the old shapes were, and
moved in just far enough to lie inside the design boundary when it would
stick out (a port on the die edge stays on the edge). Its corners go on the
manufacturing grid.

-snap_to_track: then moved across the layer's direction so its centre line
is on the nearest signal track of the layer (the tracks route_net uses: every
DEF track, or the '-' ones of assign_track_for_route) that keeps it inside
the boundary: a route on that track runs straight onto it.

route_net then reaches the port on that layer: with -layer one of the route
rule's layers the route ends on it, connected, where it ended near the port,
not connected (HT4-266), before. write_def writes the promoted ports in
PINS, with their new shape and layer in place of the old. read_def of the
design gives the port its old shapes again (and write_def leaves it out).
"""

from core import objects, vias
from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options
from core.placement import rect_in_polygon

NAME = "promote_port_to_layer"
SUMMARY = "Put ports of the design on a routing layer, a given width wide"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-port": "value", "-layer": "value", "-width": "value", "-snap_to_track": "flag"}
USAGE = "promote_port_to_layer -port <ports> -layer <layer> -width <um> [-snap_to_track]"

NO_PORT = 315
BAD_LAYER = 316
OUTSIDE = 317                # WARN: the new shape is not inside the design boundary
FAR_TRACK = 318              # WARN: -snap_to_track moved a port more than a track pitch


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    missing = [o for o in ("-port", "-layer", "-width") if o not in opts]
    if missing:
        raise HtreeError(1, f"{NAME}: {' '.join(missing)} required. Usage: {USAGE}")
    try:
        width = float(opts["-width"])
    except ValueError:
        width = None
    if width is None or not width > 0:
        raise HtreeError(1, f"{NAME}: -width must be a width in um above 0, got "
                         f"'{opts['-width']}'")
    objects.require_tech(db)
    layer = opts["-layer"].removeprefix("layer:")
    if vias.tech_layers(db).get(layer, (0, ""))[1] != "routing":
        raise HtreeError(BAD_LAYER, f"{NAME}: -layer '{layer}' is not a routing layer of the "
                         f"tech (get_db layers .name)")
    ports = _ports(session, opts["-port"])
    direction = (db.layer_row(layer)["direction"] or "").lower()
    grid = (db.tech_row()["manufacturing_grid"] or 0) if db.has_tech() else 0
    snap = (lambda v: round(round(v / grid) * grid, 6)) if grid else (lambda v: round(v, 6))
    boundary = [float(v) for v in (db.design_row()["boundary"] or "").split()]
    made = []
    for name in ports:
        row = db.port_row(name)
        old = db.port_shape_rows(row["id"])
        v = [float(c) for s in old for c in s["points"].split()]
        if v:
            box = (min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2]))
        elif row["x"] is not None:
            box = (row["x"], row["y"], row["x"], row["y"])
        else:
            raise HtreeError(NO_PORT, f"{NAME}: port {name} has no shapes and no location "
                             f"(DEF PINS): nowhere to put it")
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        w = width if direction != "horizontal" else max(width, box[2] - box[0])
        h = width if direction != "vertical" else max(width, box[3] - box[1])
        rect = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        if boundary:                     # moved in off the boundary's bbox, if it sticks out
            bx1, by1 = min(boundary[0::2]), min(boundary[1::2])
            bx2, by2 = max(boundary[0::2]), max(boundary[1::2])
            dx = max(bx1 - rect[0], 0) - max(rect[2] - bx2, 0)
            dy = max(by1 - rect[1], 0) - max(rect[3] - by2, 0)
            rect = [rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy]
        on_track = ""
        if opts["-snap_to_track"]:       # its centre line on the nearest signal track
            rect, on_track, moved, pitch = _on_track(db, layer, direction, rect, boundary, name)
            if pitch and abs(moved) > pitch + 1e-6:
                warn(FAR_TRACK, f"{NAME}: port {name}: the nearest {layer} signal track inside "
                     f"the boundary is {_num(round(abs(moved), 6))} um away (the track pitch "
                     f"is {_num(round(pitch, 6))}): the port is moved that far", out)
        rect = [snap(c) for c in rect]
        db.set_port_shapes(row["id"], [(layer, "rect", " ".join(_num(c) for c in rect))],
                           promoted=layer)
        was = ", ".join(dict.fromkeys(s["layer"] for s in old)) or "no shapes"
        info(f"{NAME}: port {name}: on {layer} at {{{' '.join(_num(c) for c in rect)}}}, "
             f"{_num(round(rect[2] - rect[0], 6))} x {_num(round(rect[3] - rect[1], 6))} "
             f"(was {was} {{{' '.join(_num(round(c, 6)) for c in box)}}}){on_track}", out)
        if boundary and not rect_in_polygon(tuple(rect), boundary):
            warn(OUTSIDE, f"{NAME}: port {name}: its shape on {layer} is not inside the design "
                 f"boundary", out)
        made.append(f"port:{db.design_row()['name']}/{name}")
    return tuple(made)


def _on_track(db, layer, direction, rect, boundary, name):
    """rect moved across the layer's direction so its centre line is on the
    nearest signal track of the layer (route_net's: every DEF track, or the
    '-' ones of assign_track_for_route) that keeps it inside the boundary's
    bbox; (rect, the words for the report, how far it moved, the pitch of
    the signal tracks)."""
    from core.commands import route_net
    if direction not in ("horizontal", "vertical"):
        raise HtreeError(1, f"{NAME}: -snap_to_track: {layer} has no direction, so no tracks "
                         f"to snap port {name} to")
    axis = "x" if direction == "vertical" else "y"
    try:
        tracks = route_net._signal_tracks(db, layer, axis)
    except HtreeError as exc:
        raise HtreeError(exc.msg_id, exc.text.replace("route_net:", f"{NAME}: -snap_to_track:"))
    k = 0 if axis == "x" else 1
    c, half = (rect[k] + rect[k + 2]) / 2, (rect[k + 2] - rect[k]) / 2
    lo = min(boundary[k::2]) if boundary else None
    hi = max(boundary[k::2]) if boundary else None
    fits = [p for p in tracks if lo is None or (p - half >= lo - 1e-6 and p + half <= hi + 1e-6)]
    if not fits:
        raise HtreeError(1, f"{NAME}: -snap_to_track: no signal track of {layer} keeps port "
                         f"{name} inside the design boundary")
    at = min(fits, key=lambda p: (abs(p - c), p))
    rect = list(rect)
    rect[k], rect[k + 2] = at - half, at + half
    pitch = min((b - a for a, b in zip(tracks, tracks[1:])), default=0.0)
    return rect, (f", on the {layer} signal track at {axis} {_num(round(at, 6))} (moved "
                  f"{_num(round(at - c, 6))})"), at - c, pitch


def _ports(session, text):
    """The port names of -port: names or port:<design>/<name> handles."""
    db = session.db
    words = session.split_list(text)
    if not words:
        raise HtreeError(1, f"{NAME}: -port is empty")
    names = []
    for word in words:
        name = word.rpartition("/")[2] if word.startswith("port:") else word
        if not db.has_design() or db.port_row(name) is None:
            raise HtreeError(NO_PORT, f"{NAME}: no port '{word}' of the design (get_db ports "
                             f"lists them)")
        names += [name] if name not in names else []
    return names
