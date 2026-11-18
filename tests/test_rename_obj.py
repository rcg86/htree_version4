"""rename_obj: a net or an instance renamed everywhere it is named; a spine's
root input on <spine>_primary_input when its spec's root_net is 'net'."""

import pytest

pytest.importorskip("scipy")

from core import vias
from test_route_net import DEF, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import err, out_of, placed  # noqa: F401  (placed is a fixture)
from test_vias import _route, routed, via_session  # noqa: F401  (fixtures)
from test_connect_pin import design  # noqa: F401  (a fixture: a design with ports)


def lst(s, script):
    return list(s.split_list(s.eval(script)))


def test_the_root_net_is_primary_input(routed, tmp_path):
    s = routed
    assert s.eval("get_db spine:sp .root_net") == "net:sp_primary_input"
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == "net:sp_primary_input"
    assert s.eval("get_db [get_db spine:sp .root_net] .pins") == "pin:sp_L1_inv1/A"
    s.eval(f"write_logical -output {tmp_path / 'l.tcl'}")
    text = (tmp_path / "l.tcl").read_text()
    step1 = text.split("Step 2")[0]
    assert "create_net -name sp_primary_input\n" in step1          # created, then connected
    assert "connect sp_L1_inv1/A -net sp_primary_input\n" in text
    assert "-net net\n" not in text


def test_rename_the_root_net(routed, tmp_path):
    s = routed
    got = s.eval("rename_obj -from [get_db [get_db spine:sp .root_net] .name] -to clk_root")
    assert got == "net:clk_root"
    assert "rename_obj: root net of spine sp sp_primary_input renamed clk_root" in out_of(s)
    assert s.eval("get_db spine:sp .root_net") == "net:clk_root"
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == "net:clk_root"
    s.eval(f"write_logical -output {tmp_path / 'l.tcl'}")
    text = (tmp_path / "l.tcl").read_text()
    assert "create_net -name clk_root\n" in text and "sp_primary_input" not in text
    # kept by write_db / read_db
    s.eval(f"write_db -file {tmp_path / 'r.db'}")
    s.eval(f"read_db -file {tmp_path / 'r.db'}")
    assert s.eval("get_db pin:sp_L1_inv1/A .net") == "net:clk_root"


def test_rename_a_routed_spine_net(routed):
    s = routed
    old = "sp_L3_inv1_Y"
    wires = len(s.db.net_wire_rows(old))
    stub_wires = len(s.db.stub_wire_rows(old))
    loads = s.eval(f"get_db spine_net:sp/{old} .pins")
    s.eval("check_drc")
    before = out_of(s)
    s.eval(f"set_db spine_net:sp/{old} .route_status fixed")
    s.db.selection[:] = [f"spine_net:sp/{old}", f"net_wire:{old}_stub/1"]
    s.db.highlights[:] = [(f"spine_net:sp/{old}", "#ff1744")]
    assert s.eval(f"rename_obj -from {old} -to leaf_a") == "spine_net:sp/leaf_a"
    assert f"({wires + stub_wires} wire(s))" in out_of(s)
    assert s.db.net_wire_rows(old) == [] and len(s.db.net_wire_rows("leaf_a")) == wires
    assert len(s.db.stub_wire_rows("leaf_a")) == stub_wires and stub_wires
    assert all(r["shield_net"] == "leaf_a" for r in s.db.stub_wire_rows("leaf_a")
               if r["kind"] in ("stub", "stub_cross"))
    assert s.eval("get_db spine_net:sp/leaf_a .pins") == loads
    assert s.eval("get_db pin:sp_L3_inv1/Y .net") == "spine_net:sp/leaf_a"
    assert s.eval("get_db spine_net:sp/leaf_a .route_rule") == "route_rule:r"
    assert s.eval("get_db spine_net:sp/leaf_a .route_status") == "fixed"
    assert s.eval("get_db stub:sp/stub1 .net") == "spine_net:sp/leaf_a"
    assert vias.rows(s.db, "leaf_a") and not vias.rows(s.db, old)
    assert not [r for r in s.db.net_wire_rows() if old in r["net"]]          # auto vias too
    assert s.db.selection == ["spine_net:sp/leaf_a", "net_wire:leaf_a_stub/1"]
    assert s.db.highlights == [("spine_net:sp/leaf_a", "#ff1744")]
    s.eval("check_drc")                  # the same routing: the same result, by the new name
    assert out_of(s).replace("leaf_a", old) == before


def test_rename_an_instance(routed):
    s = routed
    straps = len(s.db.strap_rows("sp_L2_inv1"))
    s.eval("rename_obj -from [get_db inst:sp_L2_inv1 .name] -to mid")
    assert "instance sp_L2_inv1 renamed mid (the nets it drives keep their names)" in out_of(s)
    assert s.db.inst_row("sp_L2_inv1") is None and len(s.db.strap_rows("mid")) == straps
    assert "inst:mid" in lst(s, "get_db spine:sp .insts")
    assert s.eval("get_db spine_net:sp/sp_L1_inv1_Y .pins").split()[-1] == "pin:mid/A"
    assert s.eval("get_db spine_net:sp/sp_L2_inv1_Y .driver") == "inst:mid"
    assert s.eval("get_db pin:mid/Y .net") == "spine_net:sp/sp_L2_inv1_Y"
    assert s.eval("get_db pin:mid/A .net") == "spine_net:sp/sp_L1_inv1_Y"


def test_errors(routed):
    s = routed
    assert "HT4-292" in err(s, "rename_obj -from nothing -to x")
    assert "HT4-294" in err(s, "rename_obj -from sp_L1_inv1_Y -to sp_L2_inv1_Y")
    assert "HT4-294" in err(s, "rename_obj -from sp_L1_inv1 -to sp_L2_inv1")
    assert "HT4-294" in err(s, "rename_obj -from sp_L1_inv1_Y -to sp_L1_inv1_Y")
    assert "ends in _stub" in err(s, "rename_obj -from sp_L1_inv1_Y -to a_stub")
    assert "HT4-295" in err(s, "rename_obj -from VSS -to gnd")
    assert "HT4-295" in err(s, "rename_obj -from layer:IA -to x")
    assert "HT4-296" in err(s, "rename_obj -from sp_L1_inv1_Y -to {a b}")
    assert "HT4-296" in err(s, "rename_obj -from sp_L1_inv1_Y -to a/b")
    assert "give -from and -to" in err(s, "rename_obj -from sp_L1_inv1_Y")
    assert "takes one net or instance" in err(s, "rename_obj -from {a b} -to c")


def test_a_port_net_and_a_connect_pin_net(design, tmp_path):
    s = design
    s.eval("connect_pin -from clk -to buf1/A")
    s.eval("connect_pin -from buf1/Y -to d1/A")
    out_of(s)
    assert "is the net of a port" in err(s, "rename_obj -from clk -to x")
    assert s.eval("rename_obj -from buf1_Y -to clk_buf") == "net:clk_buf"
    assert s.eval("get_db pin:d1/A .net") == s.eval("get_db pin:buf1/Y .net") == "net:clk_buf"
    s.eval(f"write_logical -output {tmp_path / 'l.tcl'}")
    text = (tmp_path / "l.tcl").read_text()
    assert "create_net -name clk_buf\n" in text and "buf1_Y" not in text
    # the root renamed to a port's net: the design has it, no create_net
    s.eval("rename_obj -from sp_primary_input -to clk_root")
    s.db.conn.execute("UPDATE spine SET root_net = 'clk'")
    s.db.netlist = None
    s.eval(f"write_logical -output {tmp_path / 'l.tcl'} -overwrite")
    text = (tmp_path / "l.tcl").read_text()
    assert "# spine sp: root net clk must exist in the design" in text
    assert "create_net -name clk\n" not in text
