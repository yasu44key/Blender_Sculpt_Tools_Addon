"""Panel Raise — a grooved raised panel on the selected faces, one shot, F9.

Replaces: panel_raise_addon.py (docs/old/)

margin / groove_width / groove_depth / panel_height / bevel_width are lengths
in object units; panel_height is measured from the original surface.
"""

import bpy

from . import ops, panels  # noqa: F401

META = {
    "label": "Panel Raise",
    "description": "Grooved raised panel on the selected faces (one shot, adjust with F9)",
    "tabs": ("Model",),
}

JA = {
    "Panel Raise": "パネル起こし",
    "Margin": "余白",
    "Groove Width": "溝の幅",
    "Groove Depth": "溝の深さ",
    "Panel Height": "パネルの高さ",
    "Bevel Width": "面取りの幅",
    "Bevel Segments": "面取りの分割数",
    "Each Face": "面ごとに個別",
    "Adjust with F9 after running": "実行後は F9 で調整",
    "Edit Mode only": "編集モード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
