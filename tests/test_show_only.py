"""show_only: draw only some nets, instances or spines in the GUI, the other
instances and net routing hidden; -show_all draws everything again."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import tkinter

import pytest

pytest.importorskip("scipy")

from core import vias
from core.commands.show_only import Scope, scope
from core.gui.layout_data import load_layout
from test_gui_vias import shown  # noqa: F401  (a fixture)
from test_route_net import spine  # noqa: F401  (spine is a fixture)
from test_route_pin import out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import routed, via_session  # noqa: F401  (fixtures)

NET = "spine_net:sp/sp_L1_inv1_Y"


def drawn(s):
    """{kind: handles} of the instances, pins, centre lines, route shapes and
    vias the filter of the session leaves on the display (no Qt)."""
    sc, lay = scope(s.db), load_layout(s.db)
    found = {"inst": [i.handle for i in lay.insts],
             "pin": [f"pin:{i.handle[5:]}/{p[0]}" for i in lay.insts for p in i.pins],
             "line": [f"{kind}:{sp.handle[6:]}/{n}" for sp in lay.spines
                      for kind, lines in (("stub", sp.stubs), ("spine_net", sp.segments))
                      for n, _ in lines],
             "route": [st.handle for st in lay.straps + lay.pin_wires + lay.net_wires
                       if sc is None or sc.shows(st.handle, st.net)],
             "via": [v.handle for v in lay.vias
                     if sc is None or sc.shows(v.handle, v.net, v.source)]}
    for kind in ("inst", "pin", "line"):
        found[kind] = [h for h in found[kind] if sc is None or sc.shows(h)]
    return {kind: sorted(set(hs)) for kind, hs in found.items()}


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def pin_layers(s, net=None, inst=None):
    """The handles of route_pin's pieces under the pin wires (H1, kind pin_layer) of a
    net or an instance."""
    return [f"net_wire:{r['net']}/{r['seq']}" for r in s.db.net_wire_rows()
            if r["kind"] == "pin_layer" and (net is None or r["shield_net"] == net)
            and (inst is None or r["net"] == f"pg:{inst}")]


def err(s, script):
    with pytest.raises(tkinter.TclError) as e:
        s.eval(script)
    return str(e.value)


# -- what is shown (no Qt) --------------------------------------------------------------

def test_a_net_shows_its_routing_and_its_pins(routed):
    s = routed
    everything = drawn(s)
    assert s.eval("show_only -object sp_L1_inv1_Y") == NET
    text = out_of(s)
    assert "show_only: showing only 1 object(s); the other instances and net routing are " \
        "hidden" in text
    assert "  Nets        : 1 (sp/sp_L1_inv1_Y)" in text
    assert "show_only -show_all shows everything again" in text
    assert s.db.show_only == [NET]
    got = drawn(s)
    assert got["inst"] == []                                    # not the cells of its pins
    assert got["pin"] == ["pin:sp_L1_inv1/Y", "pin:sp_L2_inv1/A"]
    assert got["line"] == [NET]
    wires = lst(s, f"get_db {NET} .net_wires")
    # with the H1 piece under each of its pin wires
    assert len(pin_layers(s, "sp_L1_inv1_Y")) == 2
    assert got["route"] == sorted(wires + ["pin_wire:sp_L1_inv1/Y", "pin_wire:sp_L2_inv1/A",
                                           "strap:sp_L1_inv1/3", "strap:sp_L2_inv1/5"]
                                  + pin_layers(s, "sp_L1_inv1_Y"))
    assert got["via"] == sorted(lst(s, f"get_db {NET} .vias"))  # its pin stacks too
    assert len(got["route"]) < len(everything["route"]) and len(got["via"]) < \
        len(everything["via"])


def test_an_instance_shows_its_cell_and_pin_routes(routed):
    s = routed
    assert s.eval("show_only -object inst:sp_L2_inv1") == "inst:sp_L2_inv1"
    assert "  Instances   : 1 (sp_L2_inv1)" in out_of(s)
    got = drawn(s)
    assert got["inst"] == ["inst:sp_L2_inv1"]
    assert got["pin"] == sorted(lst(s, "get_db inst:sp_L2_inv1 .pins"))
    assert got["line"] == []
    assert got["route"] == sorted(lst(s, "get_db inst:sp_L2_inv1 .straps") +
                                  lst(s, "get_db inst:sp_L2_inv1 .pin_wires") +
                                  pin_layers(s, inst="sp_L2_inv1"))
    assert got["via"] == sorted(vias.handle(r) for r in vias.rows(s.db)
                                if r["source"].startswith("pin_wire:sp_L2_inv1/"))
    assert got["via"]


def test_a_spine_shows_all_of_it(routed):
    s = routed
    everything = drawn(s)
    assert s.eval("show_only -object sp") == "spine:sp"        # the name of the spine
    assert "  Spines      : 1 (sp)" in out_of(s)
    assert drawn(s) == everything                               # the design is this spine
    s.eval("create_inst -name u1 -ref_cell INV_RP -location {40 40}")
    s.eval("route_pin -inst u1")
    assert drawn(s) == everything                               # u1 is not of the spine
    s.eval("show_only -show_all")
    assert "inst:u1" in drawn(s)["inst"] and "strap:u1/1" in drawn(s)["route"]
    assert s.eval("show_only -object spine:sp") == "spine:sp"
    assert drawn(s) == everything


def test_a_stub_shows_its_bar_wires_and_vias(routed):
    s = routed
    assert s.eval("show_only -object stub:sp/stub1") == "stub:sp/stub1"
    assert "  Stubs       : 1 (sp/stub1)" in out_of(s)
    got = drawn(s)
    assert got["inst"] == got["pin"] == []
    assert got["line"] == ["stub:sp/stub1"]
    assert got["route"] == sorted(lst(s, "get_db stub:sp/stub1 .net_wires")) and got["route"]
    assert got["via"] == sorted(lst(s, "get_db stub:sp/stub1 .vias")) and got["via"]


def test_a_power_net_shows_the_shapes_on_it(routed):
    s = routed
    assert s.eval("show_only -object VSS") == "net:VSS"         # no net object: by name
    got = drawn(s)
    assert got["inst"] == got["pin"] == got["line"] == []
    lay = load_layout(s.db)
    on_vss = [st.handle for st in lay.straps + lay.pin_wires + lay.net_wires if st.net == "VSS"]
    # the straps and pin wires, and an H1 piece under each VSS pin wire
    assert got["route"] == sorted(on_vss) and len(on_vss) == 12 + 4
    assert set(pin_layers(s, "VSS")) <= set(on_vss) and len(pin_layers(s, "VSS")) == 4
    assert got["via"] == sorted(v.handle for v in lay.vias if v.net == "VSS")
    assert s.eval("show_only -object net:VSS") == "net:VSS"
    assert "HT4-270" in err(s, "show_only -object SIGNAL")     # route_pin's placeholder net


def test_names_patterns_and_several_objects(routed):
    s = routed
    # A name or a pattern takes every spine, instance, net and stub of the name.
    assert lst(s, "show_only -object sp_L3*") == [
        "inst:sp_L3_inv1", "inst:sp_L3_inv2", "spine_net:sp/sp_L3_inv1_Y",
        "spine_net:sp/sp_L3_inv2_Y"]
    text = out_of(s)
    assert "showing only 4 object(s)" in text
    assert "  Instances   : 2 (sp_L3_inv1 sp_L3_inv2)" in text
    assert "  Nets        : 2 (sp/sp_L3_inv1_Y sp/sp_L3_inv2_Y)" in text
    assert lst(s, "show_only -object stub?") == ["stub:sp/stub1", "stub:sp/stub2"]
    got = lst(s, "show_only -object {sp_L1_inv1_Y inst:sp_L1_inv1 sp_L1_inv1_Y sp_L2_inv1}")
    assert got == [NET, "inst:sp_L1_inv1", "inst:sp_L2_inv1"]   # each once
    shown_ = drawn(s)
    assert shown_["inst"] == ["inst:sp_L1_inv1", "inst:sp_L2_inv1"] and shown_["line"] == [NET]
    assert lst(s, "show_only -object [get_db insts *L3*]") == ["inst:sp_L3_inv1",
                                                               "inst:sp_L3_inv2"]


def test_a_second_show_only_replaces_the_first(routed):
    s = routed
    s.eval("show_only -object sp_L1_inv1")
    s.eval("show_only -object sp_L2_inv1")
    assert s.db.show_only == ["inst:sp_L2_inv1"] and drawn(s)["inst"] == ["inst:sp_L2_inv1"]


def test_a_pin_wire_or_via_stands_for_its_instance_or_net(routed):
    s = routed
    wire = lst(s, f"get_db {NET} .net_wires")[0]
    cross = next(vias.handle(r) for r in vias.rows(s.db, "sp_L1_inv1_Y") if r["kind"] == "cross")
    stack = next(vias.handle(r) for r in vias.rows(s.db) if r["kind"] == "strap"
                 and r["source"] == "pin_wire:sp_L3_inv1/VSS")
    assert s.eval(f"show_only -object {wire}") == NET
    assert s.eval(f"show_only -object {cross}") == NET
    assert s.eval(f"show_only -object {stack}") == "inst:sp_L3_inv1"
    assert lst(s, "show_only -object {pin:sp_L2_inv1/A strap:sp_L1_inv1/1 "
               "pin_wire:sp_L2_inv1/Y}") == ["inst:sp_L2_inv1", "inst:sp_L1_inv1"]
    s.eval(f"select_obj {wire}")                                # as after a click
    assert s.eval("show_only -object [get_db selected]") == NET


def test_show_all(routed):
    s = routed
    everything = drawn(s)
    s.eval("show_only -object sp_L1_inv1")
    out_of(s)
    assert s.eval("show_only -show_all") == ""
    assert "show_only: every instance and all net routing are shown again" in out_of(s)
    assert s.db.show_only == [] and scope(s.db) is None and drawn(s) == everything
    s.eval("show_only -show_all")
    assert "show_only: nothing was hidden" in out_of(s)


@pytest.mark.parametrize("args, number", [
    ("", "HT4-001"),                                            # neither
    ("-object sp -show_all", "HT4-001"),                        # both
    ("-object {}", "HT4-001"),
    ("-object", "HT4-001"),
    ("-objects sp", "HT4-001"),
    ("sp", "HT4-001"),
    ("-object nothing_named_so", "HT4-270"),
    ("-object {sp no_*}", "HT4-270"),                           # one of them
    ("-object inst:u9", "HT4-022"),
    ("-object net:sp_L1_inv1_Y", "HT4-022"),                    # a spine's: spine_net:
    ("-object layer:IA", "HT4-271"),
    ("-object {sp route_rule:r}", "HT4-271"),
])
def test_errors_leave_the_display_as_it_is(routed, args, number):
    s = routed
    s.eval("show_only -object sp_L2_inv1")
    assert number in err(s, f"show_only {args}")
    assert s.db.show_only == ["inst:sp_L2_inv1"]


def test_the_database_is_not_changed_and_the_filter_not_saved(routed, tmp_path):
    s = routed
    before = s.db.conn.total_changes
    s.eval("show_only -object sp_L1_inv1_Y")
    s.eval("show_only -show_all")
    assert s.db.conn.total_changes == before
    s.eval("show_only -object sp_L1_inv1_Y")
    s.eval(f"write_db -file {{{tmp_path / 'a.deb'}}}")
    assert s.db.show_only == [NET]                              # write_db keeps it on
    s.eval(f"read_db -file {{{tmp_path / 'a.deb'}}}")
    assert s.db.show_only == [] and scope(s.db) is None         # session state: not saved


def test_the_filter_follows_a_net_routed_again(routed):
    s = routed
    s.eval("show_only -object sp_L1_inv1_Y")
    s.eval("delete_route -nets sp_L1_inv1_Y")
    # the H1 pieces under its pin wires are pin routes (route_pin): they stay
    assert not [h for h in drawn(s)["route"] if h.startswith("net_wire:")
                and not h.startswith("net_wire:pg:")]
    s.eval("route_net -net sp_L1_inv1_Y -rule r")
    wires = lst(s, f"get_db {NET} .net_wires")
    assert wires and set(wires) <= set(drawn(s)["route"])
    assert all(h.startswith(("net_wire:sp_L1_inv1_Y/", "pin_wire:", "strap:"))
               or h in pin_layers(s, "sp_L1_inv1_Y") for h in drawn(s)["route"])


def test_scope_of_shapes_by_handle():
    sc = Scope()
    sc.insts.add("top/u1")                                      # a name with a /
    assert sc.shows("inst:top/u1") and not sc.shows("inst:top/u2")
    assert sc.shows("pin:top/u1/A") and sc.shows("strap:top/u1/2")
    assert sc.shows("pin_wire:top/u1/A", "VDD") and not sc.shows("pin_wire:top/u2/A", "VDD")
    # optimize_pg_connection: the wires of an instance, on the net pg:<inst>
    assert sc.shows("net_wire:pg:top/u1/3", "VSS") and not sc.shows("net_wire:pg:top/u2/3", "VSS")
    assert sc.shows("via:VDD/4", "VDD", "pin_wire:top/u1/VDD")
    assert not sc.shows("via:VDD/9", "VDD", "pin_wire:top/u2/VDD")
    assert not sc.shows("net_wire:n1/1", "n1") and not sc.shows("spine_net:sp/n1")
    assert sc.shows("port:top/clk")                             # not an instance or a route
    sc.nets.add("VSS")                                          # a shield of n1 on VSS
    assert sc.shows("net_wire:n1/2", "VSS") and sc.shows("via:VSS/1", "VSS", "net_wire:n1/5")


# -- the window -------------------------------------------------------------------------

def seen(w):
    """The owners of the instance and route items the window shows."""
    c = w.canvas
    items = c.inst_items + c.spine_items + [
        i for group in (c.inst_pin_items, c.strap_items, c.via_items)
        for its in group.values() for i in its]
    from core.gui.canvas import OWNER_KEY
    return sorted({i.data(OWNER_KEY) for i in items if i.isVisible()})


def everything(s):
    return sorted({h for hs in drawn(s).values() for h in hs})


def test_window_shows_only_the_objects_given(shown):
    s, w = shown
    w.object_boxes["pins"].setChecked(True)
    for name, box in w.layer_boxes.items():                     # the pin layers too
        box.setChecked(True)
    whole = seen(w)
    assert whole == everything(s)
    assert w.only_label.text() == ""
    s.eval("show_only -object sp_L1_inv1_Y")
    assert seen(w) == everything(s) and len(seen(w)) < len(whole)
    assert NET in seen(w) and "inst:sp_L1_inv1" not in seen(w)
    assert w.only_label.text() == "Showing only: sp/sp_L1_inv1_Y"
    assert w.canvas.boundary_item.isVisible()                   # not an instance or a route
    s.eval("show_only -object {sp_L2_inv1 stub1}")
    assert seen(w) == everything(s)
    assert "inst:sp_L2_inv1" in seen(w) and NET not in seen(w)
    assert w.only_label.text() == "Showing only: sp_L2_inv1, sp/stub1"
    s.eval("show_only -show_all")
    assert seen(w) == whole and w.only_label.text() == ""


def test_window_filter_works_over_the_view_boxes(shown):
    s, w = shown
    s.eval("show_only -object sp_L1_inv1_Y")
    routes = [h for h in seen(w) if h.startswith(("net_wire:", "strap:"))]
    assert routes
    w.object_boxes["routes"].setChecked(False)                  # Objects: Routes
    assert not [h for h in seen(w) if h.startswith(("net_wire:", "strap:", "pin_wire:"))]
    w.object_boxes["routes"].setChecked(True)
    w.layer_boxes["IA"].setChecked(False)                       # a layer: the straps go
    left = [h for h in seen(w) if h.startswith(("net_wire:", "strap:"))]
    assert 0 < len(left) < len(routes) and not [h for h in left if h.startswith("strap:")]
    w.layer_boxes["IA"].setChecked(True)
    assert [h for h in seen(w) if h.startswith(("net_wire:", "strap:"))] == routes
    assert not [h for h in seen(w) if not h.startswith(("net_wire:sp_L1_inv1_Y/", "pin", "strap:",
                                                        "via:sp_L1_inv1_Y/", NET))
                and h not in pin_layers(s, "sp_L1_inv1_Y")]


def test_hidden_shapes_cannot_be_picked(shown):
    s, w = shown
    s.eval("show_only -object sp_L3_inv2")
    picked = w.canvas.owners_in(w.canvas.sceneRect(), touching=True)
    assert "inst:sp_L3_inv2" in picked and set(picked) <= set(seen(w))
    assert not [h for h in picked if h.startswith(("inst:", "strap:", "pin_wire:"))
                and "sp_L3_inv2" not in h]
    assert not [h for h in picked if h.startswith(("net_wire:", "spine_net:", "stub:"))
                and h not in pin_layers(s, inst="sp_L3_inv2")]     # its own H1 pieces


def test_window_keeps_the_filter_when_the_database_changes(shown):
    s, w = shown
    s.eval("show_only -object sp_L1_inv1_Y")
    first = seen(w)
    s.eval("create_inst -name u1 -ref_cell INV_RP -location {40 40}")     # a reload
    assert seen(w) == first and "inst:u1" not in seen(w)
    assert w.only_label.text() == "Showing only: sp/sp_L1_inv1_Y"
    s.eval("delete_route -nets sp_L1_inv1_Y")
    s.eval("route_net -net sp_L1_inv1_Y -rule r")               # routed again: shown again
    assert seen(w) == everything(s)
    assert [h for h in seen(w) if h.startswith("net_wire:sp_L1_inv1_Y/")]
    s.eval("show_only -show_all")
    assert "inst:u1" in seen(w)


def test_window_keeps_the_filter_through_an_edit_made_in_it(shown):
    s, w = shown
    s.eval("show_only -object sp_L1_inv1_Y")
    first = seen(w)
    wire = next(h for h in first if h.startswith("net_wire:sp_L1_inv1_Y/"))
    transform = w.canvas.transform()
    w.run_edit(f"delete_wire -wires {wire}", "delete_wire -undo")
    assert wire not in seen(w) and set(seen(w)) < set(first)
    w.undo_edit()                                               # drawn again: within the filter
    assert wire in seen(w)
    assert not [h for h in seen(w) if h.startswith("net_wire:") and "sp_L1_inv1_Y" not in h
                and h not in pin_layers(s, "sp_L1_inv1_Y")]
    assert w.canvas.transform() == transform                    # no reload


def test_window_opens_with_a_filter_set_before(routed, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    s = routed
    s.eval("show_only -object sp_L2_inv1")
    try:
        s.eval("gui_show")
        w = app.window()
        assert [h for h in seen(w) if h.startswith("inst:")] == ["inst:sp_L2_inv1"]
        assert w.only_label.text() == "Showing only: sp_L2_inv1"
    finally:
        app.close()
