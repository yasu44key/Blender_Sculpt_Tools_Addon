"""Quick Buttons — one-press transform helpers in the Utility tab.

Reset location / rotation / scale per axis, rotate by fixed angles, flatten,
mirror, step along an axis, pivot / orientation / Affect Only, 3D cursor moves.

Replaces (idea only, no code taken): ★archive/BlenderProject/Tools for me_v2.py
"""

import bpy

from . import ops, panels

META = {
    "label": "Quick Buttons",
    "description": "One-press transform buttons (reset, rotate, flatten, mirror, cursor)",
    "tabs": ("Utility",),
}

JA = {
    "Quick Buttons": "一押しボタン",
    "Reset Transform": "トランスフォームをリセット",
    "Rotate (global)": "回転（グローバル）",
    "Quick Rotate": "決まった角度で回転",
    "Step": "刻み",
    "Distance moved by the step buttons": "刻みボタンで動かす距離",
    "Selection to Cursor": "選択物をカーソルへ",
    "World Origin": "ワールド原点",
    "Origin to Cursor": "原点をカーソルへ",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_quick_buttons = bpy.props.PointerProperty(type=ops.QuickButtonsSettings)


def unregister():
    del bpy.types.Scene.sts_quick_buttons
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
