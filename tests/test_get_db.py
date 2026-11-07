import tkinter

import pytest


def ev(session, script):
    return session.eval(script)


# -- the three forms the user specified ---------------------------------------

def test_get_db_tech_prints_everything(tech_session):
    assert ev(tech_session, "get_db tech") == "tech"
    out = tech_session.out.getvalue()
    assert "db_units            : 4000" in out
    assert "manufacturing_grid  : 0.00025" in out
    for name in ("H1", "H2", "G1", "G2", "IA", "IB"):
        assert f"layer:{name}\n" in out
    assert "min_enclosed_area   : 0.7047" in out


def test_get_db_tech_layer(tech_session):
    assert ev(tech_session, "get_db tech.layer") == \
        "layer:H1 layer:H2 layer:G1 layer:G2 layer:IA layer:IB"


@pytest.mark.parametrize("cond", ["(.name == IA)", "{.name == IA}"])
def test_nested_min_width(tech_session, cond):
    assert ev(tech_session, f"get_db [get_db tech.layer -if {cond}] .min_width") == "0.36"


# -- handles, aliases, attributes ---------------------------------------------

def test_name_and_handle(tech_session):
    assert ev(tech_session, "get_db layer:IA .name") == "IA"
    assert ev(tech_session, "get_db layer:IA .obj_type") == "layer"
    assert ev(tech_session, "get_db layer:IA .tech") == "tech"
    assert ev(tech_session, "get_db layer:IA .tech.lef_version") == "5.8"


@pytest.mark.parametrize("path", ["layers", "head.layers", "tech.layers", "layer"])
def test_innovus_aliases(tech_session, path):
    assert ev(tech_session, f"get_db {path}") == ev(tech_session, "get_db tech.layer")


def test_chained_path_and_attr(tech_session):
    assert ev(tech_session, "get_db layers.name") == "H1 H2 G1 G2 IA IB"
    assert ev(tech_session, "get_db tech.layer.pitch_x") == "0.128 0.128 0.378 0.36 0.72 0.72"
    assert ev(tech_session, "get_db layers .direction") == \
        "horizontal vertical horizontal vertical horizontal vertical"


def test_list_of_handles_and_variables(tech_session):
    assert ev(tech_session, "get_db {layer:G1 layer:G2} .pitch_x") == "0.378 0.36"
    assert ev(tech_session, "set l [get_db layers IA]; get_db $l .offset_x") == "0.36"


def test_empty_value(tech_session):
    assert ev(tech_session, "get_db layer:IA .min_step") == ""
    assert ev(tech_session, "get_db layer:IA .min_spacing") == ""


def test_name_pattern(tech_session):
    assert ev(tech_session, "get_db layers G*") == "layer:G1 layer:G2"
    assert ev(tech_session, "get_db layers X*") == ""


def test_star_prints_all_attrs(tech_session):
    assert ev(tech_session, "get_db layer:IB .*") == ""
    out = tech_session.out.getvalue()
    assert "Object: layer:IB" in out
    assert "  direction: vertical" in out
    assert "LAYER IB" in out


def test_lef_text(tech_session):
    text = ev(tech_session, "get_db layer:H1 .lef_text")
    assert text.startswith("LAYER H1") and "# Hx.W.1" in text


# -- -if ------------------------------------------------------------------------

@pytest.mark.parametrize("expr, expected", [
    ("{.direction == vertical}", "H2 G2 IB"),
    ("{.direction != vertical}", "H1 G1 IA"),
    ("{.pitch_x > 0.3}", "G1 G2 IA IB"),
    ("{.pitch_x >= 0.36}", "G1 G2 IA IB"),
    ("{.pitch_x < 0.36}", "H1 H2"),
    ("{.pitch_x <= 0.36}", "H1 H2 G2"),
    ("{.name == G*}", "G1 G2"),
    ("{.name == I?}", "IA IB"),
    ("{.direction == vertical && .pitch_x > 0.2}", "G2 IB"),
    ("{.name == H1 || .name == IB}", "H1 IB"),
    ("{!(.direction == vertical)}", "H1 G1 IA"),
    ("{.min_step}", "H1 H2 G1 G2"),
    ("{!.min_step}", "IA IB"),
    ('{.name == "IA"}', "IA"),
    ("(.pitch_x > 0.3 && .direction == horizontal)", "G1 IA"),
])
def test_if_operators(tech_session, expr, expected):
    assert ev(tech_session, f"get_db layers .name -if {expr}") == expected


# -- errors ---------------------------------------------------------------------

def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.mark.parametrize("script, msg_id", [
    ("get_db", "HT4-020"),
    ("get_db bogus.thing", "HT4-021"),
    ("get_db layer:XX .name", "HT4-022"),
    ("get_db layer:IA .bogus", "HT4-023"),
    ("get_db layers -if {.bogus == 1}", "HT4-023"),
    ("get_db layers -if {.name ==}", "HT4-024"),
    ("get_db layers -if (.name == IA", "HT4-020"),
    ("get_db layer:IA .name.foo", "HT4-020"),
])
def test_errors(tech_session, script, msg_id):
    assert msg_id in err(tech_session, script)


def test_no_tech_loaded(session):
    assert "HT4-025" in err(session, "get_db tech")
    assert "HT4-025" in err(session, "get_db tech.layer")


def test_error_is_catchable(tech_session):
    assert ev(tech_session, "catch {get_db layer:XX .name} m; set m") == \
        "**ERROR: (HT4-022): object 'layer:XX' does not exist"
