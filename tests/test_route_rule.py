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
    assert tech.eval("create_route_rule -name r1 -layer H2 -width 0.41") == "route_rule:r1"
    assert tech.eval("get_db route_rule_layer:r1/H2 .spacing") == "0.105"      # row 0.196, first column
    assert tech.eval("get_db route_rule_layer:r1/H2 .spacing_given") == "false"
    assert tech.eval("get_db route_rule_layer:r1/H2 .pitch") == "0.515"
    assert "spacing 0.105 on each side" in tech.out.getvalue()


@pytest.mark.parametrize("width, spacing", [("0.064", "0.064"), ("0.196", "0.105"),
                                            ("0.7", "0.175"), ("2", "0.175")])
def test_twowidths_row_follows_width(tech, width, spacing):
    tech.eval(f"create_route_rule -name r1 -layer H2 -width {width}")
    assert tech.eval("get_db route_rule_layer:r1/H2 .spacing") == spacing


def test_parallel_run_table_uses_longest_run(tech):
    tech.eval("create_route_rule -name r1 -layer M5 -width 0.3")
    assert tech.eval("get_db route_rule_layer:r1/M5 .spacing") == "0.3"


def test_plain_spacing(tech):
    tech.eval("create_route_rule -name r1 -layer layer:D12 -width 0.038")
    assert tech.eval("get_db route_rule_layer:r1/D12 .spacing") == "0.038"


def test_given_spacing(tech):
    tech.eval("create_route_rule -name r1 -layer H2 -width 0.41 -spacing 0.2")
    assert tech.eval("get_db route_rule_layer:r1/H2 .spacing") == "0.2"
    assert tech.eval("get_db route_rule_layer:r1/H2 .spacing_given") == "true"
    assert tech.eval("get_db route_rule_layer:r1/H2 .tech_spacing") == "0.105"
    assert tech.eval("get_db route_rule_layer:r1/H2 .tech_min_width") == "0.064"


def test_spacing_below_tech(tech):
    assert "HT4-132" in err(tech, "create_route_rule -name r1 -layer H2 -width 0.41 -spacing 0.1")


def test_no_tech_spacing_needs_option(tech):
    assert "HT4-132" in err(tech, "create_route_rule -name r1 -layer NOSP -width 0.1")
    tech.eval("create_route_rule -name r1 -layer NOSP -width 0.1 -spacing 0.1")


@pytest.mark.parametrize("width", ["0.05", "4.5"])
def test_width_limits(tech, width):
    assert "HT4-131" in err(tech, f"create_route_rule -name r1 -layer H2 -width {width}")


@pytest.mark.parametrize("script", [
    "create_route_rule -name r1 -layer H2",
    "create_route_rule -name r1 -width 0.1",
    "create_route_rule -layer H2 -width 0.1",
    "create_route_rule -name a/b -layer H2 -width 0.1",
    "create_route_rule -name {a b} -layer H2 -width 0.1",
    "create_route_rule -name r1 -layer H2 -width abc",
    "create_route_rule -name r1 -layer H2 -width 0",
    "create_route_rule -name r1 -layer H2 -width 0.1 -spacing -1",
])
def test_usage_errors(tech, script):
    assert "HT4-001" in err(tech, script)


def test_layer_errors(tech):
    assert "HT4-130" in err(tech, "create_route_rule -name r1 -layer XX -width 0.1")
    assert "HT4-130" in err(tech, "create_route_rule -name r1 -layer V1 -width 0.05")
    assert "HT4-130" in err(Session(out=io.StringIO()), "create_route_rule -name r1 -layer H2 -width 0.1")


def test_replace_and_grid_warnings(tech):
    tech.eval("create_route_rule -name r1 -layer H2 -width 0.41")
    tech.eval("create_route_rule -name r1 -layer H2 -width 0.0641")
    out = tech.out.getvalue()
    assert "HT4-133" in out and "HT4-134" in out
    assert tech.eval("get_db route_rules") == "route_rule:default route_rule:r1"
    assert tech.eval("get_db route_rule_layer:r1/H2 .width") == "0.0641"


# -- -name and -append ---------------------------------------------------------------

def test_append_adds_layers_to_one_rule(tech):
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.41")
    assert tech.eval("create_route_rule -name rule1 -layer D12 -width 0.038 -append") \
        == "route_rule:rule1"
    assert tech.eval("get_db route_rule:rule1 .layers") == "layer:H2 layer:D12"
    assert tech.eval("get_db route_rule:rule1 .route_rule_layers") == \
        "route_rule_layer:rule1/H2 route_rule_layer:rule1/D12"
    assert tech.eval("get_db route_rule:rule1 .route_rule_layers.width") == "0.41 0.038"
    assert tech.eval("get_db route_rule_layer:rule1/D12 .name") == "D12"
    assert tech.eval("get_db route_rule_layer:rule1/D12 .layer") == "layer:D12"
    assert tech.eval("get_db route_rule_layer:rule1/D12 .route_rule") == "route_rule:rule1"
    assert "HT4-133" not in tech.out.getvalue()


def test_without_append_replaces_the_whole_rule(tech):
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.41")
    tech.eval("create_route_rule -name rule1 -layer D12 -width 0.038 -append")
    tech.eval("create_route_rule -name rule1 -layer M5 -width 0.3")
    assert "replacing route rule rule1 (layers H2 D12)" in tech.out.getvalue()
    assert tech.eval("get_db route_rule:rule1 .layers.name") == "M5"


def test_append_same_layer_replaces_its_entry_in_place(tech):
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.41")
    tech.eval("create_route_rule -name rule1 -layer D12 -width 0.038 -append")
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.7 -append")
    assert "replacing the H2 entry of route rule rule1" in tech.out.getvalue()
    assert tech.eval("get_db route_rule:rule1 .layers.name") == "H2 D12"
    assert tech.eval("get_db route_rule_layer:rule1/H2 .spacing") == "0.175"


def test_rules_are_separate(tech):
    tech.eval("create_route_rule -name a -layer H2 -width 0.41")
    tech.eval("create_route_rule -name route_rule:b -layer H2 -width 0.7")
    assert tech.eval("get_db route_rules") == "route_rule:default route_rule:a route_rule:b"
    assert tech.eval("get_db route_rule_layer:a/H2 .width") == "0.41"
    assert tech.eval("get_db route_rule_layer:b/H2 .width") == "0.7"


def test_append_needs_an_existing_rule(tech):
    assert "HT4-135" in err(tech, "create_route_rule -name nope -layer H2 -width 0.41 -append")
    assert tech.eval("get_db route_rules") == "route_rule:default"


def test_failed_append_leaves_rule_unchanged(tech):
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.41")
    assert "HT4-131" in err(tech, "create_route_rule -name rule1 -layer H2 -width 9 -append")
    assert "HT4-130" in err(tech, "create_route_rule -name rule1 -layer V1 -width 0.05 -append")
    assert tech.eval("get_db route_rule:rule1 .layers.name") == "H2"
    assert tech.eval("get_db route_rule_layer:rule1/H2 .width") == "0.41"


def test_missing_rule_objects(tech):
    tech.eval("create_route_rule -name rule1 -layer H2 -width 0.41")
    for handle in ("route_rule:nope", "route_rule:rule1/H2", "route_rule_layer:rule1",
                   "route_rule_layer:rule1/D12"):
        assert "HT4-022" in err(tech, f"get_db {handle} .name"), handle


# -- the built-in default rule ------------------------------------------------------

def test_default_rule_is_tech_min_width_on_every_routing_layer(tech):
    assert tech.eval("get_db route_rule:default .layers.name") == "D12 H2 M5 NOSP"
    assert tech.eval("get_db route_rule:default .route_rule_layers.width") == \
        "0.038 0.064 0.1 0.1"
    assert tech.eval("get_db route_rule_layer:default/H2 .spacing") == "0.064"
    assert tech.eval("get_db route_rule_layer:default/H2 .pitch") == "0.128"
    assert tech.eval("get_db route_rule_layer:default/H2 .spacing_given") == "false"
    assert tech.eval("get_db route_rule_layer:default/NOSP .spacing") == ""   # no tech spacing
    assert tech.eval("get_db route_rule_layer:default/NOSP .pitch") == ""
    assert "HT4-022" in err(tech, "get_db route_rule_layer:default/V1 .width")


def test_default_name_is_reserved(tech):
    assert "HT4-136" in err(tech, "create_route_rule -name default -layer H2 -width 0.41")
    assert "HT4-136" in err(tech, "create_route_rule -name route_rule:default -layer H2 "
                                  "-width 0.41")


def test_default_rule_without_tech():
    s = Session(out=io.StringIO())
    assert s.eval("get_db route_rules") == "route_rule:default"
    assert s.eval("get_db route_rule:default .layers") == ""


def test_rules_survive_write_and_read(tech, tmp_path):
    tech.eval("create_route_rule -name r1 -layer H2 -width 0.41")
    tech.eval("create_route_rule -name r1 -layer D12 -width 0.038 -append")
    tech.eval("create_route_rule -name r2 -layer M5 -width 0.3")
    path = tmp_path / "r.db"
    tech.eval(f"write_db {{{path}}}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {{{path}}}")
    assert fresh.eval("get_db route_rules .name") == "default r1 r2"
    assert fresh.eval("get_db route_rule:r1 .layers.name") == "H2 D12"


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


@pytest.mark.parametrize("layers", ["{H2 D12}", "H2,D12", "{H2, D12}", "{layer:H2 layer:D12}"])
def test_layer_list_same_width_and_spacing(tech, layers):
    assert tech.eval(f"create_route_rule -name r -layer {layers} -width 0.41 -spacing 0.5") \
        == "route_rule:r"
    assert tech.eval("get_db route_rule:r .layers") == "layer:H2 layer:D12"
    assert tech.eval("get_db route_rule:r .route_rule_layers.width") == "0.41 0.41"
    assert tech.eval("get_db route_rule:r .route_rule_layers.spacing") == "0.5 0.5"
    assert "HT4-133" not in tech.out.getvalue()        # one new rule, nothing replaced


def test_layer_list_without_spacing_takes_each_layers_tech_spacing(tech):
    tech.eval("create_route_rule -name r -layer {H2 D12} -width 0.41")
    h2 = tech.eval("get_db route_rule_layer:r/H2 .tech_spacing")
    d12 = tech.eval("get_db route_rule_layer:r/D12 .tech_spacing")
    assert tech.eval("get_db route_rule:r .route_rule_layers.spacing") == f"{h2} {d12}"


def test_layer_list_append_and_replace(tech):
    tech.eval("create_route_rule -name r -layer H2 -width 0.41 -spacing 0.5")
    tech.eval("create_route_rule -name r -layer {D12 H2} -width 0.41 -spacing 0.6 -append")
    assert tech.eval("get_db route_rule:r .layers") == "layer:H2 layer:D12"
    assert tech.eval("get_db route_rule:r .route_rule_layers.spacing") == "0.6 0.6"
    tech.eval("create_route_rule -name r -layer {D12 H2} -width 0.41 -spacing 0.5")
    assert tech.eval("get_db route_rule:r .layers") == "layer:D12 layer:H2"   # replaced


def test_layer_list_checks_every_layer_first(tech):
    tech.eval("create_route_rule -name r -layer H2 -width 0.41 -spacing 0.5")
    with pytest.raises(tkinter.TclError, match="HT4-130"):
        tech.eval("create_route_rule -name r -layer {D12 NOPE} -width 0.41 -spacing 0.5")
    assert tech.eval("get_db route_rule:r .layers") == "layer:H2"           # unchanged
    with pytest.raises(tkinter.TclError, match="HT4-001"):
        tech.eval("create_route_rule -name r -layer {} -width 0.41")
