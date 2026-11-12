import io
import tkinter

import pytest

pytest.importorskip("scipy")

from conftest import ROOT
from core.htree_builder import Session
from core.spine_build import SpecCell, SpecData, SpineError, mirror_overlaps, mirrored, plan

CELLS_LEF = ROOT / "tests" / "data" / "cells.lef"
SMALL_DEF = ROOT / "tests" / "data" / "small.def"


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


def spec(cells, levels=None, span=200.0, pitch=2.88, max_drive=200.0, gap=10.0,
         deviation=10.0, orientation="vertical", stub_count=None, origin=None):
    """cells: [(level, name, input, output[, location])]"""
    levels = levels or list(dict.fromkeys(c[0] for c in cells))
    return SpecData("sp", orientation, span, pitch, max_drive, gap, deviation, "net", "center",
                    stub_count, levels, [SpecCell(*c) for c in cells], origin)


# root L1/inv1 drives two leaves in L2
TWO = [("L1", "inv1", "net", None), ("L2", "inv1", "L1/inv1/Y", "stub1"),
       ("L2", "inv2", "L1/inv1/Y", "stub2")]


# -- geometry ----------------------------------------------------------------------------

def test_two_leaf_spine_geometry():
    p = plan(spec(TWO), "sp", (100, 1000), "+x")
    assert p.stub_length == pytest.approx(95)                 # (200 - 10) / 2
    assert [(s.lo, s.hi) for s in p.stubs] == [(0, 95), (105, 200)]
    root = p.cells["L1/inv1"]
    assert (root.s, p.point(root.col, root.s)) == (0, (100, 1000))
    taps = sorted(p.cells[k].s for k in ("L2/inv1", "L2/inv2"))
    assert taps == [47.5, 152.5]                               # leaves at stub middles
    assert p.point(1, 0) == (102.88, 1000)                     # L2 one pitch to +x
    assert p.point(p.stub_col, 0) == (105.76, 1000)            # stubs one pitch beyond
    assert p.warnings == []


def test_origin_and_mirror_vertical():
    p = plan(spec(TWO, origin=10), "sp", (100, 1000), "+x")
    assert p.point(0, 0) == (100, 1010)                       # root 10 above -location
    assert p.point(p.stub_col, 0) == (105.76, 1010)           # the stubs start there too
    m = mirrored(p)
    assert m.point(0, 0) == (100, 990)                        # mirrored root 10 below: 20 apart
    assert m.point(p.stub_col, 200) == (105.76, 790)          # stubs run down
    assert m.cells["L1/inv1"].inst == "sp_mirror_L1_inv1"
    assert [s.name for s in m.stubs] == ["stub1_mirror", "stub2_mirror"]
    assert [(s.lo, s.hi) for s in m.stubs] == [(s.lo, s.hi) for s in p.stubs]
    assert [n.name for n in m.nets] == [n.name.replace("sp_", "sp_mirror_", 1) for n in p.nets]
    assert [n.length for n in m.nets] == [n.length for n in p.nets]
    leaf = m.net_of("L2/inv1")
    assert leaf.loads[0].endswith("_mirror")
    assert m.groups[0][1][0].startswith("sp_mirror_")


def test_origin_and_mirror_horizontal():
    p = plan(spec(TWO, orientation="horizontal", origin=10), "sp", (100, 1000))
    m = mirrored(p)
    assert p.point(0, 0) == (110, 1000) and m.point(0, 0) == (90, 1000)
    assert m.point(1, 50) == (40, 1002.88)                    # runs left, still steps up


def test_mirror_overlap_warning():
    # cells 1.0 along the spine: roots 2 x 0.25 apart overlap, 2 x 10 do not
    for origin, warned in ((0.25, True), (10, False)):
        p = plan(spec(TWO, origin=origin), "sp", (0, 0), "+x", (0.6, 1.0))
        mirror_overlaps(p, mirrored(p))
        texts = [t for k, t in p.warnings if k == "overlap"]
        assert bool(texts) == warned
        if warned:
            assert "sp_L1_inv1-sp_mirror_L1_inv1" in texts[0]


def test_negative_origin():
    with pytest.raises(SpineError, match="placement.origin"):
        plan(spec(TWO, origin=-1), "sp", (0, 0))


def test_net_length_counts_shared_wire_once():
    p = plan(spec(TWO), "sp", (0, 0), "+x")
    root = p.net_of("L1/inv1")
    # both loads above the root share the trunk: pitch + farthest load, not the sum
    assert root.length == pytest.approx(2.88 + 152.5)
    assert root.group == "L1-L2"
    leaf = p.net_of("L2/inv1")
    assert (leaf.length, leaf.group) == (pytest.approx(2.88 + 95), "L2-stubs")


def test_build_direction_and_orientation():
    p = plan(spec(TWO), "sp", (100, 1000), "-x")
    assert p.point(1, 50) == (97.12, 1050)
    h = plan(spec(TWO, orientation="horizontal"), "sp", (100, 1000))     # default +y
    assert h.point(1, 50) == (150, 1002.88)                  # runs right, steps up
    assert plan(spec(TWO, orientation="horizontal"), "sp", (0, 0), "-y").point(1, 0) == \
        (0, -2.88)


def test_movable_cell_balances_its_level():
    # root -> L2/inv1 -> two leaves in L3; L2/inv1 settles between its stubs
    cells = [("L1", "inv1", "net", None), ("L2", "inv1", "L1/inv1/Y", None),
             ("L3", "inv1", "L2/inv1/Y", "stub1"), ("L3", "inv2", "L2/inv1/Y", "stub2")]
    p = plan(spec(cells, max_drive=500), "sp", (0, 0))
    mid = p.cells["L2/inv1"]
    assert 47.5 - 1e-6 <= mid.s <= 152.5 + 1e-6
    assert p.net_of("L2/inv1").length == pytest.approx(2.88 + 105)      # taps 105 apart
    assert not [w for w in p.warnings if w[0] == "over"]


def test_location_fixes_a_cell_from_its_driver():
    # L2/inv1 is 30 above the root (a constant), L3/inv1 20 below a movable L2/inv2
    cells = [("L1", "inv1", "net", None),
             ("L2", "inv1", "L1/inv1/Y", None, 30.0), ("L2", "inv2", "L1/inv1/Y", None),
             ("L3", "inv1", "L2/inv1/Y", "stub1"), ("L3", "inv2", "L2/inv2/Y", None, -20.0),
             ("L4", "inv1", "L3/inv2/Y", "stub2")]
    p = plan(spec(cells, max_drive=500), "sp", (0, 0))
    assert p.cells["L2/inv1"].s == pytest.approx(30)
    assert p.cells["L3/inv2"].s == pytest.approx(p.cells["L2/inv2"].s - 20)
    # without the locations the solver puts them elsewhere
    free = plan(spec([c[:4] for c in cells], max_drive=500), "sp", (0, 0))
    assert free.cells["L2/inv1"].s != pytest.approx(30)
    # horizontal: + is right; the build direction does not change the sign
    h = plan(spec(cells, max_drive=500, orientation="horizontal"), "sp", (100, 50), "-y")
    assert h.point(1, h.cells["L2/inv1"].s) == (130, 47.12)


def test_location_may_leave_the_span_and_moves_a_dummy():
    cells = TWO + [("L2", "dum", "L1/inv1/Y", None, -40.0)]
    p = plan(spec(cells), "sp", (0, 0))
    assert p.cells["L2/dum"].s == pytest.approx(-40)            # below the location
    dummy = next(t for k, t in p.warnings if k == "dummy")
    assert "placed -40 um from its driver" in dummy


# -- warnings ----------------------------------------------------------------------------

def test_over_limit_and_spread_warnings():
    p = plan(spec(TWO, max_drive=100, deviation=0), "sp", (0, 0))
    kinds = [k for k, _ in p.warnings]
    assert "over" in kinds                                    # root net 155.38 > 100
    over = next(t for k, t in p.warnings if k == "over")
    assert "L1_inv1_Y" in over and "by 55.380" in over


def test_spread_warning_when_a_level_cannot_balance():
    # L2/a drives stub1 directly (fixed: 2 x 2.88 + stub); L2/b drives two stubs
    # 10 apart, so its net is at least 2.88 + stub + gap: 7.12 longer
    cells = [("L1", "inv1", "net", None), ("L2", "a", "L1/inv1/Y", "stub1"),
             ("L2", "b", "L1/inv1/Y", None), ("L3", "inv1", "L2/b/Y", "stub2"),
             ("L3", "inv2", "L2/b/Y", "stub3")]
    p = plan(spec(cells, span=320, max_drive=1000, deviation=0), "sp", (0, 0))
    assert p.net_of("L2/a").length == pytest.approx(2 * 2.88 + 100)
    spread = [t for k, t in p.warnings if k == "spread"]
    assert len(spread) == 1 and spread[0].startswith("L2-L3 nets")
    ok = plan(spec(cells, span=320, max_drive=1000, deviation=8), "sp", (0, 0))
    assert not [k for k, _ in ok.warnings if k == "spread"]


def test_depth_dummy_and_overlap_warnings():
    cells = [("L1", "inv1", "net", None), ("L1", "inv2", "L1/inv1/Y", None),
             ("L2", "inv1", "L1/inv1/Y", "stub1"), ("L2", "inv2", "L1/inv2/Y", "stub2"),
             ("L2", "dum", "L1/inv2/Y", None)]
    p = plan(spec(cells, levels=["L1", "L2"]), "sp", (0, 0))
    kinds = {k for k, _ in p.warnings}
    assert {"depth", "dummy"} <= kinds
    depth = next(t for k, t in p.warnings if k == "depth")
    assert "stub1 through 2 inverters" in depth and "stub2 through 3 inverters" in depth
    # with the cell size, a cell driven from its own column moves one cell along
    p = plan(spec(cells, levels=["L1", "L2"]), "sp", (0, 0), cell_size=(3.12, 1.778))
    assert p.cells["L1/inv2"].s >= 1.778 - 1e-6
    # the dummy (L2) sits at its driver's (L1/inv2) height, one column over:
    # level_pitch 2.88 is under the 3.12 cell width, so they overlap
    overlap = next(t for k, t in p.warnings if k == "overlap")
    assert "L1/inv2-L2/dum" in overlap


# -- spec errors -------------------------------------------------------------------------

@pytest.mark.parametrize("cells, kwargs, text", [
    (TWO + [("L1", "inv9", "net", None)], {}, "exactly one cell must take the root net"),
    ([("L1", "inv1", "net", None), ("L2", "inv1", "L1/nope/Y", "s1")], {}, "neither the root"),
    (TWO + [("L2", "inv3", "L2/inv4/Y", None), ("L2", "inv4", "L2/inv3/Y", None)], {},
     "not connected to the root"),
    ([("L1", "inv1", "net", None), ("L2", "inv1", "L1/inv1/Y", "s1"),
      ("L2", "inv2", "L1/inv1/Y", "s1")], {}, "driven by more than one cell"),
    ([("L1", "inv1", "net", "s0"), ("L2", "inv1", "L1/inv1/Y", "s1")], {}, "a leaf drives only"),
    (TWO, {"stub_count": 3}, "stubs.count is 3"),
    (TWO, {"span": 5}, "do not fit"),
    (TWO, {"orientation": "diagonal"}, "vertical or horizontal"),
    (TWO, {"pitch": None}, "placement.level_pitch must be a positive number"),
    ([("L1", "inv1", "net", None)], {}, "no cell drives a stub"),
    ([("L1", "inv1", "net", None, 5.0), ("L2", "inv1", "L1/inv1/Y", "s1")], {},
     "is the root: it sits at -location"),
    ([("L1", "inv1", "net", None), ("L2", "inv1", "L1/inv1/Y", "s1", 5.0)], {},
     "sits at the middle of its stub"),
])
def test_spec_errors(cells, kwargs, text):
    with pytest.raises(SpineError) as e:
        plan(spec(cells, **kwargs), "sp", (0, 0))
    assert text in str(e.value)


def test_bad_build_direction():
    with pytest.raises(SpineError, match="toward \\+x or -x, not '\\+y'"):
        plan(spec(TWO), "sp", (0, 0), "+y")


# -- the command -------------------------------------------------------------------------

SPEC_YAML = """spine_spec:
  name: sp1
  root_net: net
  constraints:
    max_drive_length: 30
  placement:
    level_pitch: 2.88
    deviation: 1
  spine:
    orientation: vertical
    span: 40
  stubs:
    gap: 2
    tap: center
  levels:
    L1:
      cells:
        inv1: {input: net}
    L2:
      cells:
        inv1: {input: L1/inv1/Y}
    L3:
      cells:
        inv1: {input: L2/inv1/Y, output: stub1}
        inv2: {input: L2/inv1/Y, output: stub2}
---
spine_spec:
  name: tight
  root_net: net
  constraints:
    max_drive_length: 10
  placement:
    level_pitch: 2.88
  spine:
    orientation: vertical
    span: 40
  stubs:
    gap: 2
  levels:
    L1:
      cells:
        inv1: {input: net}
    L2:
      cells:
        inv1: {input: L1/inv1/Y, output: stub1}
        inv2: {input: L1/inv1/Y, output: stub2}
"""


@pytest.fixture
def lib(tech_session, write_lef):
    tech_session.eval(f"read_lef -file {{{CELLS_LEF}}}")
    tech_session.eval(f"read_def -file {{{SMALL_DEF}}}")
    tech_session.eval(f"read_spine_spec -file {{{write_lef(SPEC_YAML, 'sp.yaml')}}}")
    tech_session.out.seek(0)
    tech_session.out.truncate()
    return tech_session


VALIDATE = "create_spine -name sp1 -spec_name sp1 -location {10 5} -validate"
BUILD = "create_spine -name sp1 -spec_name sp1 -location {10 5} -build -ref_cell INV_D1"


def test_validate_changes_nothing(lib):
    count = lib.eval(VALIDATE)
    out = lib.out.getvalue()
    assert "Spine sp1 (spec sp1): vertical, built toward +x from {10 5}" in out
    assert "Stubs   : 2 x 19.000 um" in out                    # (40 - 2) / 2
    assert "sp1_L2_inv1_Y" in out and "Levels:" in out
    assert f"create_spine: {count} warning(s)" in out
    assert lib.eval("get_db insts") == "" and lib.eval("get_db spines") == ""


def test_validate_warnings(lib):
    # sp1 fits: stubs 19 long (taps 9.5 and 30.5), every net under 30 + 1
    assert lib.eval(VALIDATE) == "0"
    assert "HT4-15" not in lib.out.getvalue()
    # tight: 10 um limit, but each leaf drives a 19 um stub
    lib.out.seek(0)
    lib.out.truncate()
    assert lib.eval("create_spine -name tight -spec_name tight -location {10 5} -validate") == "3"
    out = lib.out.getvalue()
    assert out.count("HT4-154") == 3 and out.count("OVER") == 3    # root + 2 leaves


CS = "create_spine -name sp1 -spec_name sp1"


@pytest.mark.parametrize("script, code", [
    (f"{CS} -validate", "HT4-001"),
    ("create_spine -name sp1 -location {1 1} -validate", "HT4-001"),     # no -spec_name
    ("create_spine -spec_name sp1 -location {1 1} -validate", "HT4-001"),  # no -name
    ("create_spine -name a/b -spec_name sp1 -location {1 1} -validate", "HT4-001"),
    (f"{CS} -location {{1 1}}", "HT4-001"),
    (f"{CS} -location {{1 1}} -validate -build -ref_cell INV_D1", "HT4-001"),
    (f"{CS} -location {{1 1}} -build -show -ref_cell INV_D1", "HT4-001"),
    (f"{CS} -location {{1 1}} -build", "HT4-001"),
    (f"{CS} -location {{1}} -validate", "HT4-001"),
    ("create_spine -name sp1 -spec_name nope -location {1 1} -validate", "HT4-150"),
    (f"{CS} -location {{1 1}} -validate -build_direction +y", "HT4-151"),
    (f"{CS} -location {{1 1}} -build -ref_cell NOPE", "HT4-152"),
])
def test_command_errors(lib, script, code):
    assert code in err(lib, script)


def test_no_spec_loaded(session):
    assert "HT4-027" in err(session, "create_spine -name a -spec_name a -location {1 1} "
                                     "-validate")


def test_build(lib, tmp_path):
    assert lib.eval(BUILD) == "spine:sp1"
    assert "Built spine:sp1: 4 instances of INV_D1, 2 stubs of 19.000 um, 4 nets" in \
        lib.out.getvalue()
    assert lib.eval("get_db spines") == "spine:sp1"
    assert lib.eval("get_db spine:sp1 .insts") == \
        "inst:sp1_L1_inv1 inst:sp1_L2_inv1 inst:sp1_L3_inv1 inst:sp1_L3_inv2"
    # centred on -location: INV_D1 is 0.6 x 0.254
    assert lib.eval("get_db inst:sp1_L1_inv1 .location") == "9.7 4.873"
    assert lib.eval("get_db spine:sp1 .stub_length") == "19.0"
    stubs = lib.eval("get_db spine:sp1 .stubs").split()
    assert stubs == ["stub:sp1/stub1", "stub:sp1/stub2"]
    assert {lib.eval(f"get_db {s} .points") for s in stubs} == \
        {"18.64 5 18.64 24", "18.64 26 18.64 45"}              # x = 10 + 3 x 2.88
    nets = lib.eval("get_db spine:sp1 .spine_nets").split()
    assert len(nets) == 4
    root = "spine_net:sp1/sp1_L1_inv1_Y"
    assert lib.eval(f"get_db {root} .driver") == "inst:sp1_L1_inv1"
    assert lib.eval(f"get_db {root} .group") == "L1-L2"
    assert float(lib.eval(f"get_db {root} .length")) > 2.88
    assert "HT4-153" in err(lib, BUILD)                        # built once only
    lib.eval(f"write_db -file {tmp_path}/s.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {tmp_path}/s.db")
    assert fresh.eval("get_db spine:sp1 .ref_cell") == "INV_D1"
    assert fresh.eval(f"get_db {root} .route") == lib.eval(f"get_db {root} .route")


def test_build_mirror(lib, write_lef):
    lib.eval(f"read_spine_spec -file {{{write_lef(MIRROR_YAML, 'm.yaml')}}}")
    lib.eval("create_spine -name m -spec_name sp1 -location {10 50} -mirror -validate")
    out = lib.out.getvalue()
    assert "root 10 up (placement.origin)" in out
    assert "Spine m_mirror (spec sp1)" in out and "root 10 down (placement.origin), mirrored" in out
    lib.eval("create_spine -name m -spec_name sp1 -location {10 50} -mirror -build "
             "-ref_cell INV_D1")
    assert "8 instances of INV_D1, 4 stubs of 19.000 um, 8 nets (with its mirror m_mirror_*)" \
        in lib.out.getvalue()
    g = lambda h, a: lib.eval(f"get_db {h} .{a}")
    # INV_D1 is 0.6 x 0.254: roots centred at y 60 and 40, 20 apart
    assert (g("inst:m_L1_inv1", "location"), g("inst:m_L1_inv1", "orient")) == ("9.7 59.873", "N")
    assert (g("inst:m_mirror_L1_inv1", "location"), g("inst:m_mirror_L1_inv1", "orient")) == \
        ("9.7 39.873", "FS")
    assert g("stub:m/stub1", "points") == "18.64 60 18.64 79"
    assert g("stub:m/stub1_mirror", "points") == "18.64 40 18.64 21"
    assert g("spine_net:m/m_mirror_L1_inv1_Y", "driver") == "inst:m_mirror_L1_inv1"
    assert (g("spine:m", "origin"), g("spine:m", "mirror"), g("spine:m", "location")) == \
        ("10.0", "true", "10 50")
    assert g("spine_spec:sp1", "origin") == "10"


MIRROR_YAML = SPEC_YAML.split("---")[0].replace("    deviation: 1\n",
                                                "    deviation: 1\n    origin: 10\n")


def test_build_refuses_taken_instance_names(lib):
    lib.eval("create_inst -ref_cell INV_D1 -location {50 40} -name sp1_L2_inv1")
    assert "HT4-153" in err(lib, BUILD)
    assert lib.eval("get_db spines") == ""


def test_build_counts_ignored_warnings(lib):
    lib.eval("create_spine -name tight -spec_name tight -location {10 5} -build "
             "-ref_cell INV_D1")
    assert "3 warning(s) ignored" in lib.out.getvalue()
    lib.eval(BUILD)
    assert lib.out.getvalue().count("ignored") == 1                # sp1 has none


def test_name_is_the_spine_and_spec_name_the_spec(lib):
    # one spec placed twice under two spine names
    for name, x in (("clk_a", 10), ("clk_b", 60)):
        assert lib.eval(f"create_spine -name {name} -spec_name spine_spec:sp1 "
                        f"-location {{{x} 5}} -build -ref_cell INV_D1") == f"spine:{name}"
    assert lib.eval("get_db spines") == "spine:clk_a spine:clk_b"
    assert lib.eval("get_db spine:clk_b .spine_spec") == "spine_spec:sp1"
    assert lib.eval("get_db spine:clk_a .insts") == \
        "inst:clk_a_L1_inv1 inst:clk_a_L2_inv1 inst:clk_a_L3_inv1 inst:clk_a_L3_inv2"
    assert lib.eval("get_db spine:clk_b .stubs") == \
        "stub:clk_b/stub1 stub:clk_b/stub2"
    assert lib.eval("get_db spine_net:clk_b/clk_b_L1_inv1_Y .driver") == "inst:clk_b_L1_inv1"
    names = lib.eval("get_db insts .name").split()
    assert len(names) == 8 and all(n.startswith(("clk_a_", "clk_b_")) for n in names)
    lib.out.seek(0)
    lib.out.truncate()
    lib.eval("create_spine -name clk_c -spec_name sp1 -location {10 5} -validate")
    assert "Spine clk_c (spec sp1): vertical" in lib.out.getvalue()
