import pytest

from core.lef import LefParseError, parse_tech_lef
from conftest import TECH_LEF


def test_tech_lef_header_and_layers():
    tech = parse_tech_lef(str(TECH_LEF))
    assert tech.lef_version == "5.8"
    assert tech.db_units == 4000
    assert tech.manufacturing_grid == 0.00025
    assert [l.name for l in tech.layers] == ["H1", "H2", "G1", "G2", "IA", "IB"]
    assert tech.extras == []


def test_tech_lef_layer_values():
    layers = {l.name: l for l in parse_tech_lef(str(TECH_LEF)).layers}
    h1 = layers["H1"]
    assert (h1.type, h1.direction) == ("routing", "horizontal")
    assert (h1.pitch_x, h1.pitch_y, h1.offset_x, h1.offset_y) == (0.128, 0.128, 0.0, 0.0)
    assert (h1.width, h1.min_width, h1.max_width) == (0.064, 0.064, 4.0)
    assert (h1.area, h1.min_enclosed_area) == (0.02, 0.07)
    assert (h1.min_step, h1.min_step_max_edges) == (0.06425, 1)
    assert layers["G1"].pitch_x == 0.378
    ib = layers["IB"]
    assert (ib.direction, ib.pitch_x, ib.offset_x, ib.min_width) == ("vertical", 0.72, 0.36, 0.36)
    assert ib.min_step is None and ib.min_spacing is None
    assert ib.extra == []
    assert ib.lef_text.startswith("LAYER IB") and ib.lef_text.endswith("END IB")
    assert "# Iz.W.1" in ib.lef_text


LEF_EXTRAS = """VERSION 5.8 ;
BUSBITCHARS "[]" ;
UNITS
  DATABASE MICRONS 2000 ;
  TIME NANOSECONDS 1 ;
END UNITS
LAYER M1
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 0.2 ;
  OFFSET 0.1 ;
  SPACING 0.08 ;
  SPACING 0.06 ;
  SPACING 0.1 RANGE 0.3 10 ;
  PROPERTY LEF58_X "SPACING 0.1 ; # not a comment" ;
  MINSTEP 0.05 LENGTHSUM 0.1 ;
END M1
LAYER V1
  TYPE CUT ;
END V1
VIA V1_0 DEFAULT
  LAYER M1 ;
    RECT -0.1 -0.1 0.1 0.1 ;
END V1_0
SITE core
  SIZE 0.2 BY 1.2 ;
END core
END LIBRARY
"""


def test_extras_are_kept(write_lef):
    tech = parse_tech_lef(write_lef(LEF_EXTRAS))
    assert tech.db_units == 2000
    m1, v1 = tech.layers
    assert (m1.pitch_x, m1.pitch_y, m1.offset_x, m1.offset_y) == (0.2, 0.2, 0.1, 0.1)
    assert m1.min_spacing == 0.06
    assert m1.min_step is None
    assert m1.extra == [
        "SPACING 0.1 RANGE 0.3 10 ;",
        'PROPERTY LEF58_X "SPACING 0.1 ; # not a comment" ;',
        "MINSTEP 0.05 LENGTHSUM 0.1 ;",
    ]
    assert v1.type == "cut"
    kinds = [(e.kind, e.line) for e in tech.extras]
    assert kinds == [("BUSBITCHARS", 2), ("UNITS", 5), ("VIA", 21), ("SITE", 25)]
    assert tech.extras[2].text.splitlines()[-1] == "END V1_0"


LEF_MULTILINE_PROPERTY = """LAYER D12
  TYPE ROUTING ;
  PROPERTY LEF58_MINSTEP "
    MINSTEP 0.03925 MAXEDGES 1 ;
    # not a comment ;
    MINSTEP 0.040 MAXEDGES 1 ; " ;
  # a real comment ; with a semicolon
  SPACING 0.038 ;
END D12
"""


def test_multiline_quoted_property_is_one_statement(write_lef):
    d12, = parse_tech_lef(write_lef(LEF_MULTILINE_PROPERTY)).layers
    assert d12.extra == ['PROPERTY LEF58_MINSTEP "\n    MINSTEP 0.03925 MAXEDGES 1 ;\n'
                         '    # not a comment ;\n    MINSTEP 0.040 MAXEDGES 1 ; " ;']
    assert d12.min_spacing == 0.038           # statement after the string parses


@pytest.mark.parametrize("body, line, text", [
    ('LAYER M1\n  WIDTH 0.1 ;\n  PROPERTY X "\n  A ;\nEND M1\n', 3, "no closing"),
    ("LAYER M1\n  TYPE ROUTING ;\n", 1, "has no 'END M1'"),
    ("LAYER M1\n  WIDTH abc ;\nEND M1\n", 2, "expected a number"),
    ("LAYER M1\nEND M2\n", 2, "expected 'END M1'"),
    ("LAYER M1\nEND M1\nLAYER M1\nEND M1\n", 3, "duplicate layer"),
    ("UNITS\n  DATABASE MICRONS 2000 ;\n", 1, "no END UNITS"),
])
def test_parse_errors(write_lef, body, line, text):
    with pytest.raises(LefParseError) as err:
        parse_tech_lef(write_lef(body))
    assert err.value.line == line
    assert text in err.value.text
