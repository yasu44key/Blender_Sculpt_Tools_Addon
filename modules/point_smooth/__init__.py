"""Point Smooth — edit selected points in Edit Mode: straighten open chains,
smooth closed loops, relax 2D patches, inflate along normals and wrap onto
another object (mesh, curve and NURBS surface).

Replaces: point_smooth_rap_all.py (smooth + inflate + wrap; no mouse tools)
"""

import bpy

from . import ops, panels  # noqa: F401

META = {
    "label": "Point Smooth",
    "description": "Straighten chains, smooth loops and relax patches of selected points (mesh, curve, NURBS surface)",
    "tabs": ("Model",),
}

JA = {
    "Point Smooth": "ポイントスムース",
    "Edit Mode only": "編集モード専用",
    "Adjust with F9 after running": "実行後は F9 で調整",
    "Fix Boundary": "境界を固定",
    "Tangent Smooth": "接線方向にスムーズ",
    "Auto Handle Length": "ハンドル長を自動",
    # "Inflate" alone is left to Blender's dictionary ("インフレート"), so the
    # panel heading uses "Inflate Points" instead.
    "Inflate Points": "点を膨らませ",
    "Wrap": "ラップ",
    "Wrap Points": "点をラップ",
    "Wrap Target": "ラップ対象",
    # "Strength", "Iterations", "Amount" and "Offset" are left to Blender's own dictionary.
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_point_smooth = bpy.props.PointerProperty(type=ops.PointSmoothSettings)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(panels.menu_mesh)
    bpy.types.VIEW3D_MT_edit_curve_ctrlpoints.append(panels.menu_curve)


def unregister():
    bpy.types.VIEW3D_MT_edit_curve_ctrlpoints.remove(panels.menu_curve)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(panels.menu_mesh)
    del bpy.types.Scene.sts_point_smooth
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
