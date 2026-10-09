"""Wear — edge chips near sharp edges and surface erosion, one shot, F9.

Replaces: aging_toolkit.py (docs/old/)

Sizes are relative to each face (sqrt of its area) so the result scales with
the object; the random generator restarts from the seed for every mesh.
"""

import bpy

from . import ops, panels  # noqa: F401

META = {
    "label": "Wear",
    "description": "Edge chips and surface erosion sized to each face (one shot, adjust with F9)",
    "tabs": ("Sculpt",),
}

JA = {
    "Wear": "摩耗",
    "Edge Damage": "エッジ欠け",
    "Sharp Angle": "鋭角のしきい値",
    "Damage Band": "欠けの届く幅",
    "Chip Rate": "欠け率",
    "Chip Depth": "欠け深さ",
    "Erosion": "浸食",
    "Erosion Rate": "浸食率",
    "Erosion Depth": "浸食深さ",
    "Gravity Bias": "重力の偏り",
    "Crumble Open Borders": "開いた縁を崩す",
    "Crumble Strength": "崩す強さ",
    "Adjust with F9 after running": "実行後は F9 で調整",
    "Object Mode only": "オブジェクトモード専用",
    # "Subdivisions" and "Seed" are left to Blender's own dictionary.
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
