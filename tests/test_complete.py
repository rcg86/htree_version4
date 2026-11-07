import pytest

from core.complete import Completer


def comp(session, line):
    """Complete the last word of 'line', as readline would with our delimiters."""
    begidx = max(line.rfind(c) for c in " \t\n[]{}()\"';") + 1
    return Completer(session).candidates(line, begidx, line[begidx:])


def test_command_names(session):
    assert comp(session, "get") == ["get_db "]
    assert comp(session, "puts [get") == ["get_db "]
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


def test_attr_after_nested_command_offers_all_types(tech_session):
    got = comp(tech_session, "get_db [get_db layers IA] .")
    assert ".min_width " in got and ".db_units " in got


def test_if_expression(tech_session):
    assert comp(tech_session, "get_db layers -if {.dir") == [".direction "]
    assert comp(tech_session, "get_db layers -if {.name == IA && .pit") == \
        [".pitch_x ", ".pitch_y "]
    assert comp(tech_session, "get_db layers -") == ["-if "]


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
