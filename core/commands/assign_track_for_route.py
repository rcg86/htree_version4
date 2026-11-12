"""assign_track_for_route -net {<net|-> ...} -layer <layer>: give a layer's
routing tracks a repeating net pattern.

    assign_track_for_route -net {VDD_SOC, -, VSS, -} -layer IA

Track 1 (the lowest coordinate) gets VDD_SOC, track 2 any signal ('-'),
track 3 VSS, track 4 any signal, track 5 VDD_SOC again, and so on. 'NA'
leaves a track blank: nothing may use it.
"""

from core.db import _num
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "assign_track_for_route"
SUMMARY = "Assign a repeating net pattern (e.g. VDD_SOC - VSS -) to a layer's tracks"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-net": "value", "-layer": "value"}

USAGE = 1
NO_LAYER = 110
NO_TRACKS = 111
UNKNOWN_NET = 112
REPLACED = 113
SIGNAL = "-"          # any signal may use the track
BLANK = "NA"          # the track is left blank: not used at all
RESERVED = (SIGNAL, BLANK)
# Tech DIRECTION -> the DEF TRACKS whose lines run that way.
TRACKS_FOR = {"horizontal": "y", "vertical": "x"}


def parse_pattern(text):
    """'VDD_SOC, - , VSS, -' -> ['VDD_SOC', '-', 'VSS', '-'] (commas optional)."""
    return [w for w in text.replace(",", " ").split() if w]


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    if "-net" not in opts or "-layer" not in opts:
        raise HtreeError(USAGE, "assign_track_for_route: -net and -layer are required. "
                         "Usage: assign_track_for_route -net {VDD_SOC - VSS -} -layer IA")
    pattern = parse_pattern(opts["-net"])
    layer = opts["-layer"]
    if not pattern:
        raise HtreeError(USAGE, "assign_track_for_route: -net is empty")
    if all(n in RESERVED for n in pattern):
        raise HtreeError(USAGE, "assign_track_for_route: -net names no net, only "
                         "'-' (signal) and 'NA' (blank)")

    db = session.db
    if not db.has_tech():
        raise HtreeError(NO_LAYER, "assign_track_for_route: no tech data; run read_tech first")
    row = db.layer_row(layer)
    if row is None:
        raise HtreeError(NO_LAYER, f"assign_track_for_route: layer '{layer}' is not in tech "
                         f"(tech layers: {' '.join(db.layer_names())})")
    direction = TRACKS_FOR.get(row["direction"] or "")
    if direction is None:
        raise HtreeError(NO_LAYER, f"assign_track_for_route: layer {layer} has no "
                         f"HORIZONTAL or VERTICAL direction in tech")
    if not db.has_design():
        raise HtreeError(NO_TRACKS, "assign_track_for_route: no design; run read_def first")
    positions = db.track_positions(layer, direction)
    if not positions:
        have = db.track_directions(layer)
        raise HtreeError(NO_TRACKS, f"assign_track_for_route: layer {layer} is "
                         f"{row['direction']}, so it needs DEF 'TRACKS {direction.upper()}' "
                         f"patterns; the DEF has "
                         + (f"only TRACKS {' '.join(d.upper() for d in have)} for {layer}"
                            if have else f"no tracks on {layer}"))

    port_nets = {r[0] for r in db.conn.execute("SELECT DISTINCT net FROM port")}
    for net in dict.fromkeys(n for n in pattern if n not in RESERVED):
        if net not in port_nets:
            warn(UNKNOWN_NET, f"net '{net}' is not the net of any port in design "
                 f"{db.design_row()['name']}; check the spelling", session.out)
    if db.set_track_assignment(layer, direction, pattern):
        warn(REPLACED, f"replacing the previous track assignment of {layer}", session.out)

    axis = "y" if direction == "y" else "x"
    out = session.out
    info(f"Track assignment for {layer} ({row['direction']}, DEF TRACKS {direction.upper()}): "
         f"{len(positions)} tracks, {axis} {_num(positions[0])} .. {_num(positions[-1])}", out)
    info(f"  Pattern (repeats every {len(pattern)}): {' '.join(pattern)}", out)
    for net, count, first in summarize(pattern, positions):
        label = {SIGNAL: "signal", BLANK: "blank (NA)"}.get(net, net)
        info(f"  {label:<12}: {count} tracks, first at {axis} {_num(first)}", out)
    return None


def summarize(pattern, positions):
    """[(net, track count, first coordinate)]: nets in pattern order, then '-'
    (signal), then 'NA' (blank)."""
    seen = {}
    for i, c in enumerate(positions):
        net = pattern[i % len(pattern)]
        if net not in seen:
            seen[net] = [0, c]
        seen[net][0] += 1
    order = [n for n in dict.fromkeys(pattern) if n not in RESERVED] + \
        [n for n in RESERVED if n in seen]
    return [(n, seen[n][0], seen[n][1]) for n in order if n in seen]
