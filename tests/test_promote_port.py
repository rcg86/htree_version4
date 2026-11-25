"""promote_port_to_layer, and how route_net ends at a port: on a layer of its
rule, connected; else left to the top level, at least 1 um from it."""

import pytest

pytest.importorskip("scipy")

from core.commands.route_net import Layer, Terminal, _port_drop
from test_route_net_no_spine import err, lst, ported, rects  # noqa: F401  (ported: fixture)
from test_route_pin import out_of


def shape(s, port):
    return [(r["layer"], [float(c) for c in r["points"].split()])
            for r in s.db.port_shape_rows(s.db.port_row(port)["id"])]


def test_the_port_on_the_layer_the_width_given(ported):
    s = ported
    # clk: H2 {-30.1 29.9 -29.9 30.1}; on IB (vertical): 0.36 across x, along y as long
    # as it was (0.2) and at least the width
    assert lst(s, "promote_port_to_layer -port clk -layer IB -width 0.36") == ["port:t/clk"]
    assert shape(s, "clk") == [("IB", [-30.18, 29.82, -29.82, 30.18])]
    assert "port clk: on IB at {-30.18 29.82 -29.82 30.18}, 0.36 x 0.36 (was H2 " \
        "{-30.1 29.9 -29.9 30.1})" in out_of(s)
    # longer than wide along the layer: kept; across it the width given
    s.eval("promote_port_to_layer -port port:t/clk2 -layer IA -width 0.2")
    assert shape(s, "clk2") == [("IA", [19.76, 30.14, 20.56, 30.34])]   # was 0.8 x 0.8
    # on the die edge (x 100): moved in to lie inside the boundary, still on the edge
    s.eval("promote_port_to_layer -port edge -layer IA -width 0.36")
    assert shape(s, "edge") == [("IA", [99.64, -20.18, 100.0, -19.82])]
    assert "HT4-317" not in out_of(s)


def test_snap_to_track(ported):
    s = ported
    # clk's middle is x -30; the IB signal tracks are 0.72 apart, -30.24 the nearest
    s.eval("promote_port_to_layer -port clk -layer IB -width 0.36 -snap_to_track")
    assert shape(s, "clk") == [("IB", [-30.42, 29.82, -30.06, 30.18])]
    text = out_of(s)
    assert "on the IB signal track at x -30.24 (moved -0.24)" in text and "HT4-318" not in text
    s.eval("route_net -net clk_in -rule r")
    assert "driver port clk: connected on IB" in out_of(s)
    # promoted again, on IA: from the IB shape it has now, its y onto the nearest IA
    # track (30.24)
    s.eval("promote_port_to_layer -port clk -layer IA -width 0.36 -snap_to_track")
    assert shape(s, "clk") == [("IA", [-30.42, 30.06, -30.06, 30.42])]
    assert "on the IA signal track at y 30.24 (moved 0.24)" in out_of(s)
    # edge (x 100) is beyond the last IB signal track (x 50.4): moved there, with a warning
    s.eval("promote_port_to_layer -port edge -layer IB -width 0.36 -snap_to_track")
    assert shape(s, "edge")[0][1][0::2] == [50.22, 50.58]
    assert "HT4-318" in out_of(s)


def test_errors(ported):
    s = ported
    before = shape(s, "clk")
    for options in ("-layer IB -width 1", "-port clk -width 1", "-port clk -layer IB",
                    "-port clk -layer IB -width 0", "-port clk -layer IB -width wide",
                    "-port {} -layer IB -width 1"):
        assert "HT4-001" in err(s, f"promote_port_to_layer {options}"), options
    assert "HT4-315" in err(s, "promote_port_to_layer -port nosuch -layer IB -width 1")
    assert "HT4-316" in err(s, "promote_port_to_layer -port clk -layer C6 -width 1")
    assert "HT4-316" in err(s, "promote_port_to_layer -port clk -layer NOPE -width 1")
    assert "HT4-315" in err(s, "promote_port_to_layer -port idle -layer IB -width 1")
    assert shape(s, "clk") == before


def test_route_net_reaches_a_promoted_port(ported):
    s = ported
    s.eval("route_net -net clk_in -rule r")
    assert "HT4-266" in out_of(s)                  # on H2: left to the top level
    s.eval("promote_port_to_layer -port clk -layer IA -width 0.36")
    out_of(s)
    s.eval("route_net -net clk_in -rule r")
    text = out_of(s)
    assert "HT4-266" not in text and "driver port clk: connected on IA" in text
    # an IA wire on the track by the port (y 30.24, 0.06 off its middle), over it
    assert any(r[1] <= 30.18 and r[3] >= 29.82 and r[0] <= -29.82 and r[2] >= -30.18
               for r in rects(s, "clk_in", "wire", "IA"))


IB, IA = Layer("IB", 0.72, 0.72), Layer("IA", 0.72, 0.72)


def port(layer, box):
    return Terminal("port", "port p", box, pin="p", point=((box[0] + box[2]) / 2,
                                                         (box[1] + box[3]) / 2),
                    shapes=[(layer, box)])


def test_the_drop_from_the_crossing_to_a_port():
    # the route ends at the crossing (5560.2, 1.8); the port on IB below it, on the
    # IB track: an IB wire from the crossing down to the middle of the port
    t = port("IB", (5559.838, 0, 5560.558, 0.72))
    layer, rect, cross = _port_drop(t, 5560.2, 1.8, IA, IB, [])
    assert layer == "IB" and rect == (5559.84, 0.36, 5560.56, 2.16)
    assert cross == pytest.approx((5559.84, 1.44, 5560.56, 2.16))
    # on IA, beside the crossing on its track: an IA wire to it
    layer, rect, _ = _port_drop(port("IA", (5565, 1.6, 5566, 2.0)), 5560.2, 1.8, IA, IB, [])
    assert layer == "IA" and rect == (5559.84, 1.44, 5565.5, 2.16)
    # not on the track (no wire on it would touch the port), or a shape of another net
    # in the way: none
    assert _port_drop(port("IB", (5562, 0, 5562.7, 0.72)), 5560.2, 1.8, IA, IB, []) is None
    assert _port_drop(t, 5560.2, 1.8, IA, IB, [("IB", (5560.0, 0.9, 5560.4, 1.0))]) is None
    assert _port_drop(port("H2", (5559.8, 0, 5560.6, 0.7)), 5560.2, 1.8, IA, IB, []) is None


def test_write_def_writes_a_promoted_port_in_pins(ported, tmp_path):
    from core.def_parser import parse_def
    s = ported
    s.eval(f"write_def -output {tmp_path / 'a.def'}")
    assert "PINS" not in (tmp_path / "a.def").read_text()      # none promoted: no PINS
    s.eval("promote_port_to_layer -port clk -layer IB -width 0.36")
    s.eval(f"write_def -output {tmp_path / 'b.def'}")
    assert "PINS 1" in out_of(s)
    text = (tmp_path / "b.def").read_text()
    # only the promoted port; its new shape and layer, not the old H2 one, about its
    # placement point (FIXED ( -30000 30000 ) N in the design's DEF)
    assert ("PINS 1 ;\n"
            "- clk + NET clk_in + DIRECTION INPUT + USE CLOCK\n"
            "  + LAYER IB ( -180 -180 ) ( 180 180 )\n"
            "  + FIXED ( -30000 30000 ) N ;\n"
            "END PINS\n") in text
    assert "H2" not in text[text.index("PINS 1"):text.index("END PINS")]
    assert text.index("END COMPONENTS") < text.index("PINS 1") < text.index("SPECIALNETS")
    # read back: the same port, on IB, where the database has it
    (port,) = [p for p in parse_def(str(tmp_path / "b.def")).ports if p.name == "clk"]
    assert (port.direction, port.net) == ("in", "clk_in")
    assert [(sh.layer, sh.points) for sh in port.shapes] == [("IB", shape(s, "clk")[0][1])]
    # -sections without pins: not written
    s.eval(f"write_def -output {tmp_path / 'c.def'} -sections specialnets")
    assert "PINS" not in (tmp_path / "c.def").read_text()
