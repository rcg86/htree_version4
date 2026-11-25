"""Named pin routing specs: read_pin_spec loads them into the database,
route_pin -spec_name (and add_buffer_on_net -spec_name) uses one by name; a
-spec file of named specs takes -spec_name."""

import pytest

from core.commands.route_pin import DEFAULTS, load_specs
from test_route_pin import err, out_of, placed  # noqa: F401  (a fixture)

NAMED = """pin_routing:
  vertical_routing:
    width: 0.36
    spacing: 0.36
    nets: [VSS, VDD_SOC, SIGNAL, VSS, SIGNAL, VDD_SOC]
  horizontal_routing:
    width: 0.5
    nets: [VSS, SIGNAL, SIGNAL, VDD_SOC]
"""


def test_the_shipped_file_has_the_two_named_specs():
    specs = load_specs("runs/pin_routing_spec.yaml")
    assert list(specs) == ["vertical_routing", "horizontal_routing"]
    v, h = specs["vertical_routing"], specs["horizontal_routing"]
    assert {k for k in v if v[k] != h[k]} == {"pins", "routing_direction"}   # the rest same
    assert (v["routing_direction"], h["routing_direction"]) == ("vertical", "horizontal")
    assert {k for k in v["pins"] if v["pins"][k] != h["pins"][k]} == {"horizontal_layer"}
    assert specs["vertical_routing"]["width"] == 0.36


def test_read_pin_spec_then_route_pin_by_name(placed, write_lef, tmp_path):
    s = placed
    path = write_lef(NAMED, "n.yaml")
    assert s.split_list(s.eval(f"read_pin_spec -file {path}")) == \
        ("vertical_routing", "horizontal_routing")
    text = out_of(s)
    assert "read_pin_spec: 2 pin routing spec(s)" in text
    assert "  horizontal_routing: cells *, 4 straps (VSS SIGNAL SIGNAL VDD_SOC), width 0.5" in text
    s.eval("route_pin -inst u1 -spec_name horizontal_routing")
    assert "(spec horizontal_routing)" in out_of(s)
    assert len(s.db.strap_rows("u1")) == 4
    assert s.eval("get_db inst:u1 .pin_spec") == "horizontal_routing"
    # kept in the database: the file is not read again
    s.eval(f"write_db -file {tmp_path / 'k.db'}")
    s.eval(f"read_db -file {tmp_path / 'k.db'}")
    s.eval("route_pin -inst u1 -spec_name vertical_routing")
    assert len(s.db.strap_rows("u1")) == 6 and s.db.strap_rows("u1")[0]["rect"]
    # read again: replaced, said
    s.eval(f"read_pin_spec -file {path}")
    assert "(HT4-314)" in out_of(s)


def test_a_file_of_named_specs_with_spec(placed, write_lef):
    s = placed
    path = write_lef(NAMED, "n.yaml")
    assert "give -spec_name" in err(s, f"route_pin -inst u1 -spec {path}")
    s.eval(f"route_pin -inst u1 -spec {path} -spec_name vertical_routing")
    assert len(s.db.strap_rows("u1")) == 6
    assert s.eval("get_db inst:u1 .pin_spec") == "vertical_routing"
    assert "has no spec named 'nope'" in err(s, f"route_pin -inst u1 -spec {path} -spec_name nope")
    # a file with one spec, not named: as before
    one = write_lef("pin_routing:\n  width: 0.5\n", "o.yaml")
    s.eval(f"route_pin -inst u1 -spec {one}")
    assert s.eval("get_db inst:u1 .pin_spec") == one


def test_errors(placed, write_lef):
    s = placed
    assert "no pin routing spec named 'vertical_routing'" in \
        err(s, "route_pin -inst u1 -spec_name vertical_routing")
    one = write_lef("pin_routing:\n  width: 0.5\n", "o.yaml")
    assert "HT4-313" in err(s, f"read_pin_spec -file {one}")            # not named
    bad = write_lef("pin_routing:\n  v: {widht: 1}\n", "b.yaml")
    assert "pin_routing.v.widht is not a spec key" in err(s, f"read_pin_spec -file {bad}")
    assert "-file is required" in err(s, "read_pin_spec")
    assert DEFAULTS["width"] == 0.72                                    # untouched


def test_set_db_pin_spec_then_route_pin_remakes_the_routes(placed, write_lef):
    # set_db .pin_spec gives the instance another named spec; route_pin -inst with no
    # spec removes its pin routes and makes them again with it
    s = placed
    s.eval(f"read_pin_spec -file {write_lef(NAMED, 'n.yaml')}")
    s.eval("route_pin -inst u1 -spec_name vertical_routing")
    assert len(s.db.strap_rows("u1")) == 6
    out_of(s)
    assert s.eval("set_db [get_db insts u1] .pin_spec horizontal_routing") == "inst:u1"
    assert "1 instance(s) on pin spec horizontal_routing; route_pin -inst {u1}" in out_of(s)
    assert s.eval("get_db inst:u1 .pin_spec") == "horizontal_routing"
    assert len(s.db.strap_rows("u1")) == 6                   # nothing routed yet
    s.eval("route_pin -inst u1")
    text = out_of(s)
    assert "(spec horizontal_routing)" in text and "replaced" in text.lower()
    straps = s.db.strap_rows("u1")
    assert [r["net"] for r in straps] == ["VSS", "SIGNAL", "SIGNAL", "VDD_SOC"]
    assert all(abs(float(r["rect"].split()[3]) - float(r["rect"].split()[1]) - 0.5) < 1e-6
               for r in straps)                              # width 0.5
    # back to the built-in spec
    s.eval("set_db inst:u1 .pin_spec default")
    s.eval("route_pin -inst u1")
    assert len(s.db.strap_rows("u1")) == 7 and s.eval("get_db inst:u1 .pin_spec") == "default"


def test_each_instance_its_own_spec_in_one_route_pin(placed, write_lef):
    s = placed
    s.eval("create_inst -ref_cell INV_RP -location {20 0} -name u2")
    s.eval(f"read_pin_spec -file {write_lef(NAMED, 'n.yaml')}")
    s.eval("set_db inst:u1 .pin_spec vertical_routing")
    s.eval("set_db inst:u2 .pin_spec horizontal_routing")
    s.eval("route_pin -inst {u1 u2}")
    out_of(s)
    assert (len(s.db.strap_rows("u1")), len(s.db.strap_rows("u2"))) == (6, 4)
    # a spec given on the command line wins over theirs
    s.eval("route_pin -inst {u1 u2} -spec_name vertical_routing")
    assert (len(s.db.strap_rows("u1")), len(s.db.strap_rows("u2"))) == (6, 6)


def test_set_db_pin_spec_errors(placed, write_lef):
    s = placed
    assert "none read: read_pin_spec" in err(s, "set_db inst:u1 .pin_spec vertical_routing")
    s.eval(f"read_pin_spec -file {write_lef(NAMED, 'n.yaml')}")
    assert "(read: vertical_routing horizontal_routing)" in err(
        s, "set_db inst:u1 .pin_spec nope")
    assert s.eval("get_db inst:u1 .pin_spec") == ""              # nothing set


HORIZONTAL = """pin_routing:
  horizontal_routing:
    pins: {layer: D12, horizontal_layer: none, vertical_layer: H2,
           nets: {VDD: VDD_SOC, VSS: VSS, A: SIGNAL, Y: SIGNAL}}
"""


def test_the_shipped_horizontal_routing_has_no_straps():
    specs = load_specs("runs/pin_routing_spec.yaml")
    assert specs["horizontal_routing"]["pins"]["horizontal_layer"] is None
    assert specs["vertical_routing"]["pins"]["horizontal_layer"] == "IA"


@pytest.mark.side_pins
def test_no_straps_only_h2_pin_wires_and_route_net_reaches_them(tech_session, write_lef):
    # horizontal_layer none: no IA strap; each pin an H2 wire, a signal pin's on to a free
    # IA signal track (as a side pin), so route_net brings the net in along the track
    from test_side_pins import spine
    from test_copy_obj import ALL
    s = spine(tech_session, write_lef)
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    text = out_of(s)
    assert "no straps (pins.horizontal_layer none)" in text
    assert s.db.strap_rows("sp_L2_inv1") == []
    wires = {w["pin"]: w for w in s.db.pin_wire_rows("sp_L2_inv1")}
    assert set(wires) == {"VDD", "VSS", "A", "Y"}
    assert all(w["strap"] is None and w["layer"] == "H2" for w in wires.values())
    assert "pin wire on to IA y" in text
    for inst in s.split_list(s.eval("get_db insts .name")):
        if inst != "sp_L2_inv1":
            s.eval(f"route_pin -inst {inst}")
    out_of(s)
    s.eval(f"route_net -net {ALL} -rule r -shield")         # -shield: its power pins too
    text = out_of(s)
    assert "HT4-174" not in text and "HT4-999" not in text   # every net found a path
    assert "connected on its pin wire, along the track" in text


def test_none_in_a_spec_and_dump(placed, write_lef, tmp_path):
    s = placed
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    assert "no straps: H2 pin wires only" in out_of(s)
    s.eval("route_pin -inst u1 -spec_name horizontal_routing")
    assert s.db.strap_rows("u1") == [] and len(s.db.pin_wire_rows("u1")) == 4
    path = tmp_path / "d.yaml"
    s.eval(f"route_pin -dump {path} -spec {write_lef(HORIZONTAL, 'h2.yaml')}")
    assert load_specs(str(path))[None]["pins"]["horizontal_layer"] is None


def test_power_pin_wires_go_on_to_their_ia_power_track(tech_session, write_lef):
    # no straps: VDD's and VSS's H2 wires on to the nearest IA track of their net (the
    # track assignment: VDD NA - NA VSS NA - NA, y 0.36 + 0.72 k), for insert_pg_grid
    from test_move_spine import build
    s = build(tech_session, write_lef, rows=False)
    spec = HORIZONTAL.replace("VDD: VDD_SOC", "VDD: VDD")
    s.eval(f"read_pin_spec -file {write_lef(spec, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    text = out_of(s)
    assert "VDD: pin wire on to the VDD track IA y" in text
    assert "VSS: pin wire on to the VSS track IA y" in text
    for pin, k in (("VDD", 0), ("VSS", 4)):
        w = s.db.pin_wire_row("sp_L2_inv1", pin)
        x1, y1, x2, y2 = map(float, w["rect"].split())
        ys = [round(0.36 + 0.72 * j, 6) for j in range(278) if j % 8 == k]
        assert any(y1 <= y - 0.18 + 1e-6 and y + 0.18 <= y2 + 1e-6 for y in ys), (pin, w["rect"])
    # insert_pg_grid lays VDD and VSS on those tracks; insert_vias joins the pin wires
    s.eval("insert_pg_grid -layer IA -pull_back_distance 1")
    s.eval("insert_vias -bottom_layer H2 -top_layer IA")
    text = out_of(s)
    assert "Nets          :" in text and "VDD(" in text and "VSS(" in text



def test_lee_keeps_to_the_routing_direction():
    # a 5 x 5 grid; from (H, 0, 2) to the V crossing (V, 4, 2): the cheapest way runs
    # along H then drops; with the target's rule V (vertical) it must come along V
    from core.commands.route_net import H, V, _lee
    xs = ys = [0.0, 1.0, 2.0, 3.0, 4.0]
    free = _lee({(H, 0, 2): 0}, {1: {(V, 4, 2): 0}}, xs, ys, set(), 5.0)
    assert free[1][-2] == (H, 4, 2)                       # in by a via from H
    kept = _lee({(H, 0, 2): 0}, {1: {(V, 4, 2): 0}}, xs, ys, set(), 5.0,
                rules={(V, 4, 2): V})
    assert kept[1][-2][0] == V and kept[1][-2][1] == 4     # in along V, from above or below
    side = _lee({(V, 2, 0): 0}, {1: {(H, 2, 4): 0}}, xs, ys, set(), 5.0,
                rules={(H, 2, 4): H})
    assert side[1][-2][0] == H                            # a side pin: along H only
    assert _lee({(V, 2, 0): 0}, {1: {(H, 2, 4): 0}}, xs, ys,
                {(H, 1, 4), (H, 3, 4)}, 5.0, rules={(H, 2, 4): H}) is None


DIRECTED = """pin_routing:
  vertical_routing:
    routing_direction: vertical
  horizontal_routing:
    routing_direction: horizontal
    pins: {layer: D12, horizontal_layer: none, vertical_layer: H2,
           nets: {VDD: VDD, VSS: VSS, A: SIGNAL, Y: SIGNAL}}
"""


@pytest.mark.side_pins
def test_route_net_keeps_each_cells_routing_direction(tech_session, write_lef):
    from core.commands import route_net
    from test_copy_obj import ALL
    from test_side_pins import spine
    s = spine(tech_session, write_lef)
    s.eval(f"read_pin_spec -file {write_lef(DIRECTED, 'd.yaml')}")
    for inst in s.split_list(s.eval("get_db insts .name")):      # its neighbours first:
        if inst != "sp_L2_inv1":                                    # its track clear of them
            s.eval(f"route_pin -inst {inst} -spec_name vertical_routing")
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    text = out_of(s)
    assert "reached from the side" not in text            # vertical: no side pins
    seen = {}
    real = route_net._lee

    def spy(sources, targets, *a, **k):                   # the rules route_net gives
        seen.update(k.get("rules") or (a[6] if len(a) > 6 else {}) or {})
        return real(sources, targets, *a, **k)
    route_net._lee = spy
    try:
        s.eval(f"route_net -net {ALL} -rule r")
    finally:
        route_net._lee = real
    text = out_of(s)
    assert "HT4-174" not in text and "connected on its pin wire, along the track" in text
    assert set(seen.values()) == {route_net.V, route_net.H}   # straps along V, side along H


def test_get_db_pin_route_spec(placed, write_lef):
    s = placed
    assert "no pin routing spec read" in (s.eval("get_db pin_route_spec") or out_of(s))
    out_of(s)
    s.eval(f"read_pin_spec -file {write_lef(NAMED, 'n.yaml')}")
    s.eval("route_pin -inst u1 -spec_name horizontal_routing")
    out_of(s)
    # the singular prints every spec, the plural only lists them
    assert s.eval("get_db pin_route_spec") == \
        "pin_route_spec:vertical_routing pin_route_spec:horizontal_routing"
    text = out_of(s)
    assert "pin_route_spec:horizontal_routing\n" in text
    assert "  width               : 0.5" in text
    assert "  nets                : ['VSS', 'SIGNAL', 'SIGNAL', 'VDD_SOC']" in text
    assert "  insts               : 1 instance(s) routed with it" in text
    assert s.eval("get_db pin_route_specs") == \
        "pin_route_spec:vertical_routing pin_route_spec:horizontal_routing"
    assert out_of(s) == ""
    h = "pin_route_spec:horizontal_routing"
    assert s.eval(f"get_db {h} .width") == "0.5"
    assert s.eval(f"get_db {h} .horizontal_layer") == "IA"
    assert s.eval(f"get_db {h} .insts") == "inst:u1"
    assert s.eval(f"get_db {h} .insts.name") == "u1"
    assert s.eval("get_db pin_route_specs vert*") == "pin_route_spec:vertical_routing"
    assert "HT4-022" in err(s, "get_db pin_route_spec:nope")


def test_optimize_pg_connection_extends_h2_power_pin_wires(tech_session, write_lef):
    # a horizontal pin spec (no straps): the power pin wires go up or down, up to -extend,
    # onto the IA power wires of their net (here insert_pg_grid's)
    from test_move_spine import build
    s = build(tech_session, write_lef, rows=False)
    spec = HORIZONTAL.replace("VDD: VDD_SOC", "VDD: VDD").replace(
        "  horizontal_routing:\n", "  horizontal_routing:\n    routing_direction: horizontal\n")
    s.eval(f"read_pin_spec -file {write_lef(spec, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    s.eval("insert_pg_grid -layer IA -pull_back_distance 1")
    before = {w["pin"]: w["rect"] for w in s.db.pin_wire_rows("sp_L2_inv1")}
    out_of(s)
    s.eval("optimize_pg_connection -inst sp_L2_inv1 -extend 5")
    text = out_of(s)
    assert "sp_L2_inv1: pin wire" in text and "crossing(s)" in text
    after = {w["pin"]: w["rect"] for w in s.db.pin_wire_rows("sp_L2_inv1")}
    grew = [p for p in ("VDD", "VSS") if after[p] != before[p]]
    assert grew and after["A"] == before["A"] and after["Y"] == before["Y"]
    for p in grew:
        b, a = map(float, before[p].split()), map(float, after[p].split())
        b, a = list(b), list(a)
        assert a[0] == b[0] and a[2] == b[2]                  # only up and down
        assert a[1] <= b[1] and a[3] >= b[3] and (b[1] - a[1]) <= 5 and (a[3] - b[3]) <= 5
    boxes = [r for r in s.db.net_wire_rows("pg:sp_L2_inv1") if r["kind"] == "pg_cross"]
    assert boxes and all(r["layer"] == "H2/IA" for r in boxes)
    # again: from where route_pin left them, not further
    s.eval("optimize_pg_connection -inst sp_L2_inv1 -extend 5")
    out_of(s)
    assert {w["pin"]: w["rect"] for w in s.db.pin_wire_rows("sp_L2_inv1")} == after


def test_a_side_pin_goes_on_to_its_nets_wire_on_ia(tech_session, write_lef):
    # no straps: Y's net has an IA wire running under the cell (a leaf's stub, say):
    # the pin wire goes down on to it, joined there; no track of its own, no route
    from test_move_spine import build
    s = build(tech_session, write_lef, rows=False)
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    from core import objects
    x1, y1, x2, y2 = objects.inst_bbox(s.db, s.db.inst_row("sp_L2_inv1"))
    y = max(c for c in s.db.track_positions("IA", "y") if c < y1 - 1)    # a track below it
    s.db.add_net_wires([("sp_L2_inv1_Y", "wire", "IA",
                         f"{x1 - 20} {y - 0.18} {x2 + 20} {y + 0.18}", None, None)])
    out_of(s)
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    text = out_of(s)
    assert f"Y: pin wire on to its net's route wire on IA at y {y:g}" in text
    w = [float(c) for c in s.db.pin_wire_row("sp_L2_inv1", "Y")["rect"].split()]
    assert w[1] <= y - 0.18 + 1e-6 and w[3] >= y1                    # down on to it


def test_side_spots_keep_a_side_pins_landing_free(tech_session, write_lef):
    # route_net keeps other nets off the stretch of track over a side pin's pin wire
    from test_move_spine import build
    from core.commands import route_net
    s = build(tech_session, write_lef, rows=False)
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval("route_pin -inst sp_L2_inv1 -spec_name horizontal_routing")
    out_of(s)
    grid = route_net.Grid(s.db, route_net._rule_layers(s.db, "r"))
    spots = {n: (lay, r) for n, lay, r in route_net.side_spots(s.db, grid)}
    for pin, net in (("A", "sp_L1_inv1_Y"), ("Y", "sp_L2_inv1_Y")):
        lay, r = spots[net]
        w = [float(c) for c in s.db.pin_wire_row("sp_L2_inv1", pin)["rect"].split()]
        assert lay == "IA" and (r[0], r[2]) == (w[0], w[2])         # over the pin wire only
        assert w[1] - 1e-6 <= r[1] and r[3] <= w[3] + 1e-6           # on its track in it


def test_a_leaf_side_pin_goes_on_to_its_stubs_track_before_the_stub_is_routed(
        tech_session, write_lef):
    # no straps: a leaf's Y, its stub not routed yet: the pin wire goes on to the
    # signal track nearest the stub's line, route_final_stub lays the stub there
    from test_move_spine import build
    s = build(tech_session, write_lef, rows=False)
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    from core import objects
    x1, y1, x2, y2 = objects.inst_bbox(s.db, s.db.inst_row("sp_L3_inv1"))
    x = objects.pin_centre(s.db, "sp_L3_inv1", "Y")[0]
    row = s.db.spine_stub_rows(s.db.spine_row("sp")["id"])
    st = next(r for r in row if r["driver"] == "sp_L3_inv1")
    with s.db.conn:                      # a horizontal stub line just under the cell
        s.db.conn.execute("UPDATE spine_stub SET points = ? WHERE id = ?",
                          (f"{x - 30} {y1 - 2} {x + 30} {y1 - 2}", st["id"]))
    tracks = [c for k, c in enumerate(s.db.track_positions("IA", "y")) if k % 8 in (2, 6)]
    want = min(tracks, key=lambda c: abs(c - (y1 - 2)))
    out_of(s)
    s.eval("route_pin -inst sp_L3_inv1 -spec_name horizontal_routing")
    text = out_of(s)
    assert f"Y: pin wire on to its net's stub {st['name']} track on IA at y {want:g}" in text
    w = [float(c) for c in s.db.pin_wire_row("sp_L3_inv1", "Y")["rect"].split()]
    assert w[1] <= want - 0.18 + 1e-6                     # the track is inside the pin wire


def test_route_final_stub_takes_the_track_the_leafs_pin_wire_is_on(tech_session, write_lef):
    # the leaf's Y pin wire (no strap) covers the second nearest track to the stub's line:
    # the stub goes there, on the pin wire's end, not on the nearest track
    from test_move_spine import build
    from core import objects
    from core.commands import route_net
    from core.commands.route_final_stub import plan_stubs
    s = build(tech_session, write_lef, rows=False)
    s.eval(f"read_pin_spec -file {write_lef(HORIZONTAL, 'h.yaml')}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    sp = s.db.spine_row("sp")
    x1, y1, x2, y2 = objects.inst_bbox(s.db, s.db.inst_row("sp_L3_inv1"))
    x = objects.pin_centre(s.db, "sp_L3_inv1", "Y")[0]
    st = next(r for r in s.db.spine_stub_rows(sp["id"]) if r["driver"] == "sp_L3_inv1")
    tracks = [c for k, c in enumerate(s.db.track_positions("IA", "y")) if k % 8 in (2, 6)]
    line = min(tracks, key=lambda c: abs(c - (y1 - 4)))       # the stub's line on a track
    other = min((c for c in tracks if c != line), key=lambda c: abs(c - line))
    with s.db.conn:
        s.db.conn.execute("UPDATE spine_stub SET points = ? WHERE id = ?",
                          (f"{x - 12} {line} {x + 12} {line}", st["id"]))   # in the die
    s.eval("route_pin -inst sp_L3_inv1 -spec_name horizontal_routing")
    w = s.db.pin_wire_row("sp_L3_inv1", "Y")
    lo, hi = sorted((other - 0.36, max(float(w["rect"].split()[3]), other + 0.36)))
    s.db.set_wire_rect("pin_wire", w["id"], f"{w['rect'].split()[0]} {lo} "
                       f"{w['rect'].split()[2]} {hi}")         # over the other track only
    out_of(s)
    grid = route_net.Grid(s.db, route_net._rule_layers(s.db, "r"))
    plan = plan_stubs(s.db, grid, sp)
    assert plan.tracks[st["name"]] == [pytest.approx(other)]


AUTO = """pin_routing:
  vertical_routing:
    routing_direction: vertical
    nets: [VSS, VDD_SOC, SIGNAL, VSS, SIGNAL, VDD_SOC]
  horizontal_routing:
    routing_direction: horizontal
    width: 0.5
    nets: [VSS, SIGNAL, SIGNAL, VDD_SOC]
"""


def test_spec_name_auto_picks_by_the_way_the_nets_run(placed, write_lef):
    # u1 -> u2 -> u3 along x (an arm), u3 -> u4 along y: u2's nets run along x,
    # u4's along y; u3 has one of each, x the longer (40 against 30)
    s = placed
    for name, at in (("u2", "40 0"), ("u3", "80 0"), ("u4", "80 30")):
        s.eval(f"create_inst -ref_cell INV_RP -location {{{at}}} -name {name}")
    s.eval("connect_pin -from u1/Y -to u2/A")
    s.eval("connect_pin -from u2/Y -to u3/A")
    s.eval("connect_pin -from u3/Y -to u4/A")
    s.eval(f"read_pin_spec -file {write_lef(AUTO, 'a.yaml')}")
    out_of(s)
    s.eval("route_pin -inst {u2 u3 u4} -spec_name auto")
    text = out_of(s)
    assert s.eval("get_db inst:u2 .pin_spec") == "horizontal_routing"
    assert s.eval("get_db inst:u3 .pin_spec") == "horizontal_routing"
    assert s.eval("get_db inst:u4 .pin_spec") == "vertical_routing"
    assert "-spec_name auto: horizontal_routing for 2 instance(s), their nets run " \
           "horizontally: u2 u3" in text
    assert "-spec_name auto: vertical_routing for 1 instance(s), their nets run " \
           "vertically: u4" in text
    assert len(s.db.strap_rows("u2")) == 4 and len(s.db.strap_rows("u4")) == 6   # each spec's
    # a -spec file with no spec of the way u2's nets run: an error
    only = write_lef(AUTO.split("  horizontal_routing")[0], "v.yaml")
    assert "u2's nets run horizontally and no named spec has routing_direction horizontal" \
        in err(s, f"route_pin -inst u2 -spec {only} -spec_name auto")
