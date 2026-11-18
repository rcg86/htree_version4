"""check_drc: shorts, spacing and width against the tech LEF and the route
rules, opens of signal and power nets, -layer_range and the report."""

import pytest

pytest.importorskip("scipy")

from test_route_net import DEF, SPEC
from test_route_pin import CELL_LEF, err, out_of
from test_vias import routed, via_session  # noqa: F401  (fixtures)

# Two routing layers with spacing rules, one with a table check_drc does
# not read. The layer names and every value are made up.
RULES_LEF = """VERSION 5.8 ;
UNITS
  DATABASE MICRONS 1000 ;
END UNITS
MANUFACTURINGGRID 0.001 ;
LAYER MA
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 1 ;
  WIDTH 0.2 ;
  MINWIDTH 0.1 ;
  SPACING 0.2 ;
  SPACINGTABLE
    PARALLELRUNLENGTH 0 2
    WIDTH 0   0.2 0.2
    WIDTH 0.5 0.2 0.4 ;
END MA
LAYER CA
  TYPE CUT ;
END CA
LAYER MB
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  PITCH 1 ;
  WIDTH 0.2 ;
  SPACINGTABLE TWOWIDTHS
    WIDTH 0         0.2 0.3
    WIDTH 0.5 PRL 1 0.3 0.6 ;
END MB
LAYER CB
  TYPE CUT ;
END CB
LAYER MC
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 1 ;
  WIDTH 0.2 ;
  PROPERTY LEF58_SPACINGTABLE "SPACINGTABLE PARALLELRUNLENGTH 0 WIDTH 0 0.3 ;" ;
END MC
END LIBRARY
"""
SECTIONS = ("Shorts", "Tech spacing", "Tech width", "Custom spacing", "Custom width",
            "Opens, signal nets", "Opens, power nets")


@pytest.fixture
def rules(session, write_lef):
    session.eval(f"read_tech -file {{{write_lef(RULES_LEF, 'rules.lef')}}}")
    out_of(session)
    return session


def wires(s, net, *rows):
    """Give net these wires: (kind, layer, 'x1 y1 x2 y2'[, shield net])."""
    s.db.set_net_wires(net, list(rows))


def check(s, args=""):
    """(count, {section: [violation line]}, text) of check_drc."""
    count = int(s.eval(f"check_drc {args}"))
    text = out_of(s)
    found, at = {}, None
    for line in text.splitlines():
        title = next((t for t in SECTIONS if line.startswith(t)), None)
        if title is not None:
            at = found.setdefault(title, [])
        elif at is not None and line.startswith("  "):
            at.append(line.strip())
        else:
            at = None
    assert count == sum(len(v) for v in found.values())
    return count, found, text


def summary(text):
    """{(check, rule, layer): count} of the summary table."""
    rows = {}
    for line in text.splitlines():
        words = line.split()
        if len(words) == 4 and words[0] in ("short", "spacing", "width", "open"):
            rows[tuple(words[:3])] = int(words[3])
    return rows


def spine(s, write_lef, shield="", stubs=True):
    """The spine of test_route_net, routed with rule r."""
    s.eval(f"read_lef -file {{{write_lef(CELL_LEF, 'c.lef')}}}")
    s.eval(f"read_def -file {{{write_lef(DEF, 'd.def')}}}")
    s.eval(f"read_spine_spec -file {{{write_lef(SPEC, 's.yaml')}}}")
    s.eval("create_spine -name sp -spec_name sp -location {0 0} -build -ref_cell INV_RP")
    s.eval("route_pin -inst sp_*")
    s.eval("create_route_rule -name r -layer IA -width 0.36 -spacing 0.36")
    s.eval("create_route_rule -name r -layer IB -width 0.36 -spacing 0.36 -append")
    s.eval(f"route_net -net [get_db nets .name] -rule r {shield}")
    if stubs:
        s.eval("route_final_stub -rule r")
    out_of(s)
    return s


# -- shorts ----------------------------------------------------------------------

def test_nothing_to_check(rules):
    count, found, text = check(rules)
    assert (count, found) == (0, {})
    assert "check_drc: no violations" in text and "HT4-250" not in text
    assert summary(text) == {("short", "-", "-"): 0, ("spacing", "tech", "-"): 0,
                             ("width", "tech", "-"): 0, ("spacing", "custom", "-"): 0,
                             ("width", "custom", "-"): 0, ("open", "signal", "-"): 0,
                             ("open", "power", "-"): 0}


def test_shorts(rules):
    s = rules
    wires(s, "a", ("wire", "MA", "0 0 10 0.2"))
    wires(s, "b", ("wire", "MA", "8 0.1 12 0.3"),          # overlaps a
          ("wire", "MA", "10 0 11 0.05"),                  # abuts a's end (also thin)
          ("wire", "MB", "0 0 0.2 5"),                     # another layer: no short
          ("wire", "MA", "20 0 30 0.2"))
    wires(s, "c", ("wire", "MA", "30 0.2 40 0.4"))         # touches b at a corner only
    wires(s, "a2", ("shield", "MA", "0 0.1 5 0.3", "a"))   # a's own shield net: same net
    count, found, text = check(s, "-check_shorts_only")
    assert found == {"Shorts": [
        "MA {8 0.1 10 0.2}  net_wire:a/1 (a) and net_wire:b/1 (b) overlap 2 x 0.1",
        "MA {10 0 10 0.05}  net_wire:a/1 (a) and net_wire:b/2 (b) abut"]}
    assert summary(text) == {("short", "-", "MA"): 2}
    assert "**WARN: (HT4-250): check_drc: 2 violation(s)" in text
    # the corner touch is a spacing violation of 0, not a short
    _, found, _ = check(s, "-check_spacing_only")
    assert [v for v in found["Tech spacing"] if "net_wire:c/1" in v] == [
        "MA {30 0.2 30 0.2}  0 < 0.2  net_wire:b/4 (b) and net_wire:c/1 (c)  "
        "[SPACINGTABLE PARALLELRUNLENGTH, widths 0.2 and 0.2, parallel run 0]"]
    assert "Shorts" not in found


# -- spacing ---------------------------------------------------------------------

def test_tech_spacing(rules):
    s = rules
    wires(s, "a", ("wire", "MA", "0 0 10 0.2"),            # narrow
          ("wire", "MA", "0 10 10 10.6"),                  # wide, long beside e
          ("wire", "MA", "0 20 10 20.5"),                  # exactly the row width: narrow
          ("wire", "MA", "0 30 10 30.6"))                  # wide, short beside h
    wires(s, "b", ("wire", "MA", "0 0.35 9 0.55"))         # 0.15 from a/1
    wires(s, "c", ("wire", "MA", "0 -0.4 10 -0.2"))        # 0.2 from a/1: clean
    wires(s, "d", ("wire", "MA", "10.1 0.3 12 0.5"))       # diagonal of a/1
    wires(s, "e", ("wire", "MA", "0 10.9 10 11.1"))        # 0.3 from the wide wire
    wires(s, "g", ("wire", "MA", "0 20.8 10 21"))          # 0.3 from the 0.5 wire: clean
    wires(s, "h", ("wire", "MA", "8.5 30.9 20 31.1"))      # 0.3 away over 1.5: clean
    count, found, text = check(s)
    assert found == {"Tech spacing": [
        "MA {0 0.2 9 0.35}  0.15 < 0.2  net_wire:a/1 (a) and net_wire:b/1 (b)  "
        "[SPACINGTABLE PARALLELRUNLENGTH, widths 0.2 and 0.2, parallel run 9]",
        "MA {0 10.6 10 10.9}  0.3 < 0.4  net_wire:a/2 (a) and net_wire:e/1 (e)  "
        "[SPACINGTABLE PARALLELRUNLENGTH, widths 0.6 and 0.2, parallel run 10]",
        "MA {10 0.2 10.1 0.3}  0.141421 < 0.2  net_wire:a/1 (a) and net_wire:d/1 (d)  "
        "[SPACINGTABLE PARALLELRUNLENGTH, widths 0.2 and 0.2, parallel run 0]"]}
    assert summary(text)["spacing", "tech", "MA"] == 3


def test_two_widths_table(rules):
    s = rules
    wires(s, "a", ("wire", "MB", "0 0 0.2 10"),            # narrow
          ("wire", "MB", "10 0 10.6 10"),                  # wide
          ("wire", "MB", "20 0 20.6 10"),                  # wide
          ("wire", "MB", "30 0 30.6 10"))                  # wide
    wires(s, "b", ("wire", "MB", "0.35 0 0.55 10"),        # narrow, 0.15 away
          ("wire", "MB", "10.85 0 11.05 10"),              # narrow, 0.25 from a wide one
          ("wire", "MB", "21.1 0 21.7 10"),                # wide, 0.5 from a wide one
          ("wire", "MB", "30.85 9.5 31.05 20"))            # narrow, 0.25 away over 0.5 only
    _, found, _ = check(s)
    assert [v.split("  ")[1] for v in found.pop("Tech spacing")] == [
        "0.15 < 0.2", "0.25 < 0.3", "0.5 < 0.6"]
    assert found == {}


def test_custom_spacing_and_width(rules):
    s = rules
    s.eval("create_route_rule -name r -layer MA -width 0.3 -spacing 0.5")
    s.db.set_net_route_rule("a", "r")
    wires(s, "a", ("wire", "MA", "0 0 10 0.3"),
          ("wire", "MA", "0 5 10 5.2"),                    # narrower than the rule
          ("extension", "MA", "0 8 10 8.2"))               # not drawn by the rule
    wires(s, "b", ("wire", "MA", "0 0.7 10 0.9"),          # 0.4 from a/1: tech clean
          ("wire", "MA", "0 8.6 10 8.8"))                  # 0.4 from the extension
    wires(s, "c", ("wire", "MA", "0 -0.4 10 -0.25"))       # 0.25 from a/1; rule default
    s.db.set_net_route_rule("c", "default")
    count, found, text = check(s)
    assert found == {
        "Custom spacing": [
            "MA {0 -0.25 10 0}  0.25 < 0.5  net_wire:a/1 (a) and net_wire:c/1 (c)  "
            "[route rule r of net_wire:a/1]",
            "MA {0 0.3 10 0.7}  0.4 < 0.5  net_wire:a/1 (a) and net_wire:b/1 (b)  "
            "[route rule r of net_wire:a/1]"],
        "Custom width": ["MA {0 5 10 5.2}  0.2 < 0.3  net_wire:a/2 (a)  [route rule r]"]}
    assert summary(text)["spacing", "custom", "MA"] == 2
    assert summary(text)["spacing", "tech", "-"] == 0
    # 0.15 apart fails both: reported once in each bracket
    wires(s, "c", ("wire", "MA", "0 -0.35 10 -0.15"))
    _, found, _ = check(s, "-check_spacing_only")
    assert len(found["Tech spacing"]) == 1 and len(found["Custom spacing"]) == 2


def test_width(rules):
    s = rules
    wires(s, "a", ("wire", "MA", "0 0 10 0.3"),
          ("extension", "MA", "10 0 10.05 0.3"),           # a piece of the same wire
          ("wire", "MA", "0 5 10 5.05"),                   # thinner than MINWIDTH
          ("wire", "MB", "0 10 0.15 20"))                  # no MINWIDTH: WIDTH counts
    _, found, _ = check(s)
    assert found == {"Tech width": [
        "MA {0 5 10 5.05}  0.05 < 0.1  net_wire:a/3 (a)  [minimum width]",
        "MB {0 10 0.15 20}  0.15 < 0.2  net_wire:a/4 (a)  [minimum width]"]}


def test_tables_not_applied_are_named(rules):
    s = rules
    wires(s, "a", ("wire", "MC", "0 0 10 0.2"))
    wires(s, "b", ("wire", "MC", "0 0.25 10 0.45"))
    count, _, text = check(s)
    assert count == 0
    assert "  Spacing tables not applied (LEF58 or of a kind not read): MC(1)" in text


# -- the routed spine ------------------------------------------------------------

def test_routed_spine(routed):
    """The test spine is routed clean but for the straps of the L2 and L3
    cells: 3.12 long on a level pitch of 2.88, so those of different nets
    on one track overlap, the more for the routes lengthening them."""
    s = routed
    count, found, text = check(s)
    assert list(found) == ["Shorts"] and count == 2
    assert found["Shorts"] == [
        "IA {4.14 7.7 4.5 8.42}  strap:sp_L2_inv1/5 (sp_L1_inv1_Y) and strap:sp_L3_inv1/5 "
        "(sp_L2_inv1_Y) overlap 0.36 x 0.72",
        "IA {4.14 10.58 4.5 11.3}  strap:sp_L2_inv1/3 (sp_L2_inv1_Y) and strap:sp_L3_inv1/3 "
        "(sp_L3_inv1_Y) overlap 0.36 x 0.72"]
    assert summary(text) == {("short", "-", "IA"): 2, ("spacing", "tech", "-"): 0,
                             ("width", "tech", "-"): 0, ("spacing", "custom", "-"): 0,
                             ("width", "custom", "-"): 0, ("open", "signal", "-"): 0,
                             ("open", "power", "-"): 0}
    assert "  Nets  : 5 signal nets, 2 power nets" in text     # 4 of the spine, its root net
    assert "107 without a definition" in text


def test_via_pads(routed):
    s = routed
    s.eval("assign_via_for_route -via {V_D12_H1 V_H1_H2 V_H2_G1 V_G1_G2 V_G2_IA V_IA_IB}")
    out_of(s)
    count, found, text = check(s)
    assert "214 via pads" in text and "without a definition" not in text
    # the pads of the overlapping straps' vias are in the same two shorts
    assert count == 6 and list(found) == ["Shorts"]
    assert sum("via:" in v for v in found["Shorts"]) == 4
    assert all(v.startswith("IA {4.") for v in found["Shorts"])
    # The IA pad at the L1 wire's first crossing ends at x 1.64, 0.02 past the
    # strap extension: another net's wire from there abuts the pad alone.
    wires(s, "other", ("wire", "IA", "1.64 1.3 2.5 1.6"))
    _, found, _ = check(s, "-check_shorts_only")
    assert [v for v in found["Shorts"] if "other" in v] == [
        "IA {1.64 1.3 1.64 1.59}  via:sp_L1_inv1_Y/1 (sp_L1_inv1_Y) and "
        "net_wire:other/1 (other) abut"]


# -- opens -----------------------------------------------------------------------

def test_open_signal(routed):
    s = routed
    s.eval("delete_wire -wires net_wire:sp_L2_inv1_Y/1")          # the trunk
    count, found, _ = check(s, "-check_open_only")
    assert count == 2 and list(found) == ["Opens, signal nets"]
    assert all("net sp_L2_inv1_Y: no path to the driver sp_L2_inv1/Y from " in v
               for v in found["Opens, signal nets"])
    assert ["pin sp_L3_inv1/A" in v for v in found["Opens, signal nets"]] == [True, False]
    assert ["pin sp_L3_inv2/A" in v for v in found["Opens, signal nets"]] == [False, True]


def test_open_before_routing(via_session, write_lef):
    s = spine(via_session, write_lef, stubs=False)
    _, found, _ = check(s, "-check_open_only")
    assert found == {"Opens, signal nets": [
        "{8.64 0 8.64 19}  net sp_L3_inv1_Y: stub stub1 has no wire (route_final_stub)",
        "{8.64 21 8.64 40}  net sp_L3_inv2_Y: stub stub2 has no wire (route_final_stub)"]}
    s.eval("delete_route -nets [get_db nets .name]")
    count, found, _ = check(s, "-check_open_only")
    # L1 and L2 drive one and two cells; the leaves only their stubs
    assert count == 5 and len(found["Opens, signal nets"]) == 5
    assert sum("has no wire" in v for v in found["Opens, signal nets"]) == 2


def test_open_power(routed):
    s = routed
    assert check(s, "-check_open_only")[0] == 0           # no shields: nothing to reach
    # A VSS shield beside the L1 wire, tied to nothing.
    wires(s, "extra", ("shield", "IB", "1.98 1.08 2.34 8.42", "VSS"))
    _, found, _ = check(s, "-check_open_only")
    power = found.pop("Opens, power nets")
    assert found == {}
    assert "{1.98 1.08 2.34 8.42}  net VSS: no path to a strap from net_wire:extra/1" in power
    # and with a shield on the net, every strap of it is to reach one
    assert len(power) == 7
    assert sum("net VSS: no path to a shield from " in v for v in power) == 6
    assert any("pin sp_L1_inv1/VSS" in v for v in power)
    assert any("pin sp_L2_inv1/VSS, pin sp_L3_inv1/VSS" in v for v in power)
    # The L2 cell's strap 4 (1.32 9.14 4.44 9.86) runs under the shield: a
    # crossing box there ties the two, and what hangs on that strap with them.
    wires(s, "extra", ("shield", "IB", "1.98 1.08 2.34 9.86", "VSS"),
          ("cross", "IB/IA", "1.98 9.14 2.34 9.86", "VSS"))
    _, found, _ = check(s, "-check_open_only")
    power = found["Opens, power nets"]
    assert len(power) == 5 and not any("net_wire:extra/1" in v for v in power)
    assert not any("pin sp_L2_inv1/VSS" in v for v in power)
    assert any("pin sp_L1_inv1/VSS" in v for v in power)


# -- -layer_range ----------------------------------------------------------------

def test_layer_range_shapes(routed):
    s = routed
    assert check(s, "-layer_range IA")[0] == 2
    assert check(s, "-layer_range IB:IA")[0] == 2          # either order
    count, _, text = check(s, "-layer_range IB")
    assert count == 0
    assert "check_drc: layers IB\n" in text and " pin shapes on IB\n" in text
    _, _, text = check(s, "-layer_range H2:IA")
    assert "check_drc: layers H2 C3 G1 C4 G2 C5 IA\n" in text      # the cut layers too


def test_layer_range_opens(routed):
    s = routed
    for r in ("D12:IB", "H2:IA", "IA:IB"):
        assert check(s, f"-check_open_only -layer_range {r}")[0] == 0
    # Without its crossing box the L1 cell's output strap has no way up.
    s.eval("delete_wire -wires net_wire:sp_L1_inv1_Y/2")
    _, found, _ = check(s, "-check_open_only -layer_range IA:IB")
    assert len(found["Opens, signal nets"]) == 1
    assert "net sp_L1_inv1_Y: no path to IB from " in found["Opens, signal nets"][0]
    assert found["Opens, signal nets"][0].endswith(" on IA")
    assert check(s, "-check_open_only -layer_range H2:IA")[0] == 0     # H2 still reaches IA
    _, found, _ = check(s, "-check_open_only")
    assert len(found["Opens, signal nets"]) == 1
    assert "no path to the driver sp_L1_inv1/Y from pin sp_L2_inv1/A" in \
        found["Opens, signal nets"][0]


def test_layer_range_pin_wire(routed):
    """A pin wire that stops short of its strap: no path from H2 to IA."""
    s = routed
    row = next(r for r in s.db.pin_wire_rows() if (r["inst"], r["pin"]) == ("sp_L2_inv1", "A"))
    s.db.set_wire_rect("pin_wire", row["id"], "3.843 8.6 4.253 14.18")
    _, found, _ = check(s, "-check_open_only -layer_range H2:IA")
    assert found == {"Opens, signal nets": [
        "{3.843 8.6 4.253 14.18}  net sp_L1_inv1_Y: no path to IA from "
        "pin_wire:sp_L2_inv1/A on H2"]}
    assert check(s, "-check_open_only -layer_range IA:IB")[0] == 0


def test_bad_layer_range(routed):
    for text in ("XX:IA", "H2:IA:IB", ":IA", "IA:"):
        assert "HT4-247" in err(routed, f"check_drc -layer_range {text}")


# -- options and the report ------------------------------------------------------

def test_only_options(routed):
    s = routed
    _, _, text = check(s, "-check_shorts_only")
    assert list(summary(text)) == [("short", "-", "IA")]
    _, _, text = check(s, "-check_open_only")
    assert list(summary(text)) == [("open", "signal", "-"), ("open", "power", "-")]
    _, _, text = check(s, "-check_spacing_only")
    assert list(summary(text)) == [("spacing", "tech", "-"), ("width", "tech", "-"),
                                   ("spacing", "custom", "-"), ("width", "custom", "-")]
    assert "HT4-001" in err(s, "check_drc -check_shorts_only -check_open_only")
    assert "HT4-001" in err(s, "check_drc -check_spacing_only -check_open_only")
    assert "HT4-001" in err(s, "check_drc -overwrite")
    assert "HT4-001" in err(s, "check_drc -bogus")


def test_report_file(routed, tmp_path):
    s = routed
    path = tmp_path / "drc.rpt"
    assert s.eval(f"check_drc -file {{{path}}}") == "2"
    screen = out_of(s)
    report = path.read_text()
    assert "Shorts: 2" in report and "Shorts: 2" not in screen
    assert "  short     -       IA      2" in report and "  short     -       IA      2" in screen
    assert f"Report written to '{path}'" in screen and "HT4-250" in screen
    assert report.count("\n  IA {") == 2
    assert "HT4-248" in err(s, f"check_drc -file {{{path}}}")
    path.write_text("old")
    s.eval(f"check_drc -file {{{path}}} -overwrite")
    assert "Shorts: 2" in path.read_text()
    assert "HT4-249" in err(s, f"check_drc -file {{{tmp_path / 'none' / 'drc.rpt'}}}")


def test_needs_tech(session):
    assert "HT4-025" in err(session, "check_drc")
