import io
import tkinter

import pytest

from conftest import ROOT, TECH_LEF
from core.htree_builder import Session
from core.lef import LefParseError, parse_cell_lef

CELLS_LEF = ROOT / "tests" / "data" / "cells.lef"
CELLS = ["INV_D1", "INV_D2", "PAD1"]
A = "lib_pin:INV_D1/A"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def lib_session(tech_session):
    tech_session.eval(f"read_lef -file {{{CELLS_LEF}}}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


# -- parser -----------------------------------------------------------------------

def test_parse_macros():
    lib = parse_cell_lef(str(CELLS_LEF))
    assert lib.lef_version == "5.8"
    assert [m.name for m in lib.macros] == CELLS
    inv, inv2, pad = lib.macros
    assert (inv.cls, inv.size_x, inv.size_y, inv.site) == ("core", 0.6, 0.254, "core")
    assert inv.extra == ["ORIGIN 0 0 ;", "SYMMETRY X Y ;"]
    assert inv.line == 10
    assert inv.lef_text.startswith("MACRO INV_D1") and inv.lef_text.endswith("END INV_D1")
    assert (pad.cls, pad.size_x, pad.site) == ("pad inout", None, None)
    assert inv2.pins[0].direction == "out"
    assert inv2.pins[0].extra == ["DIRECTION OUTPUT TRISTATE ;"]
    assert [(e.kind, e.line) for e in lib.extras] == [("BUSBITCHARS", 2), ("SITE", 4)]


def test_parse_pins_ports_shapes():
    inv = parse_cell_lef(str(CELLS_LEF)).macros[0]
    a, y = inv.pins
    assert (a.name, a.direction, a.use) == ("A", "in", "signal")
    assert a.extra == ["ANTENNAGATEAREA 0.01 LAYER M1 ;"]
    assert len(a.ports) == 2
    s1, s2 = a.ports[0].shapes
    assert (s1.layer, s1.type, s1.points, s1.mask) == ("M1", "rect", [0.1, 0.2, 0, 0], None)
    assert (s2.layer, s2.mask, s2.points) == ("H1", 2, [0.2, 0, 0.3, 0.1])
    poly, = a.ports[1].shapes
    assert (poly.type, len(poly.points)) == ("polygon", 12)
    assert y.ports[0].extra == ["LAYER M1 SPACING 0.05 ;"]
    assert y.ports[0].shapes[0].layer == "M1"


@pytest.mark.parametrize("body, line, text", [
    ("MACRO X\n  CLASS CORE ;\n", 1, "has no 'END X'"),
    ("MACRO X\n  PIN A\n  END B\nEND X\n", 3, "expected 'END A' for PIN A"),
    ("MACRO X\n  PIN A\n    PORT\n      RECT 0 0 1 1 ;\n    END\n  END A\nEND X\n", 4,
     "RECT before any LAYER"),
    ("MACRO X\n  PIN A\n    PORT\n      LAYER M1 ;\n      RECT 0 0 1 ;\n", 5, "RECT needs 4"),
    ("MACRO X\n  PIN A\n    PORT\n      LAYER M1 ;\n      POLYGON 0 0 1 1 ;\n", 5,
     "POLYGON needs 3"),
    ("MACRO X\n  SIZE a BY 1 ;\nEND X\n", 2, "expected a number"),
])
def test_parse_errors(write_lef, body, line, text):
    with pytest.raises(LefParseError) as e:
        parse_cell_lef(write_lef(body))
    assert text in e.value.text and e.value.line == line


# -- read_lef ---------------------------------------------------------------------

def test_read_lef_summary_and_layer_message(tech_session):
    tech_session.eval(f"read_lef -file {{{CELLS_LEF}}}")
    out = tech_session.out.getvalue()
    assert "Cells       : 3 added" in out
    assert "Pins        : 3, ports 3, shapes 4" in out
    assert "Pin layers  : M1(2) H1(2)" in out
    assert "In tech     : H1" in out
    assert "WARN: (HT4-064): 2 pin shape(s) on layers not in tech: M1. " \
           "They are kept but ignored in calculations" in out
    assert "WARN: (HT4-063): 1 SITE statement(s) not modeled" in out


def test_read_lef_without_tech(session):
    session.eval(f"read_lef -file {{{CELLS_LEF}}}")
    assert "WARN: (HT4-065): no tech data loaded" in session.out.getvalue()
    assert session.eval("get_db layer_shape:INV_D1/A/1/2 .in_tech") == "false"
    session.eval(f"read_tech -file {{{TECH_LEF}}}")          # in_tech is evaluated live
    assert session.eval("get_db layer_shape:INV_D1/A/1/2 .in_tech") == "true"


def test_read_lef_errors(session, tmp_path, write_lef):
    assert "HT4-001" in err(session, "read_lef")
    assert "HT4-060" in err(session, f"read_lef -file {tmp_path}/none.lef")
    bad = write_lef("MACRO X\n")
    assert "HT4-061" in err(session, f"read_lef -file {bad}")
    assert "HT4-026" in err(session, "get_db library_physical")   # db unchanged


def test_second_file_adds_and_duplicates_warn(lib_session, write_lef):
    more = write_lef("MACRO NAND2\nEND NAND2\nMACRO INV_D1\n  CLASS BLOCK ;\nEND INV_D1\n")
    lib_session.eval(f"read_lef -file {more}")
    out = lib_session.out.getvalue()
    assert "WARN: (HT4-062): MACRO INV_D1 is already in the library" in out
    assert "Cells       : 1 added, 1 duplicate(s) skipped" in out
    assert lib_session.eval("get_db lib_cells .ref_name") == " ".join(CELLS + ["NAND2"])
    assert lib_session.eval("get_db lib_cell:INV_D1 .class") == "core"
    assert len(lib_session.split_list(lib_session.eval("get_db library_physical .files"))) == 2


# -- get_db: cells ------------------------------------------------------------------

def test_library_summary(lib_session):
    assert lib_session.eval("get_db library_physical") == "library_physical"
    out = lib_session.out.getvalue()
    assert "lib_cells           : 3" in out
    assert "lib_cell:INV_D1\n  class               : core\n  size                : 0.6 x 0.254\n" \
           "  site                : core\n  pins                : A Y\n" in out


@pytest.mark.parametrize("path", [".lib_cell", "lib_cells", "library_physical.lib_cells"])
def test_lib_cell_list(lib_session, path):
    assert lib_session.eval(f"get_db {path}") == " ".join(f"lib_cell:{c}" for c in CELLS)


def test_cell_attrs(lib_session):
    ev = lib_session.eval
    assert ev("get_db lib_cell:INV_D1 .ref_name") == "INV_D1"
    assert ev("get_db lib_cell:INV_D1 .class") == "core"
    assert (ev("get_db lib_cell:INV_D1 .size_x"), ev("get_db lib_cell:INV_D1 .size_y")) == \
        ("0.6", "0.254")
    assert ev("get_db lib_cell:INV_D1 .site") == "core"
    assert ev("get_db lib_cell:PAD1 .class") == "pad inout"
    assert ev("get_db lib_cell:PAD1 .site") == ""
    assert ev("get_db lib_cell:INV_D1 .lib_pins") == "lib_pin:INV_D1/A lib_pin:INV_D1/Y"
    assert ev("get_db lib_cell:INV_D1 .extra") == "{ORIGIN 0 0 ;} {SYMMETRY X Y ;}"
    assert ev("get_db lib_cell:INV_D1 .file") == str(CELLS_LEF)
    assert ev("get_db lib_cells -if {.size_y > 0.3} .name") == "INV_D2"


# -- get_db: pins, ports, shapes ----------------------------------------------------

def test_pin_attrs(lib_session):
    ev = lib_session.eval
    assert (ev(f"get_db {A} .name"), ev(f"get_db {A} .direction"), ev(f"get_db {A} .use")) == \
        ("A", "in", "signal")
    assert ev(f"get_db {A} .lib_ports") == "lib_port:INV_D1/A/1 lib_port:INV_D1/A/2"
    assert ev(f"get_db {A} .layers") == "M1 H1"
    assert ev(f"get_db {A} .tech_layers") == "H1"
    assert ev(f"get_db {A} .lib_cell") == "lib_cell:INV_D1"
    assert ev(f"get_db {A} .extra") == "{ANTENNAGATEAREA 0.01 LAYER M1 ;}"
    assert ev("get_db lib_cells.lib_pins.name -if {.direction == out}") == "Y INV_D2X"


def test_port_and_shape_attrs(lib_session):
    ev = lib_session.eval
    assert ev("get_db lib_port:INV_D1/A/1 .layer_shapes") == \
        "layer_shape:INV_D1/A/1/1 layer_shape:INV_D1/A/1/2"
    assert ev("get_db lib_port:INV_D1/A/1 .layers") == "M1 H1"
    assert ev("get_db lib_port:INV_D1/Y/1 .extra") == "{LAYER M1 SPACING 0.05 ;}"
    s = "layer_shape:INV_D1/A/1/1"
    assert (ev(f"get_db {s} .layer"), ev(f"get_db {s} .type")) == ("M1", "rect")
    assert ev(f"get_db {s} .points") == "0.1 0.2 0 0"
    assert ev(f"get_db {s} .rect") == "0 0 0.1 0.2"               # normalized
    assert ev(f"get_db {s} .in_tech") == "false"
    assert ev("get_db layer_shape:INV_D1/A/1/2 .mask") == "2"
    poly = "layer_shape:INV_D1/A/2/1"
    assert ev(f"get_db {poly} .type") == "polygon"
    assert ev(f"get_db {poly} .rect") == "0 0 0.4 0.2"            # bounding box


def test_tech_layer_shapes_query(lib_session):
    got = lib_session.eval(
        f"get_db [get_db {A} .lib_ports.layer_shapes] -if {{.in_tech == true}} .rect")
    assert lib_session.split_list(got) == ("0.2 0 0.3 0.1", "0 0 0.4 0.2")


@pytest.mark.parametrize("handle", ["lib_cell:NOPE", "lib_pin:INV_D1/B", "lib_pin:INV_D1",
                                    "lib_port:INV_D1/A/3", "lib_port:INV_D1/A/x",
                                    "layer_shape:INV_D1/A/1/9", "layer_shape:INV_D1/A/1"])
def test_missing_objects(lib_session, handle):
    assert "HT4-022" in err(lib_session, f"get_db {handle} .name")


def test_bad_attr(lib_session):
    assert "HT4-023" in err(lib_session, f"get_db {A} .bogus")


def test_no_library_loaded(session):
    assert "HT4-026" in err(session, "get_db lib_cells")
    assert "HT4-026" in err(session, "get_db .lib_cell")


def test_round_trip(lib_session, tmp_path):
    db = tmp_path / "lib.db"
    lib_session.eval(f"write_db {db}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {db}")
    assert fresh.eval("get_db lib_cells .ref_name") == " ".join(CELLS)
    assert fresh.eval("get_db layer_shape:INV_D1/A/2/1 .rect") == "0 0 0.4 0.2"


def test_completion(lib_session):
    from core.complete import Completer
    c = Completer(lib_session)

    def comp(line):
        begidx = line.rfind(" ") + 1
        return c.candidates(line, begidx, line[begidx:])

    assert comp("get_db .lib") == [".library_physical", ".lib_cells", ".lib_cell"]
    assert comp("get_db lib_cell:INV") == ["lib_cell:INV_D1 ", "lib_cell:INV_D2 "]
    assert comp("get_db lib_pin:INV_D1/") == ["lib_pin:INV_D1/A ", "lib_pin:INV_D1/Y "]
    assert ".lib_ports" in comp("get_db lib_pin:INV_D1/A .")
    assert comp("get_db .lib_cell.lib_pins.lib_ports.layer_shapes.in") == \
        [".lib_cell.lib_pins.lib_ports.layer_shapes.in_tech "]


# -- -if filters the end of the chain (Cadence behavior) -----------------------------

def test_if_filters_returned_pins(lib_session):
    # The user's form: -if applies to the pins .lib_pins returns, not to the cells.
    got = lib_session.eval("get_db [get_db lib_cells -if {.name == INV_D1}] .lib_pins "
                           "-if {.direction == out}")
    assert got == "lib_pin:INV_D1/Y"
    assert lib_session.eval("get_db lib_cell:INV_D1 .lib_pins.name -if {.direction == in}") == "A"


def test_if_on_value_filters_owners(lib_session):
    assert lib_session.eval("get_db lib_cells .name -if {.class == pad*}") == "PAD1"


def test_if_through_deep_chain(lib_session):
    got = lib_session.eval("get_db lib_cell:INV_D1 .lib_pins.lib_ports.layer_shapes.rect "
                           "-if {.in_tech == true}")
    assert lib_session.split_list(got) == ("0.2 0 0.3 0.1", "0 0 0.4 0.2")


def test_pin_without_direction(lib_session, write_lef):
    lef = write_lef("MACRO NODIR\n  PIN P\n  END P\nEND NODIR\n")
    lib_session.eval(f"read_lef -file {lef}")
    assert lib_session.eval("get_db lib_pin:NODIR/P .direction") == ""
    assert lib_session.eval("get_db lib_cell:NODIR .lib_pins -if {.direction == out}") == ""
    assert lib_session.eval('get_db lib_cell:NODIR .lib_pins -if {.direction == ""}') == \
        "lib_pin:NODIR/P"
    assert lib_session.eval("get_db lib_cell:NODIR .lib_pins -if {!.direction}") == \
        "lib_pin:NODIR/P"


@pytest.mark.parametrize("lef_dir, value", [("INPUT", "in"), ("OUTPUT", "out"),
                                            ("INOUT", "inout"), ("FEEDTHRU", "feedthru")])
def test_direction_values(write_lef, lef_dir, value):
    lef = write_lef(f"MACRO C\n  PIN P\n    DIRECTION {lef_dir} ;\n  END P\nEND C\n")
    assert parse_cell_lef(lef).macros[0].pins[0].direction == value
