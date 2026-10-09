"""Metaball Brush — drag in the 3D view to paint metaballs under the mouse.

Replaces: MetaballBrushTool_v87.py
"""

import bpy

from . import logic, ops, panels  # noqa: F401  (logic is imported for tests)

META = {
    "label": "Metaball Brush",
    "description": "Drag in the 3D view to paint metaballs under the mouse",
    "tabs": ("Sculpt",),
}

JA = {
    "Metaball Brush": "メタボールブラシ",
    # "Snap to Surface" and "Plane Axis" are left to Blender's own dictionary
    # (it wins over add-on entries and its wording is fine).
    "Depth Mode": "奥行きモード",
    "Cursor Depth": "カーソルの奥行き",
    "World Plane": "ワールド平面",
    "Placement Mode": "配置モード",
    "Undo Mode": "取り消しモード",
    "Placement Interval": "配置間隔",
    "Pixel Distance": "ピクセル距離",
    "Min Size": "最小サイズ",
    "Max Size": "最大サイズ",
    "Pressure Curve": "筆圧カーブ",
    # "Mirror X" / "Mirror Y" are left to Blender's own dictionary
    # (ミラー X / ミラー Y); "Mirror Z" has no entry there, so we match its wording.
    "Mirror Z": "ミラー Z",
    "Drag: paint": "ドラッグ: 描く",
    "Esc, Right-click: end (strokes stay)": "Esc・右クリック: 終了 (ストロークは残る)",
    "Middle mouse, wheel: navigate": "中ボタン・ホイール: 視点移動",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_metaball_brush = bpy.props.PointerProperty(type=ops.MetaballBrushSettings)


def unregister():
    del bpy.types.Scene.sts_metaball_brush
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
