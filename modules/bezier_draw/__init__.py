"""Bezier Draw — freehand Bezier drawing, curve effects and curve generators.

Replaces: BezierDrawTool/BezierDraw23.py, Curve_Subdivide_&_Decimate,
spiral/bezier_spiral.py
"""

import bpy

from . import ops_connect, ops_convert, ops_draw, ops_effects, ops_generate, ops_topology, panels

META = {
    "label": "Bezier Draw",
    "description": "Freehand Bezier drawing, curve effects, decimate and curve generators",
    "tabs": ("Curve", "Generate"),
}

JA = {
    # module / panels
    "Bezier Draw": "ベジェ描画",
    "Effects": "エフェクト",
    "Connect (G1)": "接続（G1）",
    "Select one more curve (the active curve stays put)": "もう1つカーブを選んでください（アクティブなカーブは動きません）",
    "Both curves need an open Bezier spline": "両方のカーブに開いたベジェのスプラインが必要です",
    "Points": "ポイント",
    "Convert": "変換",
    "Parametric Curves": "パラメトリックカーブ",
    "New Stroke": "新しいストローク",
    "Mirror": "ミラー",
    "Active Curve": "アクティブなカーブ",
    "Applies to: Selected points": "対象: 選択した点",
    "Applies to: All points": "対象: 全ての点",
    "Object Mode only": "オブジェクトモード専用",
    # draw
    "Start Drawing": "描画開始",
    "Finish Drawing": "描画終了",
    "Curve Thickness": "太さ",
    "Bevel Resolution": "ベベル解像度",
    "Cursor": "カーソル",
    "Pressure Radius": "筆圧で太さ",
    "Nothing was drawn; the empty curve was removed": "何も描かれなかったので空のカーブを削除しました",
    # effects
    "Spiral": "スパイラル",
    "Radius Profile": "半径プロファイル",
    "Smooth / Handles": "スムーズ / ハンドル",
    "Progress By": "進み方",
    "Point Order": "点の順番",
    "Axis Position": "軸上の位置",
    "Start Angle": "開始角度",
    "Radius Multiplier": "半径の倍率",
    "Handle Scale": "ハンドルスケール",
    "Start": "開始",
    "End": "終了",
    "Change Pattern": "変化の形",
    "Wave Count": "波の数",
    "Step per Point": "1点ごとの角度",
    "Average Tilt": "傾きを平均化",
    "Average Radius": "半径を平均化",
    "Handle Type": "ハンドルタイプ",
    "No Bezier points selected": "ベジェの点が選択されていません",
    # points
    "Subdivide": "細分化",
    "Decimate": "間引き",
    "Number of Cuts": "分割数",
    "Max Deviation": "許容誤差",
    "Nothing to decimate": "間引ける点がありません",
    # convert
    "Points to Metaballs": "点をメタボールに",
    # generators
    "3D Lissajous": "3D リサージュ",
    "Strand Curve": "ストランドカーブ",
    "Cross Net": "クロスネット",
    "Twisted Wire": "より線",
    "Braid": "三つ編み",
    "Diamond Braid": "ダイヤ編み",
    "Strands": "本数",
    "Radius": "半径",
    "Length": "長さ",
    "Guide Curve": "ガイドカーブ",
    "Follow Strand Angle": "ストランドの角度に追従",
    "Pick a curve object": "カーブオブジェクトを選んでください",
    "Rounded up to an even number": "偶数に切り上げます",
    "Strands (vertical)": "本数（縦）",
    "Strands (horizontal)": "本数（横）",
    "Spacing": "間隔",
    "Weave Height": "編みの高さ",
    "Weave Frequency": "編みの頻度",
    "Start Radius": "開始半径",
    "End Radius": "終了半径",
    "Height": "高さ",
    "Size X": "サイズ X",
    "Size Y": "サイズ Y",
    "Size Z": "サイズ Z",
    "Frequency X": "周波数 X",
    "Frequency Y": "周波数 Y",
    "Frequency Z": "周波数 Z",
    "Phase X": "位相 X",
    "Phase Y": "位相 Y",
    "Phase Z": "位相 Z",
    "Curve Geometry": "カーブ形状",
    "Point Tilt": "点の傾き",
    "Tilt Mode": "傾きモード",
    "Progressive": "徐々に変化",
    "Tilt Start": "開始の傾き",
    "Tilt End": "終了の傾き",
}

classes = (
    ops_draw.classes
    + ops_effects.classes
    + ops_topology.classes
    + ops_connect.classes
    + ops_convert.classes
    + ops_generate.classes
    + panels.classes
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sts_bezier_draw = bpy.props.PointerProperty(type=ops_draw.BezierDrawSettings)
    bpy.types.VIEW3D_MT_curve_add.append(ops_generate.add_menu)


def unregister():
    bpy.types.VIEW3D_MT_curve_add.remove(ops_generate.add_menu)
    del bpy.types.Scene.sts_bezier_draw
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
