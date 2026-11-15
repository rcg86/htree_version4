"""assign_via_for_route -via {<via_def> ...} [-nets {<net> ...}]: name the via
definition the routes use at each cut layer.

    assign_via_for_route -via {VIA_IA_IB VIA_G2_IA}
    assign_via_for_route -via VIA_IA_IB_WIDE -nets {clk_L1 clk_L2}

A via between two layers has no definition until one is assigned for those
layers: its shape is then the box where the two wires overlap. Each named
definition is used for every via between its bottom and top layer, on the
nets given or, without -nets, on every net that has none of its own.
"""

from collections import Counter

from core import objects, vias
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "assign_via_for_route"
SUMMARY = "Name the via definition the routes use between two layers"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-via": "value", "-nets": "value", "-reset": "flag"}

USAGE = 1
UNKNOWN_VIA = 240
NO_LAYERS = 241
SAME_LAYERS = 242
REPLACED = 243
NET_WITHOUT_VIAS = 244


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if "-via" in opts and opts["-reset"]:
        raise HtreeError(USAGE, "assign_via_for_route: give -via or -reset, not both")
    nets = _nets(session, opts["-nets"]) if "-nets" in opts else None
    if nets is not None and not nets:
        raise HtreeError(USAGE, "assign_via_for_route: -nets is empty")
    if opts["-reset"]:
        n = db.clear_via_assignments(nets)
        info(f"Removed {n} via assignment(s)"
             + (f" of {' '.join(nets)}" if nets else ""), out)
        _report(db, out)
        return None
    if "-via" not in opts:
        if nets is not None:
            raise HtreeError(USAGE, "assign_via_for_route: -nets needs -via or -reset. Usage: "
                             "assign_via_for_route -via {<via_def> ...} [-nets {<net> ...}]")
        _report(db, out)
        return None

    names = [objects.name_of(w) if w.startswith("via_def:") else w
             for w in session.split_list(opts["-via"])]
    if not names:
        raise HtreeError(USAGE, "assign_via_for_route: -via is empty")
    stacks = vias.definition_layers(db)
    chosen = {}                                   # (bottom, top) -> (cut, definition)
    for name in names:
        if name not in stacks:
            raise HtreeError(UNKNOWN_VIA, f"assign_via_for_route: no via definition '{name}' "
                             f"({len(stacks)} in the database; get_db via_defs lists them)")
        bottom, cut, top = stacks[name]
        if cut is None:
            layers = objects.get_attr(db, f"via_def:{name}", "layers")
            raise HtreeError(NO_LAYERS, f"assign_via_for_route: via definition '{name}' has "
                             f"shapes on {' '.join(layers) or 'no layer'}: it needs one cut "
                             f"layer and two layers of the tech, which this is not")
        if (bottom, top) in chosen and chosen[bottom, top][1] != name:
            raise HtreeError(SAME_LAYERS, f"assign_via_for_route: '{chosen[bottom, top][1]}' "
                             f"and '{name}' both join {bottom} and {top}; name one of them")
        chosen[bottom, top] = (cut, name)

    have = Counter(r["net"] for r in vias.rows(db))
    for net in nets or []:
        if net not in have:
            warn(NET_WITHOUT_VIAS, f"net '{net}' has no via now; the assignment is kept "
                 f"for when it is routed", out)
    for (bottom, top), (cut, name) in chosen.items():
        for net in nets or [""]:
            old = db.set_via_assignment(bottom, cut, top, net, name)
            if old is not None and old != name:
                warn(REPLACED, f"{bottom} to {top}"
                     + (f" on net {net}" if net else "")
                     + f": via '{old}' replaced by '{name}'", out)
    _report(db, out)
    return None


def _nets(session, text):
    """Net names of -nets: names, or net objects (spine_net, stub)."""
    names = []
    for word in session.split_list(text):
        if word.startswith("stub:"):
            net = objects.get_attr(session.db, word, "net")
            word = net or word
        if word.startswith("spine_net:"):
            objects.check_exists(session.db, word)
            word = objects.name_of(word)
        if word not in names:
            names.append(word)
    return names


def _report(db, out):
    rows = db.via_assignment_rows()
    stacks = vias.definition_layers(db)
    all_vias = vias.rows(db)
    if not rows:
        info("No via assignments", out)
    else:
        info("Via assignments (layers, cut layer, net, via definition, vias using it):", out)
    wide = max((len(r["via_def"]) for r in rows), default=0)
    for r in rows:
        used = sum(1 for v in all_vias if v["via_def"] == r["via_def"]
                   and (v["bottom"], v["top"]) == (r["bottom"], r["top"])
                   and (not r["net"] or v["net"] == r["net"]))
        gone = "" if stacks.get(r["via_def"]) == (r["bottom"], r["cut"], r["top"]) else \
            "  (no such definition now: not used)"
        info(f"  {r['bottom'] + '/' + r['top']:<10} {r['cut']:<6} "
             f"{r['net'] or '(every net)':<16} {r['via_def']:<{wide}}  {used}{gone}", out)
    if all_vias:
        without = Counter(f"{v['bottom']}/{v['top']}" for v in all_vias if v["via_def"] is None)
        info(f"Vias: {len(all_vias)}, with a definition {len(all_vias) - sum(without.values())}"
             + (", without: " + " ".join(f"{pair}({n})" for pair, n in without.items())
                if without else ""), out)
