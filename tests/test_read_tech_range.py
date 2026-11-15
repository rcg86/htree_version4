"""read_tech -min_layer / -max_layer: only the layers of a range and their
vias are read, and the GUI lists only those."""

import io
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"      # before anything imports Qt

import pytest

from conftest import ROOT, TECH_LEF
from core.htree_builder import Session
from test_commands import err
from via_tech import tech_text

SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def out_of(session):
    text = session.out.getvalue()
    session.out.seek(0)
    session.out.truncate()
    return text


def lst(session, script):
    return session.eval(script).split()


# -- the layers of the range ---------------------------------------------------------

def test_range_reads_its_layers_only(session):
    session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer G1 -max_layer IA")
    text = out_of(session)
    assert "Layer range : G1 .. IA (-min_layer G1, -max_layer IA); 3 of the 6 layers of the " \
           "file left out" in text
    assert "Layers      : 3 (G1 G2 IA)" in text
    assert lst(session, "get_db layers.name") == ["G1", "G2", "IA"]
    assert session.eval("get_db tech .min_layer") == "G1"
    assert session.eval("get_db tech .max_layer") == "IA"
    assert "HT4-022" in err(session, "get_db layer:IB .name")      # not in the database
    session.eval("get_db tech")
    text = out_of(session)
    assert "min_layer           : G1" in text and "max_layer           : IA" in text


@pytest.mark.parametrize("options, layers, said", [
    ("-max_layer G1", ["H1", "H2", "G1"], "H1 .. G1 (-max_layer G1); 3 of the 6"),
    ("-min_layer IA", ["IA", "IB"], "IA .. IB (-min_layer IA); 4 of the 6"),
    ("-min_layer G2 -max_layer G2", ["G2"], "G2 .. G2 (-min_layer G2, -max_layer G2); 5 of"),
    ("-min_layer H1 -max_layer IB", ["H1", "H2", "G1", "G2", "IA", "IB"],
     "H1 .. IB (-min_layer H1, -max_layer IB); 0 of the 6"),
])
def test_one_end_or_both(session, options, layers, said):
    session.eval(f"read_tech -file {{{TECH_LEF}}} {options}")
    assert f"Layer range : {said}" in out_of(session)
    assert lst(session, "get_db layers.name") == layers


def test_no_range_reads_the_whole_file(session):
    session.eval(f"read_tech -file {{{TECH_LEF}}}")
    text = out_of(session)
    assert "Layer range" not in text and "Layers      : 6 (H1 H2 G1 G2 IA IB)" in text
    assert session.eval("get_db tech .min_layer") == ""
    assert session.eval("get_db tech .max_layer") == ""
    session.eval("get_db tech")
    assert "min_layer" not in out_of(session)


# -- the vias of the range -----------------------------------------------------------

def test_vias_with_every_layer_in_the_range(session, write_lef):
    lef = write_lef(tech_text(), "vt.lef")
    session.eval(f"read_tech -file {{{lef}}} -min_layer G1 -max_layer IB")
    text = out_of(session)
    # The cut layers between the routing layers of the range, and XM, come with it.
    assert lst(session, "get_db layers.name") == ["G1", "C4", "G2", "C5", "IA", "C6", "XM", "IB"]
    # V_H2_G1 ends on G1, but H2 and its cut layer are below the range.
    assert lst(session, "get_db via_defs.name") == ["V_G1_G2", "V_G2_IA", "V_IA_IB",
                                                    "V_IA_IB_2"]
    assert "Vias        : 4 (3 DEFAULT); 3 left out, a layer of theirs is not in the range" \
        in text
    assert "1 VIARULE statement(s) not modeled, kept verbatim" in text     # rules stay whole


def test_range_ending_on_a_cut_layer(session, write_lef):
    lef = write_lef(tech_text(), "vt.lef")
    session.eval(f"read_tech -file {{{lef}}} -min_layer C5 -max_layer C6")
    assert lst(session, "get_db layers.name") == ["C5", "IA", "C6"]
    assert session.eval("get_db via_defs") == ""               # each needs a layer outside


# -- errors: the database is unchanged -------------------------------------------------

@pytest.mark.parametrize("options, said", [
    ("-min_layer M9 -max_layer IB", "-min_layer 'M9' is not a layer of"),
    ("-min_layer H1 -max_layer M9", "-max_layer 'M9' is not a layer of"),
    ("-min_layer IA -max_layer G1", "-min_layer 'IA' comes after -max_layer 'G1'"),
])
def test_bad_range(tech_session, options, said):
    tech_session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer G1 -max_layer IA")
    out_of(tech_session)
    msg = err(tech_session, f"read_tech -file {{{TECH_LEF}}} {options}")
    assert "HT4-015" in msg and said in msg
    assert lst(tech_session, "get_db layers.name") == ["G1", "G2", "IA"]
    assert tech_session.eval("get_db tech .min_layer") == "G1"
    assert "HT4-012" not in out_of(tech_session)               # nothing was replaced


def test_option_without_a_value(session):
    assert "HT4-001" in err(session, f"read_tech -file {{{TECH_LEF}}} -min_layer")
    assert "HT4-001" in err(session, f"read_tech -file {{{TECH_LEF}}} -max_layer {{}}")


# -- reading again: the new range replaces the old one -------------------------------

def test_wider_range_adds_layers(session, write_lef):
    lef = write_lef(tech_text(), "vt.lef")
    session.eval(f"read_tech -file {{{lef}}} -min_layer G2 -max_layer IB")
    assert lst(session, "get_db via_defs.name") == ["V_G2_IA", "V_IA_IB", "V_IA_IB_2"]
    out_of(session)
    session.eval(f"read_tech -file {{{lef}}} -min_layer H2 -max_layer IB")
    assert "WARN: (HT4-012)" in out_of(session)
    assert lst(session, "get_db layers.name")[:3] == ["H2", "C3", "G1"]
    assert lst(session, "get_db via_defs.name")[:2] == ["V_H2_G1", "V_G1_G2"]
    assert session.eval("get_db tech .min_layer") == "H2"
    session.eval(f"read_tech -file {{{lef}}}")                 # no range: the whole file
    assert len(lst(session, "get_db layers.name")) == 14
    assert len(lst(session, "get_db via_defs")) == 7
    assert session.eval("get_db tech .min_layer") == ""
    assert session.eval("get_db tech .max_layer") == ""


def test_range_is_saved_with_the_database(session, tmp_path):
    session.eval(f"read_tech -file {{{TECH_LEF}}} -max_layer G2")
    session.eval(f"write_db {tmp_path / 'r.db'}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path / 'r.db'}")
    assert fresh.eval("get_db tech .max_layer") == "G2"
    assert fresh.eval("get_db tech .min_layer") == ""
    assert fresh.db.tech_layer_range() == (None, "G2")


def test_layer_in_use_left_out_warns(tech_session):
    tech_session.eval("create_route_rule -name r1 -layer H2 -width 0.41 -spacing 0.2")
    tech_session.eval("create_route_rule -name r1 -layer IA -width 0.72 -spacing 0.72 -append")
    out_of(tech_session)
    tech_session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer G1")
    text = out_of(tech_session)
    assert "WARN: (HT4-016): layer H2 is left out by the layer range, and route rule(s) of " \
           "the database are on it" in text
    assert text.count("HT4-016") == 1                          # IA is in the range


# -- the GUI lists the layers of the range only --------------------------------------

def test_layout_lists_the_range_only(session):
    from core.gui.layout_data import load_layout
    session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer G1 -max_layer IB")
    session.eval(f"read_def -file {{{SMALL_DEF}}}")
    lay = load_layout(session.db)
    # H1, H2 and M1 carry port shapes and tracks of the DEF: not listed, nor are they tech.
    assert [l.name for l in lay.layers] == ["G1", "G2", "IA", "IB"]
    assert all(l.in_tech for l in lay.layers)
    assert {s.layer for s in lay.shapes} - {l.name for l in lay.layers} == {"H1", "H2", "M1"}
    session.eval(f"read_tech -file {{{TECH_LEF}}}")            # the whole file again
    names = [l.name for l in load_layout(session.db).layers]
    assert names == ["H1", "H2", "G1", "G2", "IA", "IB", "M1"]   # M1: not in tech, listed


def test_window_shows_new_layers_after_a_wider_read(session, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    try:
        session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer G1 -max_layer IB")
        session.eval(f"read_def -file {{{SMALL_DEF}}}")
        session.eval("gui_show")
        w = app.window()
        assert list(w.layer_boxes) == ["G1", "G2", "IA", "IB"]
        assert w.canvas.visible_layers == {"G1", "G2", "IA", "IB"}
        hidden = [item for item in w.canvas.shape_items["H1"]]
        assert hidden and not any(item.isVisible() for item in hidden)
        w.layer_boxes["G2"].setChecked(False)                  # the user's choice is kept
        session.eval(f"read_tech -file {{{TECH_LEF}}} -min_layer H1 -max_layer IB")
        assert list(w.layer_boxes) == ["H1", "H2", "G1", "G2", "IA", "IB"]
        assert w.layer_boxes["H1"].isChecked() and w.layer_boxes["H2"].isChecked()
        assert not w.layer_boxes["G2"].isChecked()
        assert all(item.isVisible() for item in w.canvas.shape_items["H1"])
    finally:
        app.close()


def test_layer_that_becomes_a_tech_layer_shows_up(session, tmp_path, monkeypatch):
    """M1 is listed unchecked while it is not in tech (no range); read as a
    tech layer it is checked. A tech layer the user unchecked stays so."""
    pytest.importorskip("PySide6")
    from core.gui import app
    monkeypatch.setenv("HTREE4_SHORTCUTS", str(tmp_path / "shortcuts.json"))   # not ~/.config
    more = TECH_LEF.read_text().replace(
        "END LIBRARY", "LAYER M1\n  TYPE ROUTING ;\n  DIRECTION VERTICAL ;\nEND M1\n"
        "END LIBRARY")
    lef = tmp_path / "more.lef"
    lef.write_text(more)
    try:
        session.eval(f"read_tech -file {{{TECH_LEF}}}")
        session.eval(f"read_def -file {{{SMALL_DEF}}}")
        session.eval("gui_show")
        w = app.window()
        assert not w.layer_boxes["M1"].isChecked()
        w.layer_boxes["IA"].setChecked(False)
        session.eval(f"read_tech -file {{{lef}}} -min_layer G1 -max_layer M1")
        assert list(w.layer_boxes) == ["G1", "G2", "IA", "IB", "M1"]
        assert w.layer_boxes["M1"].isChecked() and "M1" in w.canvas.visible_layers
        assert not w.layer_boxes["IA"].isChecked()
    finally:
        app.close()
