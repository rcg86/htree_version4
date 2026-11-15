"""The vias in the GUI: a via_<bottom>_<top> row of the layer list between the
two layers, with its S P G boxes, and the vias drawn with it."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

from collections import Counter

import pytest

pytest.importorskip("scipy")

from core import vias
from core.gui.layout_data import load_layout, via_layer
from test_edit_tools import _shift, window  # noqa: F401  (window is a fixture)
from test_route_net import DEF, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import _route, routed, via_session  # noqa: F401  (fixtures)
from via_tech import tech_text

ROWS = ["via_D12_H1", "via_H1_H2", "via_H2_G1", "via_G1_G2", "via_G2_IA", "via_IA_IB"]


def names(lay):
    return [l.name for l in lay.layers]


def box_of(r):
    return tuple(float(v) for v in r["rect"].split())


# -- the rows of the layer list (no Qt) -------------------------------------------------

def test_a_via_row_between_its_two_layers(routed):
    lay = load_layout(routed.db)
    # The cut layers C1 .. C6 carry no shapes: the via rows stand for them. XM is a
    # routing layer between IA and IB that no via reaches.
    assert names(lay) == ["D12", "via_D12_H1", "H1", "via_H1_H2", "H2", "via_H2_G1", "G1",
                          "via_G1_G2", "G2", "via_G2_IA", "IA", "via_IA_IB", "XM", "IB", "M1"]
    rows = [l for l in lay.layers if l.via]
    assert [l.name for l in rows] == ROWS
    assert [l.via for l in rows] == [("D12", "H1"), ("H1", "H2"), ("H2", "G1"), ("G1", "G2"),
                                     ("G2", "IA"), ("IA", "IB")]
    assert [l.cut for l in rows] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert [l.port_shapes for l in rows] == [16, 16, 16, 16, 16, 11]     # its vias
    assert all(l.in_tech for l in rows)                         # checked at start
    assert len({l.color for l in rows}) == 6                    # a colour of its own each,
    assert not {l.color for l in rows} & {l.color for l in lay.layers if not l.via}
    assert via_layer("D6", "D7") == "via_D6_D7"                 # the layer names as spelled


def test_row_colours_with_more_layers_than_colours():
    from core.gui.layout_data import PALETTE, LayerInfo, via_row_colors
    real = [LayerInfo(f"L{k}", True, PALETTE[k % len(PALETTE)], 0, 0) for k in range(45)]
    rows = [(f"L{k}", f"L{k + 1}") for k in range(44)]
    colors = via_row_colors(rows, real, len(real))
    of_layer = {l.name: l.color for l in real}
    for before, pair in zip([None] + rows, rows):               # not its layers', nor the
        assert colors[pair] not in (of_layer[pair[0]], of_layer[pair[1]])    # row before's
        assert colors[pair] != colors.get(before)


def test_vias_carry_their_row_and_net_class(routed):
    lay = load_layout(routed.db)
    rows = vias.rows(routed.db)
    assert len(lay.vias) == len(rows) == 91                     # no definition: one box each
    assert all(v.cut and v.type == "rect" for v in lay.vias)
    by = {vias.handle(r): r for r in rows}
    for v in lay.vias:
        r = by[v.handle]
        assert v.layer == via_layer(r["bottom"], r["top"]) and v.between == (r["bottom"], r["top"])
        assert tuple(v.points) == box_of(r)
    assert Counter((v.layer, v.cls) for v in lay.vias if v.layer == "via_D12_H1") == \
        {("via_D12_H1", "signal"): 8, ("via_D12_H1", "power"): 4, ("via_D12_H1", "ground"): 4}
    assert {v.cls for v in lay.vias if v.layer == "via_IA_IB"} == {"signal"}


def test_a_via_definition_gives_a_row_without_vias(via_session, write_lef):
    via_session.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    lay = load_layout(via_session.db)
    assert [l.name for l in lay.layers if l.via] == ROWS
    assert all(l.port_shapes == 0 for l in lay.layers if l.via) and lay.vias == []
    assert not {"C1", "C6"} & set(names(lay))


def test_a_via_without_a_definition_gets_a_row(spine):
    """The tech of tests/data: no cut layers, no via definitions, no D12."""
    lay = load_layout(spine.db)
    assert names(lay) == ["H1", "H2", "via_H2_IA", "G1", "G2", "IA", "IB", "D12", "via_D12_H2",
                          "M1"]                                 # each after its bottom layer
    row = lay.layer("via_H2_IA")
    assert (row.via, row.cut, row.port_shapes, row.in_tech) == (("H2", "IA"), None, 8, True)
    assert lay.layer("via_D12_H2").port_shapes == 8 and not lay.layer("D12").in_tech
    assert len(lay.vias) == 16 and all(v.cut for v in lay.vias)


def test_layer_range_puts_a_row_before_its_top_layer(session, write_lef):
    lef = write_lef(tech_text(), "vt.lef")
    session.eval(f"read_tech -file {{{lef}}} -min_layer H2 -max_layer IB")
    _route(session, write_lef)
    lay = load_layout(session.db)
    # D12 is not listed: the pin vias up to H2 are, before H2.
    assert names(lay) == ["via_D12_H2", "H2", "via_H2_G1", "G1", "via_G1_G2", "G2", "via_G2_IA",
                          "IA", "via_IA_IB", "XM", "IB"]
    assert lay.layer("via_D12_H2").cut is None
    session.eval(f"read_tech -file {{{lef}}} -min_layer IA -max_layer IB")
    lay = load_layout(session.db)
    # No definition of the range joins H2 and IA: the strap vias are H2 to IA. D12 to
    # H2: neither layer is listed, so no row, and those vias are not drawn.
    assert names(lay) == ["via_H2_IA", "IA", "via_IA_IB", "XM", "IB"]
    assert {v.layer for v in lay.vias} == {"via_H2_IA", "via_IA_IB"}
    assert {(r["bottom"], r["top"]) for r in vias.rows(session.db)} == \
        {("D12", "H2"), ("H2", "IA"), ("IA", "IB")}


def test_a_cut_layer_with_shapes_is_listed(via_session, write_lef):
    port = ("PINS 1 ;\n- a + NET a + DIRECTION INPUT + USE SIGNAL\n"
            "  + LAYER C6 ( -50 -50 ) ( 50 50 )\n  + PLACED ( 1000 1000 ) N ;\nEND PINS\n")
    text = DEF.replace("END DESIGN", port + "END DESIGN")
    via_session.eval(f"read_def -file {{{write_lef(text, 'd.def')}}}")
    listed = names(load_layout(via_session.db))
    assert listed[listed.index("IA"):listed.index("IA") + 3] == ["IA", "via_IA_IB", "C6"]
    assert "C5" not in listed


def test_an_assigned_definition_is_drawn_with_its_pads(routed):
    routed.eval("assign_via_for_route -via V_IA_IB")
    lay = load_layout(routed.db)
    mine = [v for v in lay.vias if v.layer == "via_IA_IB"]
    assert Counter(v.cut for v in mine) == {True: 11, False: 22}      # a cut, a pad each side
    r = next(r for r in vias.rows(routed.db) if r["kind"] == "cross")
    shapes = sorted(tuple(round(c - o, 6) for c, o in zip(v.points, (r["x"], r["y"]) * 2))
                    for v in mine if v.handle == vias.handle(r))
    assert shapes == [(-0.2, -0.15, 0.2, 0.15), (-0.15, -0.2, 0.15, 0.2), (-0.1, -0.1, 0.1, 0.1)]
    cut = next(v for v in mine if v.handle == vias.handle(r) and v.cut)
    assert tuple(round(c - o, 6) for c, o in zip(cut.points, (r["x"], r["y"]) * 2)) == \
        (-0.1, -0.1, 0.1, 0.1)
    assert all(v.cut for v in lay.vias if v.layer != "via_IA_IB")     # the others: their box


# -- the window -------------------------------------------------------------------------

@pytest.fixture
def shown(routed, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    routed.eval("gui_show")
    w = app.window()
    w.resize(1000, 800)
    yield routed, w
    app.close()


def seen(w, row, cls=None):
    from core.gui.canvas import CLASS_KEY
    items = [i for i in w.canvas.via_items[row] if cls is None or i.data(CLASS_KEY) == cls]
    assert items
    return {i.isVisible() for i in items}


def test_rows_and_vias_in_the_window(shown):
    from core.gui.canvas import ViaCut
    s, w = shown
    assert [n for n in w.layer_boxes if n.startswith("via_")] == ROWS
    assert list(w.layer_boxes)[:3] == ["D12", "via_D12_H1", "H1"]
    assert not {"C1", "C6"} & set(w.layer_boxes)
    assert all(w.layer_boxes[n].isChecked() for n in ROWS)
    assert w.layer_boxes["via_IA_IB"].text() == "via_IA_IB  (11)"
    assert w.layer_boxes["via_IA_IB"].toolTip() == \
        "via_IA_IB: 11 via(s) between IA and IB, cut layer C6"
    assert w.class_boxes[("via_IA_IB", "power")].toolTip() == \
        "Vias of power nets between IA and IB"
    assert w.object_boxes["vias"].isEnabled() and w.object_boxes["vias"].isChecked()
    assert {n: len(items) for n, items in w.canvas.via_items.items()} == \
        dict(zip(ROWS, [16, 16, 16, 16, 16, 11]))
    assert all(isinstance(i, ViaCut) for items in w.canvas.via_items.values() for i in items)
    assert all(seen(w, n) == {True} for n in ROWS)
    r = next(r for r in vias.rows(s.db) if r["kind"] == "cross")
    item, = w.canvas.owner_items[vias.handle(r)]
    assert w.canvas._rect_of(item) == pytest.approx(box_of(r))
    assert item.pen().color().name() == w.layout.layer("via_IA_IB").color


def test_row_objects_and_class_boxes_show_and_hide(shown):
    s, w = shown
    w.layer_boxes["via_IA_IB"].setChecked(False)                # the row
    assert seen(w, "via_IA_IB") == {False} and seen(w, "via_G2_IA") == {True}
    assert all(i.isVisible() for i in w.canvas.strap_items["IA"])     # the layers stay
    w.layer_boxes["IA"].setChecked(False)                       # a layer: its vias stay
    assert seen(w, "via_G2_IA") == {True}
    w.layer_boxes["IA"].setChecked(True)
    w.layer_boxes["via_IA_IB"].setChecked(True)
    assert seen(w, "via_IA_IB") == {True}
    w.object_boxes["vias"].setChecked(False)                    # Objects: Vias
    assert all(seen(w, n) == {False} for n in ROWS)
    assert all(i.isVisible() for i in w.canvas.strap_items["IA"])
    w.object_boxes["vias"].setChecked(True)
    w.class_boxes[("via_D12_H1", "power")].setChecked(False)    # P of one row
    assert seen(w, "via_D12_H1", "power") == {False}
    assert seen(w, "via_D12_H1", "ground") == seen(w, "via_D12_H1", "signal") == {True}
    assert seen(w, "via_H1_H2", "power") == {True}
    assert not w.all_class_boxes["power"].isChecked()
    w.all_class_boxes["ground"].setChecked(False)               # G of every layer and row
    assert all(seen(w, n, "ground") == {False} for n in ROWS[:5])
    assert seen(w, "via_G2_IA", "signal") == {True}
    w.all_class_boxes["power"].setChecked(True)
    w.all_class_boxes["ground"].setChecked(True)
    assert all(seen(w, n) == {True} for n in ROWS)
    s.eval("get_db nets")                                       # a command: the choice is kept
    w.layer_boxes["via_H2_G1"].setChecked(False)
    s.eval("delete_route -nets [get_db nets .name]")            # the view reloads
    assert not w.layer_boxes["via_H2_G1"].isChecked() and seen(w, "via_H2_G1") == {False}
    assert "via_IA_IB" not in w.canvas.via_items                # the crossings went
    assert w.layer_boxes["via_IA_IB"].text() == "via_IA_IB"     # the definition: a row still


def test_click_selects_a_via_and_a_crossing_box_stays(shown):
    from core.gui.canvas import scene
    s, w = shown
    rows = vias.rows(s.db)
    pin = next(r for r in rows if r["kind"] == "pin" and r["bottom"] == "D12")
    x1, y1, x2, y2 = box_of(pin)
    centre = scene((x1 + x2) / 2, (y1 + y2) / 2)
    w.canvas.zoom_to(w.canvas.owner_items[vias.handle(pin)][0].sceneBoundingRect())
    assert w.canvas.owner_at(w.canvas.mapFromScene(centre)).startswith("via:")
    w.layer_boxes["via_H1_H2"].setChecked(False)                # the via above it, same place
    assert w.canvas.owner_at(w.canvas.mapFromScene(centre)) == vias.handle(pin)
    w.on_select([vias.handle(pin)], "replace")
    assert s.eval("get_db selected") == vias.handle(pin)
    text = w.sel_label.text()
    assert f"{vias.handle(pin)}  pin  D12 to H1 through C1  via_def none" in text
    assert f"of {pin['source']}" in text
    w.object_boxes["vias"].setChecked(False)                    # hidden: the wire under it
    assert w.canvas.owner_at(w.canvas.mapFromScene(centre)) == pin["source"]
    w.object_boxes["vias"].setChecked(True)
    cross = next(r for r in rows if r["kind"] == "cross")
    x1, y1, x2, y2 = box_of(cross)
    centre = scene((x1 + x2) / 2, (y1 + y2) / 2)
    w.canvas.zoom_to(w.canvas.owner_items[vias.handle(cross)][0].sceneBoundingRect())
    assert w.canvas.owner_at(w.canvas.mapFromScene(centre)) == cross["source"]   # its box
    owners = w.canvas.owners_in(w.canvas.owner_items[vias.handle(cross)][0]
                                .sceneBoundingRect().adjusted(-0.01, -0.01, 0.01, 0.01))
    assert vias.handle(cross) in owners and cross["source"] in owners     # a box takes both


def test_an_assigned_definition_in_the_window(shown):
    from core.gui.canvas import ViaCut
    s, w = shown
    s.eval("assign_via_for_route -via V_IA_IB")                 # the view reloads
    items = w.canvas.via_items["via_IA_IB"]
    assert Counter(isinstance(i, ViaCut) for i in items) == {True: 11, False: 22}
    assert all(i.zValue() > p.zValue() for i in items if isinstance(i, ViaCut)
               for p in items if not isinstance(p, ViaCut))     # the cut over its pads
    assert all(i.isVisible() for i in items)
    r = next(r for r in vias.rows(s.db) if r["kind"] == "cross")
    assert len(w.canvas.owner_items[vias.handle(r)]) == 3
    w.on_select([vias.handle(r)], "replace")
    assert "through C6  via_def V_IA_IB  at" in w.sel_label.text()


def test_no_second_reload_after_a_command_that_reads(shown):
    s, w = shown
    w.canvas.scale(2, 2)                                        # a reload would fit the view
    transform = w.canvas.transform()
    items = list(w.canvas.via_items["via_IA_IB"])
    s.eval("get_db nets")
    s.eval("get_db vias")
    assert w.canvas.transform() == transform
    assert w.canvas.via_items["via_IA_IB"] == items             # not drawn again


def test_an_edit_redraws_the_vias_and_keeps_the_view(window):
    s, w = window                                               # u1 with its pin routes
    assert [n for n in w.layer_boxes if n.startswith("via_")] == ["via_H2_IA", "via_D12_H2"]
    strap = next(r for r in vias.rows(s.db) if r["kind"] == "strap"
                 and r["source"].startswith("pin_wire:u1/A"))
    assert strap["net"] == "SIGNAL"
    before = box_of(strap)
    item, = w.canvas.owner_items[vias.handle(strap)]
    assert w.canvas._rect_of(item) == pytest.approx(before)
    w.class_boxes[("via_D12_H2", "power")].setChecked(False)
    w.on_select(["strap:u1/5"], "replace")                      # the strap pin A reaches
    w.act_tool_move.setChecked(True)
    transform = w.canvas.transform()
    _shift(w, "down")                                           # onto the next track down
    assert "move_wire -wires {strap:u1/5} -next_track down" in out_of(s)
    assert w.canvas.transform() == transform                    # no reload
    after = next(r for r in vias.rows(s.db) if r["kind"] == "strap"
                 and r["source"].startswith("pin_wire:u1/A"))
    assert box_of(after) != before
    drawn = {h: its for h, its in w.canvas.owner_items.items() if h.startswith("via:")}
    assert set(drawn) == {vias.handle(r) for r in vias.rows(s.db)}
    assert w.canvas._rect_of(drawn[vias.handle(after)][0]) == pytest.approx(box_of(after))
    assert not w.class_boxes[("via_D12_H2", "power")].isChecked()     # the choice is kept
    assert not any(i.isVisible() for i in w.canvas.via_items["via_D12_H2"]
                   if i.data(3) == "power")
    w.undo_edit()
    back = next(r for r in vias.rows(s.db) if r["kind"] == "strap"
                and r["source"].startswith("pin_wire:u1/A"))
    assert box_of(back) == pytest.approx(before) and w.canvas.transform() == transform
    assert w.canvas._rect_of(w.canvas.owner_items[vias.handle(back)][0]) == pytest.approx(before)


def test_an_edit_that_makes_the_first_via_of_two_layers_adds_its_row(window):
    s, w = window
    assert "via_IA_IB" not in w.layer_boxes
    w.layer_boxes["via_H2_IA"].setChecked(False)
    transform = w.canvas.transform()
    s.db.set_net_wires("n1", [("wire", "IA", "0 8 6 8.36"), ("wire", "IB", "3 6 3.36 9"),
                              ("cross", "IA/IB", "3 8 3.36 8.36")])
    w._edited = ["strap:u1/3"]                                  # as an edit tool does
    try:
        w.refresh()
    finally:
        w._edited = None
    assert w.canvas.transform() == transform                    # no reload
    assert list(w.layer_boxes)[list(w.layer_boxes).index("IA"):][:2] == ["IA", "via_IA_IB"]
    assert w.layer_boxes["via_IA_IB"].isChecked() and "via_IA_IB" in w.canvas.visible_layers
    item, = w.canvas.via_items["via_IA_IB"]
    assert item.isVisible() and w.canvas._rect_of(item) == pytest.approx((3, 8, 3.36, 8.36))
    assert not w.layer_boxes["via_H2_IA"].isChecked()           # the choice is kept
    assert not any(i.isVisible() for i in w.canvas.via_items["via_H2_IA"])
