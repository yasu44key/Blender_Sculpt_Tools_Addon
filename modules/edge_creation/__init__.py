"""Edge Creation — click in the 3D view to place vertices and edges that
snap to object surfaces (retopology).

Replaces: Edge_Creation_Tool_4_5.py
"""

import bpy

from . import logic, ops, panels

META = {
    "label": "Edge Creation",
    "description": "Click to place vertices and edges snapped to surfaces (retopology)",
    "tabs": ("Model",),
}

JA = {
    "Edge Creation": "エッジ作成",
    "Edge Draw": "辺描画",
    "Draw Edges": "辺を描く",
    "New Object": "新規オブジェクト",
    "Active Mesh": "アクティブメッシュ",
    "Fill Face": "面を埋める",
    # "Snap to Surface" and "Plane Axis" are left to Blender's own dictionary
    # (it wins over add-on entries and its wording is fine).
    "Depth Mode": "奥行きモード",
    "Cursor Depth": "カーソルの奥行き",
    "World Plane": "ワールド平面",
    "Drag Interval": "ドラッグ間隔",
    "Fill On Close": "閉じるときに面を張る",
    "Click: add point": "クリック: 点を追加",
    "Drag: add points continuously": "ドラッグ: 連続して点を追加",
    "Backspace: remove last": "Backspace: 最後の点を削除",
    "C: close loop and finish": "C: ループを閉じて終了",
    "Enter, Right-click: finish": "Enter, 右クリック: 終了",
    "Esc: cancel (discard)": "Esc: 破棄",
    "Middle mouse, wheel: navigate": "中ボタン・ホイール: 視点移動",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_edge_creation = bpy.props.PointerProperty(type=ops.EdgeCreationSettings)


def unregister():
    del bpy.types.Scene.sts_edge_creation
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
