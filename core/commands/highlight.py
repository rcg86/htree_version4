"""highlight -object <objects> -color <colour> | -clear [-object <objects>]:
colour objects in the GUI, as Edit > Highlight does.

    highlight -object sp_L1_inv1_Y -color red
    highlight -object [get_db selected] -color #00ff00
    highlight -clear -object sp_L1_inv1_Y
    highlight -clear

A wire, strap, pin wire, via, pin or port is coloured alone, an instance
with its pins, a net, stub or spine with what show_only shows of it
(core/highlight.py). The colours are session state (db.highlights): the
database does not change.
"""

from core import highlight, objects
from core.commands.show_only import NO_OBJ, net_handles, resolve
from core.messages import HtreeError, info
from core.options import parse_options

NAME = "highlight"
SUMMARY = "Colour objects in the GUI (-clear takes the colour off)"
# Options and their kind (value | flag), also used by <tab> completion.
OPTIONS = {"-object": "value", "-color": "value", "-clear": "flag"}
USAGE = "highlight -object <objects> -color <colour> | -clear [-object <objects>]"

BAD_COLOR = 290
NO_OBJECT = 291
LISTED = 10              # names printed


def handles(session, text):
    """The handles of the words of -object: a handle stands for itself (a
    wire, a via, a pin, a port too), a name or pattern for every spine,
    instance, net and stub of that name (as show_only)."""
    db = session.db
    nets = None
    found = []
    for word in session.split_list(text):
        if word.startswith("net:"):
            nets = nets if nets is not None else net_handles(db)
            if nets.get(word[4:]) != word:
                raise HtreeError(NO_OBJECT, f"highlight: no net '{word[4:]}'. Nothing is "
                                 f"coloured")
            hits = [word]
        elif objects.is_handle(word):
            objects.check_exists(db, word)
            hits = [word]
        else:
            try:
                hits = resolve(session, word)
            except HtreeError as exc:
                if exc.msg_id != NO_OBJ:
                    raise
                raise HtreeError(NO_OBJECT, f"highlight: no net, instance, spine or stub "
                                 f"'{word}' (get_db nets, get_db insts, get_db spines). "
                                 f"Nothing is coloured")
        found += [h for h in hits if h not in found]
    return found


def _names(found):
    more = f" ... (+{len(found) - LISTED} more)" if len(found) > LISTED else ""
    return " ".join(found[:LISTED]) + more


def run(session, argv):
    opts, _ = parse_options(NAME, argv, OPTIONS)
    db, out = session.db, session.out
    if opts["-clear"]:
        if "-color" in opts:
            raise HtreeError(1, f"highlight: -clear takes no -color. Usage: {USAGE}")
        if "-object" not in opts:
            n = len(highlight.coloured(db))
            highlight.clear(db)
            info(f"highlight: colour taken off every object ({n})" if n else
                 "highlight: nothing was coloured", out)
            return None
        found = handles(session, opts["-object"])
        highlight.clear(db, found)
        info(f"highlight: colour taken off {len(found)} object(s): {_names(found)}", out)
        return found
    if "-object" not in opts or "-color" not in opts:
        raise HtreeError(1, f"highlight: give -object and -color, or -clear. Usage: {USAGE}")
    color = highlight.color_of(opts["-color"])
    if color is None:
        raise HtreeError(BAD_COLOR, f"highlight: '{opts['-color']}' is not a colour: give "
                         f"#rrggbb, #rgb or one of {', '.join(highlight.COLORS)}")
    found = handles(session, opts["-object"])
    if not found:
        raise HtreeError(1, f"highlight: -object is empty. Usage: {USAGE}")
    highlight.paint(db, found, color)
    info(f"highlight: {len(found)} object(s) coloured {color}: {_names(found)}", out)
    return found
