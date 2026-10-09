"""Retopo Assistant — reduce a mesh with a live Decimate modifier "STS Decimate"
and protect ridges (from a sculpt mask or from an angle) through the vertex
group "Ridge".

Replaces: docs/old/retopo_assistant (the working part: Decimate + sculpt-mask
ridge protection), docs/old/reducer01.py (Reduce with Sharp Preserve)
"""

import bpy

from . import ops, panels

META = {
    "label": "Retopo Assistant",
    "description": "Live Decimate modifier with ridge protection (sculpt mask / angle)",
    "tabs": ("Model",),
}

JA = {
    "Retopo Assistant": "レトポ・アシスタント",
    "Add Decimate": "デシメートを追加",
    "Ridge from Mask": "マスクから稜線",
    "Ridge from Angle": "角度から稜線",
    "Apply Decimate": "デシメートを適用",
    "Remove Decimate": "デシメートを外す",
    "Ridge Protection": "稜線保護",
    "No Ridge group yet": "まだ稜線グループがありません",
    "Select a mesh": "メッシュを選択してください",
    "Object or Sculpt Mode only": "オブジェクトまたはスカルプトモード専用",
    "No decimate modifier on this mesh": "このメッシュにデシメートモディファイアがありません",
    "This mesh has no sculpt mask": "このメッシュにはスカルプトマスクがありません",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
