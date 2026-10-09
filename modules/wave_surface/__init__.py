"""Wave Surface — z = f(x, y) (quadratic + up to three ring waves) as a live,
animatable Geometry Nodes modifier, on a new grid or on any mesh.

Replaces: parametric_plane/ (parametric_plane.py, create_wave_plane.py,
create_wave_plane01.py, Create_Complex_Wave_Plane.py, Create_Complex_Wave_Plane02.py).
smoothmod.py from the same folder is dropped (broken; Blender's Smooth Vectors /
Weighted Normal modifier do it).
"""

import bpy

from . import ops, panels

META = {
    "label": "Wave Surface",
    "description": "Quadratic and ring-wave surfaces as a live, animatable Geometry Nodes modifier",
    "tabs": ("Generate",),
}

JA = {
    # Spread / Motion / Time Offset / Along Normals: Blender's own words (広がり / モーション / タイムオフセット / 法線に追従)
    "Wave Surface": "波の曲面",
    "New Grid": "新しいグリッド",
    "Add to Selected": "選択に追加",
    "Remove Wave Surface": "波の曲面を外す",
    "No wave surface on the selected meshes": "選択したメッシュに波の曲面がありません",
    "Scatter Centers": "中心をばらまく",
    "Show Surface": "曲面を表示",
    "Apply (Bake)": "適用（確定）",
    "Shape (Quadratic)": "形（二次曲面）",
    "Constant (f)": "定数 (f)",
    "Animate": "アニメーション",
    "Wave 1": "波 1",
    "Wave 2": "波 2",
    "Wave 3": "波 3",
    "Wave 1 Amplitude": "波1 振幅",
    "Wave 2 Amplitude": "波2 振幅",
    "Wave 3 Amplitude": "波3 振幅",
    "Wave 1 Wavelength": "波1 波長",
    "Wave 2 Wavelength": "波2 波長",
    "Wave 3 Wavelength": "波3 波長",
    "Wave 1 Center X": "波1 中心 X",
    "Wave 2 Center X": "波2 中心 X",
    "Wave 3 Center X": "波3 中心 X",
    "Wave 1 Center Y": "波1 中心 Y",
    "Wave 2 Center Y": "波2 中心 Y",
    "Wave 3 Center Y": "波3 中心 Y",
    "Wave 1 Speed": "波1 速さ",
    "Wave 2 Speed": "波2 速さ",
    "Wave 3 Speed": "波3 速さ",
    "Select a mesh": "メッシュを選択してください",
    "Object Mode only": "オブジェクトモード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_mesh_add.append(ops.add_menu)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(ops.add_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
