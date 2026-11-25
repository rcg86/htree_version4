"""create_buffer_tree: the sinks of an input port through a tree of
inverters that shares its trunk and branches late, an even number of
inversions to every sink; all_fanout: the paths from a port forward."""

import pytest

pytest.importorskip("scipy")

from core.commands import create_buffer_tree as cbt
from test_connect_spine import ported  # noqa: F401  (a fixture)
from test_route_pin import CELL_LEF, err, out_of

TREE = "-inverter_ref INV_RP -buffer_ref BUF_RP -distance 30 -name ct"


@pytest.fixture
def sinks(ported, write_lef):
    """clk (an input port at {-90 10}) on three cells: two side by side far
    away, one near the port."""
    s = ported
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF.replace('INV_RP', 'BUF_RP'), 'b.lef')}}}")
    for name, at in (("s1", "60 70"), ("s2", "66 76"), ("s3", "-80 0")):
        s.eval(f"create_inst -name {name} -ref_cell INV_RP -location {{{at}}}")
    s.eval("connect_pin -from clk -to {s1/A s2/A s3/A}")
    out_of(s)
    return s


def chain(s, sink):
    """The cells from the port to sink (inst/pin), last first, by the netlist."""
    cells = []
    inst, pin = sink.split("/")
    while True:
        net = s.eval(f"get_db pin:{inst}/{pin} .net.name")
        driver = s.eval(f"get_db [get_db pin:{inst}/{pin} .net] .driver")
        if not driver.startswith("pin:"):
            return cells                 # the port
        inst = driver[4:].split("/")[0]
        pin = "A"
        cells.append((inst, s.db.inst_row(inst)["ref_cell"]))
        assert net


def test_the_tree_keeps_the_polarity_of_every_sink(sinks):
    s = sinks
    made = s.split_list(s.eval(f"create_buffer_tree -from [get_db ports clk] {TREE}"))
    text = out_of(s)
    assert made and all(m.startswith("ct_") for m in made)
    assert "create_buffer_tree: port clk (net clk) -> 3 sink(s)" in text
    for sink in ("s1/A", "s2/A", "s3/A"):
        cells = chain(s, sink)
        inv = sum(1 for _, ref in cells if ref == "INV_RP")
        assert inv % 2 == 0, (sink, cells)
    # the port drives one cell, at the port; s3, nearer the port than -distance, on
    # the tree behind it (an even count: one more inverter)
    assert s.eval("get_db net:clk .pins") == "pin:ct_1/A"
    assert [r for _, r in chain(s, "s3/A")] == ["INV_RP", "INV_RP"]
    # s1 and s2 share the trunk: all but the last cell or two before them (their ribs)
    a, b = chain(s, "s1/A")[::-1], chain(s, "s2/A")[::-1]      # from the port
    shared = next((k for k, (p, q) in enumerate(zip(a, b)) if p != q), min(len(a), len(b)))
    assert shared >= min(len(a), len(b)) - 1 and shared > 0
    # all_fanout says the same
    s.eval("all_fanout -from [get_db ports clk] -to s1/A")
    text = out_of(s)
    assert "path 1: port clk -> ct_" in text and "-> s1/A" in text
    line = next(l for l in text.splitlines() if "number of inverters" in l)
    assert int(line.split("number of inverters: ")[1].split()[0]) % 2 == 0
    assert "polarity inverted" not in text


def test_every_way_is_a_shortest_one():
    """build_tree: each sink reached the shortest way (x + y), branches late."""
    sinks = [(10, 10, "a"), (12, 11, "b"), (-5, 3, "c"), (10, -4, "d")]
    top = cbt.build_tree((0, 0), sinks)

    def ways(node, done):
        if node.sink is not None:
            yield node.sink, done
        for kid in node.kids:
            yield from ways(kid, done + abs(kid.x - node.x) + abs(kid.y - node.y))
    got = dict(ways(top, 0.0))
    assert got == {name: abs(x) + abs(y) for x, y, name in sinks}
    # a and b share their way to their merge point {10 10}
    assert any(abs(n.x - 10) < 1e-9 and abs(n.y - 10) < 1e-9 for n in _all(top))


def _all(node):
    yield node
    for kid in node.kids:
        yield from _all(kid)


def test_odd_ways_end_on_a_buffer(sinks):
    s = sinks
    s.eval("create_buffer_tree -from clk -inverter_ref INV_RP -buffer_ref BUF_RP "
           "-distance 50 -name t2")
    text = out_of(s)
    refs = {ref for sink in ("s1/A", "s2/A") for _, ref in chain(s, sink)}
    inv = {sink: sum(1 for _, ref in chain(s, sink) if ref == "INV_RP")
           for sink in ("s1/A", "s2/A", "s3/A")}
    assert all(n % 2 == 0 for n in inv.values()), inv
    assert "odd number" not in text
    assert refs <= {"INV_RP", "BUF_RP"}


def test_every_50_um_the_odd_way_ends_on_a_buffer(sinks):
    # every 50 um the way to s1 and s2 has 5 cells (the one at the port first): the
    # last one a buffer
    s = sinks
    s.eval("create_buffer_tree -from clk -inverter_ref INV_RP -buffer_ref BUF_RP "
           "-distance 50 -name t2")
    assert [r for _, r in chain(s, "s1/A")] == ["BUF_RP"] + ["INV_RP"] * 4


def test_without_buffer_ref_inverters_only(sinks):
    # the same tree without -buffer_ref: one more inverter, at the sink
    s = sinks
    s.eval("create_buffer_tree -from clk -inverter_ref INV_RP -distance 50 -name t3")
    text = out_of(s)
    assert "one more inverter before" in text
    assert "buffer(s) (no -buffer_ref)" in text and ", 0 buffer(s)" in text
    for sink in ("s1/A", "s2/A", "s3/A"):
        cells = chain(s, sink)
        assert {ref for _, ref in cells} <= {"INV_RP"}
        assert len(cells) % 2 == 0, (sink, cells)


def test_all_fanout_without_to_and_errors(sinks):
    s = sinks
    s.eval(f"create_buffer_tree -from clk {TREE}")
    out_of(s)
    got = s.split_list(s.eval("all_fanout -from clk"))
    assert len(got) == 3                                 # a path to each sink
    for path in got:
        end, buffers, inverters = s.split_list(path)
        assert int(inverters) % 2 == 0
    assert "HT4-302" in err(s, f"create_buffer_tree -from q {TREE}")       # an output port
    s.eval("disconnect_pin -pin s3/A")
    assert "HT4-305" in err(s, "all_fanout -from clk -to s3/A")
    assert "required" in err(s, "create_buffer_tree -from clk -distance 10")
    assert "must be a distance" in err(s, "create_buffer_tree -from clk -inverter_ref INV_RP "
                                          "-buffer_ref BUF_RP -distance 0")


def test_all_fanout_ends_at_the_stubs_of_a_spine(ported):
    s = ported
    got = [list(s.split_list(p)) for p in s.split_list(s.eval("all_fanout -from sp_L1_inv1/Y"))]
    text = out_of(s)
    assert got == [["stub sp/stub1", "0", "2"], ["stub sp/stub2", "0", "2"]]
    assert "path 1: sp_L1_inv1/Y -> sp_L2_inv1 (INV_RP) -> sp_L3_inv1 (INV_RP) -> " \
           "stub sp/stub1" in text


def test_even_from_the_port_to_each_end_past_an_inverting_sink(sinks):
    # s1 (an inverter) drives t1: the end t1/A is one inverter past s1/A
    s = sinks
    s.eval("create_inst -name t1 -ref_cell INV_RP -location {90 70}")
    s.eval("connect_pin -from s1/Y -to t1/A")
    out_of(s)
    s.eval(f"create_buffer_tree -from clk {TREE}")
    text = out_of(s)
    assert "odd number" not in text
    tree = lambda sink: sum(1 for _, ref in chain(s, sink) if ref == "INV_RP")  # noqa: E731
    assert tree("s1/A") % 2 == 1 and tree("s2/A") % 2 == 0
    got = {s.split_list(p)[0]: int(s.split_list(p)[2])
           for p in s.split_list(s.eval("all_fanout -from clk"))}
    assert set(got) == {"t1/A", "s2/A", "s3/A"}
    assert all(n % 2 == 0 for n in got.values()), got


def test_the_refs_are_what_the_user_says(sinks, write_lef):
    # a buffer whose name says nothing: all_fanout counts it a buffer
    s = sinks
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF.replace('INV_RP', 'DRV_RP'), 'd.lef')}}}")
    made = s.split_list(s.eval("create_buffer_tree -from clk -inverter_ref INV_RP "
                               "-buffer_ref DRV_RP -distance 50 -name ct"))
    out_of(s)
    refs = [s.db.inst_row(m)["ref_cell"] for m in made]
    assert "DRV_RP" in refs
    for p in s.split_list(s.eval("all_fanout -from clk -to s1/A")):
        end, buffers, inverters = s.split_list(p)
        assert int(buffers) == 1 and int(inverters) % 2 == 0
    assert s.db.cell_kinds() == {"INV_RP": "inverter", "DRV_RP": "buffer"}


def test_a_sink_on_the_port_net_that_needs_an_inverter(sinks):
    # s3, nearer the port than -distance, inverts on to t3: it gets an inverter of its own
    s = sinks
    s.eval("create_inst -name t3 -ref_cell INV_RP -location {-60 0}")
    s.eval("connect_pin -from s3/Y -to t3/A")
    out_of(s)
    s.eval(f"create_buffer_tree -from clk {TREE}")
    out_of(s)
    assert s.eval("get_db pin:s3/A .net.name") != "clk"
    assert s.eval("get_db net:clk .pins") == "pin:ct_1/A"       # one cell on the port
    for p in s.split_list(s.eval("all_fanout -from clk")):
        assert int(s.split_list(p)[2]) % 2 == 0, p


def test_the_tree_stays_inside_an_l_shaped_die(tech_session, write_lef):
    # the die: a band x 0 .. 100, y 0 .. 40 and a tower x 60 .. 100 up to y 200. The
    # port at the top of the tower, the sinks at the left of the band: the shortest
    # ways (along x first) would cross the empty corner
    from core import objects
    from core.placement import rect_in_polygon
    from test_connect_spine import L_DEF, ROWS, SITE_LEF
    s = tech_session
    pins = ("PINS 1 ;\n- ck + NET ck + DIRECTION INPUT\n"
            "  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 80000 190000 ) N ;\nEND PINS\n")
    s.eval(f"read_lef -file {{{write_lef(SITE_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(L_DEF % (ROWS + pins), 'd.def')}}}")
    for name, at in (("s1", "10 20"), ("s2", "20 30")):
        s.eval(f"create_inst -name {name} -ref_cell INV_RP -location {{{at}}}")
    s.eval("connect_pin -from ck -to {s1/A s2/A}")
    out_of(s)
    top = cbt.build_tree(objects.port_centre(s.db, "ck"), [
        (*objects.pin_centre(s.db, n, "A"), n) for n in ("s1", "s2")])
    from core.commands.route_net import Fence
    boundary = [float(v) for v in s.db.design_row()["boundary"].split()]
    assert not cbt._tree_inside(top, Fence(boundary))       # the plain tree leaves the die
    made = s.split_list(s.eval("create_buffer_tree -from ck -inverter_ref INV_RP "
                               "-distance 30 -name lt -topology shortest"))
    text = out_of(s)
    assert "the tree takes the shortest ways inside it" in text and "HT4-304" not in text
    assert made and all(rect_in_polygon(objects.inst_bbox(s.db, s.db.inst_row(n)), boundary)
                        for n in made)
    for sink in ("s1/A", "s2/A"):
        assert len(chain(s, sink)) % 2 == 0


def test_one_trunk_and_one_cell_on_the_port(tech_session, write_lef):
    # the port near the right edge of the tower (x 98), one sink down that edge and two
    # at the far end of the band: one trunk down the middle of the tower, not one
    # beside the edge as well; the port drives one cell
    from test_connect_spine import L_DEF, ROWS, SITE_LEF
    s = tech_session
    pins = ("PINS 1 ;\n- ck + NET ck + DIRECTION INPUT\n"
            "  + LAYER IA ( -100 -100 ) ( 100 100 ) + FIXED ( 98000 190000 ) N ;\nEND PINS\n")
    s.eval(f"read_lef -file {{{write_lef(SITE_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(L_DEF % (ROWS + pins), 'd.def')}}}")
    for name, at in (("s1", "10 20"), ("s2", "20 30"), ("s3", "94 60")):
        s.eval(f"create_inst -name {name} -ref_cell INV_RP -location {{{at}}}")
    s.eval("connect_pin -from ck -to {s1/A s2/A s3/A}")
    out_of(s)
    made = list(s.split_list(s.eval("create_buffer_tree -from ck -inverter_ref INV_RP "
                                    "-distance 20 -name lt")))
    out_of(s)
    assert s.eval("get_db net:ck .pins") == "pin:lt_1/A"
    # down the tower (y 70 .. 170) one cell every 20 um: none side by side
    ys = sorted(round(s.db.inst_row(n)["y"]) for n in made if 70 < s.db.inst_row(n)["y"] < 170)
    assert ys and len(ys) == len({round(y / 10) for y in ys})
    for sink in ("s1/A", "s2/A", "s3/A"):
        assert len(chain(s, sink)) % 2 == 0


def test_the_fishbone_is_the_least_way():
    # two sinks either side of the line from the port: the shortest-path tree takes
    # each its own way (40); the fishbone a trunk to x 10 and a rib up and down (30)
    sinks = [(10, 10, "a"), (10, -10, "b")]
    assert cbt.tree_length(cbt.build_tree((0, 0), sinks)) == 40
    top, lost = cbt.build_fishbone((0, 0), sinks)
    assert lost == [] and cbt.tree_length(top) == 30
    # a comb: the arms at y 0 .. 10 and y 40 .. 50 off a spine x 90 .. 100; the port at
    # the top of the spine, a sink at the far end of each arm: the trunk down the spine
    # (y 45 .. 5 at x 95), a rib along the middle of each arm
    comb = [0, 0, 100, 0, 100, 50, 0, 50, 0, 40, 90, 40, 90, 10, 0, 10]
    top, lost = cbt.build_fishbone((95, 49), [(1, 45, "a"), (1, 5, "b")], comb)
    assert lost == []
    assert cbt.tree_length(top) == pytest.approx(4 + 94 + 40 + 94)
