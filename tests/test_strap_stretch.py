"""A route lengthens the route_pin strap it reaches (route_net to a signal
track, route_net -shield to a shield, optimize_pg_connection): the strap is
stretched, one shape on its own y, with no piece of metal beside it. Routing
the net again or deleting its route takes the stretch back; route_pin making
the straps again drops them and names the nets to route again."""

import io

import pytest

pytest.importorskip("scipy")

from core import db as dbmod
from core.htree_builder import Session
from test_route_net import DEF, err, out_of, spine  # noqa: F401  (spine is a fixture)

NET = "sp_L1_inv1_Y"


def floats(text):
    return tuple(float(v) for v in text.split())


def stretched(s):
    """{(inst, seq): (rect, base rect)} of the straps routes lengthened."""
    return {(r["inst"], r["seq"]): (floats(r["rect"]), floats(r["base_rect"]))
            for r in s.db.strap_rows() if r["base_rect"]}


def test_a_route_lengthens_its_straps(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    out_of(s)
    assert not [r for r in s.db.net_wire_rows() if r["kind"] in dbmod.STRETCH_KINDS]
    got = stretched(s)
    assert set(got) == {("sp_L1_inv1", 3), ("sp_L2_inv1", 5)}
    for (inst, seq), (rect, base) in got.items():
        pieces = [r for r in s.db.stretch_rows(owner=NET) if (r["inst"], r["seq"]) == (inst, seq)]
        assert len(pieces) == 2                            # left and right
        assert rect == (min(r["x1"] for r in pieces), base[1], max(r["x2"] for r in pieces),
                        base[3])                           # one shape, on its own y
        assert all(r["kind"] == "extension" for r in pieces)
        # its crossing boxes lie on the strap's y
        boxes = [floats(r["rect"]) for r in s.db.net_wire_rows(NET) if r["kind"] == "cross"
                 and rect[0] <= floats(r["rect"])[0] and floats(r["rect"])[2] <= rect[2]
                 and floats(r["rect"])[1] < rect[3] and floats(r["rect"])[3] > rect[1]]
        assert boxes and all((b[1], b[3]) == (rect[1], rect[3]) for b in boxes)
    # routed again: the same stretches, not more; deleted: the straps as route_pin made them
    s.eval(f"route_net -net {NET} -rule r")
    assert stretched(s) == got and len(s.db.stretch_rows(owner=NET)) == 4
    s.eval(f"delete_route -nets {NET}")
    assert stretched(s) == {} and s.db.stretch_rows() == []
    assert floats(s.db.strap_row("sp_L1_inv1", 3)["rect"]) == got[("sp_L1_inv1", 3)][1]


def test_route_pin_drops_the_stretches_and_names_the_nets(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    out_of(s)
    s.eval("route_pin -inst sp_L2_inv1")
    text = out_of(s)
    assert f"the old straps of sp_L2_inv1 were lengthened by the routes of {NET}: route them " \
           f"again (route_net -net {{{NET}}})" in text
    assert s.db.stretch_rows(inst="sp_L2_inv1") == []
    assert not [r for r in s.db.strap_rows("sp_L2_inv1") if r["base_rect"]]
    assert s.db.stretch_rows(inst="sp_L1_inv1")             # the other cell keeps its own
    s.eval(f"route_net -net {NET} -rule r")
    assert ("sp_L2_inv1", 5) in stretched(s)


def test_a_move_and_a_rename_take_the_stretches_along(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    before = stretched(s)[("sp_L1_inv1", 3)]
    s.db.move_insts(["sp_L1_inv1"], 0.5, 0.25, pin_routes=True)
    rect, base = stretched(s)[("sp_L1_inv1", 3)]
    assert rect == pytest.approx(tuple(v + d for v, d in zip(before[0], (0.5, 0.25) * 2)))
    assert base == pytest.approx(tuple(v + d for v, d in zip(before[1], (0.5, 0.25) * 2)))
    s.eval("rename_obj -from sp_L1_inv1 -to root")
    assert ("root", 3) in stretched(s) and s.db.stretch_rows(inst="sp_L1_inv1") == []
    s.eval(f"rename_obj -from {NET} -to root_out")
    assert s.db.stretch_rows(owner=NET) == [] and len(s.db.stretch_rows(owner="root_out")) == 4


def test_a_piece_lengthens_only_a_strap_of_its_net(spine):
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    for r in s.db.stretch_rows():
        assert s.db.strap_row(r["inst"], r["seq"])["net"] == r["owner"]
    # a piece on no strap of its net (another net's strap there) stays a wire
    other = s.db.strap_rows("sp_L1_inv1")[0]
    x1, y1, x2, y2 = floats(other["rect"])
    piece = f"{x2} {y1} {x2 + 0.5} {y2}"
    s.db.set_net_wires("lone", [("extension", other["layer"], piece)])
    assert [r["rect"] for r in s.db.net_wire_rows("lone")] == [piece]
    assert s.db.stretch_rows(owner="lone") == []


def test_old_pieces_become_stretches_on_read(spine, tmp_path, monkeypatch):
    """A file of before stretches: its pieces lengthen their straps when it is
    read, and a crossing box left off the strap (the strap made again a little
    higher after the route, as route_pin can) goes onto the strap's y."""
    s = spine
    monkeypatch.setattr(dbmod, "STRETCH_KINDS", ())         # pieces, as written before
    s.eval(f"route_net -net {NET} -rule r")
    monkeypatch.undo()
    pieces = [r for r in s.db.net_wire_rows(NET) if r["kind"] == "extension"]
    assert len(pieces) == 4 and s.db.stretch_rows() == []
    strap = s.db.strap_row("sp_L1_inv1", 3)
    x1, y1, x2, y2 = floats(strap["rect"])
    with s.db.conn:              # the strap 0.016 lower than its route's pieces and boxes
        s.db.conn.execute("UPDATE strap SET rect = ? WHERE id = ?",
                          (f"{x1} {y1 - 0.016} {x2} {y2 - 0.016}", strap["id"]))
    path = tmp_path / "old.db"
    s.eval(f"write_db -file {path}")
    fresh = Session(out=io.StringIO())
    fresh.eval(f"read_db -file {path}")
    assert not [r for r in fresh.db.net_wire_rows() if r["kind"] == "extension"]
    assert len(fresh.db.stretch_rows(owner=NET)) == 4
    row = fresh.db.strap_row("sp_L1_inv1", 3)
    rect = floats(row["rect"])
    assert (rect[1], rect[3]) == pytest.approx((y1 - 0.016, y2 - 0.016))   # its own y
    assert rect[0] < x1 and rect[2] > x2                                # lengthened
    boxes = [floats(r["rect"]) for r in fresh.db.net_wire_rows(NET) if r["kind"] == "cross"
             and rect[0] <= floats(r["rect"])[0] and floats(r["rect"])[2] <= rect[2]
             and abs((floats(r["rect"])[1] + floats(r["rect"])[3]) / 2 - (y1 + y2) / 2) < 0.1]
    assert boxes and all((b[1], b[3]) == pytest.approx((rect[1], rect[3])) for b in boxes)


def test_write_def_writes_the_strap_as_one_shape(spine, tmp_path):
    from test_route_net import def_block, def_rect
    s = spine
    s.eval(f"route_net -net {NET} -rule r")
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    block = def_block((tmp_path / "o.def").read_text(), NET)
    for inst, seq in (("sp_L1_inv1", 3), ("sp_L2_inv1", 5)):
        row = s.db.strap_row(inst, seq)
        assert def_rect("FIXED", row["layer"], row["rect"]) in block
        assert def_rect("FIXED", row["layer"], row["base_rect"]) not in block
