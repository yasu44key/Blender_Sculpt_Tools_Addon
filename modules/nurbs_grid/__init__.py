"""NURBS Grid — click grid points row by row in the 3D view and build a
NURBS surface that faces the viewer (weights, snapping, patchwork helpers).

Replaces: Draw_NURBS_Grid_Patch63.py, nurbs_hud_w.py
"""

import bpy

from . import logic, ops, panels  # noqa: F401

META = {
    "label": "NURBS Grid",
    "description": "Draw a NURBS grid surface point by point, snapped and facing the viewer",
    "tabs": ("Curve",),
}

JA = {
    "NURBS Grid": "NURBSグリッド",
    "Draw NURBS Grid": "NURBSグリッドを描く",
    "Start Drawing": "描画開始",  # same text as bezier_draw's entry (shared string)
    "Flip Surface Normal": "法線を反転",
    "Join Surfaces": "サーフェスを結合",
    "Toggle Loop": "ループ切替",
    "Loop U": "ループ U",
    "Loop V": "ループ V",
    "U Count": "1行の点数 (U)",
    "Use Drag": "ドラッグで描く",
    "Drag Interval": "ドラッグ間隔",
    "Snap NURBS Only": "NURBS点のみスナップ",
    "Patchwork": "継ぎ接ぎ",
    "Select a NURBS surface": "NURBSサーフェスを選択",
    "After joining: Edit Mode, select border points, F": "結合後: 編集モードで境界点を選んで F",
    "Click: add point": "クリック: 点を追加",
    "Drag: add points continuously": "ドラッグ: 連続して点を追加",
    "Up / Down: points per row (first row only)": "↑↓: 1行の点数 (1行目まで)",
    "Ctrl + wheel: weight of the next points": "Ctrl+ホイール: 次の点の重み",
    "Backspace, Ctrl+Z: remove last point": "Backspace, Ctrl+Z: 最後の点を削除",
    "Enter: build the surface": "Enter: サーフェスを作成",
    "Esc, Right-click: cancel": "Esc, 右クリック: 破棄",
    "Middle mouse, wheel: navigate": "中ボタン・ホイール: 視点移動",
    # "Snap", "Weight", "None / Vertex / Face / Grid" and "Loop" are left to
    # Blender's own dictionary (it wins over add-on entries and its wording is fine).
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_nurbs_grid = bpy.props.PointerProperty(type=ops.NurbsGridSettings)


def unregister():
    del bpy.types.Scene.sts_nurbs_grid
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
