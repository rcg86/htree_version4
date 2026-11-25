"""add_buffer_on_net: where the buffers go on a net (split), and the command:
the instances, the spine members and nets it makes, their legalization, and
what reads them (get_db, move_obj, move_spine_to_boundary, route_pin,
route_net, write_logical, write_def, write_db / read_db, connect_pin). And on
a net of no spine (a port's, connect_pin's): its centre lines (tree), the
instances and the connections."""

import pytest

pytest.importorskip("scipy")

from core.commands.add_buffer_on_net import _check_place, _pin_centre, split, tree
from core.db import _num as _n
from core.htree_builder import Session
from test_move_spine import build
from test_route_net import DEF, SPEC, _floats
from test_route_pin import CELL_LEF, err, out_of

# The spine of test_route_net ten times as long, in a die of 1000 x 1000:
# L1 at {0 0}, L2 at {2.88 99.5}, the leaves at {5.76 99.5} and {5.76 300.5}.
#   sp_L1_inv1_Y  102.38 um  {0 0 2.88 0} {2.88 0 2.88 99.5}
#   sp_L2_inv1_Y  203.88 um  {2.88 99.5 5.76 99.5} {5.76 99.5 5.76 300.5}
LONG_SPEC = SPEC.replace("span: 40", "span: 400").replace("max_drive_length: 40",
                                                          "max_drive_length: 400")
LONG_DEF = DEF.replace("-100000 -100000 ) ( 100000 100000", "-500000 -500000 ) ( 500000 500000") \
    .replace("-49680 DO 140", "-499680 DO 1400")
# A cell that drives nothing, and one without a SIZE.
MORE_LEF = """VERSION 5.8 ;
MACRO SINK
  CLASS CORE ;
  SIZE 3.12 BY 1.778 ;
  PIN A
    DIRECTION INPUT ;
    PORT
      LAYER D12 ;
        RECT 2.523 0.348 2.933 1.444 ;
    END
  END A
END SINK
MACRO NOSIZE
  CLASS CORE ;
  PIN A
    DIRECTION INPUT ;
  END A
  PIN Y
    DIRECTION OUTPUT ;
  END Y
END NOSIZE
END LIBRARY
"""
ADD = "add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -first_distance 30 -distance 50"


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def attr(s, net, name):
    return s.eval(f"get_db spine_net:sp/{net} .{name}")


def centre(s, inst):
    x1, y1, x2, y2 = _floats(s.eval(f"get_db inst:{inst} .bbox"))
    return pytest.approx(((x1 + x2) / 2, (y1 + y2) / 2), abs=1e-3)


def make(s, write_lef, mirror=False, pins=""):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(LONG_DEF.replace('END DESIGN', pins + 'END DESIGN'), 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(LONG_SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP"
           + (" -mirror" if mirror else ""))
    out_of(s)
    return s


@pytest.fixture
def long(tech_session, write_lef):
    return make(tech_session, write_lef)


# -- where the buffers go ----------------------------------------------------------------

LINE = [((0, 0), (1000, 0))]
# a trunk of 10 um, then 100 um to each side
TEE = [((0, 0), (10, 0)), ((10, -100), (10, 100))]


def dists(bufs):
    return [pytest.approx(b.dist) for b in bufs]


def test_every_distance_from_the_first():
    # the request: 1000 um, a buffer every 100 um, the first 30 um from the driver
    top, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100)
    assert dists(bufs) == [30 + 100 * k for k in range(10)]
    assert [b.at for b in bufs] == [(30 + 100 * k, 0) for k in range(10)]
    assert top.segs == [((0, 0), (30, 0))] and top.loads == [] and top.pieces == [bufs[0]]
    for b, after in zip(bufs, bufs[1:]):
        assert after.parent is b and b.pieces == [after] and b.loads == []
        assert b.segs == [(b.at, after.at)]
    assert bufs[-1].segs == [((930, 0), (1000, 0))]
    assert bufs[-1].loads == [("x", pytest.approx(1000))] and bufs[-1].depth == 10
    # the lines run away from the driver, whichever way that is
    top, bufs = split(LINE, (1000, 0), {"x": (0, 0)}, 30, 100)
    assert top.segs == [((1000, 0), (970, 0))] and bufs[-1].segs == [((70, 0), (0, 0))]


def test_no_buffer_on_the_last_load_or_behind_it():
    _, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 100, 100)
    assert dists(bufs) == [100 * k for k in range(1, 10)]          # not at 1000
    _, bufs = split(LINE, (0, 0), {"x": (500, 0)}, 100, 100)
    assert dists(bufs) == [100, 200, 300, 400]                     # the line goes on: no load
    top, bufs = split(LINE, (0, 0), {"x": (20, 0)}, 30, 100)
    assert bufs == [] and top.loads == [("x", pytest.approx(20))]


def test_last_distance():
    _, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100, 50)
    assert dists(bufs) == [30 + 100 * k for k in range(10)] + [950]
    _, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100, 70)   # the row ends on it
    assert dists(bufs) == [30 + 100 * k for k in range(9)] + [930]
    _, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100, 150)  # and before it
    assert dists(bufs) == [30 + 100 * k for k in range(9)] + [850]
    # one for each load; a load nearer to the driver than the distance has none
    top, bufs = split(LINE, (0, 0), {"a": (20, 0), "b": (400, 0), "c": (1000, 0)}, 300, 300, 30)
    assert dists(bufs) == [300, 370, 600, 900, 970]
    assert top.loads == [("a", pytest.approx(20))]
    assert bufs[1].loads == [("b", pytest.approx(400))]
    assert top.missed == [("a", "near")]


def test_last_distance_is_in_x_plus_y_to_the_pin_of_the_load():
    # the pin 10 um behind the end of the net and 5 um beside it: 35 um of net
    top, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100, 50, pins={"x": (1010, 5)})
    assert dists(bufs) == [30 + 100 * k for k in range(10)] + [965]
    assert top.missed == []
    # a pin the net does not come that near: no last buffer, the row as without
    top, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 30, 100, 50, pins={"x": (1000, 50)})
    assert dists(bufs) == [30 + 100 * k for k in range(10)]
    assert top.missed == [("x", "far")]
    # back round two corners: the first point that far from the pin, not that far of net
    u = [((0, 0), (100, 0)), ((100, 0), (100, 50)), ((100, 50), (0, 50))]
    _, bufs = split(u, (0, 0), {"x": (0, 50)}, 1000, 1000, 120)
    assert dists(bufs) == [130] and bufs[0].at == (100, 30)
    # the net never gets 160 um from the pin: no last buffer, none on its last 160 um
    top, bufs = split(u, (0, 0), {"x": (0, 50)}, 40, 40, 160)
    assert dists(bufs) == [40, 80] and top.missed == [("x", "near")]
    # measured where the lines are drawn: here at twice the size
    _, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 1000, 1000, 50, pins={"x": (2000, 0)},
                    lines=lambda a, b: [((2 * a[0], 0), (2 * b[0], 0))])
    assert dists(bufs) == [975]


def test_a_load_on_a_buffer_point_is_before_the_buffer():
    top, bufs = split(LINE, (0, 0), {"a": (30, 0), "b": (100, 0)}, 30, 50)
    assert dists(bufs) == [30, 80]
    assert top.loads == [("a", pytest.approx(30))]
    assert bufs[1].loads == [("b", pytest.approx(100))]


def test_every_branch_is_measured_from_the_driver():
    top, bufs = split(TEE, (0, 0), {"up": (10, 100), "down": (10, -100)}, 30, 50)
    assert sorted(b.at for b in bufs) == [(10, -70), (10, -20), (10, 20), (10, 70)]
    assert sorted(b.dist for b in bufs) == pytest.approx([30, 30, 80, 80])
    assert len(top.pieces) == 2 and top.loads == []
    assert sorted(top.segs) == [((0, 0), (10, 0)), ((10, -20), (10, 20))]
    ends = {b.loads[0][0]: b for b in bufs if b.loads}
    assert ends["up"].at == (10, 70) and ends["up"].parent.at == (10, 20)
    assert ends["down"].at == (10, -70) and ends["down"].depth == 2
    # only the branch with a load gets buffers
    top, bufs = split(TEE, (0, 0), {"up": (10, 100)}, 30, 50)
    assert [b.at for b in bufs] == [(10, 20), (10, 70)]
    assert sorted(top.segs) == [((0, 0), (10, 0)), ((10, 20), (10, -100))]


def test_a_buffer_where_the_branches_part_serves_both():
    top, bufs = split(TEE, (0, 0), {"up": (10, 100), "down": (10, -100)}, 10, 50)
    assert sorted(b.at for b in bufs) == [(10, -50), (10, 0), (10, 50)]
    first = top.pieces[0]
    assert top.pieces == [first] and first.at == (10, 0) and len(first.pieces) == 2
    assert first.segs == [((10, -50), (10, 50))]


def test_points_off_the_lines_count_from_the_nearest_point_on_them():
    top, bufs = split(LINE, (0, 3), {"x": (1000, -5), "y": (500, 2)}, 30, 400)
    assert dists(bufs) == [30, 430, 830]
    assert bufs[1].loads == [("y", pytest.approx(500))]


def test_lines_that_cannot_be_followed():
    with pytest.raises(ValueError, match="no centre line leads from the driver to x"):
        split([((0, 0), (10, 0)), ((20, 5), (30, 5))], (0, 0), {"x": (30, 5)}, 3, 3)
    with pytest.raises(ValueError, match="neither along nor across"):
        split([((0, 0), (10, 10))], (0, 0), {"x": (10, 10)}, 3, 3)
    with pytest.raises(ValueError, match="no centre lines"):
        split([((4, 4), (4, 4))], (4, 4), {"x": (4, 4)}, 3, 3)


# -- the command ---------------------------------------------------------------------------

def test_buffers_on_a_net(long):
    s = long
    made = lst(s, ADD)
    text = out_of(s)
    names = [f"sp_L2_inv1_buf{k}" for k in (1, 2, 3, 4)]
    assert made == [f"inst:{n}" for n in names]
    assert "sp_L2_inv1_Y (L2-L3, 203.88 um, driver sp_L2_inv1): 4 buffer(s)" in text
    assert "load sp_L3_inv1: behind 0 buffer(s), 2.88 um after sp_L2_inv1\n" in text
    assert "load sp_L3_inv2: behind 4 buffer(s), 23.88 um after sp_L2_inv1_buf4" in text
    assert "inverts its signal" not in text                     # an even number of buffers
    assert "Added 4 buffer(s) on 1 net(s), now 5 nets. Next: legalize_placement, route_pin" \
        in text
    assert "HT4-264" in text and "no placement rows" in text    # this DEF has no ROW
    for k, name in enumerate(names):                            # 30, 80, 130, 180 um
        assert centre(s, name) == (5.76, 99.5 - 2.88 + 30 + 50 * k)
        assert s.eval(f"get_db inst:{name} .ref_name") == "INV_RP"
        assert s.eval(f"get_db inst:{name} .orient") == "N"
        assert s.eval(f"get_db inst:{name} .place_status") == \
            s.eval("get_db inst:sp_L2_inv1 .place_status")
    assert lst(s, "get_db spine:sp .insts")[4:] == made         # members of the spine
    assert lst(s, "get_db spine:sp .spine_nets")[4:] == [f"spine_net:sp/{n}_Y" for n in names]

    # the net given ends at its first buffer; each buffer drives the next stretch
    assert attr(s, "sp_L2_inv1_Y", "loads") == "sp_L3_inv1 sp_L2_inv1_buf1"
    assert attr(s, "sp_L2_inv1_Y", "route") == "{2.88 99.5 5.76 99.5} {5.76 99.5 5.76 126.62}"
    assert attr(s, "sp_L2_inv1_Y", "driver") == "inst:sp_L2_inv1"
    assert float(attr(s, "sp_L2_inv1_Y", "length")) == 30
    for k, (name, load, length) in enumerate(zip(
            names, names[1:] + ["sp_L3_inv2"], (50, 50, 50, 23.88))):
        y = 126.62 + 50 * k
        assert attr(s, f"{name}_Y", "driver") == f"inst:{name}"
        assert attr(s, f"{name}_Y", "loads") == load
        assert attr(s, f"{name}_Y", "group") == "L2-L3"
        assert float(attr(s, f"{name}_Y", "length")) == pytest.approx(length)
        assert _floats(attr(s, f"{name}_Y", "route")) == \
            pytest.approx([5.76, y, 5.76, y + length])
    # the netlist
    assert s.eval("get_db pin:sp_L2_inv1_buf1/A .net.name") == "sp_L2_inv1_Y"
    assert s.eval("get_db pin:sp_L2_inv1_buf1/Y .net.name") == "sp_L2_inv1_buf1_Y"
    assert s.eval("get_db pin:sp_L2_inv1_buf2/A .net.name") == "sp_L2_inv1_buf1_Y"
    assert s.eval("get_db pin:sp_L3_inv2/A .net.name") == "sp_L2_inv1_buf4_Y"
    assert s.eval("get_db pin:sp_L3_inv1/A .net.name") == "sp_L2_inv1_Y"
    # the other nets are as they were
    assert attr(s, "sp_L1_inv1_Y", "route") == "{0 0 2.88 0} {2.88 0 2.88 99.5}"
    members = {m["inst"]: m for m in s.db.spine_members(s.db.spine_row("sp")["id"])}
    assert [(members[n]["level"], members[n]["cell"], members[n]["driver"]) for n in names] == \
        [("buffer", "INV_RP", d) for d in ["sp_L2_inv1"] + names[:3]]


def test_first_distance_is_the_distance_by_default(long):
    s = long
    made = lst(s, "add_buffer_on_net -net spine_net:sp/sp_L1_inv1_Y -ref_cell lib_cell:INV_RP "
                  "-distance 40")
    text = out_of(s)
    assert "INV_RP every 40 um, the first 40 um from the driver" in text
    assert made == ["inst:sp_L1_inv1_buf1", "inst:sp_L1_inv1_buf2"]
    assert centre(s, "sp_L1_inv1_buf1") == (2.88, 40 - 2.88)     # round the corner
    assert centre(s, "sp_L1_inv1_buf2") == (2.88, 80 - 2.88)
    assert attr(s, "sp_L1_inv1_Y", "route") == "{0 0 2.88 0} {2.88 0 2.88 37.12}"
    assert attr(s, "sp_L1_inv1_buf2_Y", "loads") == "sp_L2_inv1"
    assert "load sp_L2_inv1: behind 2 buffer(s), 22.38 um after sp_L1_inv1_buf2" in text


def test_last_distance_and_the_names(long):
    s = long
    made = lst(s, ADD + " -last_distance 20 -name rep")
    text = out_of(s)
    assert made == [f"inst:sp_L2_inv1_rep{k}" for k in (1, 2, 3, 4, 5)]
    assert ", the last 20 um from the pin of each load" in text
    # 30, 80, 130, 180, and the last 20 um from sp_L3_inv2/A: the pins are 1.528 um
    # apart in x with the buffer on the net, so 18.472 um below the pin
    (ax, ay), (yx, yy) = _pin_centre(s.db, "sp_L3_inv2", "A"), \
        _pin_centre(s.db, "sp_L2_inv1_rep5", "Y")
    assert (ax - yx, ay - yy) == pytest.approx((1.528, 18.472), abs=2e-3)
    assert centre(s, "sp_L2_inv1_rep5") == (5.76, 282.024)
    assert "load sp_L3_inv2: behind 5 buffer(s), 18.476 um after sp_L2_inv1_rep5, 20 um " \
        "from its pin to the pin of the load" in text
    assert float(attr(s, "sp_L2_inv1_rep5_Y", "length")) == pytest.approx(18.476)
    assert float(attr(s, "sp_L2_inv1_rep4_Y", "length")) == pytest.approx(5.404)
    assert "an odd number of inverting cells before a load inverts its signal" in text
    # sp_L3_inv1 is 2.88 um from the driver: no buffer 20 um from its pin
    assert attr(s, "sp_L2_inv1_Y", "loads") == "sp_L3_inv1 sp_L2_inv1_rep1"
    assert "no buffer 20 um from the pin of sp_L3_inv1: the driver of the net is nearer" in text


def test_again_on_a_buffered_net(long):
    s = long
    s.eval(ADD)
    out_of(s)
    # the first stretch, now 30 um: the names go on from the ones in use
    made = lst(s, "add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -distance 10")
    assert made == ["inst:sp_L2_inv1_buf5", "inst:sp_L2_inv1_buf6"]
    assert attr(s, "sp_L2_inv1_Y", "loads") == "sp_L3_inv1 sp_L2_inv1_buf5"
    assert attr(s, "sp_L2_inv1_buf6_Y", "loads") == "sp_L2_inv1_buf1"
    assert float(attr(s, "sp_L2_inv1_buf6_Y", "length")) == pytest.approx(10)
    # the net of a buffer
    made = lst(s, "add_buffer_on_net -net sp_L2_inv1_buf2_Y -ref_cell INV_RP -distance 25")
    assert made == ["inst:sp_L2_inv1_buf2_buf1"]
    assert centre(s, "sp_L2_inv1_buf2_buf1") == (5.76, 176.62 + 25)
    assert attr(s, "sp_L2_inv1_buf2_buf1_Y", "loads") == "sp_L2_inv1_buf3"
    assert s.eval("get_db pin:sp_L2_inv1_buf3/A .net.name") == "sp_L2_inv1_buf2_buf1_Y"


def test_patterns_and_leaf_nets(long):
    s = long
    made = lst(s, "add_buffer_on_net -net * -ref_cell INV_RP -distance 60")
    text = out_of(s)
    assert "HT4-259" in text and "2 net(s) of a leaf left as they are" in text
    assert "sp_L3_inv1_Y sp_L3_inv2_Y" in text
    assert made == ["inst:sp_L1_inv1_buf1", "inst:sp_L2_inv1_buf1", "inst:sp_L2_inv1_buf2",
                    "inst:sp_L2_inv1_buf3"]
    assert "Added 4 buffer(s) on 2 net(s), now 6 nets." in text
    assert attr(s, "sp_L3_inv1_Y", "loads") == "stub1"
    # only leaf nets: nothing to do
    assert s.eval("add_buffer_on_net -net sp_L3* -ref_cell INV_RP -distance 60") == ""
    assert "Added" not in out_of(s)


def test_no_buffer_fits(long):
    s = long
    before = lst(s, "get_db insts")
    assert s.eval("add_buffer_on_net -net sp_L* -ref_cell INV_RP -distance 300") == ""
    text = out_of(s)
    assert "HT4-259" in text and "no buffer on sp_L1_inv1_Y (102.38 um to its farthest load) ; " \
        "sp_L2_inv1_Y (203.88 um to its farthest load): the first would be 300 um" in text
    assert lst(s, "get_db insts") == before
    # one net of the two is long enough
    made = lst(s, "add_buffer_on_net -net sp_L* -ref_cell INV_RP -distance 150")
    assert made == ["inst:sp_L2_inv1_buf1"]
    assert "no buffer on sp_L1_inv1_Y" in out_of(s)


def test_errors_change_nothing(long, write_lef):
    s = long
    s.eval(f"read_lef -file {{{write_lef(MORE_LEF, 'more.lef')}}}")
    before = (lst(s, "get_db insts"), lst(s, "get_db spine:sp .spine_nets"),
              attr(s, "sp_L2_inv1_Y", "route"))
    for script, code, said in (
            ("add_buffer_on_net -ref_cell INV_RP -first_distance 30 -distance 100",
             "HT4-001", "-net required"),
            ("add_buffer_on_net -net sp_L2_inv1_Y", "HT4-001",
             "-ref_cell and -distance required"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -distance 0",
             "HT4-001", "-distance must be a distance in um above 0"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -distance x",
             "HT4-001", "got 'x'"),
            (ADD + " -first_distance -3", "HT4-001", "-first_distance must be"),
            (ADD + " -last_distance nan", "HT4-001", "-last_distance must be"),
            (ADD + " -name a/b", "HT4-001", "-name 'a/b'"),
            (ADD + " -bogus 1", "HT4-001", "-bogus"),
            ("add_buffer_on_net -net {sp_L2_inv1_Y nosuch} -ref_cell INV_RP -distance 50",
             "HT4-256", "no net 'nosuch'"),
            ("add_buffer_on_net -net spine_net:other/sp_L2_inv1_Y -ref_cell INV_RP -distance 50",
             "HT4-256", "no net 'spine_net:other/sp_L2_inv1_Y'"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell NOPE -distance 50",
             "HT4-257", "lib cell 'NOPE' is not in the library"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell SINK -distance 50",
             "HT4-257", "needs a SIZE, a signal input pin and a signal output pin"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell NOSIZE -distance 50",
             "HT4-257", "needs a SIZE"),
            ("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -distance 0.1",
             "HT4-263", "2038 buffers on net sp_L2_inv1_Y, more than 500")):
        text = err(s, script)
        assert code in text and said in text, script
    assert (lst(s, "get_db insts"), lst(s, "get_db spine:sp .spine_nets"),
            attr(s, "sp_L2_inv1_Y", "route")) == before


def test_needs_a_library_and_a_built_spine(session):
    assert "HT4-026" in err(session, "add_buffer_on_net -net n -ref_cell c -distance 5")


def test_a_routed_net_is_refused(long):
    s = long
    s.eval("route_pin -inst *sp_*")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    s.eval("route_net -net sp_L2_inv1_Y -rule r")
    text = err(s, "add_buffer_on_net -net sp_L* -ref_cell INV_RP -distance 50")
    assert "HT4-258" in text and "delete_route -nets {sp_L2_inv1_Y}" in text
    assert len(lst(s, "get_db insts")) == 4                      # the other net neither
    s.eval("delete_route -nets {sp_L2_inv1_Y}")
    assert len(lst(s, ADD)) == 4


def test_buffers_are_routed_like_the_other_cells(long):
    s = long
    made = lst(s, ADD)
    s.eval("route_pin -inst [get_db insts]")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    assert len(lst(s, f"get_db {made[0]} .straps")) == 7
    out_of(s)
    nets = ["sp_L2_inv1_Y"] + [f"{m[5:]}_Y" for m in made]
    done = lst(s, f"route_net -net {{{' '.join(nets)}}} -rule r")
    text = out_of(s)
    assert done == [f"spine_net:sp/{n}" for n in nets]
    assert "not connected" not in text
    assert "driver sp_L2_inv1_buf1/Y (strap 3): connected across the strap" in text
    assert "load sp_L2_inv1_buf1/A (strap 5): connected across the strap" in text
    assert "load sp_L3_inv2/A (strap 5): connected across the strap" in text
    for n in nets:
        assert lst(s, f"get_db spine_net:sp/{n} .net_wires")
    # check_drc: nothing open on the routed nets, nothing short on a buffer
    s.eval("check_drc")
    text = out_of(s)
    assert "buf" not in text.partition("Shorts")[2]


def test_mirror_spine_and_the_orientation_of_the_driver(tech_session, write_lef):
    s = make(tech_session, write_lef, mirror=True)
    made = lst(s, "add_buffer_on_net -net *L2_inv1_Y -ref_cell INV_RP -distance 90")
    assert made == ["inst:sp_L2_inv1_buf1", "inst:sp_L2_inv1_buf2",
                    "inst:sp_mirror_L2_inv1_buf1", "inst:sp_mirror_L2_inv1_buf2"]
    route = _floats(attr(s, "sp_mirror_L2_inv1_buf1_Y", "route"))
    x1, y1, x2, y2 = _floats(s.eval("get_db inst:sp_mirror_L2_inv1_buf1 .bbox"))
    assert ((x1 + x2) / 2, (y1 + y2) / 2) == pytest.approx(tuple(route[:2]), abs=1e-3)
    assert (x2 - x1, y2 - y1) == pytest.approx((3.12, 1.778))
    assert s.eval("get_db inst:sp_mirror_L2_inv1 .orient") == "FS"   # as create_spine put it
    assert s.eval("get_db inst:sp_mirror_L2_inv1_buf1 .orient") == "FS"
    assert route == pytest.approx([5.76, -186.62, 5.76, -276.62])    # away from the driver
    assert s.eval("get_db inst:sp_L2_inv1_buf1 .orient") == "N"
    assert attr(s, "sp_mirror_L2_inv1_buf2_Y", "loads") == "sp_mirror_L3_inv2"


def test_buffers_move_with_their_spine(long):
    s = long
    s.eval(ADD)
    route = _floats(attr(s, "sp_L2_inv1_buf2_Y", "route"))
    s.eval("move_obj spine:sp -direction up -distance 10")
    assert centre(s, "sp_L2_inv1_buf2") == (5.76, 186.62)
    assert _floats(attr(s, "sp_L2_inv1_buf2_Y", "route")) == \
        pytest.approx([v + (10 if k % 2 else 0) for k, v in enumerate(route)])


def test_write_db_and_read_db(long, tmp_path):
    s = long
    s.eval(ADD)
    want = (lst(s, "get_db spine:sp .insts"), lst(s, "get_db spine:sp .spine_nets"),
            s.eval("get_db [get_db spine:sp .spine_nets] .route"),
            s.eval("get_db [get_db spine:sp .spine_nets] .loads"),
            s.eval("get_db [get_db spine:sp .insts] .bbox"))
    s.eval(f"write_db -file {{{tmp_path / 'o.db'}}}")
    t = Session(out=s.out)
    t.eval(f"read_db -file {{{tmp_path / 'o.db'}}}")
    assert (lst(t, "get_db spine:sp .insts"), lst(t, "get_db spine:sp .spine_nets"),
            t.eval("get_db [get_db spine:sp .spine_nets] .route"),
            t.eval("get_db [get_db spine:sp .spine_nets] .loads"),
            t.eval("get_db [get_db spine:sp .insts] .bbox")) == want
    assert t.eval("get_db pin:sp_L3_inv2/A .net.name") == "sp_L2_inv1_buf4_Y"
    # and it goes on from there
    assert lst(t, "add_buffer_on_net -net sp_L2_inv1_buf4_Y -ref_cell INV_RP -distance 10") == \
        ["inst:sp_L2_inv1_buf4_buf1", "inst:sp_L2_inv1_buf4_buf2"]


def test_write_logical_and_write_def(long, tmp_path):
    s = long
    s.eval(ADD)
    s.eval(f"write_logical -output {{{tmp_path / 'l.tcl'}}}")
    text = (tmp_path / "l.tcl").read_text()
    assert "spine sp level buffer" in text
    for k in (1, 2, 3, 4):
        assert f"sp_L2_inv1_buf{k}" in text
    s.eval(f"write_def -output {{{tmp_path / 'o.def'}}} -sections {{components nets}}")
    text = (tmp_path / "o.def").read_text()
    assert "- sp_L2_inv1_buf1 INV_RP + PLACED ( 4200 125731 ) N ;" in text
    assert "- sp_L2_inv1_Y ( sp_L2_inv1 Y ) ( sp_L3_inv1 A ) ( sp_L2_inv1_buf1 A )" in text
    assert "- sp_L2_inv1_buf4_Y ( sp_L2_inv1_buf4 Y ) ( sp_L3_inv2 A )" in text


def test_connect_pin_loads_go_with_their_stretch(long):
    s = long
    # d1 beside the net 150 um from its driver, d2 beside its start
    s.eval("create_inst -name d1 -ref_cell INV_RP -location {20 246.62}")
    s.eval("create_inst -name d2 -ref_cell INV_RP -location {20 105}")
    s.eval("connect_pin -from sp_L2_inv1/Y -to {d1/A d1/B d2/B}")
    assert attr(s, "sp_L2_inv1_Y", "loads") == "sp_L3_inv1 sp_L3_inv2 d1"
    out_of(s)
    s.eval(ADD)
    text = out_of(s)
    # 30, 80, 130, 180: d1 is behind three buffers, d2 behind none
    assert attr(s, "sp_L2_inv1_Y", "loads") == "sp_L3_inv1 sp_L2_inv1_buf1"
    assert attr(s, "sp_L2_inv1_buf3_Y", "loads") == "d1 sp_L2_inv1_buf4"
    assert s.eval("get_db pin:d1/A .net.name") == s.eval("get_db pin:d1/B .net.name") == "sp_L2_inv1_buf3_Y"
    assert s.eval("get_db pin:d2/B .net.name") == "sp_L2_inv1_Y"
    assert "load d1/B (connect_pin): behind 3 buffer(s)" in text
    assert "load d2/B (connect_pin): behind 0 buffer(s)" in text
    rows = {(r["inst"], r["pin"]): (r["net"], r["driver"]) for r in s.db.connection_rows()}
    assert rows["d1", "B"] == ("sp_L2_inv1_buf3_Y", "sp_L2_inv1_buf3/Y")
    assert rows["d2", "B"] == ("sp_L2_inv1_Y", "sp_L2_inv1/Y")
    # the pin can be taken off its new net again
    s.eval("disconnect_pin -pin d1/B")
    assert s.eval("get_db pin:d1/B .net.name") == ""


def test_overlaps_and_the_boundary_are_warned_about(long):
    s = long
    made = lst(s, "add_buffer_on_net -net sp_L1_inv1_Y -ref_cell INV_RP -first_distance 1 "
                  "-distance 200")
    text = out_of(s)
    assert made == ["inst:sp_L1_inv1_buf1"]                     # made all the same
    assert "HT4-261" in text and "1 overlap(s): sp_L1_inv1_buf1 and sp_L1_inv1." in text
    assert "HT4-262" not in text
    s.eval("create_inst -name far -ref_cell INV_RP -location {499 0}")
    s.eval("create_inst -name near -ref_cell INV_RP -location {490 0}")
    out_of(s)
    _check_place(s.db, ["far", "near"], s.out)
    text = out_of(s)
    assert "HT4-262" in text and "not inside the design boundary: far\n" in text
    assert "HT4-261" not in text
    # two of them over each other: named once
    s.eval("create_inst -name over -ref_cell INV_RP -location {491 1}")
    out_of(s)
    _check_place(s.db, ["near", "over"], s.out)
    assert "1 overlap(s): near and over." in out_of(s)


# -- on a spine that bends, with placement rows (the design of test_move_spine) --------

def test_the_buffers_are_put_on_sites(tech_session, write_lef):
    s = build(tech_session, write_lef)
    before = {r["name"]: (r["x"], r["y"]) for r in s.db.inst_rows()}
    made = lst(s, "add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -first_distance 6 "
                  "-distance 6")
    text = out_of(s)
    assert len(made) == 3
    assert "legalize_placement: 3 instance(s) moved onto sites" in text
    assert "HT4-264" not in text and "HT4-261" not in text
    assert "Next: route_pin for the buffers" in text
    from core import objects
    from core.commands.legalize_placement import _overlap
    boxes = {r["name"]: objects.inst_bbox(s.db, r) for r in s.db.inst_rows()}
    for name in made:                                           # 0.2 sites, rows of 1.778
        x, y = _floats(s.eval(f"get_db {name} .location"))
        assert abs(x / 0.2 - round(x / 0.2)) < 1e-6 and abs(y / 1.778 - round(y / 1.778)) < 1e-6
        assert x == pytest.approx(74.2)                         # on the net, 6 um apart
        assert not any(_overlap(boxes[name[5:]], b) for n, b in boxes.items() if n != name[5:])
    assert centre(s, "sp_L2_inv1_buf2") == (75.76, 118.237)     # 118.62 as planned
    assert "sp_L2_inv1_buf2           12          6  {75.76 118.237}" in text
    # the other cells stay where they are
    assert {n: (r["x"], r["y"]) for n in before for r in [s.db.inst_row(n)]} == before


def test_buffers_follow_a_spine_that_is_bent(tech_session, write_lef):
    s = build(tech_session, write_lef, rows=False)
    s.eval("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -first_distance 6 -distance 6")
    out_of(s)
    s.eval("move_spine_to_boundary -spine sp -moves {head bottom down 69.4 left 30.76}")
    assert "7 instances, 2 stubs, 7 nets" in out_of(s)
    # each buffer is where its net starts, on the bent path
    for k in (1, 2, 3):
        route = _floats(attr(s, f"sp_L2_inv1_buf{k}_Y", "route"))
        assert centre(s, f"sp_L2_inv1_buf{k}") == tuple(route[:2])
    lengths = [float(attr(s, f"sp_L2_inv1_buf{k}_Y", "length")) for k in (1, 2, 3)]
    assert lengths == pytest.approx([6, 6, 5.88])


def test_buffers_on_a_bent_spine(tech_session, write_lef):
    s = build(tech_session, write_lef, rows=False)
    s.eval("move_spine_to_boundary -spine sp -moves {head bottom down 69.4 left 30.76}")
    before = _floats(attr(s, "sp_L1_inv1_Y", "route"))
    out_of(s)
    made = lst(s, "add_buffer_on_net -net sp_L1_inv1_Y -ref_cell INV_RP -distance 4")
    assert len(made) == 3                                       # 12.38 um: 4, 8, 12
    pieces = [_floats(attr(s, n, "route")) for n in
              ("sp_L1_inv1_Y", "sp_L1_inv1_buf1_Y", "sp_L1_inv1_buf2_Y", "sp_L1_inv1_buf3_Y")]

    def run(v):
        return sum(abs(v[k + 2] - v[k]) + abs(v[k + 3] - v[k + 1]) for k in range(0, len(v), 4))

    # the pieces are the centre lines the net had, cut at the buffers
    assert [run(v) for v in pieces] == pytest.approx([4, 4, 4, 0.38])
    assert run(before) == pytest.approx(12.38)
    assert pieces[0][:2] == pytest.approx(before[:2])
    assert pieces[-1][-2:] == pytest.approx(before[-2:])
    for k, name in enumerate(made):
        assert centre(s, name[5:]) == tuple(pieces[k + 1][:2])
    # the last distance is measured in the layout, on the path as it is bent
    s.eval("add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -distance 100 -last_distance 9")
    text = out_of(s)
    (ax, ay), (yx, yy) = _pin_centre(s.db, "sp_L3_inv2", "A"), \
        _pin_centre(s.db, "sp_L2_inv1_buf1", "Y")
    assert abs(ax - yx) + abs(ay - yy) == pytest.approx(9, abs=2e-3)
    assert "after sp_L2_inv1_buf1, 9 um from its pin to the pin of the load" in text


def test_the_gui_draws_the_buffers_and_their_nets(long):
    from core.gui.layout_data import load_layout
    long.eval(ADD)
    lay = load_layout(long.db)
    assert "inst:sp_L2_inv1_buf3" in [i.handle for i in lay.insts]
    segments = dict(lay.spines[0].segments)
    assert segments["sp_L2_inv1_buf3_Y"] == pytest.approx([5.76, 226.62, 5.76, 276.62])


# -- a net of no spine: of a port, or one connect_pin made -------------------------------

# An input port 400 um above the root of the spine, and one with nothing on it.
PORTS = """PINS 2 ;
- clk + NET clk_in + DIRECTION INPUT + USE CLOCK
  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 3000 400000 ) N ;
- idle + NET idle + DIRECTION INPUT ;
END PINS
"""
PORT_ADD = "add_buffer_on_net -net clk_in -ref_cell INV_RP -first_distance 100 -distance 100 " \
           "-last_distance 50 -name rep"


@pytest.fixture
def ported(tech_session, write_lef):
    """The long spine in a design with ports, an instance d1 of no spine, and
    the port clk on the input of the root of the spine and of d1."""
    s = make(tech_session, write_lef, pins=PORTS)
    s.eval("create_inst -name d1 -ref_cell INV_RP -location {40 20}")
    s.eval("connect_pin -from clk -to {sp_L1_inv1/A d1/A} -disconnect")
    out_of(s)
    return s


def test_centre_lines_of_a_net_without_any():
    # one pin: across from the driver, then straight to the pin
    assert tree((3, 400), [(1, 0)]) == [((1, 0), (1, 400)), ((3, 400), (1, 400))]
    # the trunk runs the way they are spread, at the middle pin across it
    assert tree((0, 0), [(100, 5), (200, -5), (300, 2)]) == [
        ((0, 2), (300, 2)), ((0, 0), (0, 2)), ((100, 5), (100, 2)), ((200, -5), (200, 2))]
    # of two pins the lower; a pin behind the driver lengthens the trunk
    assert tree((3, 400), [(41, 20), (1, 500)]) == [
        ((1, 20), (1, 500)), ((3, 400), (1, 400)), ((41, 20), (1, 20))]
    # the driver and a pin in line: one line
    assert tree((5, 0), [(5, 90)]) == [((5, 0), (5, 90))]
    top, bufs = split(tree((3, 400), [(1, 0)]), (3, 400), {"a": (1, 0)}, 100, 100)
    assert dists(bufs) == [100, 200, 300, 400]
    assert [b.at for b in bufs] == [(1, 302), (1, 202), (1, 102), (1, 2)]


def test_buffers_on_the_net_of_a_port(ported):
    s = ported
    spine = (lst(s, "get_db spine:sp .insts"), lst(s, "get_db spine:sp .spine_nets"))
    made = lst(s, PORT_ADD)
    text = out_of(s)
    assert made == [f"inst:clk_rep{k}" for k in (1, 2, 3, 4, 5)]     # named after the port
    ax, ay = _pin_centre(s.db, "sp_L1_inv1", "A")
    dx, dy = _pin_centre(s.db, "d1", "A")
    # across from the port at {3 400} to the trunk, at the x of the pin of the root
    for k in (1, 2, 3):
        assert centre(s, f"clk_rep{k}") == (ax, 400 - (100 * k - (3 - ax)))
    # the last buffers: 50 um from pin to pin before the root, and before d1
    for name, (x, y) in (("clk_rep4", (ax, ay)), ("clk_rep5", (dx, dy))):
        yx, yy = _pin_centre(s.db, name, "Y")
        assert abs(x - yx) + abs(y - yy) == pytest.approx(50, abs=2e-3)
    assert "clk_in (the net of a port, 443.385 um, driver port clk): 5 buffer(s)" in text
    assert "load d1/A: behind 5 buffer(s)" in text and "50 um from its pin to the pin" in text
    assert "Added 5 buffer(s) on 1 net(s), now 6 nets. Next: legalize_placement, route_pin " \
        "for the buffers, then route_net -net {clk_in clk_rep1_Y " in text
    # the netlist: the port drives the first buffer, each buffer the next, the last the pins
    assert lst(s, "get_db net:clk_in .pins") == ["pin:clk_rep1/A"]
    assert s.eval("get_db net:clk_in .driver") == "port:t/clk"
    for k in (1, 2, 3, 4):
        assert set(lst(s, f"get_db net:clk_rep{k}_Y .pins")) == \
            {f"pin:clk_rep{k}/Y", f"pin:clk_rep{k + 1}/A"}
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == s.eval("get_db pin:d1/A .net") == \
        "net:clk_rep5_Y"
    assert s.eval("get_db net:clk_rep5_Y .driver") == "pin:clk_rep5/Y"
    # instances of no spine, in the orientation of the first load; the spine is as it was
    assert (lst(s, "get_db spine:sp .insts"), lst(s, "get_db spine:sp .spine_nets")) == spine
    assert s.eval("get_db inst:clk_rep1 .orient") == s.eval("get_db inst:sp_L1_inv1 .orient")
    assert s.eval("get_db inst:clk_rep1 .ref_name") == "INV_RP"


def test_port_net_buffers_are_routed(ported):
    """The flow the last message names: route_pin for the buffers, route_net on the nets."""
    s = ported
    made = lst(s, PORT_ADD)
    s.eval("route_pin -inst [get_db insts]")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    nets = ["clk_in"] + [f"{m[5:]}_Y" for m in made]
    done = lst(s, f"route_net -net {{{' '.join(nets)}}} -rule r")
    text = out_of(s)
    assert done == [f"net:{n}" for n in nets]
    assert "HT4-17" not in text
    # the port is beside the tracks: the route ends at the crossing nearest to it
    assert "HT4-266" in text and "driver port clk: ends near the port, not connected" in text
    assert "load clk_rep1/A (strap 5): connected across the strap" in text
    assert "driver clk_rep5/Y (strap 3): connected across the strap" in text
    assert "load sp_L1_inv1/A (strap 5): connected across the strap" in text
    assert "load d1/A (strap 5): connected across the strap" in text
    for n in nets:
        assert lst(s, f"get_db net:{n} .net_wires")
    # routed now: buffers go along the wires, but not with -last_distance yet
    assert "-last_distance is not taken on routed nets yet (clk_in)" in err(s, PORT_ADD)


def test_again_on_the_net_of_a_port_and_by_its_handle(ported):
    s = ported
    s.eval(PORT_ADD)
    # the net of the port ends at clk_rep1 now, 100 um from the port
    made = lst(s, "add_buffer_on_net -net net:clk_in -ref_cell INV_RP -distance 30")
    assert made == ["inst:clk_buf1", "inst:clk_buf2", "inst:clk_buf3"]
    assert lst(s, "get_db net:clk_in .pins") == ["pin:clk_buf1/A"]
    assert s.eval("get_db pin:clk_rep1/A .net.driver") == "pin:clk_buf3/Y"
    # and a net of a buffer, by a pattern
    made = lst(s, "add_buffer_on_net -net clk_rep2* -ref_cell INV_RP -distance 60")
    assert made == ["inst:clk_rep2_buf1"]
    assert s.eval("get_db pin:clk_rep3/A .net.driver") == "pin:clk_rep2_buf1/Y"


def test_a_net_connect_pin_made(ported):
    s = ported
    s.eval("create_inst -name d2 -ref_cell INV_RP -location {340 20} -orient FS")
    s.eval("connect_pin -from d1/Y -to d2/A")
    out_of(s)
    made = lst(s, "add_buffer_on_net -net d1_Y -ref_cell INV_RP -distance 100")
    text = out_of(s)
    assert made == ["inst:d1_buf1", "inst:d1_buf2", "inst:d1_buf3"]     # named after the driver
    assert "d1_Y (a net of no spine, " in text and "driver d1/Y" in text
    (x, y), (ax, ay) = _pin_centre(s.db, "d1", "Y"), _pin_centre(s.db, "d2", "A")
    assert centre(s, "d1_buf1") == (x + 100 - abs(ay - y), ay)      # along x, at the y of the pin
    assert s.eval("get_db inst:d1_buf1 .orient") == s.eval("get_db inst:d1 .orient")
    assert s.eval("get_db pin:d2/A .net") == "net:d1_buf3_Y"
    assert set(lst(s, "get_db net:d1_Y .pins")) == {"pin:d1/Y", "pin:d1_buf1/A"}


def test_nets_of_no_spine_that_are_left_as_they_are(ported):
    s = ported
    before = lst(s, "get_db insts")
    # nothing on the net of the port; the root net of the spec has no driver
    assert s.eval("add_buffer_on_net -net idle -ref_cell INV_RP -distance 10") == ""
    text = out_of(s)
    assert "HT4-259" in text and "net idle left as it is: no input pin of an instance is on " \
        "it (connect_pin -from port:idle -to <pins>)" in text
    s.eval("disconnect_pin -pin sp_L1_inv1/A")
    out_of(s)
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == ""
    assert "no net 'net'" in err(s, "add_buffer_on_net -net net -ref_cell INV_RP -distance 10")
    assert "HT4-256" in err(s, "add_buffer_on_net -net net:nothing -ref_cell INV_RP -distance 10")
    # too many buffers: nothing is made
    assert "HT4-263" in err(s, "add_buffer_on_net -net clk_in -ref_cell INV_RP -distance 0.1")
    # shorter than the first distance
    assert s.eval("add_buffer_on_net -net clk_in -ref_cell INV_RP -distance 500") == ""
    assert "no buffer on clk_in (" in out_of(s)
    assert lst(s, "get_db insts") == before


def test_a_net_without_a_driver_is_left_as_it_is(long):
    s = long                             # the root net of the spine: no port drives it
    assert s.eval("add_buffer_on_net -net sp_primary_input -ref_cell INV_RP -distance 10") == ""
    text = out_of(s)
    assert "HT4-259" in text and "net sp_primary_input left as it is: it has no driver" in text


def test_port_net_buffers_in_write_logical_and_write_db(ported, tmp_path):
    s = ported
    s.eval(PORT_ADD)
    s.eval(f"write_logical -output {{{tmp_path / 'l.tcl'}}}")
    text = (tmp_path / "l.tcl").read_text()
    assert "net clk_in of port clk must exist in the design" in text
    for line in ("create_net -name clk_rep5_Y", "create_inst -cell INV_RP -name clk_rep1",
                 "connect clk_rep1/A -net clk_in", "connect clk_rep1/Y -net clk_rep1_Y",
                 "connect sp_L1_inv1/A -net clk_rep5_Y", "connect d1/A -net clk_rep5_Y"):
        assert line in text
    want = (lst(s, "get_db insts"), s.eval("get_db insts .bbox"), s.eval("get_db insts .pins.net"))
    s.eval(f"write_db -file {{{tmp_path / 'o.db'}}}")
    t = Session(out=s.out)
    t.eval(f"read_db -file {{{tmp_path / 'o.db'}}}")
    assert (lst(t, "get_db insts"), t.eval("get_db insts .bbox"),
            t.eval("get_db insts .pins.net")) == want


# -- on a routed net: along its wires, cut there ---------------------------------------------

ROUTED_ADD = "add_buffer_on_net -net clk_in -ref_cell INV_RP -first_distance 100 " \
             "-distance 100 -name rep"


@pytest.fixture
def routed_port(ported):
    """clk_in routed: from the port at {3 400} down the IB track x 1.44 to the
    root of the spine, with a branch on IA y 15.12 to d1 at {40 20}."""
    s = ported
    s.eval("route_pin -inst [get_db insts]")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval("route_net -net clk_in -rule r")
    out_of(s)
    return s


def drc_counts(s):
    s.eval("check_drc")
    return [l for l in out_of(s).splitlines() if l.startswith(("  short", "  open", "  Total"))]


def test_buffers_along_a_routed_net(routed_port):
    s = routed_port
    before = drc_counts(s)
    assert lst(s, ROUTED_ADD) == [f"inst:rep_{k}" for k in (1, 2, 3, 4)]
    text = out_of(s)
    # every 100 um from the port; two moved 10.08 um off the spine cells under the route,
    # the one 400 um down to the root of the spine has no room on its branch
    assert "clk_in: buffers moved along the route, off the cells under it (um, + is away " \
           "from the driver): rep_1 -10.08, rep_3 -10.08" in text
    assert "(HT4-261): add_buffer_on_net: clk_in: 1 buffer(s) not made: no place within 50 um " \
           "along that branch of the route clear of the cells under it and their pin routes, " \
           "at 400 um ({1.44 1.76}) from the driver" in text
    for row in ("rep_1        89.92  {1.44 311.84}        clk_in -> rep_1_Y",
                "rep_2          200  {1.44 201.76}        rep_1_Y -> rep_2_Y",
                "rep_3       289.92  {1.44 111.84}        rep_2_Y -> rep_3_Y",
                "rep_4          400  {14.8 15.12}         rep_3_Y -> rep_4_Y",
                "load sp_L1_inv1/A: on rep_3_Y, behind rep_3",
                "load d1/A: on rep_4_Y, behind rep_4"):
        assert row in text
    assert "clk_in: 4 buffer(s) along its route, its 4 wire(s) cut into" in text
    # the netlist
    assert lst(s, "get_db net:clk_in .pins") == ["pin:rep_1/A"]
    assert set(lst(s, "get_db net:rep_3_Y .pins")) == \
        {"pin:rep_3/Y", "pin:rep_4/A", "pin:sp_L1_inv1/A"}
    assert set(lst(s, "get_db net:rep_4_Y .pins")) == {"pin:rep_4/Y", "pin:d1/A"}
    # every piece kept where it was and joined to the pins: no new short or open
    assert drc_counts(s) == before
    for net in ("clk_in", "rep_1_Y", "rep_2_Y", "rep_3_Y", "rep_4_Y"):
        rows = s.db.net_wire_rows(net)
        assert [r for r in rows if r["kind"] == "wire"]
        assert not [r for r in rows if r["status"] == "fixed"]    # none was fixed before
    assert "route_pin" in text and "route_net: rule r" in text


def test_the_cut_wires_keep_their_place(routed_port):
    """Every piece is a part of a wire the net had: the route is not routed
    again, only joined to the pins of the buffers."""
    s = routed_port
    trunk = next(r for r in s.db.net_wire_rows("clk_in")
                 if r["kind"] == "wire" and r["layer"] == "IB" and float(r["rect"].split()[3]) > 300)
    x1, y1, x2, y2 = (float(c) for c in trunk["rect"].split())
    s.eval(ROUTED_ADD)
    out_of(s)
    on_track = sorted((float(r["rect"].split()[1]), float(r["rect"].split()[3]), r["net"])
                      for n in ("clk_in", "rep_1_Y", "rep_2_Y", "rep_3_Y")
                      for r in s.db.net_wire_rows(n) if r["kind"] == "wire" and r["layer"] == "IB"
                      and r["rect"].split()[0] == _n(x1))
    assert on_track[-1][2] == "clk_in" and on_track[-1][1] == pytest.approx(y2)
    # the gaps: each piece of the trunk ends short of the next buffer's cell
    for k, centre_y in ((1, 311.84), (2, 201.76)):
        above = [p for p in on_track if p[0] > centre_y]
        assert min(p[0] for p in above) > centre_y + 0.889            # past the cell


def test_a_fixed_wire_is_cut_and_its_pieces_stay_fixed(routed_port):
    s = routed_port
    trunk = next(r for r in s.db.net_wire_rows("clk_in")
                 if r["kind"] == "wire" and r["layer"] == "IB" and float(r["rect"].split()[3]) > 300)
    s.eval(f"set_db net_wire:clk_in/{trunk['seq']} .route_status fixed")
    s.eval(ROUTED_ADD)
    out_of(s)
    for net in ("clk_in", "rep_1_Y", "rep_2_Y"):
        fixed = [r for r in s.db.net_wire_rows(net) if r["status"] == "fixed"]
        assert len(fixed) == 1 and fixed[0]["layer"] == "IB"


def test_last_distance_on_a_routed_net_changes_nothing(routed_port):
    s = routed_port
    wires = [tuple(r) for r in s.db.net_wire_rows()]
    assert "HT4-001" in err(s, ROUTED_ADD + " -last_distance 20")
    assert [tuple(r) for r in s.db.net_wire_rows()] == wires
    assert not [n for n in s.db.inst_names() if n.startswith("rep_")]


# -- -buffer_count and -spread ------------------------------------------------------------

def test_buffer_count_stops_the_row():
    # every 100 um on 1000 um would be 9 buffers: 3 of them, the 6 points past left
    top, bufs = split(LINE, (0, 0), {"x": (1000, 0)}, 100, 100, count=3)
    assert dists(bufs) == [100, 200, 300] and top.capped == 6
    assert bufs[-1].loads == [("x", pytest.approx(1000))]       # the load behind the 3rd
    top, bufs = split(LINE, (0, 0), {"x": (300, 0)}, 100, 100, count=3)
    assert dists(bufs) == [100, 200] and top.capped == 0        # fewer: nothing left
    # in a row from the driver: each branch has its own
    top, bufs = split(TEE, (0, 0), {"a": (10, -100), "b": (10, 100)}, 30, 30, count=2)
    assert sorted(b.dist for b in bufs) == pytest.approx([30, 30, 60, 60])
    assert max(b.depth for b in bufs) == 2 and top.capped == 2   # 90 um on each branch


def test_spread_cuts_the_net_into_equal_parts():
    # 600 um, 3 buffers: 4 parts of 150 um
    top, bufs = split(LINE, (0, 0), {"x": (600, 0)}, None, None, count=3, spread=True)
    assert dists(bufs) == [150, 300, 450] and top.capped == 0
    # branches: the parts of the way to the farthest load; a nearer branch gets fewer
    top, bufs = split(TEE, (0, 0), {"a": (10, -100), "b": (10, 40)}, None, None, count=2,
                      spread=True)
    by = {}
    for b in bufs:
        by.setdefault(b.at[1] < 0, []).append(b.dist)
    assert by[True] == pytest.approx([110 / 3, 220 / 3]) and by[False] == pytest.approx([110 / 3])


def test_buffer_count_on_a_net(long):
    s = long
    made = lst(s, ADD + " -buffer_count 2")                      # 4 without it
    text = out_of(s)
    assert made == ["inst:sp_L2_inv1_buf1", "inst:sp_L2_inv1_buf2"]
    assert "(HT4-307): add_buffer_on_net: max buffer count reached (2 in a row from the " \
           "driver): no buffer on the point(s) past it on sp_L2_inv1_Y (2 left)" in text
    assert "at most 2 in a row" in text and "Added 2 buffer(s) on 1 net(s)" in text
    assert "load sp_L3_inv2: behind 2 buffer(s)" in text


def test_spread_on_a_net(long):
    s = long
    made = lst(s, "add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP -buffer_count 3 "
                  "-spread")
    text = out_of(s)
    assert len(made) == 3 and "HT4-307" not in text
    assert "3 INV_RP spread evenly on each net, every 1/4 of the way" in text
    # the net is 203.88 um to sp_L3_inv2: a buffer every 50.97 um
    for k in (1, 2, 3):
        assert float(attr(s, f"sp_L2_inv1_buf{k}_Y" if k < 3 else "sp_L2_inv1_buf2_Y",
                          "length")) == pytest.approx(50.97, abs=1e-3)


def test_buffer_count_and_spread_on_a_routed_net(routed_port):
    s = routed_port
    assert lst(s, ROUTED_ADD + " -buffer_count 2") == ["inst:rep_1", "inst:rep_2"]
    text = out_of(s)
    assert "(HT4-307)" in text and "clk_in (" in text and "left)" in text
    assert "clk_in: 2 buffer(s) along its route" in text


def test_spread_on_a_routed_net(routed_port):
    s = routed_port
    made = lst(s, "add_buffer_on_net -net clk_in -ref_cell INV_RP -buffer_count 1 -spread "
                  "-name rep")
    assert made == ["inst:rep_1"] and "HT4-307" not in out_of(s)


@pytest.mark.parametrize("opts, text", [
    ("-distance 50 -buffer_count 0", "-buffer_count must be a whole number above 0"),
    ("-distance 50 -buffer_count 2.5", "-buffer_count must be a whole number above 0"),
    ("-spread", "-spread needs -buffer_count"),
    ("-buffer_count 2", "-distance required"),
    ("-buffer_count 2 -spread -first_distance 30", "not with -first_distance"),
    ("-buffer_count 2 -spread -last_distance 30", "not with -last_distance"),
])
def test_buffer_count_errors(long, opts, text):
    msg = err(long, f"add_buffer_on_net -net sp_L2_inv1_Y -ref_cell INV_RP {opts}")
    assert "HT4-001" in msg and text in msg
    assert lst(long, "get_db insts") == lst(long, "get_db spine:sp .insts")


def test_spread_on_a_route_without_length_says_why(routed_port):
    # the net's routing gone but for a stub of wire at the port: every load and the
    # driver meet the route at one point, so there is no length to spread on
    s = routed_port
    rows = s.db.net_wire_rows("clk_in")
    s.db.delete_wires([("net_wire", r["id"]) for r in rows])
    s.db.add_net_wires([("clk_in", "wire", "IB", "1.08 399 1.8 399.3", None, None)])
    assert lst(s, "add_buffer_on_net -net clk_in -ref_cell INV_RP -buffer_count 1 -spread "
                  "-name rep") == []
    text = out_of(s)
    assert "(HT4-259): add_buffer_on_net: no buffer on clk_in: its route has no length to " \
           "spread them on: along its 1 signal wire(s) on IA/IB from the point nearest the " \
           "driver ({1.44 399.15}, the driver port clk at {3 400}) to the point nearest each " \
           "load: sp_L1_inv1/A 0 um, d1/A 0 um" in text
