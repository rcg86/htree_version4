"""A tech LEF with cut layers and via definitions for the via tests: the
routing layers of tests/data/tech.lef on top of a pin layer, a cut layer
between each two, and one via per cut layer. Layer XM lies between IA and IB
in tech order and no via reaches it: the cut layers between two routing
layers come from the via definitions, not from the layer order. The cut
layer names, via names and sizes are made up."""

import re

from conftest import TECH_LEF

STACK = ["D12", "H1", "H2", "G1", "G2", "IA", "IB"]
CUTS = {"D12": "C1", "H1": "C2", "H2": "C3", "G1": "C4", "G2": "C5", "IA": "C6"}
RULE = """VIARULE GEN_IA_IB GENERATE
  LAYER IA ;
    ENCLOSURE 0.05 0.02 ;
  LAYER IB ;
    ENCLOSURE 0.02 0.05 ;
  LAYER C6 ;
    RECT -0.05 -0.05 0.05 0.05 ;
    SPACING 0.2 BY 0.2 ;
END GEN_IA_IB
"""
# One row of two cuts, from the rule's parameters.
GENERATED = """VIA V_IA_IB_2
  VIARULE GEN_IA_IB ;
  CUTSIZE 0.1 0.1 ;
  LAYERS IA C6 IB ;
  CUTSPACING 0.1 0.1 ;
  ENCLOSURE 0.05 0.02 0.02 0.05 ;
  ROWCOL 1 2 ;
END V_IA_IB_2
"""


def fixed(name, bottom, cut, top, default=True):
    """A one-cut via: pads 0.4 x 0.3 below and 0.3 x 0.4 above a 0.2 cut."""
    return (f"VIA {name}{' DEFAULT' if default else ''}\n"
            f"  LAYER {bottom} ;\n    RECT -0.2 -0.15 0.2 0.15 ;\n"
            f"  LAYER {cut} ;\n    RECT -0.1 -0.1 0.1 0.1 ;\n"
            f"  LAYER {top} ;\n    RECT -0.15 -0.2 0.15 0.2 ;\n"
            f"END {name}\n")


def via_name(bottom, top):
    return f"V_{bottom}_{top}"


def tech_text(vias=True):
    base = TECH_LEF.read_text()
    blocks = dict(re.findall(r"(?ms)^(?=LAYER (\w+)$)(.*?^END \1\n)", base))
    blocks["D12"] = ("LAYER D12\n  TYPE ROUTING ;\n  DIRECTION VERTICAL ;\n  PITCH 0.1 ;\n"
                     "  WIDTH 0.05 ;\nEND D12\n")
    blocks["XM"] = ("LAYER XM\n  TYPE ROUTING ;\n  DIRECTION HORIZONTAL ;\n  PITCH 1 ;\n"
                    "  WIDTH 0.5 ;\nEND XM\n")
    text = base[:base.index("LAYER H1")]
    for layer in STACK:
        if layer == "IB":
            text += blocks["XM"]
        text += blocks[layer]
        if layer in CUTS:
            text += f"LAYER {CUTS[layer]}\n  TYPE CUT ;\nEND {CUTS[layer]}\n"
    if vias:
        text += RULE
        for bottom, top in zip(STACK, STACK[1:]):
            text += fixed(via_name(bottom, top), bottom, CUTS[bottom], top)
        text += GENERATED
    return text + "END LIBRARY\n"
