"""Shapes — add spindle, egg family, gear, star and platonic solids at the 3D cursor.

Replaces: special_object_maker_addon.py, platonic_solids_generator.py
"""

import bpy

from . import ops, panels

META = {
    "label": "Shapes",
    "description": "Spindle, egg / capsule, gear, star and platonic solids at the 3D cursor",
    "tabs": ("Generate",),
}

JA = {
    # panel ("Shapes" is left to Blender's own translation)
    "Adjust with F9 after adding": "追加後に F9 で調整",
    # operators
    "Spindle": "スピンドル",
    "Egg / Capsule": "卵型 / カプセル",
    "Gear": "ギア",
    "Star": "スター",
    "Platonic Solid": "正多面体",
    # properties
    "Radius": "半径",
    "Height": "高さ",
    "Rings": "リング",
    "Bottom Curvature": "底部の曲率",
    "Top Curvature": "頂部の曲率",
    "Cylinder Height": "円筒部の高さ",
    "Teeth": "歯数",
    "Inner Radius": "内径",
    "Outer Radius": "外径",
    "Plate Thickness": "厚さ",
    "Tooth Width": "歯先の幅",
    "Hole Radius": "穴の半径",
    "Tips": "先端の数",
    "Hole Radius must be smaller than Inner Radius": "穴の半径は内径より小さくしてください",
    "Truncated Icosahedron": "切頂二十面体",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_mesh_add.append(ops.add_menu)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(ops.add_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
