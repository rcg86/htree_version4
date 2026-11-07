import gzip
import io
import shutil
import tkinter

import pytest

from conftest import ROOT, TECH_LEF
from core.def_parser import DefParseError, parse_def, polygon_area
from core.htree_builder import Session

SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def def_session(tech_session):
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


def ports_by_name():
    return {p.name: p for p in parse_def(str(SMALL_DEF)).ports}


# -- parser -----------------------------------------------------------------------

def test_header_and_boundary():
    d = parse_def(str(SMALL_DEF))
    assert (d.name, d.version, d.units, d.divider, d.busbit) == ("top", "5.8", 1000, "/", "[]")
    # '*' repeats the previous coordinate
    assert d.boundary == [0, 0, 100, 0, 100, 50, 40, 50, 40, 80, 0, 80]
    assert polygon_area(d.boundary) == 100 * 50 + 40 * 30
    assert dict(d.skipped) == {"PROPERTYDEFINITIONS": 1, "ROW": 2, "COMPONENTS": 1, "NETS": 1}


def test_rect_diearea(write_lef):
    path = write_lef("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nDIEAREA ( 0 0 ) ( 200 100 ) ;\n"
                     "END DESIGN\n", "t.def")
    assert parse_def(path).boundary == [0, 0, 2, 0, 2, 1, 0, 1]


def test_pin_basics_and_orientations():
    p = ports_by_name()
    a = p["a"]
    assert (a.net, a.direction, a.use, a.special, a.status) == ("a", "in", "signal", False, "fixed")
    assert (a.x, a.y, a.orient) == (10, 0, "N")
    assert a.shapes[0].points == [9.95, 0, 10.05, 0.4]                     # N
    y = p["y[0]"]
    assert (y.direction, y.use, y.status, y.orient) == ("out", "clock", "placed", "W")
    assert (y.shapes[0].layer, y.shapes[0].mask) == ("M1", 2)
    assert y.shapes[0].points == [99.6, 19.95, 100, 20.05]                 # W: (x,y)->(-y,x)
    c = p["c"]
    assert c.direction == "feedthru"
    assert c.shapes[0].points == [0, 29.9, 0.2, 30]                        # E: (x,y)->(y,-x)
    d = p["d"]
    assert d.use is None
    assert d.shapes[0].points == [50, 50, 50.2, 50.1]                      # FE: (x,y)->(y,x)


def test_multiple_ports():
    b = ports_by_name()["b"]
    assert (b.direction, b.extra[0]) == ("inout", "+ DIRECTION INOUT TRISTATE")
    assert "+ VIA V12 ( 0 0 )" in b.extra
    assert (b.status, b.x, b.y, b.orient) == ("fixed", 20, 0, "FN")       # first PORT
    rect, poly = b.shapes
    assert rect.points == [19.9, 0, 20, 0.2]                               # FN: (x,y)->(-x,y)
    assert poly.type == "polygon"                                          # S, '*' repeat
    assert poly.points == [30, 80, 29.7, 80, 29.7, 79.9, 30, 79.9]


def test_special_pin_without_shape():
    vdd = ports_by_name()["VDD"]
    assert (vdd.special, vdd.status, vdd.shapes, vdd.use) == (True, "unplaced", [], "power")


def test_gzip(tmp_path):
    gz = tmp_path / "small.def.gz"
    with open(SMALL_DEF, "rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    assert len(parse_def(str(gz)).ports) == 6


@pytest.mark.parametrize("body, line, text", [
    ("DESIGN t ;\nPINS 1 ;\n- a + NET a ;\nEND PINS\n", 2, "PINS before UNITS"),
    ("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nPINS 1 ;\n- a + LAYER H1 ( 0 0 ) ;\nEND PINS\n",
     4, "+ LAYER needs 2 points"),
    ("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nPINS 1 ;\n- a + FIXED ( 0 0 ) Q ;\nEND PINS\n",
     4, "expected '+ FIXED ( x y ) <orient>'"),
    ("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nPINS 1 ;\n- a + NET a ;\n", 3,
     "has no 'END PINS'"),
    ("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nDIEAREA ( 0 0 ) ( 1 x ) ;\n", 3,
     "expected a number"),
    ("DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\nDIEAREA ( 0 0 ) ( 1 1 ) ( 2 2 ) ;\n", 3,
     "DIEAREA needs 2 points"),
    ("DESIGN t ;\nCOMPONENTS 1 ;\n- u1 INV ;\n", 2, "has no 'END COMPONENTS'"),
])
def test_parse_errors(write_lef, body, line, text):
    with pytest.raises(DefParseError) as e:
        parse_def(write_lef(body, "t.def"))
    assert text in e.value.text and e.value.line == line


# -- read_def ---------------------------------------------------------------------

def test_read_def_summary(tech_session):
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    out = tech_session.out.getvalue()
    assert "Design      : top (DEF 5.8, 1000 units/micron)" in out
    assert "Boundary    : polygon, 6 points, bbox 0 0 100 80" in out
    assert "Pins        : 6, shapes 6" in out
    assert "Tracks      : 3 patterns on 3 layers (H1 H2 M1)" in out
    assert "Tracks tech : H1 H2, tech layers without tracks: G1 G2 IA IB" in out
    assert "Skipped     : PROPERTYDEFINITIONS ROW(2) COMPONENTS NETS" in out
    assert "In tech     : H1 H2" in out
    assert "WARN: (HT4-093): 1 pin shape(s) on layers not in tech: M1." in out


def test_read_def_without_tech(session):
    session.eval(f"read_def -file {{{SMALL_DEF}}}")
    assert "WARN: (HT4-094)" in session.out.getvalue()
    assert session.eval("get_db port_shape:top/a/1 .in_tech") == "false"
    session.eval(f"read_tech -file {{{TECH_LEF}}}")                 # evaluated live
    assert session.eval("get_db port_shape:top/a/1 .in_tech") == "true"


def test_read_def_errors(session, tmp_path, write_lef):
    assert "HT4-001" in err(session, "read_def")
    assert "HT4-090" in err(session, f"read_def -file {tmp_path}/none.def")
    bad = write_lef("DESIGN t ;\nPINS 1 ;\n", "bad.def")
    assert "HT4-091" in err(session, f"read_def -file {bad}")
    nodesign = write_lef("UNITS DISTANCE MICRONS 100 ;\nEND DESIGN\n", "nd.def")
    assert "no DESIGN statement" in err(session, f"read_def -file {nodesign}")
    assert "HT4-028" in err(session, "get_db design")                # db unchanged


def test_reread_replaces(def_session, write_lef):
    other = write_lef("DESIGN t2 ;\nUNITS DISTANCE MICRONS 100 ;\nEND DESIGN\n", "t2.def")
    def_session.eval(f"read_def -file {other}")
    out = def_session.out.getvalue()
    assert "WARN: (HT4-092): replacing design top" in out
    assert "WARN: (HT4-095): no DIEAREA" in out
    assert def_session.eval("get_db designs") == "design:t2"
    assert def_session.eval("get_db design:t2 .ports") == ""


# -- get_db -----------------------------------------------------------------------

def test_get_db_design_prints_summary(def_session):
    assert def_session.eval("get_db design") == "design:top"
    out = def_session.out.getvalue()
    for line in ["design:top\n", "  bbox                : 0 0 100 80",
                 "  area                : 6200", "  boundary            : polygon, 6 points",
                 "  ports               : 6", "    direction         : in 2",
                 "    status            : fixed 4  placed 1  unplaced 1",
                 "  track_patterns      : 3 on 3 layers", "    tech layers       : H1 H2",
                 "    shape layers      : H1 4  M1 1*  H2 1"]:
        assert line in out, line


def test_design_attrs(def_session):
    ev = def_session.eval
    assert ev("get_db designs") == "design:top"
    assert ev("get_db design:top .boundary") == "0 0 100 0 100 50 40 50 40 80 0 80"
    assert ev("get_db design:top .bbox") == "0 0 100 80"
    assert ev("get_db design:top .units") == "1000"
    assert ev("get_db design:top .file") == str(SMALL_DEF)
    assert ev("llength [get_db design:top .ports]") == "6"


def test_port_attrs(def_session):
    ev = def_session.eval
    p = "{port:top/y[0]}"
    assert ev(f"get_db {p} .name") == "y[0]"
    assert (ev(f"get_db {p} .direction"), ev(f"get_db {p} .use")) == ("out", "clock")
    assert (ev(f"get_db {p} .status"), ev(f"get_db {p} .orient")) == ("placed", "W")
    assert ev(f"get_db {p} .location") == "100 20"
    assert ev(f"get_db {p} .rect") == "99.6 19.95 100 20.05"
    assert ev(f"get_db {p} .layers") == "M1"
    assert ev(f"get_db {p} .design") == "design:top"
    assert ev("get_db port:top/b .layers") == "H1 H2"
    assert ev("get_db port:top/b .rect") == "19.9 0 30 80"              # bbox of both ports
    assert ev("get_db port:top/b .extra") == "{+ DIRECTION INOUT TRISTATE} {+ VIA V12 ( 0 0 )}"
    assert ev("get_db port:top/VDD .special") == "true"
    assert ev("get_db port:top/VDD .location") == ""
    assert ev("get_db port:top/VDD .rect") == ""


def test_port_shape_attrs(def_session):
    ev = def_session.eval
    s = "port_shape:top/b/2"
    assert (ev(f"get_db {s} .layer"), ev(f"get_db {s} .type")) == ("H2", "polygon")
    assert ev(f"get_db {s} .rect") == "29.7 79.9 30 80"
    assert ev(f"get_db {s} .in_tech") == "true"
    assert ev(f"get_db {s} .port") == "port:top/b"
    assert ev("get_db {port_shape:top/y[0]/1} .mask") == "2"


def test_filters(def_session):
    ev = def_session.eval
    assert ev("get_db ports .name -if {.direction == in}") == "a d"
    assert ev("get_db ports .name -if {.layers == H1 && .orient == N}") == "a"
    assert ev("get_db design .ports.port_shapes.rect -if {.in_tech == false}") == \
        "99.6 19.95 100 20.05"
    assert ev("get_db ports A*") == ""
    assert ev("get_db ports {y*}") == "{port:top/y[0]}"


@pytest.mark.parametrize("handle", ["design:nope", "port:top/zz", "port:nope/a",
                                    "port_shape:top/a/2", "port_shape:top/a"])
def test_missing(def_session, handle):
    assert "HT4-022" in err(def_session, f"get_db {{{handle}}} .name")


def test_round_trip(def_session, tmp_path):
    db = tmp_path / "d.db"
    def_session.eval(f"write_db {db}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {db}")
    assert fresh.eval("get_db port:top/b .rect") == "19.9 0 30 80"
    assert fresh.eval("get_db design:top .bbox") == "0 0 100 80"


def test_completion(def_session):
    from core.complete import Completer
    c = Completer(def_session)

    def comp(line):
        b = line.rfind(" ") + 1
        return c.candidates(line, b, line[b:])

    assert ".design" in comp("get_db .d")
    assert comp("get_db port:top/") == [f"port:top/{n} " for n in
                                        ["a", "y[0]", "b", "c", "d", "VDD"]]
    assert comp("get_db .design.ports.port_shapes.in") == [".design.ports.port_shapes.in_tech "]


# -- TRACKS -----------------------------------------------------------------------

def test_parse_tracks():
    t1, t2, t3 = parse_def(str(SMALL_DEF)).tracks
    assert (t1.direction, t1.start, t1.num_tracks, t1.step, t1.layers, t1.mask) == \
        ("x", 0.05, 1000, 0.1, ["H1"], None)
    assert (t2.direction, t2.start, t2.mask, t2.same_mask, t2.layers) == \
        ("y", 0.025, 2, True, ["H2", "M1"])                   # inline '# WIDTH' ignored
    assert (t3.mask, t3.same_mask, t3.start, t3.line) == (1, False, 0.075, 19)  # leading MASK


@pytest.mark.parametrize("body, text", [
    ("TRACKS Z 0 DO 1 STEP 1 LAYER M1 ;", "expected 'TRACKS {X|Y}"),
    ("TRACKS X 0 DO 0 STEP 1 LAYER M1 ;", "count must be 1 or more"),
    ("TRACKS X 0 DO 2 STEP 1 FOO M1 ;", "unexpected 'FOO'"),
])
def test_track_errors(write_lef, body, text):
    path = write_lef(f"DESIGN t ;\nUNITS DISTANCE MICRONS 100 ;\n{body}\n", "t.def")
    with pytest.raises(DefParseError) as e:
        parse_def(path)
    assert text in e.value.text and e.value.line == 3


def test_track_pattern_attrs(def_session):
    ev = def_session.eval
    assert ev("get_db track_patterns") == \
        "track_pattern:top/1 track_pattern:top/2 track_pattern:top/3"
    assert ev("get_db design:top .track_patterns") == ev("get_db track_patterns")
    t = "track_pattern:top/2"
    expected = {"name": "2", "direction": "y", "start": "0.025", "num_tracks": "800",
                "step": "0.1", "end": "79.925", "mask": "2", "same_mask": "true",
                "layers": "H2 M1", "design": "design:top"}
    for attr, value in expected.items():
        assert ev(f"get_db {t} .{attr}") == value, attr
    assert ev("get_db track_pattern:top/1 .mask") == ""


def test_track_filters(def_session):
    ev = def_session.eval
    assert ev("get_db track_patterns .name -if {.layers == H2}") == "3"   # list attr: whole text
    assert ev("get_db track_patterns .name -if {.layers == *H2*}") == "2 3"
    assert ev("get_db track_patterns .start -if {.direction == y && .mask == 1}") == "0.075"


@pytest.mark.parametrize("handle", ["track_pattern:top/4", "track_pattern:top/0",
                                    "track_pattern:top/x", "track_pattern:other/1"])
def test_missing_track(def_session, handle):
    assert "HT4-022" in err(def_session, f"get_db {handle} .name")


def test_tracks_round_trip_and_replace(def_session, tmp_path, write_lef):
    db = tmp_path / "t.db"
    def_session.eval(f"write_db {db}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {db}")
    assert fresh.eval("get_db track_pattern:top/2 .layers") == "H2 M1"
    other = write_lef("DESIGN t2 ;\nUNITS DISTANCE MICRONS 100 ;\nEND DESIGN\n", "t2.def")
    def_session.eval(f"read_def -file {other}")
    assert def_session.eval("get_db design:t2 .track_patterns") == ""
