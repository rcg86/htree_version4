"""write_def writes the routing as SPECIALNETS in the form Innovus writes routed
clock and power nets: + FIXED / + ROUTED + RECT shapes, the vias as
<layer> 0 ( x y ) <via> with NEW lines, + USE on a power net; no + SHIELD
(IMPDF-168: a shield's power net must be in the signal net's + SHIELDNET)."""

import re

import pytest

pytest.importorskip("scipy")

from core import vias
from test_route_net import DEF, def_block, out_of, spine  # noqa: F401  (spine is a fixture)
from test_route_pin import placed  # noqa: F401  (placed is a fixture)
from test_vias import _route, routed, via_session  # noqa: F401  (fixtures)

# Every line of SPECIALNETS is one of these (the forms of an Innovus DEF).
N = r"-?\d+"
FORMS = [rf"SPECIALNETS {N} ;", r"- \S+( \( \S+ \S+ \))*",
         rf"  \+ (FIXED|ROUTED) \+ RECT \S+ \( {N} {N} \) \( {N} {N} \)",
         rf"  \+ (FIXED|ROUTED) \S+ 0 \( {N} {N} \) \S+",
         rf"    NEW \S+ 0 \( {N} {N} \) \S+",
         r"  \+ USE (POWER|GROUND)", r" ;", r"END SPECIALNETS"]


def special(text):
    return text.split("\nSPECIALNETS")[1].split("\nEND SPECIALNETS")[0]


def test_every_line_in_the_innovus_form(routed, tmp_path):
    s = routed
    s.eval("route_net -net [get_db nets .name] -rule r -shield")
    s.eval("route_final_stub -rule r -shield")
    s.eval("assign_via_for_route -via {V_IA_IB via_def:V_G2_IA}")
    out_of(s)
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    text = (tmp_path / "o.def").read_text()
    lines = ("SPECIALNETS" + special(text)).splitlines()
    bad = [line for line in lines if not any(re.fullmatch(f, line) for f in FORMS)]
    assert bad == []
    assert int(lines[0].split()[1]) == sum(1 for line in lines if line.startswith("- "))
    assert "SHIELD" not in text and "\nNETS " not in text


def test_the_vias_of_each_net(routed, tmp_path):
    s = routed
    s.eval("assign_via_for_route -via {V_IA_IB via_def:V_G2_IA}")
    s.eval(f"write_def -output {tmp_path / 'o.def'}")
    text = (tmp_path / "o.def").read_text()
    rows = vias.rows(s.db)
    left = sum(1 for r in rows if not r["via_def"] and r["net"] != "SIGNAL")
    assert left and f"**WARN: (HT4-183): {left} via(s) with no via definition" in out_of(s)
    written = 0
    for net in {r["net"] for r in rows if r["via_def"] and r["net"] != "SIGNAL"}:
        block = def_block(text, net)
        mine = [r for r in rows if r["net"] == net and r["via_def"]]
        lines = [line for line in block if line.endswith(tuple(r["via_def"] for r in mine))
                 and " 0 ( " in line]
        assert len(lines) == len(mine)
        status = "FIXED" if not block[-1].startswith("  + USE") else "ROUTED"
        assert lines[0].startswith(f"  + {status} ")
        assert all(line.startswith("    NEW ") for line in lines[1:])
        for r in mine:                   # its bottom layer, its centre, its definition
            x, y = round(r["x"] * 1000), round(r["y"] * 1000)
            assert any(line.split(" 0 ")[0].endswith(f" {r['bottom']}") and
                       f"( {x} {y} ) {r['via_def']}" in line for line in lines)
        written += len(mine)
    assert written == sum(1 for r in rows if r["via_def"] and r["net"] != "SIGNAL") > 0
