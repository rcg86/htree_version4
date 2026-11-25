"""The routing commands give the vias their definitions: route_pin, route_net,
route_track and route_final_stub assign each net, per layer pair it has a via
on and no assignment for, the definition that fits the most of its vias
(vias.auto_assign), so write_def writes every via."""

import pytest

pytest.importorskip("scipy")

from core import vias
from test_route_net import DEF, SPEC, def_block, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import CELL_LEF, out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import via_session  # noqa: F401  (a fixture: the tech with via definitions)


def build(s, write_lef):
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    out_of(s)
    return s


def assigned(s):
    return {(r["bottom"], r["top"], r["net"]): r["via_def"] for r in s.db.via_assignment_rows()}


def test_each_command_assigns_its_vias(via_session, write_lef, tmp_path):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    text = out_of(s)
    assert "route_pin: via definitions given to" in text
    assert ("D12", "H1", "VSS") in assigned(s)                   # the power pins' vias
    s.eval("route_net -net [get_db nets .name] -rule r")
    assert "route_net: via definitions given to" in out_of(s)
    assert assigned(s)[("IA", "IB", "sp_L1_inv1_Y")] in ("V_IA_IB", "V_IA_IB_2")
    s.eval("route_final_stub -rule r")
    out_of(s)
    rows = [r for r in vias.rows(s.db) if r["net"] != "SIGNAL"]
    assert rows and all(r["via_def"] for r in rows)          # every via has its definition
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    assert "HT4-183" not in out_of(s)
    text = (tmp_path / "o.def").read_text()
    for net in {r["net"] for r in rows}:                       # all of them written
        block = def_block(text, net)
        mine = [r for r in rows if r["net"] == net]
        assert sum(1 for line in block if " 0 ( " in line) == len(mine)
    # routed again: nothing more to assign, nothing printed
    s.eval("route_net -net sp_L1_inv1_Y -rule r")
    assert "via definitions given" not in out_of(s)


def test_route_track_assigns_too(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("assign_via_for_route -reset")
    s.eval("route_track -net [get_db nets .name] -rule r")
    assert "route_track: via definitions given to" in out_of(s)
    assert ("IA", "IB", "sp_L1_inv1_Y") in assigned(s)


def test_the_choice_fits_and_an_assignment_by_hand_stays(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("assign_via_for_route -via V_IA_IB_2")               # for every net, by hand
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    a = assigned(s)
    assert a[("IA", "IB", "")] == "V_IA_IB_2"
    assert not [k for k in a if k[:2] == ("IA", "IB") and k[2]]     # no net's own over it
    # each net's choice fits the most of its vias of the pair
    metal = vias.net_shapes(s.db)
    for (bottom, top, net), name in a.items():
        if not net:
            continue
        mine = [r for r in vias.rows(s.db, net) if (r["bottom"], r["top"]) == (bottom, top)]
        fit = lambda n: sum(vias.fits(vias.definition_shapes(s.db, n), metal.get(net, {}),
                                      r["bottom"], r["cut"], r["top"], r["x"], r["y"])
                            for r in mine)
        others = [n for n, st in vias.definition_layers(s.db).items()
                  if st[0] == bottom and st[2] == top]
        assert fit(name) == max(fit(n) for n in others) == len(mine)


def test_fits():
    # an IA wire (horizontal) across an IB wire (vertical), 0.36 wide, crossing at 0..0.36
    metal = {"IA": [(-5, 0, 5, 0.36)], "IB": [(0, -5, 0.36, 5)]}
    on = lambda shapes: vias.fits(shapes, metal, "IA", "C6", "IB", 0.18, 0.18)
    small = [("IA", "RECT", [-0.25, -0.15, 0.25, 0.15]), ("C6", "RECT", [-0.1, -0.1, 0.1, 0.1]),
             ("IB", "RECT", [-0.15, -0.25, 0.15, 0.25])]
    assert on(small)                             # each pad runs on along its wire
    assert not on([("IA", "RECT", [-0.15, -0.25, 0.15, 0.25])] + small[1:])  # off the IA wire
    assert not on([small[0], ("C6", "RECT", [-0.3, -0.1, 0.3, 0.1]), small[2]])  # cut past IB
    # a pin: a short shape; a pad longer than it does not fit, on two shapes it does
    pin = {"IA": [(0, 0, 0.4, 0.36)], "IB": [(0, -5, 0.36, 5)]}
    long_pad = [("IA", "RECT", [-0.15, -0.15, 0.3, 0.15])] + small[1:]   # x 0.03 .. 0.48
    assert not vias.fits(long_pad, pin, "IA", "C6", "IB", 0.18, 0.18)
    pin["IA"].append((0.35, 0, 0.6, 0.36))
    assert vias.fits(long_pad, pin, "IA", "C6", "IB", 0.18, 0.18)
    # the inside of a stack: no metal of the net on the layer, not looked at
    assert vias.fits([("G2", "RECT", [-1, -1, 1, 1])] + small, metal, "IA", "C6", "IB", 0.18,
                     0.18)
    assert vias.fits([("G2", "RECT", [-1, -1, 1, 1])], {}, "G1", "T1", "G2", 0, 0)


# V_IA_IB turned a quarter: its IA pad 0.3 wide and 0.4 tall, past a 0.36 IA wire;
# and one of 0.3 square pads, on the IB wire's end where the IA wire stops at its edge
TURNED = ("VIA V_IA_IB_T\n  LAYER IA ;\n    RECT -0.15 -0.2 0.15 0.2 ;\n"
          "  LAYER C6 ;\n    RECT -0.1 -0.1 0.1 0.1 ;\n"
          "  LAYER IB ;\n    RECT -0.2 -0.15 0.2 0.15 ;\nEND V_IA_IB_T\n"
          "VIA V_IA_IB_S\n  LAYER IA ;\n    RECT -0.15 -0.15 0.15 0.15 ;\n"
          "  LAYER C6 ;\n    RECT -0.1 -0.1 0.1 0.1 ;\n"
          "  LAYER IB ;\n    RECT -0.15 -0.15 0.15 0.15 ;\nEND V_IA_IB_S\n")


def test_a_via_its_net_definition_does_not_fit_gets_its_own(via_session, write_lef):
    from via_tech import tech_text
    s = build(via_session, write_lef)
    text = tech_text()
    s.eval(f"read_tech -file {{{write_lef(text.replace('END LIBRARY', TURNED + 'END LIBRARY'), 'vt.lef')}}}")
    s.eval("route_pin -inst sp_*")
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    net = "sp_L1_inv1_Y"
    s.eval(f"assign_via_for_route -via V_IA_IB_T -nets {net}")   # by hand: fits none of them
    out_of(s)
    metal = vias.net_shapes(s.db)
    ia_ib = lambda: [r for r in vias.rows(s.db, net) if (r["bottom"], r["top"]) == ("IA", "IB")]
    fit = lambda r: vias.fits(vias.definition_shapes(s.db, r["via_def"]), metal.get(net, {}),
                              r["bottom"], r["cut"], r["top"], r["x"], r["y"])
    defs = [n for n, st in vias.definition_layers(s.db).items() if st == ("IA", "C6", "IB")]
    fits_one = lambda r: [n for n in defs if vias.fits(vias.definition_shapes(s.db, n),
                                                       metal.get(net, {}), "IA", "C6", "IB",
                                                       r["x"], r["y"])]
    mine = ia_ib()
    assert mine and all(r["via_def"] == "V_IA_IB_T" and not fit(r) for r in mine)
    assert all(fits_one(r) for r in mine)                    # another definition fits each
    # another net routed (the vias of every net looked at): each of them gets a definition
    # that fits, its own, kept on its crossing box
    s.eval("route_net -net sp_L3_inv1_Y -rule r")
    text = out_of(s)
    assert f"{len(mine)} IA/IB via(s) given a definition of their own" in text
    now = ia_ib()
    assert [(r["x"], r["y"]) for r in now] == [(r["x"], r["y"]) for r in mine]
    assert all(r["via_def"] in fits_one(r) for r in now)
    assert all(fit(r) for r in now)
    for r in now:
        n, seq = r["source"][len("net_wire:"):].rsplit("/", 1)
        assert r["via_def"] in s.db.net_wire_row(n, int(seq))["via_def"].split()
    assert assigned(s)[("IA", "IB", net)] == "V_IA_IB_T"     # the net's assignment stays
    assert vias.own_misfits(s.db) == {}                         # nothing more to change


def test_a_crossing_box_is_made_the_full_crossing_of_its_wires(via_session, write_lef):
    s = build(via_session, write_lef)
    s.eval("route_pin -inst sp_*")
    s.eval("route_net -net [get_db nets .name] -rule r")
    out_of(s)
    rows = lambda net: {r["seq"]: r for r in s.db.net_wire_rows(net)}
    net, fixed = "sp_L2_inv1_Y", "sp_L3_inv1_Y"
    wire = next(r for r in rows(net).values() if r["kind"] == "wire" and r["layer"] == "IB")
    box = next(r for r in rows(net).values()
               if r["kind"] == "cross" and r["rect"].split()[1] == wire["rect"].split()[1])
    full = box["rect"]                        # the IB wire's end on the IA strap: the crossing
    x1, y1, x2, y2 = (float(c) for c in wire["rect"].split())
    # by hand: the IB wire stops 0.05 short of the strap's lower edge, the box 0.1 off it
    s.db.set_wire_rect("net_wire", wire["id"], f"{x1} {y1 + 0.05} {x2} {y2}")
    b = [float(c) for c in full.split()]
    s.db.set_wire_rect("net_wire", box["id"], f"{b[0]} {b[1] + 0.1} {b[2]} {b[3] + 0.1}")
    # the same on a fixed net: left as it is
    fwire = next(r for r in rows(fixed).values() if r["kind"] == "wire")
    fbox = next(r for r in rows(fixed).values() if r["kind"] == "cross")
    fb = [float(c) for c in fbox["rect"].split()]
    s.db.set_wire_rect("net_wire", fbox["id"], f"{fb[0]} {fb[1] + 0.1} {fb[2]} {fb[3] + 0.1}")
    s.eval(f"set_db [get_db nets {fixed}] .route_status fixed")
    moved_fixed = rows(fixed)[fbox["seq"]]["rect"]
    out_of(s)
    assert box["rect"] != rows(net)[box["seq"]]["rect"]
    s.eval("route_net -net sp_L3_inv2_Y -rule r")              # another net: every box looked at
    text = out_of(s)
    assert "1 crossing box(es) made the full crossing of their two wires, 1 wire(s) " \
           "lengthened to it" in text
    assert rows(net)[box["seq"]]["rect"] == full                # back on the crossing
    assert rows(net)[wire["seq"]]["rect"].split() == wire["rect"].split()   # reaches it again
    assert rows(fixed)[fbox["seq"]]["rect"] == moved_fixed       # the fixed net's: as it was
    assert rows(fixed)[fwire["seq"]]["rect"] == fwire["rect"]
    v = next(v for v in vias.rows(s.db, net) if v["source"] == f"net_wire:{net}/{box['seq']}")
    b = [float(c) for c in full.split()]
    assert (v["x"], v["y"]) == (round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6))
    assert vias.square_crossings(s.db) == (0, 0)               # nothing more to do
