"""remove_layer -layer <layers>: take layers out of the tech data; add_layer
puts them back.

    remove_layer -layer XM
    remove_layer -layer {H1 H2}
    remove_layer -layer [get_db layers -if {.type == masterslice}]

A layer removed is, for every command, a layer that is not in tech, as one a
layer range of read_tech leaves out; the GUI does not list it. The vias of
the tech LEF with a shape on it go with it. What the database has on the
layer (route rules, track assignments, wires, pin and port shapes) stays.
"""

import fnmatch

from core import objects
from core.commands.read_tech import LAYER_IN_USE, layers_in_use
from core.messages import HtreeError, info, warn
from core.options import parse_options

NAME = "remove_layer"
SUMMARY = "Remove layers from the tech data (add_layer puts them back)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-layer": "value"}
USAGE = "remove_layer -layer <layers>"

NOT_A_LAYER = 17
NO_LAYER_LEFT = 18


def layer_words(cmd, opts, usage):
    """The words of -layer: names or patterns, with or without 'layer:'."""
    words = [w.partition(":")[2] if w.startswith("layer:") else w
             for w in (opts.get("-layer") or "").split()]
    if not words:
        raise HtreeError(1, f"{cmd}: -layer is required: layer names or patterns. "
                         f"Usage: {usage}")
    return words


def match(words, names):
    """({name of names a word names or matches}, [words that match none])."""
    hits, missed = set(), []
    for word in words:
        found = [word] if word in names else [n for n in names if fnmatch.fnmatchcase(n, word)]
        hits.update(found)
        if not found:
            missed.append(word)
    return hits, missed


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    words = layer_words(NAME, opts, USAGE)
    db = session.db
    objects.require_tech(db)
    names = db.layer_names()
    hits, missed = match(words, names)
    if missed:
        raise HtreeError(NOT_A_LAYER, f"remove_layer: {' '.join(missed)}: not in tech (tech "
                         f"layers: {' '.join(names) or 'none'}). Nothing is removed")
    out = [n for n in names if n in hits]
    if len(out) == len(names):
        raise HtreeError(NO_LAYER_LEFT, f"remove_layer: -layer names every tech layer "
                         f"({' '.join(names)}); one has to stay. Nothing is removed")
    used = layers_in_use(db)
    vias = db.remove_layers(out)

    left = db.layer_names()
    info(f"remove_layer: removed {len(out)} layer(s) from tech: {' '.join(out)}", session.out)
    info(f"  Layers      : {len(left)} ({' '.join(left)})", session.out)
    if vias:
        info(f"  Vias        : {len(vias)} removed, a layer of theirs is removed "
             f"({' '.join(vias)})", session.out)
    info("  add_layer -layer <layers> puts them back", session.out)
    for name in out:
        if name in used:
            warn(LAYER_IN_USE, f"layer {name} is removed, and {', '.join(used[name])} of the "
                 f"database are on it: it is no tech layer now. add_layer -layer {name} "
                 f"puts it back", session.out)
    return out
