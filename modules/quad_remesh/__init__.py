"""Quad Remesh — rebuild a (scanned, sculpted) mesh as clean quads with QuadWild Bi-MDF.

New tool (no old add-on). The engine is the QuadWild DLL pair of an installed QRemeshify
(GPL-3.0): this MIT suite does not ship it and runs it in a separate background Blender
(worker.py). What this module adds on top of QRemeshify: a light proxy (voxel + decimate,
so 10M-triangle scans finish in under a minute), a target face count instead of a raw scale
factor, crash isolation with progress / Esc, and fitting the result back onto the source.
"""

import bpy

from . import detail, ops, panels

META = {
    "label": "Quad Remesh",
    "description": "Clean quad topology with QuadWild (needs QRemeshify installed)",
    "tabs": ("Model",),
}

JA = {
    "Quad Remesh": "クアッドリメッシュ",
    "Cancel Quad Remesh": "クアッドリメッシュを中止",
    "Target Faces": "目標の面数",
    "Sharp Edge Angle": "シャープとみなす角度",
    "Relax Result": "結果をならす",
    "Proxy Surface": "代理メッシュ",
    "Voxel": "ボクセル",
    "Fit to Source": "元の形状に合わせる",
    "Hide Source": "元を隠す",
    "Target: ": "対象: ",
    "Selected faces": "選択した面",
    "Whole object": "オブジェクト全体",
    "Needs QRemeshify (free, GPL)": "QRemeshify（無料・GPL）が必要です",
    "It provides the QuadWild engine": "QuadWild エンジンはこれに含まれています",
    "Get QRemeshify": "QRemeshify を入手",
    "Object, Edit or Sculpt Mode only": "オブジェクト／編集／スカルプトモード専用",
    "Starting": "開始",
    "Reading the surface": "形状を読み込み中",
    "Building the proxy": "代理メッシュを作成中",
    "Computing the field": "流れを計算中",
    "Tracing patches": "パッチに分割中",
    "Quadrangulating (pass 1)": "四角形化中（1回目）",
    "Quadrangulating (pass 2)": "四角形化中（2回目）",
    "Quadrangulating (pass 3)": "四角形化中（3回目）",
    "QRemeshify is not installed (it provides the QuadWild engine)":
        "QRemeshify が入っていません（QuadWild エンジンはこれに含まれています）",
    "Not enough faces to remesh": "リメッシュするには面が足りません",
    "Select faces to remesh": "リメッシュする面を選択してください",
    "cancelled": "中止しました",
    "failed": "失敗しました",
    "Follow Guide Lines": "ガイド線に沿わせる",
    "Steer": "流れを誘導",
    "Steer + Snap Long": "誘導＋長い線は辺を乗せる",
    "Snap All": "すべての線に辺を乗せる",
    "Detect Crease Lines": "稜線・谷線を検出",
    "Replace Previous Lines": "前回の線を置き換える",
    "Draw Guide Lines": "ガイド線を描く",
    "Guide Lines": "ガイド線",
    "Detecting needs Blender 5.2+": "検出は Blender 5.2 以降が必要です",
    "Uses the visible layers": "表示中のレイヤーを使います",
    "Density Map": "密度マップ",
    "Project Detail": "詳細を投影",
    "Relax Rounds": "ならしの回数",
    "Relax Strength": "ならしの強さ",
    "Detail projected into %d Multires levels": "マルチレゾの %d 段に詳細を投影しました",
    "Apply or remove the other modifiers first: ": "先にほかのモディファイアを適用するか外してください: ",
    "Clear Guide Lines": "ガイド線を消去",
    "Clear Detected Lines": "検出した線を消去",
    "No such guide layer": "そのガイドレイヤーはありません",
    "Engine: STS (density maps)": "エンジン: STS（密度マップ対応）",
    "Engine: QRemeshify (no density maps)": "エンジン: QRemeshify（密度マップ非対応）",
    "Sculpt Mask": "スカルプトマスク",
    "Detail Ratio": "細かさの倍率",
    "Split at Density Edges": "塗り境界でパッチを分ける",
    "Finding density edges": "塗り境界を探索中",
    "No sculpt mask on this mesh": "このメッシュにはスカルプトマスクがありません",
    "No color attribute on this mesh": "このメッシュにはカラー属性がありません",
    "This engine cannot use a density map (needs the STS QuadWild engine)":
        "このエンジンは密度マップを使えません（STS QuadWild エンジンが必要です）",
    "Draw on Surface": "表面に描く",
    "Embedding guide lines": "ガイド線を埋め込み中",
    "Finding crease lines": "稜線・谷線を探索中",
    "Crease lines: %d ridges, %d valleys": "稜線 %d 本・谷線 %d 本",
    "Not symmetric on %s: the mirrored side is up to %.3g off (%d%% of a quad). Turn that axis off or align the model first":
        "%s 軸で対称ではありません: ミラー側が最大 %.3g ずれています（クアッド1辺の %d%%）。その軸をオフにするか、先にモデルの向きを揃えてください",
}

classes = ops.classes + detail.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if ops.RUN["job"] is not None:
        ops.RUN["job"].cancel()
        ops.RUN["job"] = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
