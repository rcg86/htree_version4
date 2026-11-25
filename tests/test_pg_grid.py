"""insert_pg_grid: wires of the power nets on a layer's power tracks, from
the design boundary to the boundary, short of it by -pull_back_distance,
broken clear of other nets' shapes."""

import pytest

pytest.importorskip("scipy")

from test_move_spine import build, err
from test_route_pin import out_of

# the test die is an L: x 0 .. 100 up to y 40, then x 60 .. 100 up to y 200;
# IA tracks at y 0.36 + 0.72 k, VDD on k % 8 == 0, VSS on k % 8 == 4


def rects(s, net=None):
    return [tuple(float(c) for c in r["rect"].split()) for r in s.db.net_wire_rows("pg_grid:IA")
            if net is None or r["shield_net"] == net]


@pytest.fixture
def grid(tech_session, write_lef):
    s = build(tech_session, write_lef, rows=False)
    s.eval("route_pin -inst [get_db insts .name]")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    out_of(s)
    return s


def test_every_power_track_boundary_to_boundary(grid):
    s = grid
    made = s.split_list(s.eval("insert_pg_grid -layer IA -pull_back_distance 1"))
    text = out_of(s)
    assert made and len(made) == len(rects(s))
    assert "insert_pg_grid: IA horizontal power tracks, 0.36 wide" in text
    # the first VDD track, y 0.36, is in the wide part: 1 um in from x 0 and x 100
    assert (1, 0.18, 99, 0.54) in rects(s, "VDD")
    # VSS at y 3.24 too; nothing on the signal and NA tracks
    assert (1, 3.06, 99, 3.42) in rects(s, "VSS")
    assert {r[1] for r in rects(s)} <= {round(0.18 + 0.72 * k, 6) for k in range(0, 278, 4)}
    # in the narrow part, x 60 .. 100: from 61 to 99 where nothing is in the way
    high = [r for r in rects(s) if r[1] > 150]
    assert high and all(r[0] >= 61 - 1e-6 and r[2] <= 99 + 1e-6 for r in high)
    assert (61, 190.26, 99, 190.62) in rects(s, "VDD")                 # k = 264


def test_broken_clear_of_the_spine_cells(grid):
    s = grid
    s.eval("check_drc")
    shorts = [l for l in out_of(s).splitlines() if l.startswith("  short")]
    s.eval("insert_pg_grid -layer IA")
    text = out_of(s)
    assert "left out where shapes of other nets are on IA" in text
    # a track over the cells' straps is cut, at least the spacing from them
    straps = [tuple(float(c) for c in r["rect"].split()) for r in s.db.strap_rows()
              if r["layer"] == "IA" and r["net"] not in ("VDD", "VSS")]
    for g in rects(s):
        for st in straps:
            dy = max(st[1] - g[3], g[1] - st[3], 0)
            dx = max(st[0] - g[2], g[0] - st[2], 0)
            assert max(dx, dy) >= 0.36 - 1e-6, (g, st)
    s.eval("check_drc")
    drc = out_of(s)
    # the test spine's own strap overlaps stay; no grid wire is in a short or too near
    assert [l for l in drc.splitlines() if l.startswith("  short")] == shorts
    assert "  spacing   tech    -       0" in drc
    assert not [l for l in drc.splitlines()
                if "pg_grid" in l and ("overlap" in l or "apart" in l)]


def test_again_replaces_and_pull_back(grid):
    s = grid
    s.eval("insert_pg_grid -layer IA")
    n = len(rects(s))
    s.eval("insert_pg_grid -layer IA -pull_back_distance 0")
    assert "(replacing" in out_of(s) and len(rects(s)) == n
    assert (0, 0.18, 100, 0.54) in rects(s, "VDD")
    # write_def writes them under their power net
    assert s.eval("get_db [lindex [get_db net_wires pg_grid:IA/*] 0] .kind") == "pg_grid"


def test_errors(grid):
    s = grid
    assert "-layer is required" in err(s, "insert_pg_grid")
    assert "HT4-309" in err(s, "insert_pg_grid -layer H2")              # no track assignment
    assert "not in tech" in err(s, "insert_pg_grid -layer NOPE")
    assert "-pull_back_distance must be" in err(s, "insert_pg_grid -layer IA "
                                                   "-pull_back_distance -1")
    assert rects(s) == []


def test_write_def_writes_them_under_their_power_net(grid, tmp_path):
    s = grid
    s.eval("insert_pg_grid -layer IA")
    out_of(s)
    path = tmp_path / "g.def"
    s.eval(f"write_def -output {path}")
    text = path.read_text()
    special = text[text.index("SPECIALNETS"):text.index("END SPECIALNETS")]
    nets = {}                            # each special net's statement
    for part in special.split("\n- ")[1:]:
        name = part.split()[0]
        nets[name] = part[:part.index(";")]
    assert "+ RECT IA ( 1000 180 ) ( 99000 540 )" in nets["VDD"]     # the first VDD track
    assert "+ RECT IA ( 1000 3060 ) ( 99000 3420 )" in nets["VSS"]
