"""Voxel Remesh — join selected objects into one mesh and voxel-remesh it,
keeping one face set per source object.

Replaces: Voxel/VoxelV2_28.py (and its older versions, My_Sculpt_Tools/voxel_remesh.py),
Voxel/quick_voxel_remesh_panel_merged.py, Voxel/Fask_Face_set.py,
★archive/Dyntopo/DyntopoFlow1.py (remesh while sculpting with Dyntopo kept on)
"""

import bpy

from . import ops, panels

META = {
    "label": "Voxel Remesh",
    "description": "Join selected objects and voxel-remesh them, one face set per object",
    "tabs": ("Sculpt",),
}

JA = {
    "Voxel Remesh": "ボクセルリメッシュ",
    "Voxels on the longest side": "最長辺のボクセル数",
    "(under 400 is safe)": "（400 未満なら安全）",
    "Join & Remesh": "統合してリメッシュ",
    "Apply Remesh": "リメッシュを適用",
    "Use Modifier Results": "モディファイア適用後の形を使う",
    "Keep Originals": "元を残す",
    "Face Set per Object": "オブジェクトごとに面セット",
    "Apply Now": "すぐに適用",
    "As Modifier": "モディファイア",
    "Then": "その後",
    "Sources": "元のオブジェクト",
    "Resolution from Voxel Size": "ボクセルサイズから解像度",
    "Voxel size is very small for this size": "この大きさにはボクセルサイズが細かすぎます",
    "Voxel Remesh modifier (preview)": "ボクセルリメッシュ・モディファイア（確認中）",
    "Join & Remesh: Object Mode only": "統合してリメッシュ: オブジェクトモード専用",
    "Edit Voxel Size (Shift+R)": "ボクセルサイズを編集 (Shift+R)",
    "Dyntopo: On": "Dyntopo: オン",
    "Dyntopo: Off": "Dyntopo: オフ",
    "Apply Remesh keeps Dyntopo on": "リメッシュを適用しても Dyntopo はオンのまま",
    "No mesh, curve, surface, metaball or text selected": "メッシュ・カーブ・サーフェス・メタボール・テキストが選択されていません",
    "The selected objects have no faces": "選択したオブジェクトに面がありません",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
