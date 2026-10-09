"""Sujibori — panel lines carved into a mesh along curves.

Two methods on the same lines: Live (Geometry Nodes; the groove follows while
you edit the curves) and Boolean (cutter meshes rebuilt on Update Grooves).

Replaces: Sujibori/Sujibori.py v0.5 (and SujiboriBk.py)
"""

import bpy

from . import ops, panels

META = {
    "label": "Sujibori (Panel Lines)",
    "description": "Carve panel lines into a mesh along curves (live Geometry Nodes or Boolean)",
    "tabs": ("Model",),
}

JA = {
    "Sujibori (Panel Lines)": "筋彫り（パネルライン）",
    "Panel Lines": "筋彫り",
    "Set Up Panel Lines": "筋彫りを準備",
    "Set Up (Live)": "準備（ライブ）",
    "Set Up (Boolean)": "準備（ブーリアン）",
    "Live (Geometry Nodes)": "ライブ（ジオメトリノード）",
    "Boolean (Snapshot)": "ブーリアン（写し）",
    "Groove Width": "溝の幅",
    "Show Grooves": "溝を表示",
    "Draw Line": "線を描く",
    "Add Selected Curves": "選択カーブを線に追加",
    "Remove Line": "線から外す",
    "Update Grooves": "溝を更新",
    "Press Update Grooves after editing lines or width": "線や幅を変えたら「溝を更新」を押してください",
    "Remove Panel Lines": "筋彫りを外す",
    "Apply (Bake)": "適用（確定）",
    "Select the mesh to carve": "彫るメッシュを選択してください",
    "Line of": "筋彫りの線:",
    "Object Mode only": "オブジェクトモード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.sts_sujibori = bpy.props.PointerProperty(type=ops.SujiboriSettings)


def unregister():
    del bpy.types.Object.sts_sujibori
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
