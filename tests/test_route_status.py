"""route_status: fixed nets and stubs, whose routes no routing command
changes."""

import io
import sqlite3

import pytest

pytest.importorskip("scipy")

from core.htree_builder import Session
from test_copy_obj import routed  # noqa: F401  (the fixture)
from test_move_spine import build
from test_route_net import err, out_of

L1 = "sp_L1_inv1_Y"
L2 = "sp_L2_inv1_Y"


def rows(s, net):
    return [tuple(r) for r in s.db.net_wire_rows(net) + s.db.stub_wire_rows(net)]


def status(s, handle):
    return s.eval(f"get_db {handle} .route_status")


def held(text, cmd, n, what):
    return f"**WARN: (HT4-286): {cmd}: {n} {what} left as they are, route_status fixed " \
           f"(set_db .route_status routed frees them)" in text


def test_the_attribute(tech_session, write_lef):
    s = build(tech_session, write_lef, mirror=True)
    assert status(s, f"spine_net:sp/{L1}") == "unrouted"
    assert status(s, "stub:sp/stub1") == "unrouted"
    for inst in s.split_list(s.eval("get_db insts .name")):
        s.eval(f"route_pin -inst {inst}")
    s.eval("create_route_rule -name r -layer {IA IB} -width 0.36 -spacing 0.36")
    s.eval(f"route_net -net {L1} -rule r")
    assert status(s, f"spine_net:sp/{L1}") == "routed"
    assert set(s.split_list(s.eval("get_db nets .route_status"))) == {"routed", "unrouted"}
    s.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    assert status(s, f"spine_net:sp/{L1}") == "fixed"
    assert status(s, "stub:sp/stub1") == "unrouted"        # a stub is keyed apart
    s.eval("set_db stub:sp/stub1 .route_status fixed")
    assert status(s, "stub:sp/stub1") == "fixed"
    s.eval(f"set_db [get_db nets {L1}] .route_status routed")
    assert status(s, f"spine_net:sp/{L1}") == "routed"
    assert "HT4-141" in err(s, f"set_db spine_net:sp/{L1} .route_status unrouted")
    assert "HT4-141" in err(s, f"set_db spine_net:sp/{L1} .route_status maybe")


def test_routing_commands_leave_a_fixed_net(routed):
    s = routed
    s.eval(f"set_db [concat [get_db nets {L1}] [get_db nets sp_mirror_L1_inv1_Y]] "
           f".route_status fixed")
    keep = rows(s, L1)
    other = rows(s, L2)
    out_of(s)
    s.eval("route_net -net [get_db nets .name] -rule r -shield")
    text = out_of(s)
    assert held(text, "route_net", 2, "fixed net(s)")
    assert f"route_status fixed (set_db .route_status routed frees them): {L1} " \
           f"sp_mirror_L1_inv1_Y" in text
    assert rows(s, L1) == keep and rows(s, L2) != [] and "HT4-174" not in text
    s.eval(f"route_track -net {L1} -rule r -compact")
    assert held(out_of(s), "route_track", 1, "fixed net(s)") and rows(s, L1) == keep
    s.eval(f"delete_route -nets {{{L1} {L2}}}")
    text = out_of(s)
    assert held(text, "delete_route", 1, "fixed net(s)")
    assert rows(s, L1) == keep and not [r for r in rows(s, L2) if not r[3].startswith("stub")]


def test_a_fixed_stub(routed):
    s = routed
    leaf = s.eval("get_db stub:sp/stub1 .net").partition("/")[2]
    stub = [r for r in rows(s, leaf) if r[3].startswith("stub")]
    assert stub
    s.eval("set_db stub:sp/stub1 .route_status fixed")
    out_of(s)
    s.eval("route_final_stub -rule r -shield")
    text = out_of(s)
    assert held(text, "route_final_stub", 1, "fixed stub(s)") and "stub:sp/stub1" in text
    assert [r for r in rows(s, leaf) if r[3].startswith("stub")] == stub
    s.eval("delete_route -nets stub:sp/stub1")
    assert held(out_of(s), "delete_route", 1, "fixed net(s)")
    assert [r for r in rows(s, leaf) if r[3].startswith("stub")] == stub
    s.eval(f"delete_route -nets {leaf}")                   # the net is not fixed: it goes
    assert [r for r in rows(s, leaf) if r[3].startswith("stub")] == stub
    assert not [r for r in rows(s, leaf) if not r[3].startswith("stub")]


def test_wire_edits_leave_a_fixed_net(routed):
    s = routed
    s.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    keep = rows(s, L1)
    wire = next(f"net_wire:{L1}/{r[2]}" for r in keep if r[3] == "wire")
    ext = next(f"net_wire:{L1}/{r[2]}" for r in keep if r[3] == "cross")
    free = next(f"net_wire:{L2}/{r[2]}" for r in rows(s, L2) if r[3] == "wire")
    strap = next(f"strap:{r['inst']}/{r['seq']}" for r in s.db.strap_rows() if r["net"] == L1)
    out_of(s)
    assert s.eval(f"move_wire -wires {{{wire} {ext} {free}}} -delta {{0 0.72}}") == free
    assert held(out_of(s), "move_wire", 2, "wire(s) of fixed nets")
    s.eval(f"move_wire -wires {wire} -next_track left")
    assert held(out_of(s), "move_wire", 1, "wire(s) of fixed nets")
    assert s.eval(f"stretch_wire -wire {strap} -edge right -to 90") == ""
    assert held(out_of(s), "stretch_wire", 1, "wire(s) of fixed nets")
    # delete_wire (the GUI's Delete) deletes what it is given, fixed or not
    s.eval(f"delete_wire -wires {{{wire} {strap}}}")
    text = out_of(s)
    assert "delete_wire: deleted 2 wire(s), 2 of them of fixed nets (they stay fixed): " \
           f"{wire} {strap}" in text and "HT4-286" not in text
    assert wire not in [f"net_wire:{L1}/{r[2]}" for r in rows(s, L1)]
    assert s.eval(f"get_db spine_net:sp/{L1} .route_status") == "fixed"
    s.eval("delete_wire -undo")                            # back as they were
    out_of(s)
    assert rows(s, L1) == keep
    straps = [tuple(r) for r in s.db.strap_rows() if r["net"] == L1]
    inst = straps[0][1]
    s.eval(f"route_pin -inst {inst}")
    assert held(out_of(s), "route_pin", 1, "instance(s) with pin routes on fixed nets")
    assert [tuple(r) for r in s.db.strap_rows() if r["net"] == L1] == straps


def test_insert_vias_adds_none_on_a_fixed_net(routed):
    s = routed
    box = next(f"net_wire:{L1}/{r[2]}" for r in rows(s, L1) if r[3] == "cross")
    s.eval(f"delete_wire -wires {box}")                    # a crossing without its via
    s.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    keep = rows(s, L1)
    out_of(s)
    s.eval(f"insert_vias -bottom_layer IA -top_layer IB -nets {L1}")
    text = out_of(s)
    assert "(HT4-286): insert_vias: 1 wire(s) of fixed nets with crossings that would get a " \
           "via left as they are" in text
    assert rows(s, L1) == keep
    assert not [r for r in s.db.net_wire_rows() if r["net"].startswith(f"auto_via:net_wire:{L1}")]
    s.eval(f"set_db spine_net:sp/{L1} .route_status routed")
    s.eval(f"insert_vias -bottom_layer IA -top_layer IB -nets {L1}")
    assert "Inserted      : 2 via(s)" in out_of(s)        # each crossing of the net
    # fixed again: its inserted vias are not removed and made again
    s.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    mine = lambda: [tuple(r) for r in s.db.net_wire_rows()           # noqa: E731
                    if r["kind"] == "insert_via" and r["shield_net"] == L1]
    keep = mine()
    out_of(s)
    s.eval(f"insert_vias -bottom_layer IA -top_layer IB -nets {L1}")
    assert mine() == keep and "Removed" not in out_of(s)


def test_a_spine_with_a_fixed_net_is_not_bent(routed):
    s = routed
    s.eval(f"set_db spine_net:sp/{L2} .route_status fixed")
    keep = rows(s, L2)
    assert f"move_spine_to_boundary: spine sp has 1 net(s) with route_status fixed, whose " \
           f"routes the move would remove: {L2}; nothing changed" in \
           err(s, "move_spine_to_boundary -spine sp -moves {head top up 5}")
    assert rows(s, L2) == keep


def test_kept_in_the_database_and_copied(routed, tmp_path):
    s = routed
    s.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    s.eval("set_db stub:sp/stub2 .route_status fixed")
    s.eval("copy_obj -from sp -name cp -x_shift 11.52")
    assert status(s, "spine_net:cp/cp_L1_inv1_Y") == "fixed"
    assert status(s, "stub:cp/stub2") == "fixed" and status(s, "stub:cp/stub1") == "routed"
    path = tmp_path / "f.db"
    s.eval(f"write_db -file {path}")
    other = Session(out=io.StringIO())
    other.eval(f"read_db -file {path}")
    assert status(other, f"spine_net:sp/{L1}") == "fixed"
    con = sqlite3.connect(path)                            # as written before route_status
    with con:
        con.execute("DROP TABLE net_route_status")
        con.execute("UPDATE meta SET value = '23' WHERE key = 'schema_version'")
    con.close()
    other.eval(f"read_db -file {path}")
    assert status(other, f"spine_net:sp/{L1}") == "routed"
    other.eval(f"set_db spine_net:sp/{L1} .route_status fixed")
    assert status(other, f"spine_net:sp/{L1}") == "fixed"


def fixed_wire(s, net=L2):
    """Move the net's IB wire one signal track right (onto the free 76.68) and
    fix it; returns its handle and rect."""
    w = next(r for r in s.db.net_wire_rows(net) if r["kind"] == "wire" and r["layer"] == "IB")
    handle = f"net_wire:{net}/{w['seq']}"
    s.eval(f"move_wire -wires {handle} -next_track right")
    s.eval(f"set_db {handle} .route_status fixed")
    out_of(s)
    return handle, s.db.net_wire_row(net, w["seq"])["rect"]


def test_a_wire_fixed_alone(routed):
    s = routed
    handle, rect = fixed_wire(s)
    assert rect == "76.5 107.7 76.86 129.42"
    assert status(s, handle) == "fixed" and status(s, f"spine_net:sp/{L2}") == "routed"
    other = next(f"net_wire:{L2}/{r['seq']}" for r in s.db.net_wire_rows(L2)
                 if r["kind"] == "cross")
    assert "is a cross: .route_status is set on route_net wires (kind wire) one by one" in \
        err(s, f"set_db [list {handle} {other}] .route_status fixed")
    assert status(s, other) == "routed"                    # nothing was set
    s.eval(f"move_wire -wires {handle} -delta {{0.72 0}}")
    assert held(out_of(s), "move_wire", 1, "wire(s) of fixed nets")
    s.eval(f"delete_wire -wires {handle}")                  # by hand: it goes, fixed or not
    assert "1 of them of fixed nets" in out_of(s)
    s.eval("delete_wire -undo")
    assert status(s, handle) == "fixed"                      # back, still fixed
    s.eval(f"delete_route -nets {L2}")                      # the rest goes, the fixed wire stays
    assert [r["rect"] for r in s.db.net_wire_rows(L2) if r["kind"] != "stub"] == [rect]
    s.eval(f"set_db {handle} .route_status routed")
    s.eval(f"delete_route -nets {L2}")
    assert not [r for r in s.db.net_wire_rows(L2) if r["kind"] != "stub"]


def test_route_net_joins_the_fixed_wire(routed):
    s = routed
    handle, rect = fixed_wire(s)
    s.eval(f"route_net -net {L2} -rule r -shield")
    text = out_of(s)
    assert f"    fixed wire {handle}: kept; the route joins it at {{76.68 111.24}}" in text
    rows = s.db.net_wire_rows(L2)
    assert s.db.net_wire_row(L2, int(handle.rpartition("/")[2]))["rect"] == rect
    wires = [r["rect"] for r in rows if r["kind"] == "wire"]
    assert wires == [rect]                    # the loads are taken on it: no wire over it
    assert len([r for r in rows if r["kind"] == "cross"]) == 3      # driver and two loads
    s.eval("check_drc")
    assert not [l for l in out_of(s).splitlines() if L2 in l and "no path" in l]
    s.eval(f"route_net -net {L2} -rule r")                 # again: the same
    assert [r["rect"] for r in s.db.net_wire_rows(L2) if r["kind"] == "wire"] == [rect]


def test_a_fixed_wire_off_the_tracks_is_left_apart(routed):
    s = routed
    w = next(r for r in s.db.net_wire_rows(L2) if r["kind"] == "wire" and r["layer"] == "IB")
    handle = f"net_wire:{L2}/{w['seq']}"
    s.eval(f"move_wire -wires {handle} -delta {{1.0 0}}")
    s.eval(f"set_db {handle} .route_status fixed")
    out_of(s)
    s.eval(f"route_net -net {L2} -rule r")
    text = out_of(s)
    assert f"**WARN: (HT4-287): {L2}: fixed wire {handle} is not on a signal track of IA or " \
           f"IB (or every track crossing on it is blocked): the route does not join it; it " \
           f"stays as it is" in text
    assert len([r for r in s.db.net_wire_rows(L2) if r["kind"] == "wire"]) == 2


def test_a_fixed_wire_is_copied_fixed(routed):
    s = routed
    handle, _ = fixed_wire(s)
    s.eval("copy_obj -from sp -name cp -x_shift 11.52")
    assert status(s, handle.replace("sp_", "cp_")) == "fixed"


def test_a_via_steps_to_the_next_track(routed):
    """move_wire takes a via (via:<net>/<n>) as its crossing box: alone, it
    steps onto the next signal track of the layer whose tracks run across
    the move. A via of a pin does not move by itself."""
    from core import vias
    s = routed
    cross = next(r for r in vias.rows(s.db, L1) if r["kind"] == "cross")
    via, box = vias.handle(cross), cross["source"]
    x, y = cross["x"], cross["y"]
    assert s.eval(f"move_wire -wires {via} -next_track right") == box
    assert f"{box} (crossing box, IB signal track): x {x:g} -> {x + 2.88:g}" in out_of(s)
    moved = next(r for r in vias.rows(s.db, L1) if r["source"] == box)
    assert (moved["x"], moved["y"]) == (pytest.approx(x + 2.88), pytest.approx(y))
    s.eval(f"move_wire -wires {box} -next_track left")
    back = next(r for r in vias.rows(s.db, L1) if r["source"] == box)
    assert (back["x"], back["y"]) == (pytest.approx(x), pytest.approx(y))
    pin = next(r for r in vias.rows(s.db, L1) if r["kind"] == "pin")
    assert "is the via of a pin" in err(s, f"move_wire -wires {vias.handle(pin)} -next_track up")


def test_force_routes_a_fixed_net_on_to_its_new_pin(routed):
    """-force: the fixed net keeps every shape; only the pin connect_pin put
    on it is routed, from the route there is."""
    s = routed
    leaf = "sp_L3_inv1_Y"
    s.eval(f"set_db spine_net:sp/{leaf} .route_status fixed")
    s.eval("create_inst -name extra -ref_cell INV_RP -location {84 112}")
    s.eval("route_pin -inst extra")
    s.eval(f"connect_pin -from sp_L3_inv1/Y -to extra/A")
    before = {(r["kind"], r["layer"], r["rect"]) for r in s.db.net_wire_rows(leaf) +
              s.db.stub_wire_rows(leaf)}
    straps = {(r["inst"], r["seq"]): r["rect"] for r in s.db.strap_rows() if r["net"] == leaf}
    out_of(s)
    s.eval(f"route_net -net {leaf} -rule r")
    assert held(out_of(s), "route_net", 1, "fixed net(s)")       # without -force: left
    s.eval(f"route_net -net {leaf} -rule r -force")
    text = out_of(s)
    assert "-force: 1 fixed net(s) keep every shape" in text
    assert "shape(s) added to the fixed net" in text and "to extra/A" in text
    after = {(r["kind"], r["layer"], r["rect"]) for r in s.db.net_wire_rows(leaf) +
             s.db.stub_wire_rows(leaf)}
    assert before < after                                      # all kept, some added
    assert {k for k, _, _ in after - before} <= {"wire", "cross"}
    assert all(s.db.strap_row(i, k)["rect"] == r for (i, k), r in straps.items())
    assert s.db.strap_row("extra", s.db.pin_wire_row("extra", "A")["strap"])["net"] == leaf
    assert s.eval(f"get_db spine_net:sp/{leaf} .route_status") == "fixed"
    # again: nothing to add
    s.eval(f"route_net -net {leaf} -rule r -force")
    assert "every pin is on its route already; nothing added" in out_of(s)


def test_route_and_unfixed_free_a_net_as_routed(routed):
    s = routed
    for word in ("route", "unfixed", "free", "ROUTED"):
        s.eval(f"set_db [get_db nets] .route_status fixed")
        assert s.db.fixed_nets()
        s.eval(f"set_db [get_db nets] .route_status {word}")
        assert not s.db.fixed_nets(), word
    assert "must be fixed" in err(s, "set_db [get_db nets] .route_status open")
