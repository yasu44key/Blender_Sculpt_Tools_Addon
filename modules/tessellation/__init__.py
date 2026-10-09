"""Tessellation — cover a mesh with a tile or cell pattern.

Two ways to the same kind of result:
- Tile Faces: exact-size tiles (square, brick, triangle, hexagon, octagon,
  Voronoi) cut into the mesh in one shot; adjustable with F9.
- Live Cells: a Geometry Nodes modifier; seamless on curved surfaces and
  editable any time (density, jitter, gap, thickness, lattice).
Plus Skin Lattice: edge struts through the Skin modifier.

Replaces: Tessellation/cell_tessellation.py v1.1
"""

import bpy

from . import ops, panels

META = {
    "label": "Tessellation",
    "description": "Cover meshes with exact tiles (one shot) or live Geometry Nodes cells",
    "tabs": ("Model",),
}

JA = {
    # Tile Size / Lattice / Jitter / Gap: Blender's own words (タイルサイズ / ラティス / ジッター / ギャップ)
    "Tessellation": "テッセレーション",
    "Tile Faces": "面をタイル化",
    "Length / Height": "長さ／高さ",
    "Row Shift": "段ずらし",
    "Pattern Rotation": "模様の回転",
    "Pattern Offset": "模様のずらし",
    "Continuous up to": "連続させる角度",
    "Merge Small Pieces": "小片を結合",
    "Octagon + Square": "八角形＋正方形",
    "Brick": "レンガ",
    "Hexagon": "六角形",
    "Voronoi": "ボロノイ",
    "Target: selected faces": "対象: 選択した面",
    "Target: whole mesh": "対象: メッシュ全体",
    "Adjust with F9 after tiling": "タイル化の後 F9 で調整できます",
    "Select the faces to tile": "タイル化する面を選択してください",
    "Too many tiles: make Tile Size larger": "タイルが多すぎます。タイルの大きさを大きくしてください",
    "Meshes with shape keys are not supported": "シェイプキーのあるメッシュには使えません",
    "No tiles were made": "タイルを作れませんでした",
    "Select a mesh with faces": "面のあるメッシュを選択してください",
    "Live Cells": "ライブセル",
    "Add Live Cells": "ライブセルを追加",
    "Remove Live Cells": "ライブセルを外す",
    "No live cells on the selected meshes": "選択したメッシュにライブセルがありません",
    "Show Cells": "セルを表示",
    "Apply (Bake)": "適用（確定）",
    "Keep Base": "下地を残す",
    "Cell Thickness": "セルの厚み",
    "Strut Radius": "支柱の半径",
    "Skin Lattice": "スキン格子",
    "Add Skin Modifier": "スキンモディファイアを追加",
    "Select the vertices": "頂点を選択してください",
    "Select a mesh": "メッシュを選択してください",
    "Object Mode only": "オブジェクトモード専用",
}

classes = ops.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
