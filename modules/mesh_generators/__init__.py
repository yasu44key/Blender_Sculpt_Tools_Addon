"""Mesh Generators — add lattice, hexagonal grid, random grid and leaf venation at the 3D cursor.

Replaces: CrystalStructureMesh.py, TetrahedralSpace-Filling.py, HexagonalMeshGenerator.py,
gridmesh3.py, LeafVenationMeshGenerator4.py
"""

import bpy

from . import ops, panels

META = {
    "label": "Mesh Generators",
    "description": "Lattice, hexagonal grid, random grid and leaf venation at the 3D cursor",
    "tabs": ("Generate",),
}

JA = {
    # panel
    "Mesh Generators": "メッシュ生成",
    "Adjust with F9 after adding": "追加後に F9 で調整",
    # operators
    "Lattice Grid": "格子メッシュ",
    "Hexagonal Grid": "六角格子メッシュ",
    "Random Grid": "ランダム格子メッシュ",
    "Leaf Venation": "葉脈",
    # properties
    # ("Cell Type" is left to Blender's own セルタイプ; "Jitter X/Y/Z" to object_brush's ジッター X etc.)
    "Build Style": "作り方",
    "Cell Gap": "セルの隙間",
    "Tile Gap": "タイルの隙間",
    "Count X": "X 方向の本数",
    "Count Y": "Y 方向の本数",
    "Count Z": "Z 方向の本数",
    "Cols": "列数",
    "Add Midpoints": "中点も追加",
    "Leaf Outline": "輪郭",
    "Attractors": "引き寄せ点",
    "Growth Step": "成長の歩幅",
    "Kill Distance": "除去距離",
    "Pull Radius": "引き寄せ半径",
    "Include Outline": "輪郭も含める",
    "Use Skin": "スキンで太さ",
    # reports
    "A curve must be active for the CURVE outline": "CURVE 輪郭にはカーブをアクティブにしてください",
    "The active curve has no closed spline": "アクティブなカーブに閉じたスプラインがありません",
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
