"""Thickness Guard — wall thickness for 3D printing.

Replaces: MinThicknessGuard (docs/old/min_thickness_guard.py)

Bake thickness, select / fix thin areas, write a sculpt mask from the
thickness, and a brush that pushes thin walls out only where you paint.
"""

import bpy

from . import brush, ops, panels

META = {
    "label": "Thickness Guard",
    "description": "Bake wall thickness, select and fix thin areas, write a sculpt mask from it",
    "tabs": ("Sculpt",),
}

# Only strings Blender's own dictionary does not translate; its dictionary wins.
JA = {
    "Bake Thickness": "厚みをベイク",
    "Select Thin": "薄い部分を選択",
    "Fix Thin": "薄い部分を修正",
    "Thickness to Mask": "厚みをマスクに",
    "Thickness Guard": "厚みガード",
    "Adjust with F9 after running": "実行後は F9 で調整",
    "Thickness Guard Brush": "厚みガードブラシ",
    "Walls thinner than this are pushed out under the brush": "これより薄い壁をブラシの下で押し出す",
    "Share of the missing thickness added per dab": "1回の塗りで足りない厚みのうち足す割合",
    "Brush radius on the surface (mouse wheel or [ ] while painting)": "表面上のブラシ半径（塗っている間はホイールか [ ]）",
}

classes = ops.classes + brush.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_thickness_brush = bpy.props.PointerProperty(type=brush.ThicknessBrushSettings)


def unregister():
    del bpy.types.Scene.sts_thickness_brush
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
