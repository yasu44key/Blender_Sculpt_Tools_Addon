"""Strip Draw — draw bands on a surface: armor plates, straps, or soft clay strips.

Each drawn curve gets its own live Geometry Nodes modifier (width x pen pressure,
lift, thickness, optional clay remesh); change it any time, per strip.

Replaces: ★archive/Armor_Ribbon/Armor_Ribbon_Pro.py, Mesh_Clay_Strip.py,
Mesh_Clay_Strip.sculpt.py, mesh_clay_strip_v024.py
"""

import bpy

from . import live, ops, panels

META = {
    "label": "Strip Draw",
    "description": "Draw armor ribbons or clay strips on a surface (live, per stroke)",
    "tabs": ("Sculpt",),
}

JA = {
    "Strip Draw": "帯を描く",
    "Draw On": "描く面",
    "Ribbon": "リボン",
    "Clay": "クレイ",
    "Band Thickness": "帯の厚み",
    "Pressure Width": "筆圧で幅",
    "Start Strip": "帯を描き始める",
    "Finish Strip": "帯を描き終える",
    "Strips from Curves": "カーブから帯",
    "Strips to Meshes": "帯をメッシュに",
    "This strip": "この帯",
    "Draw on the surface (Draw tool)": "表面に描く（描画ツール）",
    "Select the surface (a mesh) first": "先に表面（メッシュ）を選んでください",
    "Select curves and a surface (a mesh, active or set in the panel)": "カーブと表面（メッシュ：アクティブかパネルで指定）を選んでください",
    "Select strips": "帯を選んでください",
    "Nothing was drawn; the empty strip was removed": "何も描かれなかったので空の帯を削除しました",
    "Object Mode only": "オブジェクトモード専用",
    "Points": "ポイント",
    "Point Spacing": "点の間隔",
    "Even Spacing": "間隔で整える",
    "Decimate": "間引き",
    "Subdivide": "細分化",
    "Keep Every": "残す間隔",
    "Drawn on {}: Target set to it": "{} に描かれていたのでターゲットをそれにしました",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_strip_draw = bpy.props.PointerProperty(type=ops.StripDrawSettings)
    live.register()


def unregister():
    live.unregister()
    del bpy.types.Scene.sts_strip_draw
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
