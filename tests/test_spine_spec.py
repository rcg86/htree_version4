import io
import tkinter

import pytest

from conftest import ROOT
from core.htree_builder import Session
from core.spine_spec import SpineSpecError, parse_spine_spec

SPINE_YAML = ROOT / "tests" / "data" / "spine.yaml"
A = "spine_spec:sp_a"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


@pytest.fixture
def spine_session(session):
    session.eval(f"read_spine_spec -file {{{SPINE_YAML}}}")
    session.out.seek(0)
    session.out.truncate()
    return session


# -- parser -----------------------------------------------------------------------

def test_parse_two_documents():
    specs = parse_spine_spec(str(SPINE_YAML)).specs
    assert [s.name for s in specs] == ["sp_a", "sp_b"]
    a, b = specs
    assert (a.line, b.line) == (3, 34)
    assert (a.type, a.units, a.point, a.root_net) == ("spine", "um", "center", "net")
    assert (a.max_drive_length, a.count_stub_in_drive) == (1020, True)
    assert (a.origin_x, a.level_pitch_x, a.orientation, a.span) == (10, 2.88, "vertical", 5000)
    assert (a.stub_count, a.stub_gap, a.stub_tap, a.stub_order) == (2, 10, "center",
                                                                    ["stub2", "stub1"])
    assert [l.name for l in a.levels] == ["L1", "L2"]
    cell = a.levels[1].cells[0]
    assert (cell.name, cell.input, cell.output, cell.extra) == \
        ("inv1", "L1/inv2/Y", "stub1", ["cell: INVX4"])
    assert a.extra == ["future_key: 7"]
    assert a.yaml_text.splitlines()[0] == "spine_spec:"
    assert a.yaml_text.splitlines()[-1] == "  future_key: 7"
    assert (b.span, b.type, b.levels) == (1000, None, [])


def test_parse_list_form(write_lef):
    path = write_lef("spine_spec:\n  - name: x\n    units: um\n  - name: y\n", "s.yaml")
    assert [s.name for s in parse_spine_spec(path).specs] == ["x", "y"]


DUP = """spine_spec:
  name: one
  units: um

  name: two
"""


@pytest.mark.parametrize("body, line, text", [
    (DUP, 5, "duplicate key 'name' (first at line 2)"),
    ("spine_spec:\n  units: um\n", 2, "has no 'name'"),
    ("spine_spec:\n  name: a\n---\nspine_spec:\n  name: a\n", 5, "defined twice"),
    ("spine_spec:\n  name: a\n  spine:\n    span: big\n", 4, "'spine.span' must be a number"),
    ("spine_spec:\n  name: a\n  stubs:\n    count: 2.5\n", 4, "must be an integer"),
    ("spine_spec:\n  name: a\n  constraints:\n    count_stub_in_drive: 1\n", 4,
     "must be true or false"),
    ("spine_spec:\n  name: a\n  stubs:\n    order: stub1\n", 4, "must be a list of names"),
    ("spine_spec:\n  name: a/b\n", 2, "must not contain '/'"),
    ("spine_spec:\n  name: a\n  levels:\n    L1:\n      cells:\n        i1: 3\n", 6,
     "must be a mapping like"),
    ("spine_spec: [\n", 2, "YAML syntax"),
    ("spine_spec:\n  name: a\n        type: spine\n", 3, "check the indentation"),
    ("other: 1\n", None, "no spine_spec found"),
])
def test_parse_errors(write_lef, body, line, text):
    with pytest.raises(SpineSpecError) as e:
        parse_spine_spec(write_lef(body, "s.yaml"))
    assert text in e.value.text
    assert e.value.line == line


# -- read_spine_spec ----------------------------------------------------------------

def test_read_summary(session):
    session.eval(f"read_spine_spec -file {{{SPINE_YAML}}}")
    out = session.out.getvalue()
    assert "sp_a                    : line 3, levels L1(2) L2(2), 4 cells, " \
           "1 unmodeled key(s) in .extra" in out
    assert "sp_b                    : line 34, levels (none), 0 cells" in out


def test_read_errors(session, tmp_path, write_lef):
    assert "HT4-001" in err(session, "read_spine_spec")
    assert "HT4-080" in err(session, f"read_spine_spec -file {tmp_path}/none.yaml")
    bad = write_lef(DUP, "dup.yaml")
    msg = err(session, f"read_spine_spec -file {bad}")
    assert "HT4-081" in msg and "line 5: duplicate key 'name'" in msg
    assert "HT4-027" in err(session, "get_db spine_spec")        # db unchanged


def test_reread_replaces_and_warns(spine_session, write_lef):
    new = write_lef("spine_spec:\n  name: sp_a\n  units: nm\n", "new.yaml")
    spine_session.eval(f"read_spine_spec -file {new}")
    assert "WARN: (HT4-082): spine_spec sp_a replaced" in spine_session.out.getvalue()
    assert spine_session.eval(f"get_db {A} .units") == "nm"
    assert spine_session.eval(f"get_db {A} .spine_levels") == ""
    assert spine_session.eval("get_db spine_spec .name") == "sp_b sp_a"


def test_ignored_top_level_key(session, write_lef):
    path = write_lef("other: 1\nspine_spec:\n  name: x\n", "s.yaml")
    session.eval(f"read_spine_spec -file {path}")
    assert "WARN: (HT4-083): top-level key 'other' is not a spine_spec" in session.out.getvalue()


# -- get_db -----------------------------------------------------------------------

@pytest.mark.parametrize("path", ["spine_spec", ".spine_spec", "spine_specs"])
def test_get_db_spine_spec_lists_all(spine_session, path):
    assert spine_session.eval(f"get_db {path}") == "spine_spec:sp_a spine_spec:sp_b"


def test_spec_attrs(spine_session):
    ev = spine_session.eval
    expected = {"name": "sp_a", "type": "spine", "units": "um", "point": "center",
                "root_net": "net", "max_drive_length": "1020", "count_stub_in_drive": "true",
                "origin_x": "10", "level_pitch_x": "2.88", "orientation": "vertical",
                "span": "5000", "stub_count": "2", "stub_gap": "10", "stub_tap": "center",
                "stub_order": "stub2 stub1", "extra": "{future_key: 7}",
                "file": str(SPINE_YAML)}
    for attr, value in expected.items():
        assert ev(f"get_db {A} .{attr}") == value, attr
    assert ev(f"llength [get_db {A} .stub_order]") == "2"
    assert ev(f"get_db {A} .spine_levels") == "spine_level:sp_a/L1 spine_level:sp_a/L2"
    assert ev("get_db spine_spec:sp_b .type") == ""
    assert "future_key: 7" in ev(f"get_db {A} .yaml_text")


def test_levels_and_cells(spine_session):
    ev = spine_session.eval
    assert ev("get_db spine_level:sp_a/L2 .spine_cells") == \
        "spine_cell:sp_a/L2/inv1 spine_cell:sp_a/L2/inv2"
    c = "spine_cell:sp_a/L2/inv1"
    assert (ev(f"get_db {c} .input"), ev(f"get_db {c} .output")) == ("L1/inv2/Y", "stub1")
    assert ev(f"get_db {c} .extra") == "{cell: INVX4}"
    assert ev(f"get_db {c} .spine_level.spine_spec") == A
    assert ev("get_db spine_cell:sp_a/L1/inv1 .output") == ""


def test_filters(spine_session):
    ev = spine_session.eval
    assert ev(f"get_db {A} .spine_levels.spine_cells.name -if {{.output == stub2}}") == "inv2"
    assert ev("get_db spine_spec .name -if {.span > 2000}") == "sp_a"


@pytest.mark.parametrize("handle", ["spine_spec:nope", "spine_level:sp_a/L9",
                                    "spine_cell:sp_a/L1/inv9", "spine_cell:sp_a/L1"])
def test_missing(spine_session, handle):
    assert "HT4-022" in err(spine_session, f"get_db {handle} .name")


def test_round_trip(spine_session, tmp_path):
    db = tmp_path / "s.db"
    spine_session.eval(f"write_db {db}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db {db}")
    assert fresh.eval(f"get_db {A} .stub_order") == "stub2 stub1"
    assert fresh.eval("get_db spine_cell:sp_a/L2/inv2 .output") == "stub2"


def test_completion(spine_session):
    from core.complete import Completer
    c = Completer(spine_session)

    def comp(line):
        b = line.rfind(" ") + 1
        return c.candidates(line, b, line[b:])

    assert comp("get_db spine_spec:sp") == ["spine_spec:sp_a ", "spine_spec:sp_b "]
    assert ".spine_spec.spine_levels" in comp("get_db .spine_spec.")
    assert comp("get_db .spine_spec.spine_levels.spine_cells.ou") == \
        [".spine_spec.spine_levels.spine_cells.output "]
