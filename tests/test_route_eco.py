"""route_net -eco: only the nets that are open or shorted, completed from the
routing they have (every shape kept, only what joins the pieces added); a
net's own wire in a short taken out first."""

import pytest

pytest.importorskip("scipy")

from test_route_net import spine  # noqa: F401  (a fixture)
from test_route_pin import err, out_of

NETS = "{sp_L1_inv1_Y sp_L2_inv1_Y}"


@pytest.fixture
def routed(spine):
    """sp_L1_inv1_Y: one IB wire x 1.26 .. 1.62, y 1.08 .. 8.42; sp_L2_inv1_Y:
    one IB wire x 4.14 .. 4.5, y 7.7 .. 29.42 (to sp_L3_inv1 and sp_L3_inv2)."""
    s = spine
    s.eval("route_pin -inst {sp_L3_inv1 sp_L3_inv2}")
    s.eval(f"route_net -net {NETS} -rule r")
    out_of(s)
    return s


def rows(s, net):
    return [(r["id"], r["kind"], r["layer"], r["rect"]) for r in s.db.net_wire_rows(net)]


def signal_opens_and_shorts(s):
    s.eval("check_drc")
    text = out_of(s)
    # the test spine's cells overlap, so do their straps: shorts of a route wire only
    shorts = [l for l in text.splitlines() if " and " in l and "overlap" in l
              and ("net_wire:sp_L1_inv1_Y/" in l or "net_wire:sp_L2_inv1_Y/" in l)]
    opens = [l for l in text.splitlines() if "no path to the driver" in l]
    return opens, shorts


def test_whole_nets_are_left_alone(routed):
    s = routed
    before = {n: rows(s, n) for n in ("sp_L1_inv1_Y", "sp_L2_inv1_Y")}
    assert s.eval(f"route_net -eco -net {NETS} -rule r") == ""
    text = out_of(s)
    assert "route_net: -eco: 2 net(s) checked (check_drc: signal opens and shorts): 0 open" in text
    assert "nothing to route" in text
    assert {n: rows(s, n) for n in before} == before


def test_an_open_net_is_completed_from_where_it_stops(routed):
    s = routed
    wire = s.db.net_wire_rows("sp_L2_inv1_Y")[0]
    s.db.set_wire_rect("net_wire", wire["id"], "4.14 7.7 4.5 20")   # cut short: L3_inv2 off
    kept = rows(s, "sp_L2_inv1_Y")
    opens, _ = signal_opens_and_shorts(s)
    assert opens
    assert s.eval(f"route_net -eco -net {NETS} -rule r") == "spine_net:sp/sp_L2_inv1_Y"
    text = out_of(s)
    assert "-eco: 2 net(s) checked (check_drc: signal opens and shorts): 1 open" in text
    assert "  sp_L2_inv1_Y: " in text and "shape(s) cut off" in text
    assert "-eco: " in text and "wire(s) kept: to" in text and "sp_L3_inv2" in text
    assert "-eco: the 1 net(s) are whole now, no short" in text     # those it routed
    # every shape it had is still there, as it was; only new ones are added
    now = rows(s, "sp_L2_inv1_Y")
    assert now[:len(kept)] == kept and len(now) > len(kept)
    assert signal_opens_and_shorts(s) == ([], [])
    # sp_L1_inv1_Y was whole: not touched
    assert "sp_L1_inv1_Y: " not in text


def test_a_short_is_taken_out_and_the_net_routed_again(routed):
    s = routed
    l2 = rows(s, "sp_L2_inv1_Y")
    # sp_L1_inv1_Y routed on sp_L2's track instead: its wire and crossing boxes there
    s.db.delete_wires([("net_wire", r["id"]) for r in s.db.net_wire_rows("sp_L1_inv1_Y")])
    s.db.add_net_wires([("sp_L1_inv1_Y", "wire", "IB", "4.14 1.08 4.5 8.42", None, None),
                        ("sp_L1_inv1_Y", "cross", "IB/IA", "4.14 1.08 4.5 1.8", None, None),
                        ("sp_L1_inv1_Y", "cross", "IB/IA", "4.14 7.7 4.5 8.42", None, None)])
    _, shorts = signal_opens_and_shorts(s)
    assert shorts
    s.eval(f"route_net -eco -net {NETS} -rule r")
    text = out_of(s)
    assert "1 open (1 of them after taking out 1 wire(s) of theirs in" in text
    assert "sp_L1_inv1_Y: " in text and "(a short of it taken out)" in text
    assert "-eco: the 1 net(s) are whole now, no short" in text     # those it routed
    assert signal_opens_and_shorts(s) == ([], [])
    assert rows(s, "sp_L2_inv1_Y") == l2                            # the other net as it was
    l1 = rows(s, "sp_L1_inv1_Y")
    assert all(not r[3].startswith("4.14 ") for r in l1)              # nothing left there
    # the wire taken out went with its crossing boxes: every box is on a wire now
    wires = [tuple(map(float, r[3].split())) for r in l1 if r[1] == "wire"]
    for r in l1:
        if r[1] == "cross":
            b = tuple(map(float, r[3].split()))
            assert any(w[0] <= b[0] + 1e-6 and b[2] <= w[2] + 1e-6 and w[1] <= b[1] + 1e-6
                       and b[3] <= w[3] + 1e-6 for w in wires), r



def test_without_net_every_net_and_errors(routed):
    s = routed
    wire = s.db.net_wire_rows("sp_L2_inv1_Y")[0]
    s.db.set_wire_rect("net_wire", wire["id"], "4.14 7.7 4.5 20")
    assert s.eval("route_net -eco -rule r") == "spine_net:sp/sp_L2_inv1_Y"
    assert "-eco: 4 net(s) checked (check_drc: signal opens and shorts): 1 open" in out_of(s)
    assert "-net and -rule are required" in err(s, "route_net -rule r")
    assert "not with -force" in err(s, "route_net -eco -rule r -force")
    assert "not with -force or -min_routing_distance" in err(
        s, "route_net -eco -rule r -min_routing_distance 10")


def test_fixed_nets_are_mended_and_stay_fixed(routed):
    # the whole design fixed, as a flow leaves it: -eco mends them all the same
    s = routed
    s.eval("set_db [get_db nets] .route_status fixed")
    wire = s.db.net_wire_rows("sp_L2_inv1_Y")[0]
    s.db.set_wire_rect("net_wire", wire["id"], "4.14 7.7 4.5 20")
    kept = rows(s, "sp_L2_inv1_Y")
    out_of(s)
    assert s.eval("route_net -net [get_db nets] -eco -rule r") == "spine_net:sp/sp_L2_inv1_Y"
    text = out_of(s)
    assert "HT4-286" not in text                                  # fixed: not skipped
    assert "stub(s) left to route_final_stub:" not in text        # no list of every stub
    assert "sp_L2_inv1_Y: " in text and "(fixed: it stays fixed)" in text
    assert "-eco: the 1 net(s) are whole now, no short" in text
    assert rows(s, "sp_L2_inv1_Y")[:len(kept)] == kept
    assert s.eval("get_db spine_net:sp/sp_L2_inv1_Y .route_status") == "fixed"
    assert signal_opens_and_shorts(s) == ([], [])




def test_an_open_net_with_no_driver_is_said(routed):
    # the spine's root net (sp_primary_input, nothing drives it) on one more input,
    # far away: open to check_drc; route_net cannot route it, -eco says why
    s = routed
    s.eval("create_inst -name d1 -ref_cell INV_RP -location {-60 0}")
    s.eval("route_pin -inst d1")
    with s.db.conn:
        s.db.conn.execute("INSERT INTO connection (inst, pin, net, driver) VALUES "
                          "('d1', 'A', 'sp_primary_input', NULL)")
    s.db.netlist = None                  # the netlist cache: read the table again
    out_of(s)
    assert s.eval("get_db net:sp_primary_input .driver") == ""
    s.eval("check_drc")
    assert "net sp_primary_input: no path to the rest of the net" in out_of(s)
    s.eval("route_net -eco -rule r")
    assert "(HT4-312): route_net: -eco: 1 open net(s) not routed, no driver (connect_pin " \
           "or connect_spine gives it one): sp_primary_input" in out_of(s)
