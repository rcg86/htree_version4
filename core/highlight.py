"""The colours of highlight and of the GUI's Highlight panel.

db.highlights is [(handle, colour)], session state: the last entry that
covers a drawn shape gives its colour ('#rrggbb'), None its own. A wire,
strap, pin wire, via, pin or port covers itself; an instance itself and its
pins; a net, stub or spine what show_only shows of it (a net: its wires,
shields, vias and the pins on it).
"""

import re

from core import objects

# The names highlight -color takes, and the Highlight palette, in its order.
COLORS = {"red": "#ff1744", "orange": "#ff9100", "yellow": "#ffea00", "lime": "#76ff03",
          "green": "#00e676", "teal": "#1de9b6", "cyan": "#00e5ff", "blue": "#2979ff",
          "indigo": "#3d5afe", "purple": "#d500f9", "magenta": "#f50057", "pink": "#ff80ab",
          "white": "#ffffff", "grey": "#bdbdbd", "brown": "#8d6e63", "black": "#000000"}
HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
GROUPS = ("spine", "spine_net", "net", "stub")    # coloured with what show_only shows of them
# The drawn items a group's colour takes (not ports, which show_only keeps on).
ROUTED = ("inst", "pin", "pin_wire", "strap", "net_wire", "via", "stub", "spine_net")


def color_of(text):
    """'#rrggbb' of a colour name of COLORS ('gray' too) or #rgb / #rrggbb;
    None when it is neither."""
    word = text.strip().lower()
    word = "grey" if word == "gray" else word
    if word in COLORS:
        return COLORS[word]
    if HEX.fullmatch(word):
        h = word[1:]
        return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)
    return None


def paint(db, handles, color):
    """Colour these objects; a colour given before to one of them is replaced."""
    handles = list(dict.fromkeys(handles))
    db.highlights[:] = [(h, c) for h, c in db.highlights if h not in handles] + \
        [(h, color) for h in handles]


def clear(db, handles=None):
    """Take the colour off these objects (None: off every object). One
    coloured with its net or spine goes back to its own colour too."""
    if handles is None:
        db.highlights.clear()
        return
    handles = list(dict.fromkeys(handles))
    db.highlights[:] = [(h, c) for h, c in db.highlights if h not in handles]
    if db.highlights:
        db.highlights += [(h, None) for h in handles]


def coloured(db):
    """[(handle, colour)] of the objects given a colour (not cleared)."""
    return [(h, c) for h, c in db.highlights if c is not None]


def drop_gone(db):
    """Forget the colours of objects that are gone (a deleted wire)."""
    db.highlights[:] = [(h, c) for h, c in db.highlights
                        if objects.obj_type(h) == "net" or objects.exists(db, h)]


def covers(db, handle):
    """covers(handle, owner, net, source) of a canvas item: does the colour
    of the object handle take it."""
    kind, name = objects.obj_type(handle), handle.partition(":")[2]
    scope = None
    if kind in GROUPS:
        from core.commands.show_only import scope_of
        scope = scope_of(db, [handle])
    pins = f"pin:{name}/" if kind == "inst" else None

    def takes(item, owner, net, source):
        if handle in (item, owner) or (pins and owner.startswith(pins)):
            return True
        return scope is not None and owner.partition(":")[0] in ROUTED and \
            scope.shows(owner, net, source)
    return takes
