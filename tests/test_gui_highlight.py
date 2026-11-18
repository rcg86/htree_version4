"""Edit > Highlight: a panel on the left; Highlight opens a palette, a colour
paints the selected objects, Clear takes it off them, Close closes the panel."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

pytest.importorskip("scipy")
pytest.importorskip("PySide6")

from test_route_net import DEF, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import _route, routed, via_session  # noqa: F401  (fixtures)

RED, BLUE = "#ff1744", "#2979ff"


@pytest.fixture
def window(routed, tmp_path, monkeypatch):
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))
    routed.eval("gui_show")
    w = app.window()
    out_of(routed)
    yield routed, w
    app.close()


def select(s, w, handles):
    s.db.selection[:] = handles
    w.show_selection()


def items_of(w, pred):
    from core.gui.canvas import NET_KEY, OWNER_KEY
    return [i for i in w.canvas.scene().items() if i.data(OWNER_KEY) is not None
            and pred(i.data(OWNER_KEY), i.data(NET_KEY))]


def fill(item):
    return item.brush().color().name()


def filled(item):
    """Not an outline (a crossing box, a via pad): it has a fill to colour."""
    from PySide6.QtCore import Qt
    return item.brush().style() != Qt.NoBrush


def swatch(w, color):
    from core.gui.highlight import PALETTE
    return w.highlighter.swatches[PALETTE.index(color)]


def test_the_panel_opens_on_the_left_from_edit(window):
    from PySide6.QtCore import Qt
    s, w = window
    assert w.highlighter.isHidden()
    w.act_highlight.trigger()
    assert w.highlighter.isVisible()
    assert w.dockWidgetArea(w.highlighter) == Qt.LeftDockWidgetArea
    assert not w.highlighter.palette.isVisible()
    w.highlighter.highlight_button.click()             # Highlight opens the palette
    assert w.highlighter.palette.isVisible()
    w.highlighter.close_button.click()
    assert w.highlighter.isHidden()


def test_a_colour_paints_the_selected_net_and_clear_takes_it_off(window):
    s, w = window
    net = "sp_L1_inv1_Y"
    mine = items_of(w, lambda owner, n: n == net and owner.startswith(("net_wire:", "via:")))
    other = items_of(w, lambda owner, n: n == "sp_L2_inv1_Y" and owner.startswith("net_wire:"))
    assert mine and other
    before = {i: fill(i) for i in mine + other}
    w.highlighter.open()
    w.highlighter.highlight_button.click()
    select(s, w, [f"spine_net:sp/{net}"])
    swatch(w, RED).click()
    assert all(fill(i) == RED for i in mine if filled(i))
    assert all(i.pen().color().name() == RED for i in mine if i not in w.canvas.highlighted)
    assert all(fill(i) == before[i] for i in other)              # not selected: as it was
    assert "1 object(s) coloured #ff1744" in w.highlighter.note_label.text()
    # deselected, it keeps the colour; a reload paints it again
    select(s, w, [])
    w.refresh()
    again = items_of(w, lambda owner, n: n == net and owner.startswith("net_wire:"))
    assert again and all(i.pen().color().name() == RED for i in again)
    assert all(fill(i) == RED for i in again if filled(i))
    select(s, w, [f"spine_net:sp/{net}"])
    w.highlighter.clear_button.click()
    assert all(i.pen().color().name() != RED for i in again if i not in w.canvas.highlighted)
    assert not w.canvas.painted


def test_one_wire_another_colour_and_clear_all(window):
    s, w = window
    inst = "sp_L1_inv1"
    w.highlighter.open()
    select(s, w, [f"inst:{inst}"])
    swatch(w, BLUE).click()
    cell = items_of(w, lambda owner, n: owner == f"inst:{inst}"
                    or owner.startswith(f"pin:{inst}/"))
    assert cell and all(fill(i) == BLUE for i in cell)
    wire = [i for i in items_of(w, lambda owner, n: owner.startswith("net_wire:sp_L1_inv1_Y/"))
            if filled(i)][0]
    select(s, w, [f"spine_net:sp/sp_L1_inv1_Y"])
    swatch(w, RED).click()
    select(s, w, [wire.data(1)])                       # one wire of the red net: blue
    swatch(w, BLUE).click()
    assert fill(wire) == BLUE
    w.highlighter.clear_button.click()                 # off it: its own, not the net's red
    assert fill(wire) not in (RED, BLUE)
    w.highlighter.clear_all_button.click()
    assert not w.canvas.painted and not s.db.highlights
    assert all(fill(i) != BLUE for i in cell)


def test_nothing_selected(window):
    s, w = window
    select(s, w, [])
    swatch(w, RED).click()
    assert w.highlighter.note_label.text() == "Nothing selected"
    assert not w.canvas.painted


def test_the_highlight_command_paints_the_window(window):
    from core.gui import app
    s, w = window
    hook = app._refresh_if_changed(s)                  # what runs after each typed command
    s.eval("highlight -object sp_L1_inv1_Y -color red")
    hook()
    net = items_of(w, lambda owner, n: n == "sp_L1_inv1_Y" and owner.startswith("net_wire:"))
    assert net and all(i.pen().color().name() == RED for i in net)
    # the panel clears what the command coloured
    select(s, w, ["spine_net:sp/sp_L1_inv1_Y"])
    w.highlighter.clear_button.click()
    assert not w.canvas.painted
    s.eval("highlight -object sp_L1_inv1 -color blue")
    hook()
    assert w.canvas.painted
    s.eval("highlight -clear")
    hook()
    assert not w.canvas.painted


def test_the_status_bar_names_a_stub_wire_with_stub(window):
    """A route_final_stub wire is named <leaf net>_stub, not its leaf net."""
    s, w = window
    for h in s.split_list(s.eval("get_db [get_db stubs] .net_wires")):
        leaf = s.eval(f"get_db {h} .net").partition("/")[2]
        assert w.object_name(h) == f"{leaf}_stub"
    wire = s.split_list(s.eval("get_db net_wires sp_L1_inv1_Y/*"))[0]
    assert w.object_name(wire) == "sp_L1_inv1_Y"            # a net's own wire: its net
