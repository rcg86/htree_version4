"""remove_layer / add_layer: layers taken out of the tech data and put back,
with their vias; the GUI does not list a layer removed."""

import io
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

from conftest import ROOT, TECH_LEF
from core.htree_builder import Session
from test_commands import err
from test_read_tech_range import lst, out_of
from via_tech import tech_text

SMALL_DEF = ROOT / "tests" / "data" / "small.def"
ALL = ["D12", "C1", "H1", "C2", "H2", "C3", "G1", "C4", "G2", "C5", "IA", "C6", "XM", "IB"]
VIAS = ["V_D12_H1", "V_H1_H2", "V_H2_G1", "V_G1_G2", "V_G2_IA", "V_IA_IB", "V_IA_IB_2"]


@pytest.fixture
def vt(session, write_lef):
    """The via test tech: 14 layers, 7 vias."""
    session.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    out_of(session)
    return session


def without(*names):
    return [n for n in ALL if n not in names]


# -- remove_layer ----------------------------------------------------------------------

def test_remove_a_layer(vt):
    assert vt.eval("remove_layer -layer XM") == "XM"
    text = out_of(vt)
    assert "remove_layer: removed 1 layer(s) from tech: XM" in text
    assert f"Layers      : 13 ({' '.join(without('XM'))})" in text
    assert "Vias" not in text and "HT4-016" not in text         # no via on XM, nothing on it
    assert lst(vt, "get_db layers.name") == without("XM")
    assert lst(vt, "get_db via_defs.name") == VIAS
    assert "HT4-022" in err(vt, "get_db layer:XM .name")        # no layer object now
    assert vt.eval("get_db tech .removed_layers") == "XM"
    vt.eval("get_db tech")
    assert "removed_layers      : XM" in out_of(vt)


def test_vias_on_a_removed_layer_go_with_it(vt):
    # In tech order whatever the order given; a handle is taken as a name.
    assert lst(vt, "remove_layer -layer {C6 layer:G1}") == ["G1", "C6"]
    text = out_of(vt)
    assert "Vias        : 4 removed, a layer of theirs is removed (V_H2_G1 V_G1_G2 V_IA_IB " \
           "V_IA_IB_2)" in text
    assert lst(vt, "get_db via_defs.name") == ["V_D12_H1", "V_H1_H2", "V_G2_IA"]
    assert lst(vt, "get_db layers.name") == without("G1", "C6")
    assert vt.db.conn.execute("SELECT count(*) FROM via_def_shape s LEFT JOIN via_def d ON "
                              "d.id = s.via_def_id WHERE d.id IS NULL").fetchone()[0] == 0
    assert vt.db.conn.execute("SELECT count(*) FROM layer_extra e LEFT JOIN layer l ON "
                              "l.id = e.layer_id WHERE l.id IS NULL").fetchone()[0] == 0


def test_patterns_and_get_db_handles(vt):
    assert lst(vt, "remove_layer -layer C?") == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert vt.eval("get_db via_defs") == ""                     # every via has a cut layer
    assert lst(vt, "remove_layer -layer [get_db layers -if {.direction == vertical}]") == \
        ["D12", "H2", "G2", "IB"]
    assert lst(vt, "get_db layers.name") == ["H1", "G1", "IA", "XM"]
    assert lst(vt, "get_db tech .removed_layers") == ["C1", "C2", "C3", "C4", "C5", "C6", "D12",
                                                      "H2", "G2", "IB"]


def test_a_via_of_the_def_stays(vt, write_lef):
    from test_vias import DEF, DEF_VIAS, def_text
    vt.eval(f"read_def -file {{{write_lef(def_text(DEF_VIAS), 'v.def')}}}")
    vt.eval("remove_layer -layer C6")
    assert "2 removed, a layer of theirs is removed (V_IA_IB V_IA_IB_2)" in out_of(vt)
    assert lst(vt, "get_db via_defs.name")[-4:] == ["DV_RECT", "DV_MASK", "DV_POLY", "DV_GEN"]


@pytest.mark.parametrize("script, number, said", [
    ("remove_layer", "HT4-001", "-layer is required"),
    ("remove_layer -layer {}", "HT4-001", "-layer is required"),
    ("remove_layer -layer XM -file x", "HT4-001", "unknown option '-file'"),
    ("remove_layer -layer {XM M9 Q*}", "HT4-017", "M9 Q*: not in tech (tech layers: D12 C1"),
    ("remove_layer -layer *", "HT4-018", "names every tech layer"),
    ("add_layer", "HT4-001", "-layer is required"),
    ("add_layer -layer {G1 M9}", "HT4-017", "M9: not in '"),
])
def test_errors_change_nothing(vt, script, number, said):
    msg = err(vt, script)
    assert number in msg and said in msg
    assert lst(vt, "get_db layers.name") == ALL and lst(vt, "get_db via_defs.name") == VIAS
    assert vt.eval("get_db tech .removed_layers") == ""


def test_no_tech(session):
    assert "HT4-025" in err(session, "remove_layer -layer XM")
    assert "HT4-025" in err(session, "add_layer -layer XM")


def test_layer_in_use_warns(tech_session):
    tech_session.eval("create_route_rule -name r1 -layer H2 -width 0.41 -spacing 0.2")
    out_of(tech_session)
    tech_session.eval("remove_layer -layer {H2 G1}")
    text = out_of(tech_session)
    assert "WARN: (HT4-016): layer H2 is removed, and route rule(s) of the database are on " \
           "it: it is no tech layer now. add_layer -layer H2 puts it back" in text
    assert text.count("HT4-016") == 1                           # nothing is on G1
    assert "r1" in lst(tech_session, "get_db route_rules.name")        # the rule stays


# -- add_layer -------------------------------------------------------------------------

def test_add_puts_layers_and_vias_back(vt):
    vt.eval("remove_layer -layer {XM G1 C6}")
    out_of(vt)
    assert vt.eval("add_layer -layer G1") == "G1"
    text = out_of(vt)
    assert "add_layer: added 1 layer(s) to tech from '" in text and "vt.lef': G1" in text
    assert f"Layers      : 12 ({' '.join(without('XM', 'C6'))})" in text     # in file order
    assert "Vias        : 2 added, their layers are all in tech now (V_H2_G1 V_G1_G2)" in text
    assert "HT4-012" not in text and "HT4-013" not in text      # not a read_tech
    assert lst(vt, "get_db tech .removed_layers") == ["C6", "XM"]
    assert vt.eval("get_db layer:G1 .width") == "0.18"
    assert lst(vt, "add_layer -layer {layer:XM C6}") == ["C6", "XM"]
    assert lst(vt, "get_db layers.name") == ALL
    assert lst(vt, "get_db via_defs.name") == VIAS
    assert vt.eval("get_db tech .removed_layers") == ""
    vt.eval("get_db tech")
    assert "removed_layers" not in out_of(vt)


def test_a_via_needs_all_its_layers(vt):
    vt.eval("remove_layer -layer {IB C6}")
    vt.eval("add_layer -layer IB")
    assert "Vias" not in out_of(vt).split("add_layer:")[1]      # C6 is still out
    assert lst(vt, "get_db via_defs.name") == VIAS[:5]
    vt.eval("add_layer -layer C6")
    assert lst(vt, "get_db via_defs.name") == VIAS


def test_add_a_layer_already_in_tech(vt):
    assert vt.eval("add_layer -layer G*") == ""
    assert "add_layer: nothing to add: G1 G2 already in tech" in out_of(vt)
    vt.eval("remove_layer -layer G1")
    assert vt.eval("add_layer -layer G*") == "G1"               # G2 is passed over
    assert lst(vt, "get_db layers.name") == ALL


def test_remove_and_add_round_trip(vt):
    vt.eval("add_layer -layer [remove_layer -layer {C? XM}]")
    assert lst(vt, "get_db layers.name") == ALL and lst(vt, "get_db via_defs.name") == VIAS
    vt.eval("remove_layer -layer {H1 IA}")
    vt.eval("add_layer -layer [get_db tech .removed_layers]")
    assert lst(vt, "get_db layers.name") == ALL and lst(vt, "get_db via_defs.name") == VIAS


def test_add_a_layer_the_range_left_out(session, write_lef):
    lef = write_lef(tech_text(), "vt.lef")
    session.eval(f"read_tech -file {{{lef}}} -min_layer G1 -max_layer IB")
    session.eval("remove_layer -layer XM")
    session.eval("add_layer -layer {C3 H2}")
    assert lst(session, "get_db layers.name") == ["H2", "C3", "G1", "C4", "G2", "C5", "IA",
                                                  "C6", "IB"]
    assert lst(session, "get_db via_defs.name")[0] == "V_H2_G1"
    assert session.eval("get_db tech .min_layer") == "G1"       # as read_tech was given
    assert session.eval("get_db tech .removed_layers") == "XM"
    session.eval(f"read_tech -file {{{lef}}} -min_layer G1 -max_layer IB")
    assert session.eval("get_db tech .removed_layers") == ""    # read_tech starts again
    assert lst(session, "get_db layers.name")[-2:] == ["XM", "IB"]


def test_add_from_a_file_that_moved(vt, tmp_path):
    vt.eval("remove_layer -layer XM")
    lef = tmp_path / "vt.lef"
    moved = tmp_path / "moved.lef"
    lef.rename(moved)
    msg = err(vt, "add_layer -layer XM")
    assert "HT4-010" in msg and "Give the file with -file if it has moved" in msg
    assert vt.eval(f"add_layer -layer XM -file {{{moved}}}") == "XM"
    assert vt.eval("get_db tech .file") == str(moved)
    assert lst(vt, "get_db layers.name") == ALL


def test_add_from_another_tech_lef(vt):
    vt.eval("remove_layer -layer XM")
    out_of(vt)
    msg = err(vt, f"add_layer -layer H1 -file {{{TECH_LEF}}}")  # no D12, cut layers
    assert "HT4-019" in msg and "tech layer(s) D12 C1 C2 C3 C4 C5 C6 of the database are not " \
        "in" in msg
    assert "HT4-010" in err(vt, "add_layer -layer XM -file nowhere.lef")
    assert lst(vt, "get_db layers.name") == [n for n in ALL if n != "XM"]


def test_add_with_a_file_that_does_not_parse(vt, write_lef):
    vt.eval("remove_layer -layer XM")
    bad = write_lef("LAYER H1\n  TYPE ROUTING ;\n", "bad.lef")
    assert "HT4-011" in err(vt, f"add_layer -layer XM -file {{{bad}}}")
    assert vt.eval("get_db tech .removed_layers") == "XM"


def test_removed_layers_are_saved_with_the_database(vt, tmp_path):
    vt.eval("remove_layer -layer {XM C6}")
    vt.eval(f"write_db {tmp_path / 'r.db'}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path / 'r.db'}")
    assert lst(fresh, "get_db tech .removed_layers") == ["C6", "XM"]
    assert lst(fresh, "get_db layers.name") == without("XM", "C6")
    assert lst(fresh, "add_layer -layer {C6 XM}") == ["C6", "XM"]
    assert lst(fresh, "get_db via_defs.name") == VIAS


# -- vias of the routes ----------------------------------------------------------------

def test_an_assigned_via_follows_its_definition(session, write_lef):
    pytest.importorskip("scipy")
    from core import vias
    from test_vias import _route
    session.eval(f"read_tech -file {{{write_lef(tech_text(), 'vt.lef')}}}")
    s = _route(session, write_lef)
    s.eval("assign_via_for_route -via V_IA_IB")

    def crossings():
        return {(r["cut"], r["via_def"]) for r in vias.rows(s.db) if r["kind"] == "cross"}
    assert crossings() == {("C6", "V_IA_IB")}
    s.eval("remove_layer -layer C6")
    assert crossings() == {(None, None)}                        # its box again, no cut layer
    s.eval("add_layer -layer C6")
    assert crossings() == {("C6", "V_IA_IB")}                   # the assignment was kept


# -- the GUI does not list a layer removed ---------------------------------------------

def test_layout_does_not_list_a_removed_layer(session):
    from core.gui.layout_data import load_layout
    session.eval(f"read_tech -file {{{TECH_LEF}}}")
    session.eval(f"read_def -file {{{SMALL_DEF}}}")

    def names():
        return [l.name for l in load_layout(session.db).layers]
    assert names() == ["H1", "H2", "G1", "G2", "IA", "IB", "M1"]
    session.eval("remove_layer -layer {H1 G2}")
    # H1 carries port shapes and tracks of the DEF: not listed as 'H1 *' either. M1,
    # never a tech layer, still is.
    assert names() == ["H2", "G1", "IA", "IB", "M1"]
    lay = load_layout(session.db)
    assert "H1" in {s.layer for s in lay.shapes}
    session.eval("add_layer -layer H1")
    assert names() == ["H1", "H2", "G1", "IA", "IB", "M1"]


def test_window_follows_remove_and_add(session, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    try:
        session.eval(f"read_tech -file {{{TECH_LEF}}}")
        session.eval(f"read_def -file {{{SMALL_DEF}}}")
        session.eval("gui_show")
        w = app.window()
        w.layer_boxes["IA"].setChecked(False)
        session.eval("remove_layer -layer {H1 G2}")
        assert list(w.layer_boxes) == ["H2", "G1", "IA", "IB", "M1"]
        assert "H1" not in w.canvas.visible_layers
        hidden = [item for item in w.canvas.shape_items["H1"]]
        assert hidden and not any(item.isVisible() for item in hidden)
        assert not w.layer_boxes["IA"].isChecked()              # the user's choice is kept
        session.eval("add_layer -layer H1")
        assert list(w.layer_boxes) == ["H1", "H2", "G1", "IA", "IB", "M1"]
        assert w.layer_boxes["H1"].isChecked() and "H1" in w.canvas.visible_layers
        assert all(item.isVisible() for item in w.canvas.shape_items["H1"])
        assert not w.layer_boxes["IA"].isChecked()
    finally:
        app.close()
