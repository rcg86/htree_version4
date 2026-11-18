import pytest

from core.complete import Completer


def comp(session, line):
    """Complete the last word of 'line', as readline would with our delimiters."""
    begidx = max(line.rfind(c) for c in " \t\n[]{}()\"';") + 1
    return Completer(session).candidates(line, begidx, line[begidx:])


def test_command_names(session):
    assert comp(session, "get") == ["get_db ", "get_obj_in_area "]
    assert comp(session, "puts [get") == ["get_db ", "get_obj_in_area "]
    assert "read_tech " in comp(session, "")


def test_dot_shows_roots(tech_session):
    assert comp(tech_session, "get_db .") == [".tech", ".library_physical", ".spine_spec",
                                              ".design"]
    assert comp(tech_session, "get_db ") == ["tech", "library_physical", "spine_spec", "design"]


def test_tech_children(tech_session):
    got = comp(tech_session, "get_db .tech.")
    assert ".tech.layer" in got and ".tech.layers" in got
    assert ".tech.db_units " in got          # value attr: trailing space
    assert comp(tech_session, "get_db tech.la") == ["tech.layer", "tech.layers"]


def test_walks_relations(tech_session):
    got = comp(tech_session, "get_db .tech.layer.")
    assert ".tech.layer.pitch_x " in got and ".tech.layer.tech" in got
    assert comp(tech_session, "get_db .tech.layer.min_w") == [".tech.layer.min_width "]
    assert comp(tech_session, "get_db .tech.bogus.") == []


def test_alias_roots_complete_once_typed(tech_session):
    assert comp(tech_session, "get_db la") == ["layers", "layer"]
    assert comp(tech_session, "get_db layers.di") == ["layers.direction "]


def test_layer_handles(tech_session):
    assert comp(tech_session, "get_db layer:I") == ["layer:IA ", "layer:IB "]


def test_handles_need_tech(session):
    assert comp(session, "get_db layer:") == []


def test_attr_word_after_objects(tech_session):
    got = comp(tech_session, "get_db layer:IA .")
    assert ".* " in got and ".min_width " in got and ".file " not in got
    assert comp(tech_session, "get_db tech .lef") == [".lef_version "]
    assert comp(tech_session, "get_db layer:IA .tech.db") == [".tech.db_units "]


def test_attr_after_nested_get_db_offers_its_type_only(tech_session):
    got = comp(tech_session, "get_db [get_db layers IA] .")
    assert ".min_width " in got and ".db_units " not in got
    got = comp(tech_session, "get_db [get_db spine sp] .")
    assert ".spine_input" in got and ".spine_output" in got and ".min_width " not in got
    assert ".insts" in got and ".area " not in got      # relations: '.' can follow
    got = comp(tech_session, "get_db [get_db spine:sp .insts] .")       # through .insts
    assert ".place_status " in got and ".spine_input" not in got
    assert comp(tech_session, "get_db [get_db [get_db spine sp] .spine_input] .dir") == \
        [".direction "]
    assert comp(tech_session, "get_db [get_db insts -if {.name == a}] .pla") == [".place_status "]
    assert comp(tech_session, "get_db [get_db nets] .route_s") == [".route_status "]


def test_attr_after_other_words_offers_all_types(tech_session):
    for line in ("get_db $objs .", "get_db [concat a b] .", "get_db [get_db spine sp .name] ."):
        got = comp(tech_session, line)
        assert ".min_width " in got and ".db_units " in got


def test_if_expression(tech_session):
    assert comp(tech_session, "get_db layers -if {.dir") == [".direction "]
    assert comp(tech_session, "get_db layers -if {.name == IA && .pit") == \
        [".pitch_x ", ".pitch_y "]
    assert comp(tech_session, "get_db layers -") == ["-if ", "-help "]


def test_other_commands_complete_files(tmp_path, session):
    (tmp_path / "a.lef").write_text("")
    (tmp_path / "sub").mkdir()
    got = comp(session, f"read_tech -file {tmp_path}/")
    assert got == [f"{tmp_path}/a.lef ", f"{tmp_path}/sub/"]


def test_leaf_display(tech_session):
    c = Completer(tech_session)
    c.candidates("get_db .tech.", len("get_db "), ".tech.")
    assert c.leaf_display


@pytest.mark.parametrize("path", [".tech.layer", ".layers"])
def test_get_db_accepts_leading_dot(tech_session, path):
    assert tech_session.eval(f"get_db {path}") == \
        "layer:H1 layer:H2 layer:G1 layer:G2 layer:IA layer:IB"


def test_get_db_dot_tech_dumps_like_tech(tech_session):
    assert tech_session.eval("get_db .tech") == "tech"
    assert "db_units" in tech_session.out.getvalue()


def test_command_options(session):
    assert comp(session, "route_net -") == ["-net ", "-rule ", "-via_weight ", "-shield ",
                                            "-shield_nets ", "-help "]
    assert comp(session, "route_net -n") == ["-net "]
    assert comp(session, "route_pin -s") == ["-spec ", "-spacing "]
    assert comp(session, "route_net -net a -rule r -") == ["-via_weight ", "-shield ",
                                                           "-shield_nets ", "-help "]
    assert comp(session, "puts [route_net -r") == ["-rule "]
    assert comp(session, "get_db -") == ["-if ", "-help "]
    assert comp(session, "select_obj -") == ["-help "]
    assert comp(session, "route_net -x") == []


def test_options_match_the_man_pages(session):
    """Every command's OPTIONS (what <tab> offers and parse_options accepts) is
    what its man page lists under OPTIONS, apart from -help."""
    import re
    from conftest import ROOT
    for name, module in session.commands.items():
        text = (ROOT / "docs" / "man" / f"{name}.md").read_text()
        section = re.split(r"\n[A-Z][A-Z ]+\n", "\n" + text.split("\nOPTIONS\n", 1)[1])[0] \
            if "\nOPTIONS\n" in text else ""
        documented = set(re.findall(r"^    (-\w+)", section, re.M)) - {"-help"}
        assert documented == set(getattr(module, "OPTIONS", {})), name


def test_selected_offers_the_selected_types(tech_session, write_lef):
    from test_move_spine import build
    s = build(tech_session, write_lef)
    s.eval("route_pin -inst sp_L1_inv1")
    strip = lambda got: [m.strip() for m in got]
    s.eval("select_obj inst:sp_L1_inv1")
    got = strip(comp(s, "get_db [get_db selected] ."))
    assert ".place_status" in got and ".kind" not in got and ".min_width" not in got
    assert strip(comp(s, "get_db selected .pl")) == [".place_status"]
    assert strip(comp(s, "set_db [get_db selected] .")) == [".place_status", ".status"]
    assert strip(comp(s, "set_db [get_db selected] .place_status ")) == \
        ["placed", "fixed", "cover"]
    s.eval("deselect_obj inst:sp_L1_inv1")
    s.eval("select_obj spine_net:sp/sp_L1_inv1_Y")
    assert strip(comp(s, "set_db [get_db selected] .")) == [".route_rule", ".route_status"]
    assert strip(comp(s, "set_db [get_db selected] .route_status ")) == ["fixed", "routed"]
    assert strip(comp(s, "set_db [get_db selected] .route_rule ")) == ["default"]
    s.eval("select_obj inst:sp_L1_inv1")             # nothing settable on both
    assert comp(s, "set_db [get_db selected] .") == []
    got = strip(comp(s, "get_db [get_db selected] ."))
    assert ".place_status" in got and ".loads" in got and ".min_width" not in got


def test_set_db_of_unknown_objects_offers_every_settable_attribute(tech_session):
    got = [m.strip() for m in comp(tech_session, "set_db $objs .")]
    assert {".route_status", ".place_status", ".route_rule"} <= set(got)
    assert comp(tech_session, "set_db [get_db selected] .") == comp(tech_session, "set_db $x .")
