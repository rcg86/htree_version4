"""route_net -min_routing_distance / -max_routing_distance: the wire from the
driver to its nearest load is that long; a shorter route goes out and back
(a hairpin) on free tracks, with as few turns as can be."""

import pytest

pytest.importorskip("scipy")

from core.commands import route_net
from test_route_net import DEF, err, out_of, spine  # noqa: F401  (spine is a fixture)

NET = "sp_L1_inv1_Y"


def lengths(s, net=NET):
    """The route length of the report line, and the line."""
    text = out_of(s)
    line = next(l for l in text.splitlines()
                if ("route length" in l and "asked" in l) or "long enough" in l)
    return float(line.split("route length ")[1].split(" um")[0]), text


def test_the_shortest_way_and_a_hairpin(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    text = out_of(s)
    short = float(text.split(f"{NET}: ")[1].split("track length ")[1].split(" um")[0])
    want = round(short + 40, 2)
    s.eval(f"route_net -net {NET} -rule r -min_routing_distance {want} "
           f"-max_routing_distance {want + 10}")
    got, text = lengths(s)
    assert want <= got <= want + 10
    assert "and back, 2 turn(s)" in text                  # out, one track over, back
    line = next(l for l in text.splitlines() if "route length" in l and "asked" in l)
    assert f"(asked {want:g} .. {want + 10:g}): out " in line
    # the wires: one leg out, the jog, the leg back; no violation of the net
    wires = [r for r in s.db.net_wire_rows(NET) if r["kind"] == "wire"]
    assert len(wires) == 3
    s.eval("check_drc")
    drc = out_of(s)
    assert not [l for l in drc.splitlines() if NET in l and "{" in l]


def test_long_enough_already_and_too_long(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r -min_routing_distance 1")
    assert "the shortest way is long enough" in out_of(s)
    s.eval(f"route_net -net {NET} -rule r -min_routing_distance 1 -max_routing_distance 2")
    text = out_of(s)
    assert "HT4-300" in text and "longer than -max_routing_distance 2" in text


def test_no_room_says_so(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r -min_routing_distance 100000")
    text = out_of(s)
    assert "HT4-300" in text and "no way out and back on free tracks" in text
    assert s.db.net_wire_rows(NET)                         # the shortest way, routed


def test_options(spine):
    s = spine
    assert "goes with -min_routing_distance" in \
        err(s, f"route_net -net {NET} -rule r -max_routing_distance 10")
    assert "must be a distance in um above 0" in \
        err(s, f"route_net -net {NET} -rule r -min_routing_distance 0")
    assert "is less than -min_routing_distance" in \
        err(s, f"route_net -net {NET} -rule r -min_routing_distance 50 "
               f"-max_routing_distance 40")
    assert route_net.DEVIATION == 10.0                     # without -max_routing_distance
    s.eval(f"route_net -net {NET} -rule r -min_routing_distance 60")
    assert "60 .. 70 um (-min_routing_distance, -max_routing_distance)" in out_of(s)
