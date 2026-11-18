"""copy_obj: a built spine copied, with its cells, pin routes, stubs and
routing, under a new name and shifted."""

import pytest

pytest.importorskip("scipy")

from core import vias
from core.commands import copy_obj
from test_move_spine import build
from test_route_net import err, out_of

ALL = "[get_db nets .name]"
SHIFT = 11.52          # two periods of the 8-track pattern of 0.72 tracks


@pytest.fixture
def routed(tech_session, write_lef):
    """The mirrored spine of test_move_spine, pins routed, nets and stubs
    routed with shields: tracks at x 70.92 .. 79.56. No DEF rows, so the
    legal step is the track period alone (5.76)."""
    s = build(tech_session, write_lef, mirror=True, rows=False)
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval(f"route_net -net {ALL} -rule r -shield")
    s.eval("route_final_stub -rule r -shield")
    out_of(s)
    return s


def shifted(rect, dx, dy):
    v = [float(c) for c in rect.split()]
    return tuple(round(c + (dy if k % 2 else dx), 6) for k, c in enumerate(v))


def shapes(s, table, key, owner):
    rect = lambda r: tuple(round(float(c), 6) for c in r["rect"].split())
    return sorted((r[key].replace(owner, "@", 1), r["net"].replace(owner, "@", 1), r["layer"],
                   rect(r)) for r in s.db.conn.execute(f"SELECT * FROM {table}")
                  if r[key].startswith(owner) or r[key].startswith("pg:" + owner))


def test_the_copy_is_the_spine_shifted_and_renamed(routed):
    s = routed
    before = {t: shapes(s, t, k, "sp_") for t, k in
              (("strap", "inst"), ("pin_wire", "inst"), ("net_wire", "net"))}
    assert s.eval(f"copy_obj -from [get_db spine sp] -name cp -x_shift {SHIFT}") == "spine:cp"
    text = out_of(s)
    assert "Copied spine:sp to spine:cp (x 11.52, y 0): 8 instance(s), 8 net(s), 56 strap(s), " \
           "32 pin wire(s), 30 routed shape(s) (wires, crossing boxes, shields, stubs), " \
           "28 strap stretch(es)" in text
    assert "HT4-282" not in text                 # on its tracks
    assert "HT4-204" not in text and "HT4-203" not in text and "HT4-284" not in text
    # the original is unchanged; every shape of the copy is one of it, shifted
    for (table, key), want in zip((("strap", "inst"), ("pin_wire", "inst"),
                                   ("net_wire", "net")), before.values()):
        assert shapes(s, table, key, "sp_") == want
        copy = shapes(s, table, key, "cp_")
        moved = sorted((o, n.replace("sp_", "@", 1) if n.startswith("sp_") else n, lay,
                        shifted(" ".join(map(str, r)), SHIFT, 0)) for o, n, lay, r in want)
        assert copy == [(o, n, lay, r) for o, n, lay, r in moved] and copy
    # a spine like a built one: its nets, stubs, location and pins
    assert s.eval("get_db spine:cp .location") == "81.52 100"
    assert s.eval("get_db spine:cp .stubs").split()[0] == "stub:cp/stub1"
    assert s.eval("get_db pin:cp_L2_inv1/A .net") == "spine_net:cp/cp_L1_inv1_Y"
    # its own root net, as a spine built by create_spine has (spec root_net: net)
    assert s.eval("get_db pin:cp_L1_inv1/A .net") == "net:cp_primary_input"
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == "net:sp_primary_input"
    assert s.eval("get_db spine_net:cp/cp_L1_inv1_Y .route_rule") == "route_rule:r"
    vias.sync(s.db)
    for net in ("L1_inv1_Y", "L3_inv2_Y", "mirror_L2_inv1_Y"):
        a = s.eval(f"llength [get_db spine_net:sp/sp_{net} .vias]")
        assert s.eval(f"llength [get_db spine_net:cp/cp_{net} .vias]") == a != "0"
    # no short between the two (the copy has the original's own, between its roots)
    s.eval("check_drc")
    text = out_of(s)
    assert "  short     -       IA      12" in text      # 6 in each: its overlapping cells
    assert not [l for l in text.splitlines() if "sp_" in l and "cp_" in l]


def test_the_copy_routes_and_moves_as_a_spine(routed):
    s = routed
    s.eval(f"copy_obj -from sp -name cp -x_shift {SHIFT}")
    out_of(s)
    copied = shapes(s, "net_wire", "net", "cp_")
    s.eval("move_obj -direction right -distance 5.76 cp")
    assert shapes(s, "net_wire", "net", "cp_") == sorted(
        (o, n, lay, shifted(" ".join(map(str, r)), 5.76, 0)) for o, n, lay, r in copied)
    s.eval("delete_route -nets [get_db spine:cp .spine_nets]")    # the stubs stay
    routes = lambda owner: [r for r in s.db.net_wire_rows() if r["net"].startswith(owner)
                            and not r["kind"].startswith("stub")]
    assert not routes("cp_") and routes("sp_")
    s.eval("route_net -net {cp_*} -rule r -shield")
    assert "HT4-174" not in out_of(s)
    assert len(routes("cp_")) == len(routes("sp_"))


@pytest.mark.parametrize("given, want", [("1", 5.76), ("7", 5.76), ("9", 11.52),
                                         ("-3", -5.76), ("11.52", 11.52), ("0", 0)])
def test_a_shift_snaps_to_whole_track_periods(routed, given, want):
    s = routed
    s.eval(f"copy_obj -from sp -name a -x_shift 0 -y_shift {given}")
    text = out_of(s)
    assert s.eval("get_db spine:a .location") == f"70 {100 + want:g}"
    snapped = f"**WARN: (HT4-282): copy_obj: -y_shift {given} snapped to {want:g}, the nearest " \
              f"whole number of the legal step 5.76 (track period 5.76): signal wires on " \
              f"signal tracks, shields on their nets' tracks, cells on sites"
    assert (snapped in text) == (float(given) != want)
    # every copied wire on a track of its own net: the shapes are the original's
    sp = sorted((o, n, lay, shifted(" ".join(map(str, r)), 0, want))
                for o, n, lay, r in shapes(s, "net_wire", "net", "sp_"))
    assert shapes(s, "net_wire", "net", "a_") == sp and sp


# rows of 0.24 sites (the x step is then 5.76, as the tracks), 1.778 apart, N
# and FS in turn (the y step: 5.76 and 3.556, 5120.64)
ROWS = "".join(f"ROW r{k} core 0 {k * 1778} {'N' if k % 2 == 0 else 'FS'} DO 400 BY 1 STEP 240 0 ;\n"
               for k in range(112))


@pytest.fixture
def placed(tech_session, write_lef, monkeypatch):
    """The mirrored spine on sites of 0.24 rows, pins routed."""
    import test_move_spine
    monkeypatch.setattr(test_move_spine, "ROWS", ROWS)
    s = build(tech_session, write_lef, mirror=True)
    s.eval("legalize_placement -inst [get_db insts]")
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    out_of(s)
    assert all(copy_obj._on_site(s.db, n) for n in s.db.inst_names())
    return s


def test_the_step_keeps_the_cells_on_their_sites(placed):
    """The cells move with their pin routes by the one shift and land on
    sites; they are never moved on their own."""
    s = placed
    s.eval("copy_obj -from sp -name a -x_shift 13")
    text = out_of(s)
    assert "copy_obj: -x_shift 13 snapped to 11.52, the nearest whole number of the legal " \
           "step 5.76 (track period 5.76, site step 0.24)" in text
    assert "HT4-283" not in text and "HT4-203" not in text
    assert all(copy_obj._on_site(s.db, n) for n in s.db.inst_names())
    for table in ("strap", "pin_wire"):
        assert shapes(s, table, "inst", "a_") == sorted(
            (o, n, lay, shifted(" ".join(map(str, r)), 11.52, 0))
            for o, n, lay, r in shapes(s, table, "inst", "sp_"))
    s.eval("copy_obj -from sp -name b -y_shift 1")
    assert "-y_shift 1 snapped to 5120.64, the nearest whole number of the legal step 5120.64 " \
           "(track period 5.76, site step 3.556)" in out_of(s)


def test_a_cell_off_its_site_stays_with_its_routes(placed):
    s = placed
    s.eval("move_obj -direction right -distance 0.1 sp_L2_inv1")
    out_of(s)
    s.eval("copy_obj -from sp -name a -x_shift 11.52")
    assert "**WARN: (HT4-283): copy_obj: 1 copied instance(s) not on a placement site of " \
           "their orientation, left where the shift put them (their routes go with them); 1 of " \
           "them because the original is not on one either: a_L2_inv1" in out_of(s)
    assert s.db.inst_row("a_L2_inv1")["x"] == \
        pytest.approx(s.db.inst_row("sp_L2_inv1")["x"] + 11.52)


def test_errors(routed):
    s = routed
    assert "HT4-001" in err(s, "copy_obj -from sp")
    assert "HT4-001" in err(s, "copy_obj -from sp -name x -x_shift left")
    assert "HT4-001" in err(s, "copy_obj -from sp -name {a b}")
    assert "HT4-280" in err(s, "copy_obj -from nope -name x")
    assert "HT4-280" in err(s, "copy_obj -from {sp sp} -name x")
    assert "HT4-281" in err(s, "copy_obj -from sp -name sp")
    s.eval("create_inst -name x_L1_inv1 -ref_cell INV_RP -location {10 150}")
    assert "copy_obj: the copy's names are taken: x_L1_inv1" in err(s, "copy_obj -from sp -name x")
    assert s.db.spine_names() == ["sp"]


def test_an_unrouted_spine_copies_what_it_has(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True, rows=False)
    s.eval("copy_obj -from sp -name cp -y_shift 5.76")
    assert "8 instance(s), 8 net(s), 0 strap(s), 0 pin wire(s), 0 routed shape(s)" in out_of(s)
    assert [r["name"] for r in s.db.spine_stub_rows(s.db.spine_row("cp")["id"])] == \
           [r["name"] for r in s.db.spine_stub_rows(s.db.spine_row("sp")["id"])]
    sp, cp = (s.db.spine_net_rows(s.db.spine_row(n)["id"]) for n in ("sp", "cp"))
    assert [shifted(a["route"].replace(";", " "), 0, 5.76) for a in sp] == \
           [tuple(float(c) for c in b["route"].replace(";", " ").split()) for b in cp]


def test_power_wires_and_auto_vias_on_the_spine_are_copied(routed):
    """Every owner form of the optimize_pg_connection wires and the auto vias
    (stretch_wire, insert_vias) of the spine's shapes."""
    s = routed
    box = "70 100 70.36 100.36"
    s.db.add_net_wires([("pg:sp_L1_inv1", "pg_ext", "IA", box, "VSS", None),
                        ("auto_via:strap:sp_L1_inv1/2", "via", "IA/IB", box, "VDD_SOC", None),
                        ("auto_via:pin_wire:sp_L1_inv1/Y", "via", "H2/IA", box, "sp_L1_inv1_Y",
                         None),
                        ("auto_via:net_wire:sp_L1_inv1_Y/1", "insert_via", "IA/IB", box,
                         "sp_L1_inv1_Y", "V1"),
                        ("auto_via:net_wire:pg:sp_L1_inv1/1", "via", "IA/IB", box, "VSS", None),
                        ("auto_via:net_wire:VSS/1", "via", "IA/IB", box, "VSS", None)])
    s.eval(f"copy_obj -from sp -name cp -x_shift {SHIFT}")
    assert "35 routed shape(s)" in out_of(s)        # 30 + the 5 of the spine (not VSS)
    got = {(r["net"], r["kind"], r["layer"], r["rect"], r["shield_net"], r["via_def"])
           for r in s.db.net_wire_rows() if "cp_" in r["net"]}
    moved = "81.52 100 81.88 100.36"
    assert {g for g in got if g[0].startswith(("pg:", "auto_via:"))} == {
        ("pg:cp_L1_inv1", "pg_ext", "IA", moved, "VSS", None),
        ("auto_via:strap:cp_L1_inv1/2", "via", "IA/IB", moved, "VDD_SOC", None),
        ("auto_via:pin_wire:cp_L1_inv1/Y", "via", "H2/IA", moved, "cp_L1_inv1_Y", None),
        ("auto_via:net_wire:cp_L1_inv1_Y/1", "insert_via", "IA/IB", moved, "cp_L1_inv1_Y", "V1"),
        ("auto_via:net_wire:pg:cp_L1_inv1/1", "via", "IA/IB", moved, "VSS", None)}


def test_the_stubs_route_rules_and_wires_are_copied(routed):
    """A stub's route rule is kept under stub:<spine>/<stub>, apart from its
    leaf's net: the copy's stub has it under stub:<name>/<stub>."""
    s = routed
    s.eval("create_route_rule -name r2 -layer {IA IB} -width 0.36 -spacing 0.72")
    s.eval("set_db stub:sp/stub1 .route_rule r2")
    s.eval(f"copy_obj -from sp -name cp -x_shift {SHIFT}")
    assert s.eval("get_db stub:cp/stub1 .route_rule") == "route_rule:r2"
    assert s.eval("get_db stub:cp/stub2 .route_rule") == s.eval("get_db stub:sp/stub2 .route_rule")
    assert s.eval("get_db stub:sp/stub1 .route_rule") == "route_rule:r2"
    for stub in ("stub1", "stub2", "stub1_mirror"):
        a = s.split_list(s.eval(f"get_db stub:sp/{stub} .net_wires"))
        b = s.split_list(s.eval(f"get_db stub:cp/{stub} .net_wires"))
        assert len(a) == len(b) > 0
        assert [h.replace("net_wire:sp_", "net_wire:cp_") for h in a] == list(b)
