"""Face Set Tools — mask the face set you click in Sculpt Mode.

Replaces: CFS2.py, FaceToMaskTest43.py, FaceSetDeformer_fixed.py
(the deformer is dropped: Blender's built-in Mesh Filter does that job)
"""

import bpy

from . import ops, panels

META = {
    "label": "Face Set Tools",
    "description": "Click a face set in Sculpt Mode to mask it",
    "tabs": ("Sculpt",),
}

# Only strings Blender's own dictionary does not translate; its dictionary wins.
JA = {
    "Face Set Tools": "面セットツール",
    "Face Set to Mask": "面セットをマスクに",
    "Face Set from Mask": "マスクから面セット",
    "Sculpt Mode only": "スカルプトモードのみ",
    "Click a face set": "面セットをクリック",
    "Esc / right-click: cancel": "Esc・右クリック: キャンセル",
    "Smooth / Inflate: drag in the viewport": "スムーズ / インフレート: ビューポートでドラッグ",
    "Smooth Face Set": "面セットをスムーズ",
    "Keep Outline": "輪郭を保つ",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_face_set_tools = bpy.props.PointerProperty(type=ops.FaceSetToolsSettings)


def unregister():
    del bpy.types.Scene.sts_face_set_tools
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
