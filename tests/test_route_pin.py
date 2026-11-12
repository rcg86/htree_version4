import io
import os
import tkinter

import pytest

from core.htree_builder import Session

# The INV shape of the real D112 cell: 3.12 x 1.778, VDD and VSS in two D12
# pieces, A and Y signal pins, and a VNW pin that route_pin must ignore. B
# (not connected by default) has two pieces of different width and x.
CELL_LEF = """VERSION 5.8 ;
MACRO INV_RP
  CLASS CORE ;
  SIZE 3.12 BY 1.778 ;
  PIN A
    DIRECTION INPUT ;
    PORT
      LAYER D12 ;
        RECT 2.523 0.348 2.933 1.444 ;
    END
  END A
  PIN Y
    DIRECTION OUTPUT ;
    PORT
      LAYER D12 ;
        RECT 1.0 0.2 1.4 0.7 ;
    END
    PORT
      LAYER D12 ;
        RECT 1.0 1.1 1.4 1.6 ;
    END
  END Y
  PIN VDD
    USE POWER ;
    PORT
      LAYER D12 ;
        RECT 0.187 0.111 0.597 0.585 ;
    END
    PORT
      LAYER D12 ;
        RECT 0.187 0.939 0.597 1.413 ;
    END
  END VDD
  PIN VSS
    USE GROUND ;
    PORT
      LAYER D12 ;
        RECT 1.8 0.3 2.2 1.5 ;
      LAYER M1 ;
        RECT 0 -0.03 3.12 0.03 ;
    END
  END VSS
  PIN B
    DIRECTION INPUT ;
    PORT
      LAYER D12 ;
        RECT 0.65 0.2 0.85 0.5 ;
    END
    PORT
      LAYER D12 ;
        RECT 0.62 1.0 0.92 1.3 ;
    END
  END B
  PIN VNW
    PORT
      LAYER D12 ;
        RECT 0 0 0.1 0.1 ;
    END
  END VNW
END INV_RP
END LIBRARY
"""

# IA tracks every 0.72 from -9.36: the default stack sits 0.169 above them.
DEF = """VERSION 5.8 ;
DESIGN t ;
UNITS DISTANCE MICRONS 1000 ;
DIEAREA ( -10000 -10000 ) ( 10000 10000 ) ;
TRACKS Y -9360 DO 30 STEP 720 LAYER IA ;
END DESIGN
"""

# Cell at {0 0}: centre y 0.889, stack 9.36 tall, so the top is at 5.569
# and strap k spans [5.569 - 1.44 (k - 1) - 0.72, 5.569 - 1.44 (k - 1)].
TOPS = [5.569, 4.129, 2.689, 1.249, -0.191, -1.631, -3.071]


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def placed(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.out.seek(0)
    s.out.truncate()
    return s


def out_of(s):
    text = s.out.getvalue()
    s.out.seek(0)
    s.out.truncate()
    return text


def test_default_stack(placed):
    made = list(placed.split_list(placed.eval("route_pin -inst u1")))
    handles = [f"strap:u1/{k}" for k in range(1, 8)]
    assert made == handles + [f"pin_wire:u1/{p}" for p in ("VDD", "VSS", "A", "Y")]
    assert list(placed.split_list(placed.eval("get_db inst:u1 .straps"))) == handles
    assert list(placed.split_list(placed.eval("get_db straps"))) == handles
    nets = [placed.eval(f"get_db {h} .net") for h in handles]
    assert nets == ["VSS", "VDD_SOC", "SIGNAL", "VSS", "SIGNAL", "VDD_SOC", "VDD_SOC"]
    for h, top in zip(handles, TOPS):
        x1, y1, x2, y2 = map(float, placed.eval(f"get_db {h} .rect").split())
        assert (x1, x2) == (0, 3.12)                       # exactly the instance width
        assert y2 == pytest.approx(top) and y2 - y1 == pytest.approx(0.72)
        assert placed.eval(f"get_db {h} .layer") == "IA"
        assert float(placed.eval(f"get_db {h} .width")) == 0.72
        assert float(placed.eval(f"get_db {h} .length")) == 3.12
    assert placed.eval("get_db strap:u1/1 .inst") == "inst:u1"
    assert placed.eval("get_db strap:u1/1 .name") == "1"


def test_report(placed):
    placed.eval("route_pin -inst u1")
    text = out_of(placed)
    assert "height 9.36 edge to edge, 10.08 tileable" in text
    assert "straps 6 and 7 are both VDD_SOC and adjacent" in text and "2.16 wide" in text
    assert "HT4-165" in text and "moving the stack by -0.169" in text
    assert "HT4-163" not in text                               # 0.72 >= IA min width 0.36
    lines = {l.split()[0].rpartition("/")[2]: l for l in text.splitlines() if "->" in l}
    assert set(lines) == {"VDD", "VSS", "A", "Y"}
    assert "pin wires on H2 from the D12 pins (B, VNW not connected)" in text
    assert "-> strap 6:" in lines["VDD"]                      # the nearer VDD_SOC
    assert "2 pin shape(s)" in lines["Y"]
    assert "HT4-166" not in text


def test_pin_wires(placed):
    placed.eval("route_pin -inst u1")
    wires = placed.split_list(placed.eval("get_db inst:u1 .pin_wires"))
    assert wires == placed.split_list(placed.eval("get_db pin_wires"))
    g = lambda h, a: placed.eval(f"get_db {h} .{a}")
    for h in wires:
        assert g(h, "layer") == "H2" and g(h, "inst") == "inst:u1"
        assert g(h, "pin") == f"pin:u1/{g(h, 'name')}"
    # Each wire takes the pin's x span (its width) and runs over the whole
    # stack (y -3.791 .. 5.569), crossing every strap. VDD's strap is the
    # nearer VDD_SOC, 6 (3.764 away) rather than 2 (4.018).
    assert g("pin_wire:u1/VDD", "rect") == "0.187 -3.791 0.597 5.569"
    assert g("pin_wire:u1/VDD", "strap") == "strap:u1/6"
    assert g("pin_wire:u1/VDD", "net") == "VDD_SOC"
    assert float(g("pin_wire:u1/VDD", "width")) == pytest.approx(0.41)
    assert float(g("pin_wire:u1/VDD", "length")) == pytest.approx(9.36)
    assert g("pin_wire:u1/VSS", "rect") == "1.8 -3.791 2.2 5.569"
    # A and Y are different signals: one SIGNAL strap each, least total wire
    # (A 5 + Y 3 = 2.355 + 2.489 beats A 3 + Y 5 = 2.341 + 2.511).
    assert g("pin_wire:u1/A", "strap") == "strap:u1/5"
    assert g("pin_wire:u1/Y", "strap") == "strap:u1/3"
    assert g("pin_wire:u1/Y", "rect") == "1 -3.791 1.4 5.569"


def test_pin_wire_crosses_every_strap(placed, write_lef):
    # a short stack well inside the cell: the wire still covers the pin
    spec = write_lef("pin_routing:\n  width: 0.1\n  spacing: 0.1\n  nets: [VSS]\n", "v.yaml")
    placed.eval(f"route_pin -inst u1 -spec {spec}")
    vss = [float(v) for v in placed.eval("get_db pin_wire:u1/VSS .rect").split()]
    assert vss[1] == pytest.approx(0.3) and vss[3] == pytest.approx(1.5)  # the pin
    placed.eval("route_pin -inst u1")
    straps = placed.split_list(placed.eval("get_db straps"))
    for h in placed.split_list(placed.eval("get_db pin_wires")):
        _, wy1, _, wy2 = map(float, placed.eval(f"get_db {h} .rect").split())
        for st in straps:
            _, sy1, _, sy2 = map(float, placed.eval(f"get_db {st} .rect").split())
            assert wy1 <= sy1 and sy2 <= wy2, (h, st)


def test_pin_wire_takes_the_widest_shape(placed, write_lef):
    spec = write_lef("pin_routing:\n  pins:\n    nets: {B: SIGNAL}\n", "b.yaml")
    placed.eval(f"route_pin -inst u1 -spec {spec}")
    # B: 0.2 wide at x 0.65 and 0.3 wide at x 0.62; the wire is the wider one
    assert placed.eval("get_db pin_wire:u1/B .rect").split()[0::2] == ["0.62", "0.92"]
    assert "HT4-166" not in out_of(placed)                   # both pieces under it
    spec = write_lef("pin_routing:\n  pins:\n    nets: {A: SIGNAL, Y: SIGNAL, B: SIGNAL}\n",
                     "c.yaml")
    placed.eval(f"route_pin -inst u1 -spec {spec}")
    text = out_of(placed)
    assert "3 signal pins (A Y B) but only 2 SIGNAL straps" in text and "B not routed" in text
    assert placed.split_list(placed.eval("get_db pin_wires")) == ("pin_wire:u1/A",
                                                                 "pin_wire:u1/Y")


def test_pin_wire_spacing(placed, write_lef):
    # VDD (x 0.187 .. 0.597) and B (x 0.62 .. 0.92) wires are 0.023 apart
    spec = write_lef("pin_routing:\n  pins:\n    nets: {VDD: VDD_SOC, B: VSS}\n", "s.yaml")
    placed.eval(f"read_tech -file {{{write_lef(SPACED_TECH, 't.lef')}}}")
    out_of(placed)
    placed.eval(f"route_pin -inst u1 -spec {spec}")
    text = out_of(placed)
    assert "pin wires VDD and B are 0.023 apart; H2 needs 0.1" in text


SPACED_TECH = """VERSION 5.8 ;
UNITS
  DATABASE MICRONS 4000 ;
END UNITS
MANUFACTURINGGRID 0.00025 ;
LAYER H2
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  WIDTH 0.064 ;
  SPACING 0.1 ;
END H2
LAYER IA
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  WIDTH 0.36 ;
END IA
END LIBRARY
"""


def test_rerun_replaces(placed):
    placed.eval("route_pin -inst u1")
    out_of(placed)
    handles = placed.split_list(placed.eval(
        "route_pin -inst inst:u1 -nets {VSS VDD_SOC SIGNAL} -width 0.36 -spacing 0.36"))
    assert len(handles) == 6 and "HT4-162" in out_of(placed)      # 3 straps, 3 wires
    assert placed.split_list(placed.eval("get_db straps")) + \
        placed.split_list(placed.eval("get_db pin_wires")) == handles
    assert "pin_wire:u1/Y" not in handles                         # one SIGNAL strap: A only
    # 3 x 0.36 + 2 x 0.36 = 1.8, centred on 0.889
    assert placed.eval("get_db strap:u1/1 .rect") == "0 1.429 3.12 1.789"
    assert "HT4-022" in err(placed, "get_db strap:u1/4 .net")


def test_warnings(placed):
    placed.eval("route_pin -inst u1 -width 0.2 -nets {VSS SIGNAL}")
    text = out_of(placed)
    assert "HT4-163" in text and "below the IA minimum width 0.36" in text
    assert "VDD needs a VDD_SOC strap" in text and "HT4-166" in text
    placed.eval("route_pin -inst u1 -layer IB")
    assert "IB is a vertical layer" in out_of(placed)


def test_errors(placed, write_lef):
    assert "HT4-001" in err(placed, "route_pin")
    assert "HT4-160" in err(placed, "route_pin -inst nosuch")
    assert "HT4-161" in err(placed, "route_pin -inst u1 -layer D12")
    assert "HT4-161" in err(placed, "route_pin -inst u1 -spec "
                            + write_lef("pin_routing:\n  pins: {vertical_layer: D12}", "e.yaml"))
    assert "HT4-001" in err(placed, "route_pin -inst u1 -width -1")
    assert "HT4-001" in err(placed, "route_pin -inst u1 -nets {}")
    assert placed.eval("get_db straps") == ""                  # nothing stored on error


def test_saved_by_write_db(placed, tmp_path):
    placed.eval("route_pin -inst u1")
    placed.eval(f"write_db {tmp_path}/s.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {tmp_path}/s.db")
    assert len(fresh.split_list(fresh.eval("get_db straps"))) == 7
    assert len(fresh.split_list(fresh.eval("get_db pin_wires"))) == 4


def test_drawn_and_selectable_in_gui(placed):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    pytest.importorskip("PySide6")
    from core.gui import app
    from core.gui.canvas import scene
    try:
        placed.eval("gui_show")
        w = app.window()
        assert not w.object_boxes["routes"].isEnabled()
        placed.eval("route_pin -inst u1")                      # the view refreshes
        assert w.object_boxes["routes"].isEnabled()
        items = [i for its in w.canvas.strap_items.values() for i in its]
        assert len(items) == 11 and all(i.isVisible() for i in items)    # 7 straps, 4 wires
        owners = w.canvas.owners_in(w.canvas.content.adjusted(-5, -5, 5, 5), touching=True)
        assert {f"strap:u1/{k}" for k in range(1, 8)} <= set(owners)
        assert {f"pin_wire:u1/{p}" for p in ("VDD", "VSS", "A", "Y")} <= set(owners)
        assert len(w.canvas.strap_items["H2"]) == 4
        w.on_select(["pin_wire:u1/A"], "replace")
        assert "to strap:u1/5" in w.sel_label.text()
        w.canvas.zoom_to(w.canvas.owner_items["strap:u1/1"][0].sceneBoundingRect())
        w.on_select([w.canvas.owner_at(w.canvas.mapFromScene(scene(1.5, 5.2)))], "replace")
        assert placed.eval("get_db selected") == "strap:u1/1"
        assert "net VSS" in w.sel_label.text()
        w.object_boxes["routes"].setChecked(False)
        assert not any(i.isVisible() for i in items)
    finally:
        app.close()


def test_signal_power_ground_boxes_in_gui(placed):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    pytest.importorskip("PySide6")
    from core.gui import app
    from core.gui.canvas import CLASS_KEY
    try:
        placed.eval("gui_show")
        placed.eval("route_pin -inst u1")
        w = app.window()
        items = [i for its in w.canvas.strap_items.values() for i in its] + \
            [i for its in w.canvas.inst_pin_items.values() for i in its]
        by = {c: [i for i in items if i.data(CLASS_KEY) == c and i.isVisible()]
              for c in ("signal", "power", "ground")}
        assert all(by.values())                       # VDD_SOC / VSS straps and pins, A and Y
        assert all(b.isChecked() for b in w.class_boxes.values())     # all on by default
        w.all_class_boxes["power"].setChecked(False)  # every layer: no power shown
        assert not any(i.isVisible() for i in by["power"])
        assert all(i.isVisible() for i in by["signal"] + by["ground"])
        placed.eval("route_pin -inst u1")             # refresh keeps the choice
        assert not any(w.class_boxes[k].isChecked() for k in w.class_boxes if k[1] == "power")
        items = [i for its in w.canvas.strap_items.values() for i in its]
        assert not any(i.isVisible() for i in items if i.data(CLASS_KEY) == "power")
        layer = next(i for i in w.canvas.strap_items if any(
            i2.data(CLASS_KEY) == "ground" for i2 in w.canvas.strap_items[i]))
        w.class_boxes[(layer, "ground")].setChecked(False)  # one layer's VSS only
        assert not any(i.isVisible() for i in w.canvas.strap_items[layer]
                       if i.data(CLASS_KEY) == "ground")
        w.class_boxes[(layer, "ground")].setChecked(True)
        w.class_boxes[(layer, "power")].setChecked(True)
        assert all(i.isVisible() for i in w.canvas.strap_items[layer])
    finally:
        app.close()


# -- -spec file ------------------------------------------------------------------------

def test_max_strap_extension(placed, write_lef):
    placed.eval("route_pin -inst u1")
    assert "may extend each strap up to 3 past each instance edge" in out_of(placed)
    assert placed.eval("get_db strap:u1/1 .max_extension") == "3.0"
    spec = write_lef("pin_routing:\n  max_strap_extension: 1.5\n", "x.yaml")
    placed.eval(f"route_pin -inst u1 -spec {spec}")
    assert placed.eval("get_db strap:u1/1 .max_extension") == "1.5"


def test_shipped_spec_loads():
    """runs/pin_routing_spec.yaml is meant to be edited: only check it is valid."""
    from conftest import ROOT
    from core.commands.route_pin import load_spec
    spec = load_spec(str(ROOT / "runs" / "pin_routing_spec.yaml"))
    assert spec["nets"] and spec["width"] > 0 and spec["pins"]["layer"]


def test_spec_file(placed, write_lef):
    spec = write_lef("""pin_routing:
  width: 0.36
  spacing: 0.36
  nets: [VSS, SIGNAL, VDD_SOC]
  pins:
    nets: {VDD: VDD_SOC, A: SIGNAL}
""", "p.yaml")
    handles = placed.split_list(placed.eval(f"route_pin -inst u1 -spec {spec}"))
    assert len(handles) == 5                                      # 3 straps, VDD and A
    assert placed.eval("get_db strap:u1/1 .rect") == "0 1.429 3.12 1.789"
    assert placed.eval("get_db strap:u1/1 .layer") == "IA"        # not in the file: default
    text = out_of(placed)
    assert f"(spec {spec})" in text
    assert {l.split()[0].rpartition("/")[2] for l in text.splitlines() if "->" in l} == \
        {"VDD", "A"}
    assert "Y, VSS, B, VNW not connected" in text
    # options override the file
    placed.eval(f"route_pin -inst u1 -spec {spec} -width 0.72 -nets {{VSS VDD_SOC}}")
    assert len(placed.split_list(placed.eval("get_db straps"))) == 2
    assert placed.eval("get_db strap:u1/1 .width") == "0.72"


@pytest.mark.parametrize("body, text", [
    ("width: 1", "'pin_routing:' section"),
    ("pin_routing:\n  widht: 1", "pin_routing.widht is not a spec key"),
    ("pin_routing:\n  width: -1", "pin_routing.width must be a positive number"),
    ("pin_routing:\n  nets: VSS", "pin_routing.nets must be a list"),
    ("pin_routing:\n  max_strap_extension: -1", "pin_routing.max_strap_extension must be"),
    ("pin_routing:\n  pins: {nets: [VDD]}", "pin_routing.pins.nets must map"),
    ("pin_routing:\n  pins: {lyr: D12}", "pin_routing.pins.lyr is not a spec key"),
    ("pin_routing: [", "not valid YAML"),
])
def test_bad_spec(placed, write_lef, body, text):
    msg = err(placed, f"route_pin -inst u1 -spec {write_lef(body, 'b.yaml')}")
    assert "HT4-167" in msg and text in msg
    assert placed.eval("get_db straps") == ""


def test_missing_spec_file(placed, tmp_path):
    assert "HT4-167" in err(placed, f"route_pin -inst u1 -spec {tmp_path}/none.yaml")


def test_dump_spec(placed, tmp_path):
    from core.commands.route_pin import DEFAULTS, load_spec
    path = tmp_path / "d.yaml"
    assert placed.eval(f"route_pin -dump {path}") == str(path)      # no -inst needed
    assert load_spec(str(path)) == DEFAULTS
    assert "Pin routing spec written to" in out_of(placed)
    # the spec in force: the -spec file, then the options
    assert "HT4-168" in err(placed, f"route_pin -dump {path} -width 0.36")
    placed.eval(f"route_pin -dump {path} -spec {path} -width 0.36 -nets {{VSS SIGNAL}} "
                f"-layer IB -overwrite")
    spec = load_spec(str(path))
    assert spec["width"] == 0.36 and spec["spacing"] == 0.72
    assert spec["nets"] == ["VSS", "SIGNAL"] and spec["pins"]["horizontal_layer"] == "IB"
    assert placed.eval("get_db straps") == ""                      # nothing routed
    # the dumped file routes like the options did
    placed.eval(f"route_pin -inst u1 -spec {path}")
    assert placed.eval("get_db strap:u1/1 .width") == "0.36"
