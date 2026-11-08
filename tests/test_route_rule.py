import io
import tkinter

import pytest

from core.htree_builder import Session

TECH = """VERSION 5.8 ;
UNITS
  DATABASE MICRONS 4000 ;
END UNITS
MANUFACTURINGGRID 0.00025 ;

LAYER D12
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  WIDTH 0.038 ;
  SPACING 0.038 ;
END D12

LAYER H2
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  WIDTH 0.064 ;
  MINWIDTH 0.064 ;
  MAXWIDTH 4.000 ;
  SPACINGTABLE TWOWIDTHS
    WIDTH 0.000         0.064 0.105 0.175 0.175
    WIDTH 0.196 PRL 0.0 0.105 0.140 0.210 0.210
    WIDTH 0.700 PRL 0.0 0.175 0.210 0.280 0.280
    WIDTH 1.500 PRL 0.0 0.175 0.210 0.280 0.550 ;
END H2

LAYER M5
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  WIDTH 0.1 ;
  SPACINGTABLE
    PARALLELRUNLENGTH 0.0 1.0 2.0
    WIDTH 0.0   0.1 0.12 0.14
    WIDTH 0.3   0.2 0.25 0.3 ;
END M5

LAYER NOSP
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  WIDTH 0.1 ;
END NOSP

LAYER V1
  TYPE CUT ;
  WIDTH 0.05 ;
END V1
"""


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def tech(write_lef):
    s = Session(out=io.StringIO())
    s.eval(f"read_tech -file {{{write_lef(TECH)}}}")
    s.out.seek(0)
    s.out.truncate()
    return s


def test_default_spacing_from_twowidths_table(tech):
    assert tech.eval("create_route_rule -layer H2 -width 0.41") == "route_rule:H2"
    assert tech.eval("get_db route_rule:H2 .spacing") == "0.105"      # row 0.196, first column
    assert tech.eval("get_db route_rule:H2 .spacing_given") == "false"
    assert tech.eval("get_db route_rule:H2 .pitch") == "0.515"
    assert "spacing 0.105 on each side" in tech.out.getvalue()


@pytest.mark.parametrize("width, spacing", [("0.064", "0.064"), ("0.196", "0.105"),
                                            ("0.7", "0.175"), ("2", "0.175")])
def test_twowidths_row_follows_width(tech, width, spacing):
    tech.eval(f"create_route_rule -layer H2 -width {width}")
    assert tech.eval("get_db route_rule:H2 .spacing") == spacing


def test_parallel_run_table_uses_longest_run(tech):
    tech.eval("create_route_rule -layer M5 -width 0.3")
    assert tech.eval("get_db route_rule:M5 .spacing") == "0.3"


def test_plain_spacing(tech):
    tech.eval("create_route_rule -layer layer:D12 -width 0.038")
    assert tech.eval("get_db route_rule:D12 .spacing") == "0.038"


def test_given_spacing(tech):
    tech.eval("create_route_rule -layer H2 -width 0.41 -spacing 0.2")
    assert tech.eval("get_db route_rule:H2 .spacing") == "0.2"
    assert tech.eval("get_db route_rule:H2 .spacing_given") == "true"
    assert tech.eval("get_db route_rule:H2 .tech_spacing") == "0.105"
    assert tech.eval("get_db route_rule:H2 .tech_min_width") == "0.064"


def test_spacing_below_tech(tech):
    assert "HT4-132" in err(tech, "create_route_rule -layer H2 -width 0.41 -spacing 0.1")


def test_no_tech_spacing_needs_option(tech):
    assert "HT4-132" in err(tech, "create_route_rule -layer NOSP -width 0.1")
    tech.eval("create_route_rule -layer NOSP -width 0.1 -spacing 0.1")


@pytest.mark.parametrize("width", ["0.05", "4.5"])
def test_width_limits(tech, width):
    assert "HT4-131" in err(tech, f"create_route_rule -layer H2 -width {width}")


@pytest.mark.parametrize("script", [
    "create_route_rule -layer H2",
    "create_route_rule -width 0.1",
    "create_route_rule -layer H2 -width abc",
    "create_route_rule -layer H2 -width 0",
    "create_route_rule -layer H2 -width 0.1 -spacing -1",
])
def test_usage_errors(tech, script):
    assert "HT4-001" in err(tech, script)


def test_layer_errors(tech):
    assert "HT4-130" in err(tech, "create_route_rule -layer XX -width 0.1")
    assert "HT4-130" in err(tech, "create_route_rule -layer V1 -width 0.05")
    assert "HT4-130" in err(Session(out=io.StringIO()), "create_route_rule -layer H2 -width 0.1")


def test_replace_and_grid_warnings(tech):
    tech.eval("create_route_rule -layer H2 -width 0.41")
    tech.eval("create_route_rule -layer H2 -width 0.0641")
    out = tech.out.getvalue()
    assert "HT4-133" in out and "HT4-134" in out
    assert tech.eval("get_db route_rules") == "route_rule:H2"
    assert tech.eval("get_db route_rule:H2 .width") == "0.0641"


def test_rules_survive_write_and_read(tech, tmp_path):
    tech.eval("create_route_rule -layer H2 -width 0.41")
    tech.eval("create_route_rule -layer D12 -width 0.038")
    path = tmp_path / "r.db"
    tech.eval(f"write_db {{{path}}}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {{{path}}}")
    assert fresh.eval("get_db route_rules .name") == "H2 D12"


# -- -help on every command ------------------------------------------------------------

def test_every_command_has_help(session):
    for name in session.commands:
        session.out.seek(0)
        session.out.truncate()
        assert session.eval(f"{name} -help") == ""
        text = session.out.getvalue()
        for heading in ("NAME", "SYNOPSIS", "OPTIONS", "EXAMPLE"):
            assert f"\n{heading}\n" in "\n" + text, (name, heading)
        assert f"htree> {name}" in text, name
        assert "-help" in text, name


def test_help_runs_nothing(session):
    session.eval("read_tech -help")
    assert not session.db.has_tech()
    session.eval("exit -help")
    assert session.exit_code is None
