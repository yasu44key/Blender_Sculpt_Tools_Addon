"""Smooth Normals — smooth the shading normals where a vertex group is painted,
as a live Geometry Nodes modifier (custom normals; the shape does not change).

Replaces: parametric_plane/smoothmod.py, ★archive/SmoothNomal/SmoothNomal.py
(mask normal smoothing: "From Sculpt Mask")
"""

import bpy

from . import ops, panels

META = {
    "label": "Smooth Normals",
    "description": "Smooth shading normals by vertex-group weight (live Geometry Nodes modifier)",
    "tabs": ("Model",),
}

JA = {
    # Smooth Normals / Smoothness: Blender's own words (法線をスムーズに / スムーズ)
    "Add Smooth Normals": "法線のスムーズを追加",
    "Remove Smooth Normals": "法線のスムーズを外す",
    "No smooth normals on the selected meshes": "選択したメッシュに法線のスムーズがありません",
    "Show Effect": "効果を表示",
    "From Sculpt Mask": "スカルプトマスクから",
    "This mesh has no sculpt mask": "このメッシュにはスカルプトマスクがありません",
    "Apply (Bake)": "適用（確定）",
    "Select a mesh": "メッシュを選択してください",
    "Object Mode only": "オブジェクトモード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
