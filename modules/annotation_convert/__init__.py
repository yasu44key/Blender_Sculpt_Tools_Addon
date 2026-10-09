"""Annotation Convert — turn the scene's annotation strokes into one object.

Replaces: Annotations_to_Bezier_Curves_14.py, Poly_Line_Tool10.py (docs/old/)

One operator, two targets: a 3D Bezier curve (points thinned with
Ramer-Douglas-Peucker, smooth handles, VECTOR handles at sharp turns) or a
mesh polyline (edges along the thinned points, no faces). Object Mode only;
every setting is an operator property, adjustable with F9.
"""

import bpy

from . import ops, panels  # noqa: F401

META = {
    "label": "Annotation Convert",
    "description": "Convert annotation strokes to a Bezier curve or a mesh polyline",
    "tabs": ("Curve",),
}

JA = {
    "Annotation Convert": "アノテーション変換",
    "Convert Annotation": "アノテーション変換",
    "Hide After": "変換後に隠す",
    "Adjust with F9 after converting": "変換後は F9 で調整",
    "Object Mode only": "オブジェクトモード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
