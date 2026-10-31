"""Object Brush — drag in the 3D view to place copies of an object
(or a random one from a collection) onto surfaces.

Replaces: Object_Brush_Pro_Collection1_15.py
"""

import bpy

from . import logic, ops, panels  # noqa: F401  (logic is imported for tests)

META = {
    "label": "Object Brush",
    "description": "Drag in the 3D view to place object copies on surfaces",
    "tabs": ("Sculpt",),
}

JA = {
    "Object Brush": "オブジェクトブラシ",
    "Brush Source": "ブラシ元",
    "Brush Object": "ブラシオブジェクト",
    "Brush Collection": "ブラシコレクション",
    "Output Collection": "出力コレクション",
    "Target Collection": "対象コレクション",
    "New Collection Name": "新しいコレクション名",
    # "Placement Mode" and "Drag: paint" match wording already used by
    # Metaball Brush (Blender's own dictionary has no entry for them).
    "Placement Mode": "配置モード",
    "Stroke Spacing": "ストローク間隔",
    "Grid Spacing": "格子間隔",
    # "Base Scale" and "Align to Normal" are left to Blender's own dictionary
    # (it wins over add-on entries and its wording is fine: ベーススケール / 法線に揃える).
    "Pen Pressure": "筆圧",
    "Align to Stroke": "ストロークに合わせる",
    "Scale Jitter": "スケールジッター",
    "Random Rotation": "ランダム回転",
    "Jitter X": "ジッター X",
    "Jitter Y": "ジッター Y",
    "Jitter Z": "ジッター Z",
    "Connect Centers": "中心をカーブでつなぐ",
    "Smooth Line": "なめらか",
    "Close Line": "輪にする",
    "Connect Selected": "選択をカーブでつなぐ",
    "Nearest First": "近い順",
    "Select two or more objects": "オブジェクトを2つ以上選択してください",
    "Follow": "追従",
    "Curve Follows Objects": "カーブがオブジェクトに追従",
    "Objects Follow Curve": "オブジェクトがカーブに追従",
    "The objects of this line are gone": "このカーブのオブジェクトが見つかりません",
    "Drag: paint":"ドラッグ: 描く",
    "Ctrl+Z, Ctrl+Shift+Z: undo, redo": "Ctrl+Z・Ctrl+Shift+Z: 取り消し・やり直し",
    "Esc, Right-click: end (copies stay)": "Esc・右クリック: 終了 (コピーは残る)",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_object_brush = bpy.props.PointerProperty(type=ops.ObjectBrushSettings)


def unregister():
    del bpy.types.Scene.sts_object_brush
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
