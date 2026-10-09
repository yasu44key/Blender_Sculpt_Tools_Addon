"""N-panel tab names. Every panel must take its bl_category from here.

Tabs are split by work context, not by tool. See docs/CONVENTIONS.md.
"""

CURVE = "Curve"         # draw / edit / convert curves
SCULPT = "Sculpt"       # sculpt-mode helpers, remesh, face sets, masks
MODEL = "Model"         # mesh editing, retopology, alignment
GENERATE = "Generate"   # parametric objects and curves
UTILITY = "Utility"     # language switch and other environment helpers

# Only tabs Blender does not translate itself (Curve, Generate, Utility... it does).
JA = {
    "Model": "モデル",
}
