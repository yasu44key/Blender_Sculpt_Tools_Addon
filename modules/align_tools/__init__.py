"""Align Tools — the ten AlignScripts operations merged into four operators.

Replaces: AlignScripts/ (Align_Edge_To_Axis, Align_Object_To_Multi_Select_Face,
Align_Object_To_Selected_Face, Align_Object_Z_Axis_To_Selected_Faces,
Origin_To_Bottom, Origin_To_Offset_From_Bottom, Snap_To_Ground,
Snap_To_Surface_Advanced, Snap_To_Under_Object, Transport_Transform_To_Cursor)

All plain operators (no mouse interaction). Rotations multiply matrix_world in
world space instead of overwriting rotation_euler; origins use world-space
vertices and shift the mesh backwards so the object stays put; the drop casts
contact rays from both sides so bumps under an object are not missed; the
cursor match keeps the scale.
"""

import bpy

from . import ops, panels  # noqa: F401

META = {
    "label": "Align Tools",
    "description": "Align, origin, drop and cursor-match operators for meshes",
    "tabs": ("Model",),
}

JA = {
    "Align Tools": "整列ツール",
    "Align to Axis": "軸に整列",
    "Origin to Bottom": "原点を下に",
    "Drop to Surface": "表面に落とす",
    "Match Cursor": "カーソルに合わせる",
    "Align Source": "整列の基準",
    "Rotation Pivot": "回転の中心",
    "Apply Rotation": "回転を適用",
    "Bottom Offset Ratio": "底からの割合",
    "Drop Direction": "落とす方向",
    # "Snap Target" and "Align Rotation" are left to Blender's own dictionary
    # (it wins over add-on entries and its wording is fine: スナップ対象 / 回転を揃える).
    "Contact Offset": "接触手前の間隔",
    "Use Cursor Location": "カーソルの位置を使う",
    "Use Cursor Rotation": "カーソルの回転を使う",
    "Edit mode only": "編集モード専用",
    "Select a mesh": "メッシュを選択してください",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
