import io
import tkinter

import pytest

pytest.importorskip("scipy")

from core.commands.route_net import H, V, Layer, _blocked, _lee, _obstacles
from core.htree_builder import Session
from test_route_pin import CELL_LEF

# IA (horizontal) and IB (vertical) tracks every 0.72 from -49.68.
DEF = """VERSION 5.8 ;
DESIGN t ;
UNITS DISTANCE MICRONS 1000 ;
DIEAREA ( -100000 -100000 ) ( 100000 100000 ) ;
TRACKS Y -49680 DO 140 STEP 720 LAYER IA ;
TRACKS X -49680 DO 140 STEP 720 LAYER IB ;
END DESIGN
"""

# L1 drives L2, which drives two leaves with a stub each.
SPEC = """spine_spec:
  name: sp
  root_net: net
  constraints:
    max_drive_length: 40
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
"""


def err(session, script):
    with pytest.raises(tkinter.TclError) as exc:
        session.eval(script)
    return str(exc.value)


def out_of(s):
    text = s.out.getvalue()
    s.out.seek(0)
    s.out.truncate()
    return text


@pytest.fixture
def spine(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("route_pin -inst sp_L1_inv1")
    s.eval("route_pin -inst sp_L2_inv1")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    return s


def rects(s, net, kind, layer=None):
    found = []
    for h in s.split_list(s.eval(f"get_db spine_net:sp/{net} .net_wires")):
        if s.eval(f"get_db {h} .kind") == kind and layer in (None, s.eval(f"get_db {h} .layer")):
            found.append(tuple(float(v) for v in s.eval(f"get_db {h} .rect").split()))
    return found


def on_track(c):
    return abs((c + 49.68) / 0.72 - round((c + 49.68) / 0.72)) < 1e-6


def test_connects_both_straps(spine):
    assert spine.eval("route_net -net sp_L1_inv1_Y -rule r") == "spine_net:sp/sp_L1_inv1_Y"
    text = out_of(spine)
    assert "HT4-172" not in text
    assert "driver sp_L1_inv1/Y (strap 3): connected across the strap" in text   # route_pin:
    assert "load sp_L2_inv1/A (strap 5): connected across the strap" in text     # Y 3, A 5
    assert spine.eval("get_db spine_net:sp/sp_L1_inv1_Y .route_rule") == "route_rule:r"
    for x1, y1, x2, y2 in rects(spine, "sp_L1_inv1_Y", "wire", "IA"):
        assert y2 - y1 == pytest.approx(0.36) and on_track((y1 + y2) / 2)
    for x1, y1, x2, y2 in rects(spine, "sp_L1_inv1_Y", "wire", "IB"):
        assert x2 - x1 == pytest.approx(0.36) and on_track((x1 + x2) / 2)
    # a layer change: the two wires overlap in a full IB width x IA width box
    vias = rects(spine, "sp_L1_inv1_Y", "cross", "IA/IB")
    for x1, y1, x2, y2 in vias:
        assert (x2 - x1, y2 - y1) == (pytest.approx(0.36), pytest.approx(0.36))
        assert any(a[0] <= x1 + 1e-6 and x2 <= a[2] + 1e-6 and a[1] <= y1 + 1e-6
                   and y2 <= a[3] + 1e-6 for a in rects(spine, "sp_L1_inv1_Y", "wire", "IA"))
        assert any(a[0] <= x1 + 1e-6 and x2 <= a[2] + 1e-6 and a[1] <= y1 + 1e-6
                   and y2 <= a[3] + 1e-6 for a in rects(spine, "sp_L1_inv1_Y", "wire", "IB"))
    # at each strap: an IB wire across the whole strap (0.72 tall)
    straps = rects(spine, "sp_L1_inv1_Y", "cross", "IB/IA")
    assert len(straps) == 2
    for x1, y1, x2, y2 in straps:
        assert (x2 - x1, y2 - y1) == (pytest.approx(0.36), pytest.approx(0.72))


def test_pin_routes_extended_first_then_routed(spine, write_lef):
    # step a: every connected signal strap reaches the nearest signal track
    # beyond each cell edge, before routing; step b: the route lands on one
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    text = out_of(spine)
    assert "pin routes extended to the signal tracks (IB): sp_L1_inv1/Y strap 3: " in text
    assert "0 layer change(s)" in text
    assert "(its pin route, extended " in text
    exts = rects(spine, "sp_L1_inv1_Y", "extension", "IA")
    assert len(exts) == 4                       # 2 pins x left and right
    for inst, seq in (("sp_L1_inv1", 3), ("sp_L2_inv1", 5)):
        sx1, sy1, sx2, sy2 = (float(v) for v in
                              spine.eval(f"get_db strap:{inst}/{seq} .rect").split())
        left = [e for e in exts if e[2] == sx1 and e[1] == sy1]
        right = [e for e in exts if e[0] == sx2 and e[1] == sy1]
        assert len(left) == len(right) == 1
        for e, end in ((left[0], left[0][0] + 0.18), (right[0], right[0][2] - 0.18)):
            assert 0 < e[2] - e[0] <= 3 + 1e-6 and e[3] - e[1] == pytest.approx(0.72)
            assert on_track(end)                # it ends covering a signal track's wire
        # the nearest track whose wire is not already on the strap: its wire
        # starts past the edge, and the next one in would be under the strap
        assert left[0][0] < sx1 and left[0][0] + 0.72 >= sx1 - 1e-6
        assert right[0][2] > sx2 and right[0][2] - 0.72 <= sx2 + 1e-6
    (ib,) = rects(spine, "sp_L1_inv1_Y", "wire", "IB")
    assert on_track((ib[0] + ib[2]) / 2)
    # max_strap_extension 0: the straps stay the cell width; the route crosses
    # them over the cells and jogs between
    spec = write_lef("pin_routing:\n  max_strap_extension: 0\n", "noext.yaml")
    for inst in ("sp_L1_inv1", "sp_L2_inv1"):
        spine.eval(f"route_pin -inst {inst} -spec {spec}")
    out_of(spine)
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    text = out_of(spine)
    assert "2 layer change(s)" in text and "over 0" in text
    assert rects(spine, "sp_L1_inv1_Y", "extension") == []


def test_not_pinned_ends_near_the_pin(spine):
    spine.eval("route_net -net sp_L2_inv1_Y -rule r")
    text = out_of(spine)
    for inst in ("sp_L3_inv1", "sp_L3_inv2"):
        assert f"route_pin is not done on {inst} (pin A); the route ends at the track " \
               f"crossing nearest the pin, not connected" in text
        assert f"load {inst}/A: ends near the pin, not connected" in text
    assert "driver sp_L2_inv1/Y (strap 3): connected" in text


def test_leaf_net_ends_at_the_stub(spine):
    spine.eval("route_net -net sp_L3_inv1_Y -rule r")
    text = out_of(spine)
    assert "route_pin is not done on sp_L3_inv1 (pin Y)" in text
    assert "load stub stub1 (tap): ends at the stub (the stub is not routed)" in text


def test_patterns_handles_rerun_and_write_db(spine, tmp_path):
    done = spine.split_list(spine.eval("route_net -net {sp_L1* spine_net:sp/sp_L2_inv1_Y} "
                                       "-rule r"))
    assert list(done) == ["spine_net:sp/sp_L1_inv1_Y", "spine_net:sp/sp_L2_inv1_Y"]
    count = len(spine.split_list(spine.eval("get_db net_wires")))
    out_of(spine)
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert "HT4-173" in out_of(spine)                           # replaced, not added
    assert len(spine.split_list(spine.eval("get_db net_wires"))) == count
    h = spine.split_list(spine.eval("get_db spine_net:sp/sp_L1_inv1_Y .net_wires"))[0]
    assert spine.eval(f"get_db {h} .net") == "spine_net:sp/sp_L1_inv1_Y"
    spine.eval(f"write_db -file {tmp_path}/n.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {tmp_path}/n.db")
    assert len(fresh.split_list(fresh.eval("get_db net_wires"))) == count


def test_errors(spine):
    assert "HT4-001" in err(spine, "route_net -net sp_L1_inv1_Y")
    assert "HT4-001" in err(spine, "route_net -net sp_L1_inv1_Y -rule r -via_weight -1")
    assert "HT4-170" in err(spine, "route_net -net nosuch -rule r")
    assert "HT4-171" in err(spine, "route_net -net sp_L1_inv1_Y -rule default")
    assert "HT4-171" in err(spine, "route_net -net sp_L1_inv1_Y -rule nosuch")
    spine.eval("create_route_rule -name only_ia -layer IA -width 0.36 -spacing 0.36")
    assert "HT4-171" in err(spine, "route_net -net sp_L1_inv1_Y -rule only_ia")
    spine.eval("create_route_rule -name h2 -layer IA -width 0.36 -spacing 0.36")
    spine.eval("create_route_rule -name h2 -layer H2 -width 0.064 -spacing 0.064 -append")
    assert "HT4-175" in err(spine, "route_net -net sp_L1_inv1_Y -rule h2")   # no H2 tracks
    assert spine.eval("get_db net_wires") == ""


def test_via_weight_trades_wire_for_layer_changes():
    xs = [0.72 * k for k in range(30)]
    ys = [0.72 * k for k in range(5)]
    # from (H, 0, 0): target 1 is 20 tracks along the same row (no layer
    # change), target 2 is one track over and one up (two layer changes)
    targets = {1: {(H, 20, 0)}, 2: {(H, 1, 1)}}
    assert _lee({(H, 0, 0)}, targets, xs, ys, set(), 0.0)[0] == 2
    assert _lee({(H, 0, 0)}, targets, xs, ys, set(), 10.0)[0] == 1
    k, path, cost = _lee({(H, 0, 0)}, {2: {(H, 1, 1)}}, xs, ys, set(), 1.0)
    assert cost == pytest.approx(0.72 + 0.72 + 2 * 1.0)
    assert sum(1 for a, b in zip(path, path[1:]) if a[0] != b[0]) == 2
    assert _lee({(H, 0, 0)}, {2: {(H, 1, 1)}}, xs, ys, {(V, 1, 0), (V, 0, 0)}, 1.0) is not None
    blocked_all = {(V, i, 0) for i in range(30)}
    assert _lee({(H, 0, 0)}, {2: {(H, 1, 1)}}, xs, ys, blocked_all, 1.0) is None


def test_straps_block_only_their_layer(spine):
    xs = [0.72 * k - 49.68 for k in range(140)]
    ys = xs
    h, v = Layer("IA", 0.36, 0.36), Layer("IB", 0.36, 0.36)
    blocked = _blocked(_obstacles(spine.db, "x"), xs, ys, h, v)
    assert blocked and all(layer == H for layer, _, _ in blocked)   # straps are IA
    # strap 1 of sp_L1_inv1 (y 3.229 .. 3.949 here): the IA track at y 3.6 is blocked
    j = min(range(len(ys)), key=lambda k: abs(ys[k] - 3.6))
    i = min(range(len(xs)), key=lambda k: abs(xs[k]))
    assert (H, i, j) in blocked and (V, i, j) not in blocked


def test_drawn_in_gui(spine):
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    from core.gui.layout_data import load_layout
    lay = load_layout(spine.db)
    wires = [w for w in lay.net_wires if not w.outline]
    crosses = [w for w in lay.net_wires if w.outline]
    assert wires and crosses
    assert {w.layer for w in wires} == {"IA", "IB"}
    assert all(w.handle.startswith("net_wire:sp_L1_inv1_Y/") for w in lay.net_wires)


def test_collections_and_patterns(spine):
    names = spine.eval("get_db insts .name")
    spine.eval(f"route_pin -inst [get_db insts .name]")
    assert "route_pin: 4 instances routed" in out_of(spine)
    for name in spine.split_list(names):
        assert len(spine.split_list(spine.eval(f"get_db inst:{name} .straps"))) == 7
    spine.eval("route_pin -inst *sp_L3*")                         # a pattern
    spine.eval("route_pin -inst [get_db insts]")                  # handles
    assert "HT4-160" in err(spine, "route_pin -inst {sp_L1_inv1 nosuch}")
    done = spine.split_list(spine.eval("route_net -net [get_db nets .name] -rule r"))
    assert len(done) == len(spine.split_list(spine.eval("get_db spine:sp .spine_nets")))
    assert "route_net: 2 stub(s) left to route_final_stub: sp/stub1 sp/stub2" in \
        spine.out.getvalue()
    assert "HT4-172" not in out_of(spine)                         # every pin has its straps
    assert len(spine.split_list(spine.eval("route_net -net *sp_L3* -rule r"))) == 2


def test_beyond_the_tracks_warns(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    # IA tracks end at y 50.4; L2 and the leaves (taps 56.5 and 77.5) are above
    s.eval("create_spine -name sp -spec_name sp -location {0 47} -build -ref_cell INV_RP")
    s.eval("route_pin -inst *sp_*")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    s.eval("route_net -net sp_L2_inv1_Y -rule r")
    text = out_of(s)
    assert "HT4-176" in text and "is beyond the signal tracks (IA y -49.68 .. 50.4)" in text


def test_connected_straps_take_the_net_name(spine):
    assert spine.eval("get_db strap:sp_L1_inv1/3 .net") == "SIGNAL"
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert "now net sp_L1_inv1_Y: strap:sp_L1_inv1/3 pin_wire:sp_L1_inv1/Y" in out_of(spine)
    for h in ("strap:sp_L1_inv1/3", "pin_wire:sp_L1_inv1/Y", "strap:sp_L2_inv1/5",
              "pin_wire:sp_L2_inv1/A"):
        assert spine.eval(f"get_db {h} .net") == "sp_L1_inv1_Y"
    assert spine.eval("get_db strap:sp_L1_inv1/5 .net") == "SIGNAL"    # not this net's
    assert spine.eval("get_db strap:sp_L1_inv1/1 .net") == "VSS"
    spine.eval("route_pin -inst sp_L1_inv1")                         # straps rebuilt
    assert spine.eval("get_db strap:sp_L1_inv1/3 .net") == "SIGNAL"


def test_write_def(spine, tmp_path):
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    path = tmp_path / "o.def"
    assert spine.eval(f"write_def -output {path}") == str(path)
    text = path.read_text()
    assert text.startswith("VERSION 5.8 ;") and text.rstrip().endswith("END DESIGN")
    assert "UNITS DISTANCE MICRONS 1000 ;" in text and "DIEAREA ( -100000 -100000 )" in text
    assert "COMPONENTS 4 ;" in text
    assert "  - sp_L1_inv1 INV_RP + PLACED ( -1560 -889 ) N ;" in text
    special = text.split("SPECIALNETS")[1]
    assert "- VSS ( sp_L1_inv1 VSS ) ( sp_L2_inv1 VSS )" in special
    assert "+ SHAPE STRIPE" in special and "sp_L1_inv1_Y" not in special
    nets = text.split("\nNETS ")[1]
    block = nets.split("- sp_L1_inv1_Y ")[1].split("\n  ;")[0]
    assert block.startswith("( sp_L1_inv1 Y ) ( sp_L2_inv1 A ) + USE CLOCK")
    wires = [r for r in spine.db.net_wire_rows("sp_L1_inv1_Y") if r["kind"] != "cross"]
    assert block.count(" RECT ") == len(wires) + 4                 # + 2 straps, 2 pin wires
    x1, y1, x2, y2 = (round(float(v) * 1000) for v in wires[0]["rect"].split())
    assert f"{wires[0]['layer']} ( {x1} {y1} ) RECT ( 0 0 {x2 - x1} {y2 - y1} )" in block
    out_of(spine)
    assert "HT4-180" in err(spine, f"write_def -output {path}")
    spine.eval(f"write_def -output {path} -overwrite -sections components")
    assert "NETS" not in path.read_text() and "COMPONENTS 4 ;" in path.read_text()
    assert "HT4-001" in err(spine, f"write_def -output {path} -sections pins")
    assert "HT4-001" in err(spine, "write_def")


def test_write_logical(spine, tmp_path):
    path = tmp_path / "l.tcl"
    spine.eval(f"write_logical -output {path}")
    text = path.read_text()
    assert "create_net -name sp_L1_inv1_Y" in text
    assert "# spine sp: root net net must exist in the design" in text
    l1 = text.split("# sp_L1_inv1 ")[1].split("\n\n")[0]
    assert "create_inst -cell INV_RP -name sp_L1_inv1" in l1
    assert "place_inst sp_L1_inv1 -1.56 -0.889 R0" in l1
    assert "connect sp_L1_inv1/A -net net" in l1
    assert "connect sp_L1_inv1/Y -net sp_L1_inv1_Y" in l1
    assert "connect sp_L2_inv1/A -net sp_L1_inv1_Y" in text
    assert "connect sp_L3_inv1/Y -net sp_L3_inv1_Y" in text           # the stub's net
    assert text.index("Step 2") < text.index("sp_L2_inv1 ") < text.index("sp_L3_inv1 ")
    assert "HT4-185" in err(spine, f"write_logical -output {path}")
    assert "HT4-001" in err(spine, "write_logical")


def test_place_status_fixed(spine, tmp_path):
    assert spine.eval("get_db inst:sp_L1_inv1 .place_status") == "placed"
    handles = spine.eval("set_db [get_db insts] .place_status fixed")
    assert len(spine.split_list(handles)) == 4
    assert spine.eval("get_db insts .place_status") == "fixed fixed fixed fixed"
    spine.eval(f"write_def -output {tmp_path}/f.def")
    comps = (tmp_path / "f.def").read_text().split("COMPONENTS")[1]
    assert comps.count("+ FIXED (") == 4 and "+ PLACED" not in comps
    spine.eval(f"write_logical -output {tmp_path}/f.tcl")
    assert "set_db inst:sp_L1_inv1 .place_status fixed" in (tmp_path / "f.tcl").read_text()
    spine.eval("set_db inst:sp_L2_inv1 .place_status PLACED")
    assert spine.eval("get_db inst:sp_L2_inv1 .place_status") == "placed"
    assert "HT4-141" in err(spine, "set_db inst:sp_L1_inv1 .place_status locked")
    spine.eval(f"write_db -file {tmp_path}/f.db")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {tmp_path}/f.db")
    assert fresh.eval("get_db inst:sp_L1_inv1 .place_status") == "fixed"


def shields(s, net, power=None):
    found = []
    for h in s.split_list(s.eval(f"get_db spine_net:sp/{net} .net_wires")):
        if s.eval(f"get_db {h} .kind") == "shield" and \
                power in (None, s.eval(f"get_db {h} .shield_net")):
            found.append((s.eval(f"get_db {h} .layer"),
                          tuple(float(v) for v in s.eval(f"get_db {h} .rect").split())))
    return found


def test_shield_beside_every_wire(spine, tmp_path):
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield")
    text = out_of(spine)
    assert "shields on IB: one each side, VDD_SOC left of / above and VSS right of / below " \
           "the signal (no track assignment)" in text
    (ib,) = rects(spine, "sp_L1_inv1_Y", "wire", "IB")
    centre = (ib[0] + ib[2]) / 2
    found = {}
    for net in ("VSS", "VDD_SOC"):
        for layer, r in shields(spine, "sp_L1_inv1_Y", net):
            assert layer == "IB" and r[2] - r[0] == pytest.approx(0.36)
            assert r[1] <= ib[1] + 1e-6 and r[3] >= ib[3] - 1e-6   # at least the span
            assert on_track((r[0] + r[2]) / 2)
            found[round((r[0] + r[2]) / 2 - centre, 6)] = net
    # one each side, on the next track (0.72: the 0.36 spacing kept)
    assert found == {-0.72: "VDD_SOC", 0.72: "VSS"}
    path = tmp_path / "s.def"
    spine.eval(f"write_def -output {path}")
    text = path.read_text()
    special = text.split("SPECIALNETS")[1].split("END SPECIALNETS")[0]
    assert special.count("+ SHIELD sp_L1_inv1_Y IB 360 ") == 2
    assert "( sp_L2_inv1 A ) + SHIELDNET VDD_SOC + SHIELDNET VSS + USE CLOCK" in text
    # routed again without -shield: the shields go
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert shields(spine, "sp_L1_inv1_Y") == []


def test_shield_cut_at_a_jog_and_custom_nets(spine, write_lef):
    spec = write_lef("pin_routing:\n  max_strap_extension: 0\n", "noext.yaml")
    for inst in ("sp_L1_inv1", "sp_L2_inv1"):
        spine.eval(f"route_pin -inst {inst} -spec {spec}")
    out_of(spine)
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield_nets {VDDX GND}")
    text = out_of(spine)
    assert "2 layer change(s)" in text and "shields cut over" in text
    assert shields(spine, "sp_L1_inv1_Y", "VDD_SOC") == []
    assert shields(spine, "sp_L1_inv1_Y", "VDDX") and shields(spine, "sp_L1_inv1_Y", "GND")
    assert "VDDX left of / above and GND right of / below" in text
    own = rects(spine, "sp_L1_inv1_Y", "wire") + rects(spine, "sp_L1_inv1_Y", "extension")
    every = shields(spine, "sp_L1_inv1_Y")
    gap = lambda a, b: max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
    for layer, r in every:                       # spacing to the net's own wires
        for o in rects(spine, "sp_L1_inv1_Y", "wire", layer):
            assert gap(r, o) >= 0.36 - 1e-6
    for i, (la, a) in enumerate(every):          # and VDDX to GND on the same layer
        for lb, b in every[i + 1:]:
            if la == lb:
                assert gap(a, b) >= 0.36 - 1e-6 or a == b
    assert "HT4-001" in err(spine, "route_net -net sp_L1_inv1_Y -rule r -shield_nets {A B C}")


def test_power_straps_reach_the_shields(spine, tmp_path):
    spine.eval("route_pin -inst *sp_*")
    out_of(spine)
    spine.eval("route_net -net [get_db nets .name] -rule r -shield")
    text = out_of(spine)
    assert "power straps to shields:" in text
    assert "power pins connected to shields:" in text
    exts = [r for r in spine.db.net_wire_rows() if r["kind"] == "shield_ext"]
    assert exts and {r["shield_net"] for r in exts} <= {"VDD_SOC", "VSS"}
    for r in exts:                 # on the strap layer, the strap's height, within reach
        x1, y1, x2, y2 = (float(v) for v in r["rect"].split())
        assert r["layer"] == "IA" and y2 - y1 == pytest.approx(0.72) and x2 - x1 <= 3 + 1e-6
        strap = [s for s in spine.db.strap_rows() if s["net"] == r["shield_net"]
                 and tuple(float(v) for v in s["rect"].split())[1::2] == (y1, y2)
                 and (float(s["rect"].split()[2]) == x1 or float(s["rect"].split()[0]) == x2)]
        assert strap, r["rect"]    # it continues a strap of its own net
        shield = [w for w in spine.db.net_wire_rows() if w["kind"] == "shield"
                  and w["shield_net"] == r["shield_net"] and w["layer"] == "IB"]
        # it reaches the far edge of a shield of its net
        assert any(abs(float(w["rect"].split()[2]) - x2) < 1e-6 or
                   abs(float(w["rect"].split()[0]) - x1) < 1e-6 for w in shield)
    from core.commands.route_net import power_pins
    pins = power_pins(spine.db, spine.db.inst_names(), {"VDD_SOC", "VSS"})
    assert len(pins) == 8 and any(ok for *_, ok in pins)
    path = tmp_path / "p.def"
    spine.eval(f"write_def -output {path}")
    special = path.read_text().split("SPECIALNETS")[1].split("END SPECIALNETS")[0]
    x1, y1, x2, y2 = (round(float(v) * 1000) for v in exts[0]["rect"].split())
    assert f"IA {y2 - y1} + SHAPE STRIPE ( {x1} {(y1 + y2) // 2} ) ( {x2} {(y1 + y2) // 2} )" \
        in special


def test_shields_follow_the_track_assignment(spine):
    # IB tracks from -49.68: VDD_SOC, signal, VSS, signal, ... The signal is on
    # a '-' track; the tracks beside it are VDD_SOC and VSS, in either order.
    spine.eval("assign_track_for_route -net {VDD_SOC - VSS -} -layer IB")
    spine.eval("route_pin -inst *sp_*")
    out_of(spine)
    spine.eval("route_net -net {sp_L1_inv1_Y sp_L2_inv1_Y} -rule r -shield")
    text = out_of(spine)
    assert "shields on IB: one each side, the net of its track (assign_track_for_route " \
           "VDD_SOC - VSS -)" in text
    pattern = ["VDD_SOC", "-", "VSS", "-"]
    track = lambda x: pattern[round((x + 49.68) / 0.72) % 4]
    for net in ("sp_L1_inv1_Y", "sp_L2_inv1_Y"):
        ibs = rects(spine, net, "wire", "IB")
        centres = [(w[0] + w[2]) / 2 for w in ibs]
        assert ibs and all(track(c) == "-" for c in centres)          # signal tracks
        found = [(l, r) for l, r in shields(spine, net) if l == "IB"]
        assert found
        for net_name in ("VDD_SOC", "VSS"):
            for layer, r in shields(spine, net, net_name):
                if layer != "IB":
                    continue
                centre = (r[0] + r[2]) / 2
                assert track(centre) == net_name                    # its track's net
                assert any(abs(abs(centre - c) - 0.72) < 1e-6 for c in centres)  # beside
        for c in centres:                # at most one shield track each side of a wire
            sides = {round((r[0] + r[2]) / 2 - c, 6) for _, r in found
                     if abs(abs((r[0] + r[2]) / 2 - c) - 0.72) < 1e-6}
            assert sides <= {-0.72, 0.72}
    # every power strap of both cells joins the one shield of its net
    from core.commands.route_net import _joined_straps
    joined = _joined_straps(spine.db, "none")
    for inst in ("sp_L1_inv1", "sp_L2_inv1"):
        for s in spine.db.strap_rows(inst):
            if s["net"] in ("VDD_SOC", "VSS"):
                assert (inst, s["seq"]) in joined
    assert "power pins connected to shields: 4 of 4" in text or \
        "power pins connected to shields: 8 of 8" in text


def test_route_final_stub(spine, tmp_path):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r")
    out_of(spine)
    done = spine.split_list(spine.eval("route_final_stub -rule r"))
    assert list(done) == ["stub:sp/stub1", "stub:sp/stub2"]
    text = out_of(spine)
    assert "route_final_stub: 2 of 2 stubs routed" in text and "HT4-192" not in text
    for stub, net in (("stub1", "sp_L3_inv1_Y"), ("stub2", "sp_L3_inv2_Y")):
        (w,) = [r for r in spine.db.net_wire_rows(net) if r["kind"] == "stub"]
        x1, y1, x2, y2 = (float(v) for v in w["rect"].split())
        px1, py1, px2, py2 = (float(v) for v in spine.eval(
            f"get_db stub:sp/{stub} .points").split())
        assert w["layer"] == "IB" and x2 - x1 == pytest.approx(0.36)      # vertical stub
        assert (y1, y2) == (pytest.approx(py1), pytest.approx(py2))       # its full length
        assert on_track((x1 + x2) / 2) and abs((x1 + x2) / 2 - px1) <= 0.36 + 1e-6
        assert any(r["kind"] == "stub_cross" for r in spine.db.net_wire_rows(net))
    # route_net again keeps the stub; route_final_stub again replaces only it
    count = len(spine.db.net_wire_rows("sp_L3_inv1_Y"))
    spine.eval("route_net -net sp_L3_inv1_Y -rule r")
    assert any(r["kind"] == "stub" for r in spine.db.net_wire_rows("sp_L3_inv1_Y"))
    spine.eval("route_final_stub -rule r -stub stub1")
    assert len(spine.db.net_wire_rows("sp_L3_inv1_Y")) == count
    assert len([r for r in spine.db.net_wire_rows("sp_L3_inv1_Y") if r["kind"] == "stub"]) == 1
    path = tmp_path / "s.def"
    spine.eval(f"write_def -output {path}")
    block = path.read_text().split("- sp_L3_inv1_Y ")[1].split("\n  ;")[0]
    x1, y1, x2, y2 = (round(float(v) * 1000) for v in [r for r in spine.db.net_wire_rows(
        "sp_L3_inv1_Y") if r["kind"] == "stub"][0]["rect"].split())
    assert f"IB ( {x1} {y1} ) RECT ( 0 0 {x2 - x1} {y2 - y1} )" in block
    assert "HT4-190" in err(spine, "route_final_stub -rule r -stub nosuch")
    assert "HT4-001" in err(spine, "route_final_stub")


def test_route_final_stub_without_the_leaf_route(spine):
    spine.eval("route_final_stub -rule r -stub stub:sp/stub2")
    text = out_of(spine)
    assert "HT4-192" in text and "route_net -net sp_L3_inv2_Y first" in text


def test_stubs_are_their_own_class_and_nets(spine):
    assert spine.eval("get_db stubs") == "stub:sp/stub1 stub:sp/stub2"
    assert spine.eval("get_db stubs .name") == "stub1 stub2"
    assert spine.eval("get_db stubs .obj_type") == "stub stub"
    nets = spine.split_list(spine.eval("get_db nets"))
    assert "stub:sp/stub1" in nets and "spine_net:sp/sp_L1_inv1_Y" in nets
    assert spine.eval("get_db stub:sp/stub1 .orientation") == "vertical"
    assert spine.eval("get_db stub:sp/stub1 .net") == "spine_net:sp/sp_L3_inv1_Y"
    assert spine.eval("get_db stub:sp/stub1 .route_rule") == "route_rule:default"
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r")
    out_of(spine)
    done = spine.split_list(spine.eval("route_final_stub -rule r -stub [get_db stubs .name]"))
    assert list(done) == ["stub:sp/stub1", "stub:sp/stub2"]
    wires = spine.split_list(spine.eval("get_db stub:sp/stub1 .net_wires"))
    assert wires and {spine.eval(f"get_db {w} .kind") for w in wires} <= {"stub", "stub_cross"}
    assert spine.eval("route_final_stub -rule r -stub [get_db stubs]") == \
        "stub:sp/stub1 stub:sp/stub2"                             # handles work too


def test_stub_direction_follows_the_spine(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC.replace('vertical', 'horizontal'), 'h.yaml')}}}")
    s.eval("create_spine -name hs -spec_name sp -location {-20 0} -build -ref_cell INV_RP")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    assert s.eval("get_db stub:hs/stub1 .orientation") == "horizontal"
    s.eval("route_final_stub -rule r")
    for r in s.db.net_wire_rows():
        if r["kind"] == "stub":
            x1, y1, x2, y2 = (float(v) for v in r["rect"].split())
            assert r["layer"] == "IA" and y2 - y1 == pytest.approx(0.36) and x2 - x1 > 10


def test_delete_route(spine, tmp_path):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r -shield")
    spine.eval("route_final_stub -rule r")
    out_of(spine)
    kinds = lambda net: {r["kind"] for r in spine.db.net_wire_rows(net)}
    assert "stub" in kinds("sp_L3_inv1_Y") and "wire" in kinds("sp_L3_inv1_Y")
    # the stubs: only their wires go; the leaf nets keep their routes
    assert spine.eval("delete_route -nets [get_db stubs]") == "stub:sp/stub1 stub:sp/stub2"
    assert not {k for k in kinds("sp_L3_inv1_Y") if k.startswith("stub")}
    assert "wire" in kinds("sp_L3_inv1_Y")
    assert spine.eval("get_db stub:sp/stub1 .net_wires") == ""
    assert spine.eval("get_db stubs") == "stub:sp/stub1 stub:sp/stub2"        # still there
    # a spine net: its route_net wires go, its straps go back to SIGNAL
    assert spine.eval("get_db strap:sp_L1_inv1/3 .net") == "sp_L1_inv1_Y"
    assert spine.eval("delete_route -nets spine_net:sp/sp_L1_inv1_Y") == \
        "spine_net:sp/sp_L1_inv1_Y"
    assert "back on SIGNAL" in out_of(spine)
    assert spine.db.net_wire_rows("sp_L1_inv1_Y") == []
    assert spine.eval("get_db strap:sp_L1_inv1/3 .net") == "SIGNAL"
    assert spine.eval("get_db pin_wire:sp_L1_inv1/Y .net") == "SIGNAL"
    assert spine.eval("get_db spine_net:sp/sp_L1_inv1_Y .route_rule") == "route_rule:r"
    assert spine.eval("get_db spine_net:sp/sp_L1_inv1_Y .driver") == "inst:sp_L1_inv1"
    # nothing left: a warning; unknown: an error
    spine.eval("delete_route -nets sp_L1_inv1_Y")
    assert "HT4-196" in out_of(spine)
    assert "HT4-195" in err(spine, "delete_route -nets nosuch")
    assert "HT4-001" in err(spine, "delete_route")
    # it can be routed again
    spine.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert "wire" in kinds("sp_L1_inv1_Y")


def test_route_final_stub_shield(spine, tmp_path):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r -shield")
    out_of(spine)
    spine.eval("route_final_stub -rule r -shield")
    text = out_of(spine)
    assert "shield VDD_SOC:" in text and "shield VSS:" in text
    for net in ("sp_L3_inv1_Y", "sp_L3_inv2_Y"):
        rows = spine.db.net_wire_rows(net)
        (stub,) = [r for r in rows if r["kind"] == "stub"]
        sx1, sy1, sx2, sy2 = (float(v) for v in stub["rect"].split())
        centre = (sx1 + sx2) / 2
        found = {}
        for r in rows:
            if r["kind"] == "stub_shield":
                x1, y1, x2, y2 = (float(v) for v in r["rect"].split())
                assert r["layer"] == "IB" and x2 - x1 == pytest.approx(0.36)
                assert sy1 - 1e-6 <= y1 and y2 <= sy2 + 1e-6        # within the stub's span
                found.setdefault(round((x1 + x2) / 2 - centre, 6), set()).add(r["shield_net"])
        # one each side, the next track: VDD_SOC left, VSS right (no assignment)
        assert found == {-0.72: {"VDD_SOC"}, 0.72: {"VSS"}}
        long = max(float(r["rect"].split()[3]) - float(r["rect"].split()[1])
                   for r in rows if r["kind"] == "stub_shield")
        assert long > (sy2 - sy1) / 2                               # mostly not cut
    path = tmp_path / "s.def"
    spine.eval(f"write_def -output {path}")
    assert "+ SHIELD sp_L3_inv1_Y IB 360" in path.read_text()
    # delete_route on the stub takes its shields too; the leaf's own stay
    spine.eval("delete_route -nets stub1")
    kinds = {r["kind"] for r in spine.db.net_wire_rows("sp_L3_inv1_Y")}
    assert not {k for k in kinds if k.startswith("stub")} and "wire" in kinds


def _floats(text):
    return [float(v) for v in text.replace(";", " ").replace("{", " ").replace("}", " ").split()]


def test_move_obj_spine_moves_everything(spine):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r -shield")
    spine.eval("route_final_stub -rule r -shield")
    g = lambda h, a: spine.eval(f"get_db {h} .{a}")
    before = {h: _floats(g(h, a)) for h, a in (
        ("spine:sp", "location"), ("inst:sp_L2_inv1", "location"),
        ("strap:sp_L2_inv1/1", "rect"), ("pin_wire:sp_L2_inv1/A", "rect"),
        ("stub:sp/stub1", "points"), ("spine_net:sp/sp_L1_inv1_Y", "route"))}
    wires = {(r["net"], r["seq"]): _floats(r["rect"]) for r in spine.db.net_wire_rows()}
    out_of(spine)
    # -legal: tracks every 0.72 here (no pattern), so 1 rounds to 0.72
    assert spine.eval("move_obj -direction up -distance 1 -legal [get_db spine .name]") == \
        "spine:sp"
    text = out_of(spine)
    assert "rounded to 0.72" in text and "HT4-201" not in text
    shifted = lambda vals: [round(v + (0.72 if k % 2 else 0), 6) for k, v in enumerate(vals)]
    for h, a in (("spine:sp", "location"), ("inst:sp_L2_inv1", "location"),
                 ("strap:sp_L2_inv1/1", "rect"), ("pin_wire:sp_L2_inv1/A", "rect"),
                 ("stub:sp/stub1", "points"), ("spine_net:sp/sp_L1_inv1_Y", "route")):
        assert [round(v, 6) for v in _floats(g(h, a))] == shifted(before[h]), h
    for r in spine.db.net_wire_rows():     # every routed shape, stubs and shields too
        assert [round(v, 6) for v in _floats(r["rect"])] == shifted(wires[r["net"], r["seq"]])
    # without -legal: moved as asked, with a warning that routes left their tracks
    spine.eval("move_obj -direction left -distance 1 sp")
    text = out_of(spine)
    assert "Moved spine:sp 1 left" in text and "HT4-201" in text
    assert _floats(g("spine:sp", "location"))[0] == pytest.approx(before["spine:sp"][0] - 1)


def test_move_obj_inst_moves_only_the_inst(spine):
    spine.eval("route_pin -inst sp_L2_inv1")
    strap = spine.eval("get_db strap:sp_L2_inv1/1 .rect")
    x, y = _floats(spine.eval("get_db inst:sp_L2_inv1 .location"))
    out_of(spine)
    assert spine.eval("move_obj -direction right -distance 0.3 inst:sp_L2_inv1") == \
        "inst:sp_L2_inv1"
    assert _floats(spine.eval("get_db inst:sp_L2_inv1 .location")) == \
        [pytest.approx(x + 0.3), pytest.approx(y)]
    assert spine.eval("get_db strap:sp_L2_inv1/1 .rect") == strap        # left behind
    assert "HT4-202" in out_of(spine)
    spine.eval("move_obj -direction down -distance 0.0013 -legal [get_db insts sp_L3*]")
    assert "HT4-205" in out_of(spine)                  # no DEF rows here: the grid only
    for n in ("sp_L3_inv1", "sp_L3_inv2"):
        assert all(abs(v / 0.00025 - round(v / 0.00025)) < 1e-6
                   for v in _floats(spine.eval(f"get_db inst:{n} .location")))
    assert "HT4-200" in err(spine, "move_obj -direction up -distance 1 nosuch")
    assert "HT4-001" in err(spine, "move_obj -direction north -distance 1 sp")
    assert "HT4-001" in err(spine, "move_obj -direction up -distance -1 sp")
    assert "HT4-001" in err(spine, "move_obj -direction up sp")


# rows of 0.2 sites, 1.778 tall (one INV_RP), alternating N and FS from y 0
ROWS_DEF = DEF.replace("END DESIGN", "".join(
    f"ROW r{k} core -50000 {k * 1778} {'N' if k % 2 == 0 else 'FS'} DO 500 BY 1 STEP 200 0 ;\n"
    for k in range(-10, 31)) + "END DESIGN")


def test_move_obj_legal_snaps_insts_to_sites(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(ROWS_DEF, 'r.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.eval("create_inst -ref_cell INV_RP -location {10 1.778} -name u2 -orient FS")
    out_of(s)
    s.eval("move_obj -direction right -distance 0.33 -legal u1")
    assert s.eval("get_db inst:u1 .location") == "0.4 0"          # 0.33 -> the 0.2 site
    s.eval("move_obj -direction up -distance 1 -legal u1")
    # nearest N row: y 0 (FS row at 1.778 is the wrong orientation, N rows every 3.556)
    assert s.eval("get_db inst:u1 .location") == "0.4 0"
    s.eval("move_obj -direction up -distance 3 -legal u1")
    assert s.eval("get_db inst:u1 .location") == "0.4 3.556"
    s.eval("move_obj -direction down -distance 0.5 -legal u2")    # FS: FS rows only
    assert s.eval("get_db inst:u2 .location") == "10 1.778"
    s.eval("move_obj -direction left -distance 0.5 u2")           # no -legal: as given
    assert s.eval("get_db inst:u2 .location") == "9.5 1.778"
    assert "snapped to sites" in out_of(s)


def test_move_obj_legal_spine_tracks_and_sites(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(ROWS_DEF, 'r.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("route_pin -inst *sp_*")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    s.eval("move_obj -direction up -distance 2 -legal sp")
    text = out_of(s)
    assert "rounded to 2.16" in text                               # 3 tracks of 0.72
    for r in s.db.net_wire_rows():                                 # wires still on tracks
        if r["kind"] == "wire":
            x1, y1, x2, y2 = (float(v) for v in r["rect"].split())
            c = (y1 + y2) / 2 if r["layer"] == "IA" else (x1 + x2) / 2
            assert on_track(c), r["rect"]
    rows = {round(k * 1.778, 6): ("N" if k % 2 == 0 else "FS") for k in range(-10, 31)}
    for n in s.split_list(s.eval("get_db spine:sp .insts")):       # cells on sites
        x, y = _floats(s.eval(f"get_db {n} .location"))
        assert rows.get(round(y, 6)) == s.eval(f"get_db {n} .orient")
        assert abs((x + 50) / 0.2 - round((x + 50) / 0.2)) < 1e-6
    if "snapped to sites" in text:
        assert "HT4-206" in text and "route_net -net {" in text


def test_legalize_placement(tech_session, write_lef):
    s = tech_session
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF.replace('  SIZE 3.12', '  SITE core ;' + chr(10) + '  SIZE 3.12'), 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(ROWS_DEF, 'r.def')}}}")
    s.eval("create_inst -ref_cell INV_RP -location {0.03 0.1} -name u1")
    s.eval("create_inst -ref_cell INV_RP -location {0.05 -0.2} -name u2")     # would collide
    s.eval("create_inst -ref_cell INV_RP -location {10.07 1.7} -name u3 -orient FS")
    s.eval("create_inst -ref_cell INV_RP -location {20 0} -name u4")           # legal already
    s.eval("create_inst -ref_cell INV_RP -location {30.01 0.01} -name u5")
    s.eval("set_db inst:u5 .place_status fixed")
    s.eval("route_pin -inst u1")
    strap = _floats(s.eval("get_db strap:u1/1 .rect"))
    out_of(s)
    moved = s.split_list(s.eval("legalize_placement -inst [get_db inst]"))
    text = out_of(s)
    assert set(moved) == {"inst:u1", "inst:u2", "inst:u3"}
    assert "1 already legal, 1 fixed (not moved)" in text
    locs = {n: _floats(s.eval(f"get_db inst:{n} .location")) for n in ("u1", "u2", "u3", "u4")}
    rows = {round(k * 1.778, 6): ("N" if k % 2 == 0 else "FS") for k in range(-10, 31)}
    from core import objects
    from core.commands.legalize_placement import _overlap
    for n, (x, y) in locs.items():                        # on a site of its orientation
        assert rows.get(round(y, 6)) == s.eval(f"get_db inst:{n} .orient")
        assert abs((x + 50) / 0.2 - round((x + 50) / 0.2)) < 1e-6
    boxes = [objects.inst_bbox(s.db, r) for r in s.db.inst_rows()]
    assert not any(_overlap(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])
    assert locs["u3"] == [pytest.approx(10.0), pytest.approx(1.778)]           # FS row
    assert locs["u4"] == [20, 0]
    assert s.eval("get_db inst:u5 .location") == "30.01 0.01"                  # fixed
    dx = locs["u1"][0] - 0.03
    assert _floats(s.eval("get_db strap:u1/1 .rect"))[0] == pytest.approx(strap[0] + dx)
    assert "HT4-210" in err(s, "legalize_placement -inst nosuch")
    assert "HT4-001" in err(s, "legalize_placement")


def test_legalize_placement_needs_rows(spine):
    assert "HT4-211" in err(spine, "legalize_placement -inst [get_db insts]")


def test_optimize_pg_connection(spine, tmp_path):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("route_net -net [get_db nets .name] -rule r -shield")
    spine.eval("route_final_stub -rule r -shield")
    out_of(spine)
    done = spine.split_list(spine.eval("optimize_pg_connection -inst [get_db insts] -extend 3"))
    text = out_of(spine)
    assert done and "new power connection(s)" in text
    from core.commands.route_net import _gap
    pg = [r for r in spine.db.net_wire_rows() if r["net"].startswith("pg:")]
    exts = [r for r in pg if r["kind"] == "pg_ext"]
    assert exts and all(r["shield_net"] in ("VDD_SOC", "VSS") for r in pg)
    shields = [(r["shield_net"], _floats(r["rect"])) for r in spine.db.net_wire_rows()
               if r["kind"] in ("shield", "stub_shield") and r["layer"] == "IB"]
    for r in exts:
        inst = r["net"][3:]
        x1, y1, x2, y2 = _floats(r["rect"])
        assert x2 - x1 <= 3 + 1e-6 and r["layer"] == "IA"
        (strap,) = [s for s in spine.db.strap_rows(inst)
                    if _floats(s["rect"])[1::2] == [y1, y2]]           # on its strap's band
        assert strap["net"] == r["shield_net"]
        # it reaches the far edge of a same-net vertical shield across the band
        assert any(n == r["shield_net"] and s[1] <= y1 + 1e-6 and s[3] >= y2 - 1e-6
                   and (abs(s[0] - x1) < 1e-6 or abs(s[2] - x2) < 1e-6) for n, s in shields)
        for other in spine.db.strap_rows():                            # spacing to other nets
            o = _floats(other["rect"])
            if other["net"] != r["shield_net"]:
                assert _gap((x1, y1, x2, y2), o) >= 0.36 - 1e-6 or other["inst"] == inst and \
                    o[1::2] != [y1, y2]
    count = len(pg)
    # again: replaced, not added; a smaller -extend gives no more than before
    spine.eval("optimize_pg_connection -inst [get_db insts] -extend 3")
    assert len([r for r in spine.db.net_wire_rows() if r["net"].startswith("pg:")]) == count
    path = tmp_path / "pg.def"
    spine.eval(f"write_def -output {path}")
    x1, y1, x2, y2 = (round(v * 1000) for v in _floats(exts[0]["rect"]))
    special = path.read_text().split("SPECIALNETS")[1]
    assert f"IA {y2 - y1} + SHAPE STRIPE ( {x1} {(y1 + y2) // 2} ) ( {x2} {(y1 + y2) // 2} )" \
        in special
    # move_obj takes them along; route_pin rebuilding the straps drops them
    inst = exts[0]["net"][3:]
    spine.eval("move_obj -direction up -distance 0.72 sp")
    assert _floats([r for r in spine.db.net_wire_rows(f"pg:{inst}")
                    if r["seq"] == exts[0]["seq"]][0]["rect"])[1] == pytest.approx(y1 / 1000 + 0.72)
    spine.eval(f"route_pin -inst {inst}")
    assert spine.db.net_wire_rows(f"pg:{inst}") == []
    assert "HT4-001" in err(spine, "optimize_pg_connection -inst sp_L1_inv1 -extend 0")
    assert "HT4-215" in err(spine, "optimize_pg_connection -inst nosuch")


def test_optimize_pg_connection_without_straps(spine):
    spine.eval("optimize_pg_connection -inst *sp_L3*")      # route_pin not run on them
    assert "HT4-216" in out_of(spine)


def test_ignore_shield_less_than_routing_length(spine):
    attr = "ignore_shield_less_than_routing_length"
    assert spine.eval(f"get_db {attr}") == "1"            # the spec's placement.deviation
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield")
    pieces = [max(x2 - x1, y2 - y1) for layer in ("IA", "IB")
              for x1, y1, x2, y2 in rects(spine, "sp_L1_inv1_Y", "wire", layer)]
    assert shields(spine, "sp_L1_inv1_Y")
    longest = max(pieces)
    spine.eval(f"set_db {attr} {longest + 1}")            # every piece shorter: none shielded
    out_of(spine)
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield")
    text = out_of(spine)
    assert shields(spine, "sp_L1_inv1_Y") == []
    assert f"not shielded: {len(pieces)} wire piece(s) shorter than" in text
    spine.eval(f"set_db {attr} {longest - 0.01}")         # only the longest one shielded
    spine.eval("route_net -net sp_L1_inv1_Y -rule r -shield")
    text = out_of(spine)
    found = shields(spine, "sp_L1_inv1_Y")
    short = sum(1 for n in pieces if n < longest - 0.01)
    assert found and ((f"not shielded: {short} wire piece(s)" in text) if short
                      else "not shielded" not in text)
    assert all(max(r[2] - r[0], r[3] - r[1]) >= longest - 1e-6 for _, r in found)
    assert spine.eval(f"set_db {attr} default") == "1"


def test_ignore_shield_length_for_stubs(spine):
    spine.eval("route_pin -inst *sp_*")
    spine.eval("set_db ignore_shield_less_than_routing_length 100000")
    spine.eval("route_final_stub -rule r -shield")
    text = out_of(spine)
    assert "not shielded: 1 wire piece(s) shorter than 100000 um" in text
    assert not any(r["kind"] == "stub_shield" for r in spine.db.net_wire_rows())


# -- set_place_constraint and the legalizer's spacing ----------------------------------------

SITE_LEF_EDIT = ("  SIZE 3.12", "  SITE core ;\n  SIZE 3.12")


def _rows_session(s, write_lef):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF.replace(*SITE_LEF_EDIT), 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(ROWS_DEF, 'r.def')}}}")
    return s


def _boxes(s):
    from core import objects
    return {r["name"]: objects.inst_bbox(s.db, r) for r in s.db.inst_rows()}


def _all_apart(s, sx, sy):
    from core.commands.legalize_placement import _overlap, _too_close
    boxes = list(_boxes(s).items())
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            assert not _overlap(ba, bb), (a, b)
            assert not _too_close(ba, bb, (sx, sy)), (a, b, ba, bb)


def test_set_place_constraint_command(tech_session, write_lef, tmp_path):
    s = _rows_session(tech_session, write_lef)
    assert s.eval("set_place_constraint -ref_name INV_R* -space_x 1 -space_y 2.5") == "INV_RP"
    assert "INV_RP: instances at least 1 um apart in x or 2.5 um in y" in out_of(s)
    assert s.eval("set_place_constraint") == "INV_RP"
    assert "INV_RP: space_x 1 space_y 2.5" in out_of(s)
    path = tmp_path / "c.db"                                  # kept by write_db
    s.eval(f"write_db -file {{{path}}}")
    from core.commands.set_place_constraint import spacings
    s.eval("set_place_constraint -ref_name INV_RP -space_y 3")   # replaces; x 0
    assert spacings(s.db) == {"INV_RP": (0.0, 3.0)}
    s.eval(f"read_db -file {{{path}}}")
    assert spacings(s.db) == {"INV_RP": (1.0, 2.5)}
    s.eval("set_place_constraint -ref_name lib_cell:INV_RP -remove")
    assert spacings(s.db) == {}
    assert "HT4-225" in err(s, "set_place_constraint -ref_name NOPE -space_x 1")
    assert "HT4-001" in err(s, "set_place_constraint -ref_name INV_RP -space_x -1")
    assert "HT4-001" in err(s, "set_place_constraint -ref_name INV_RP")
    assert "HT4-001" in err(s, "set_place_constraint -space_x 1")


def test_legalize_spacing_vertical_spine_moves_in_y(tech_session, write_lef):
    s = _rows_session(tech_session, write_lef)
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("legalize_placement -inst [get_db insts]")
    before = _boxes(s)
    out_of(s)
    s.eval("set_place_constraint -ref_name INV_RP -space_x 1 -space_y 3")
    s.eval("legalize_placement -inst [get_db insts]")
    text = out_of(s)
    assert "pair(s) closer than set_place_constraint" in text and "0 pair(s) left" in text
    after = _boxes(s)
    moved = [n for n in after if after[n] != before[n]]
    assert moved
    for n in moved:                                           # vertical spine: in y only
        assert after[n][0] == pytest.approx(before[n][0]) and after[n][1] != before[n][1]
    _all_apart(s, 1, 3)
    s.eval("legalize_placement -inst [get_db insts]")         # met: nothing moves
    assert "placement constraints met" in out_of(s) and _boxes(s) == after


def test_legalize_spacing_horizontal_spine_moves_in_x(tech_session, write_lef):
    s = _rows_session(tech_session, write_lef)
    spec = SPEC.replace("orientation: vertical", "orientation: horizontal")
    s.eval(f"read_spine_spec -file {{{write_lef(spec, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("legalize_placement -inst [get_db insts]")
    before = _boxes(s)
    out_of(s)
    s.eval("set_place_constraint -ref_name INV_RP -space_x 2 -space_y 2")
    s.eval("legalize_placement -inst [get_db insts]")
    assert "0 pair(s) left" in out_of(s)
    after = _boxes(s)
    moved = [n for n in after if after[n] != before[n]]
    assert moved
    for n in moved:                                           # horizontal spine: in x only
        assert after[n][1] == pytest.approx(before[n][1]) and after[n][0] != before[n][0]
    _all_apart(s, 2, 2)


def test_legalize_spacing_fixed_and_placed(tech_session, write_lef):
    s = _rows_session(tech_session, write_lef)
    # u1 fixed, u2 placed right beside it (abutting): only u2 moves, the whole way
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.eval("create_inst -ref_cell INV_RP -location {3.2 0} -name u2")
    s.eval("set_db inst:u1 .place_status fixed")
    s.eval("set_place_constraint -ref_name INV_RP -space_x 2 -space_y 10")   # x is shorter
    s.eval("legalize_placement -inst [get_db insts]")
    assert "0 pair(s) left" in out_of(s)
    assert s.eval("get_db inst:u1 .location") == "0 0"
    x2 = _floats(s.eval("get_db inst:u2 .location"))
    assert x2[1] == 0 and x2[0] >= 3.12 + 2 - 1e-6           # no spine: x, the short way
    # both fixed: reported, nothing moves
    s.eval("create_inst -ref_cell INV_RP -location {20 0} -name u3")
    s.eval("create_inst -ref_cell INV_RP -location {23.2 0} -name u4")
    s.eval("set_db {inst:u3 inst:u4} .place_status fixed")
    s.eval("legalize_placement -inst [get_db insts]")
    text = out_of(s)
    assert "HT4-214" in text and "u3 u4" in text and "both fixed" in text
    assert s.eval("get_db inst:u4 .location") == "23.2 0"


def test_legalize_spacing_both_placed_move(tech_session, write_lef):
    s = _rows_session(tech_session, write_lef)
    s.eval("create_inst -ref_cell INV_RP -location {0 0} -name u1")
    s.eval("create_inst -ref_cell INV_RP -location {3.2 0} -name u2")
    s.eval("set_place_constraint -ref_name INV_RP -space_x 4 -space_y 10")
    s.eval("legalize_placement -inst [get_db insts]")
    assert "0 pair(s) left" in out_of(s)
    x1 = _floats(s.eval("get_db inst:u1 .location"))[0]
    x2 = _floats(s.eval("get_db inst:u2 .location"))[0]
    assert x1 < 0 and x2 > 3.2                                # each moved away, about half
    assert x2 - (x1 + 3.12) >= 4 - 1e-6
