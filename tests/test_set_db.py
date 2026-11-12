import io
import tkinter

import pytest

pytest.importorskip("scipy")

from core.htree_builder import Session
from test_create_spine import BUILD, lib  # noqa: F401  (lib is a fixture)


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def built(lib):  # noqa: F811
    lib.eval(BUILD)
    lib.eval("create_route_rule -name rule1 -layer H2 -width 0.41 -spacing 0.2")
    lib.eval("create_route_rule -name rule1 -layer H1 -width 0.35 -spacing 0.2 -append")
    return lib


def rules(session):
    """Rule name per net, in net order (.route_rule.name would drop repeats)."""
    return [session.eval(f"get_db {n} .route_rule").removeprefix("route_rule:")
            for n in session.eval("get_db nets").split()]


def test_nets_lists_every_spine_net_and_stub(built):
    # stubs are nets too; get_db stubs lists only them
    assert built.eval("get_db nets") == built.eval("get_db spine:sp1 .spine_nets") + " " + \
        built.eval("get_db stubs")
    assert built.eval("get_db stubs") == "stub:sp1/stub1 stub:sp1/stub2"
    assert built.eval("get_db nets *L3*") == \
        "spine_net:sp1/sp1_L3_inv1_Y spine_net:sp1/sp1_L3_inv2_Y"
    assert built.eval("get_db nets *L2*") == "spine_net:sp1/sp1_L2_inv1_Y"


def test_every_net_starts_on_the_default_rule(built):
    assert rules(built) == ["default"] * 6               # 4 nets, 2 stubs
    assert built.eval("get_db spine_net:sp1/sp1_L1_inv1_Y .route_rule") == "route_rule:default"


def test_set_route_rule_on_matching_nets(built):
    assert built.eval("set_db [get_db nets *L2*] .route_rule rule1") == \
        "spine_net:sp1/sp1_L2_inv1_Y"
    assert built.eval("get_db spine_net:sp1/sp1_L2_inv1_Y .route_rule") == "route_rule:rule1"
    assert built.eval("get_db nets -if {.route_rule == route_rule:rule1}") == \
        "spine_net:sp1/sp1_L2_inv1_Y"
    # the rule's per-layer values are reachable from the net
    assert built.eval("get_db spine_net:sp1/sp1_L2_inv1_Y .route_rule.route_rule_layers.width") \
        == "0.41 0.35"


def test_set_all_nets_handle_value_and_attr_without_dot(built):
    built.eval("set_db [get_db nets] route_rule route_rule:rule1")
    assert rules(built) == ["rule1"] * 6
    built.eval("set_db stub:sp1/stub2 .route_rule default")      # a stub keeps its own
    assert rules(built) == ["rule1"] * 5 + ["default"]


def test_back_to_default(built):
    built.eval("set_db [get_db nets] .route_rule rule1")
    built.eval("set_db [get_db nets *L1*] .route_rule default")
    assert built.eval("get_db spine_net:sp1/sp1_L1_inv1_Y .route_rule") == "route_rule:default"
    assert rules(built).count("rule1") == 5


def test_errors_change_nothing(built):
    assert "HT4-141" in err(built, "set_db [get_db nets] .route_rule nope")
    assert "HT4-140" in err(built, "set_db [get_db nets] .length 3")
    assert "HT4-140" in err(built, "set_db [concat [get_db nets] inst:sp1_L1_inv1] "
                                   ".route_rule rule1")
    assert "HT4-022" in err(built, "set_db spine_net:sp1/none .route_rule rule1")
    assert "HT4-001" in err(built, "set_db [get_db nets] .route_rule")
    assert "HT4-001" in err(built, "set_db notahandle .route_rule rule1")
    assert rules(built) == ["default"] * 6


def test_no_objects_warns(built):
    assert built.eval("set_db [get_db nets *nomatch*] .route_rule rule1") == ""
    assert "HT4-142" in built.out.getvalue()


def test_rule_survives_write_and_read_db(built, tmp_path):
    built.eval("set_db [get_db nets *L2*] .route_rule rule1")
    path = tmp_path / "n.db"
    built.eval(f"write_db -file {{{path}}}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {{{path}}}")
    assert fresh.eval("get_db spine_net:sp1/sp1_L2_inv1_Y .route_rule") == "route_rule:rule1"


# -- root attributes -----------------------------------------------------------------

def test_root_attribute_get_set_default(tmp_path):
    s = Session(out=io.StringIO())
    attr = "ignore_shield_less_than_routing_length"
    assert s.eval(f"get_db {attr}") == "10"               # no spec: 10
    assert s.eval(f"set_db {attr} 20") == "20"
    assert s.eval(f"get_db {attr}") == "20"
    assert s.eval(f"get_db .{attr}") == "20"
    s.eval("get_db root_attributes")
    assert f"{attr} = 20\n" in s.out.getvalue()
    path = tmp_path / "a.db"                              # kept by write_db / read_db
    s.eval(f"write_db -file {{{path}}}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {{{path}}}")
    assert fresh.eval(f"get_db {attr}") == "20"
    assert s.eval(f"set_db {attr} default") == "10"
    s.eval("get_db root_attributes")
    assert f"{attr} = 10  (default: the spine spec's placement.deviation, else 10)" in \
        s.out.getvalue()


def test_root_attribute_errors():
    s = Session(out=io.StringIO())
    attr = "ignore_shield_less_than_routing_length"
    assert "HT4-141" in err(s, f"set_db {attr} -1")
    assert "HT4-141" in err(s, f"set_db {attr} ten")
    assert "HT4-001" in err(s, "set_db no_such_attribute 3")
    assert s.eval(f"get_db {attr}") == "10"               # unchanged
