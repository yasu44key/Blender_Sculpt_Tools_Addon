# 統合レポート：自作アドオン群 → Sculpt Tools Suite

2026-10-10　Yoshiki Yasunaga & Claude Code

## 1. ひと言で

ばらばらに入れていた自作アドオン（実環境 5.2 に **26 件**、手元の版違いを含めると `.py` **316 ファイル**）を、
**1 つの Extension「Sculpt Tools Suite」（zip 1 本）・24 モジュール**にまとめた。
プリファレンスで使うモジュールだけ ON にでき、パネルは作業別の **5 タブ**（Curve / Sculpt / Model / Generate / Utility）に整理した。
対応 Blender 5.1 / 5.2。

## 2. 前と後

- **前**
  - 実環境 5.2 の `scripts\addons` に自作の単体アドオン 25 件＋Extension 1 件（Retopo Assistant）
  - 手元 `BlenderAddonProject\` に版違い・試作を含む `.py` 316 ファイル、zip 7 個
  - タブ名がアドオンごとにばらばら（"Custom"・"Sculpt Tools"・"Tools for me" など）
  - 設定が Scene とオペレータの二重持ち、F9 で調整できない物が多い
  - 5.x で動かない物・登録エラーを出す物が混在（下の 5 を参照）
- **後**
  - Extension 1 本（`sculpt_tools_suite-0.1.0.zip`・174 KB）、24 モジュール、本体 Python 約 1 万 3 千行
  - 自動テスト 27 ファイル（ヘッドレス 2,644 項目）＋ GUI テスト 9 本（77 項目）、5.1 と 5.2 で全 PASS
  - 設定はオペレータのプロパティ（F9 で後から調整）、または生きたモディファイア／ジオメトリノード（後から変更可）
  - 命名は `sts_` で統一、日本語表示は Blender の翻訳機構（言語切替に追従）

## 3. タブごとのモジュールと、まとめた旧アドオン

### Curve タブ

- **bezier_draw** — BezierDraw23.py ＋ BeziierDraw.py ＋ Curve_Subdivide_&_Decimate ＋ bezier_spiral.py ＋ Curve_Continuity_Tool（G1 接続）
- **annotation_convert** — Annotations_to_Bezier_Curves_14.py ＋ Poly_Line_Tool10.py（2本 → 1つの操作、ベジェかメッシュの辺か選ぶ）
- **nurbs_grid** — Draw_NURBS_Grid_Patch63.py ＋ nurbs_hud_w.py（小物3本は廃止）

### Sculpt タブ

- **voxel_remesh** — VoxelV2_28.py（旧版 25 本）＋ quick_voxel_remesh_panel_merged.py ＋ Fask_Face_set.py ＋ DyntopoFlow1.py
- **face_set_tools** — CFS2.py ＋ FaceToMaskTest43.py ＋ 面セットのスムーズ（旧 smooth_faceset_modal は構文エラーで読み込めなかった物）
- **metaball_brush** — MetaballBrushTool_v87
- **object_brush** — Object_Brush_Pro_Collection1_15.py ＋ Blob ブラシ（吸収）
- **wear** — aging_toolkit.py（＋ erosion / edge_damage 系）
- **strip_draw** — Armor_Ribbon_Pro ＋ Mesh_Clay_Strip 3 版（4本 → 1つ、帯ごとに生きた GN）
- **thickness_guard** — min_thickness_guard 一式（計測・選択・修正・マスク・ブラシの4ファイル → 1つ）

### Model タブ

- **edge_creation** — Edge_Creation_Tool_4_5.py ＋ MeshTools の Draw Polygon
- **mesh_tools** — MeshTools_1_2/1_3.py ＋ PolyMaker（MeshTools の部分集合だったので吸収）
- **sujibori** — Sujibori.py v0.5（＋ SujiboriBk.py）
- **align_tools** — AlignScripts/ の 10 本 → 1つ
- **tessellation** — cell_tessellation.py（＋ GN の生きたセル模様）
- **smooth_normals** — smoothmod.py ＋ SmoothNomal.py（スカルプトマスクから）
- **panel_raise** — panel_raise_addon.py
- **point_smooth** — point_smooth 系 4 版（point_smooth7 → … → rap_all v2.4）
- **retopo_assistant** — Retopo Assistant（Extension）の動く部分 ＋ reducer01.py（Reduce with Sharp Preserve）

### Generate タブ（＋ 追加 > メッシュ）

- **shapes** — special_object_maker（2 版）＋ platonic_solids_generator.py ＋ Capsule 系
- **wave_surface** — parametric_plane/ の 5 本（create_wave_plane 系）→ 生きた GN の曲面1つ
- **mesh_generators** — CrystalStructureMesh ＋ TetrahedralSpace-Filling ＋ HexagonalMeshGenerator ＋ gridmesh2/3 ＋ LeafVenationMeshGenerator 1〜4（葉脈は本物のスペースコロニゼーション法に作り直し）

### Utility タブ

- **language_switch** — Switch_Jp_En.py
- **quick_buttons** — Tools for me v2 の「発想だけ」（他者製・ライセンス表記なしのためコードは使わず新規に作成）

## 4. 廃止したもの（ユーザー決定）

- **adaptive_remesh** — 代わりは Dyntopo「詳細度で埋める」・QuadriFlow・QRemeshify・voxel_remesh
- **panel_tools**（Inset / 押し出し / Bevel のプリセットボタン）— 標準の I / Alt+E / Ctrl+B と同じ
- **PolyMaker** — MeshTools の完全な部分集合
- **NURBS の小物 3 本**（4点・2クリックなど）、**空メッシュ作成**、**Torus / Pyramid**（標準に任せる）
- **Retopo Assistant の作りかけ**（GP 描画・穴埋め・投影。ファイルはあったが登録されていなかった）
- **tessellation の Custom N-gon**（3/4/6 以外は穴の開いたメッシュになっていた）・境界の三角形化（Ctrl+T で足りる）

## 5. 移植の途中で見つけて直した旧版の不具合（主なもの）

- **5.x で動かない／壊れる**
  - VoxelV2_28.py: 起動時に登録エラー（`_is_warning` プロパティ）
  - MetaballBrushTool（実環境の物は中身が v86）: 廃止されたシェーダー名でプレビューが描けない
  - NURBS の HUD: `blf.size` の 3 引数（4.0 で廃止）で文字が一切出ない
  - min_thickness_guard: `register()` が 2 回定義されてマスク系 4 操作が登録されない／4.1 で消えた `calc_normals()` を呼ぶ
  - smooth_faceset_modal: 構文エラーで読み込めない／SmoothNomal: マスク属性名違いで効かない
- **結果が逆・ずれる**
  - Retopo Assistant: Decimate の頂点グループの向きが逆で、**稜線を守るつもりが先に削っていた**
  - 曲線の G1 接続: ローカル座標どうしを代入していて、位置や回転が違うとずれる
  - アーマーリボン: 共有の GN グループを毎回作り直すので、設定を変えると**過去のリボンも全部変わる**
  - 四面体充填: 名前と違い空間を埋めていなかった／結晶: 正四面体の頂点が正しくない
  - Voxel のリメッシュ: Dyntopo を切ったまま戻らなかった
- **使い勝手**
  - 乱数にシードが無く F9 のたびに形が変わる／カーソル位置に作らない／作った物を選ばない（生成系全般）
  - 押すたびに新しいモディファイアが増える（MeshTools の Solidify など）
  - special_object_maker の 2 版が同時に入っていて bl_idname を取り合う
- **スイート全体の検査で見つけた物**: 5.x に無いアイコン名 4 か所（パネルの描画が丸ごと止まる）→ 共通テストに「アイコン名の検査」を追加

## 6. 作り方（参考）

- 1 本ずつ旧版を精査 → 方針をユーザーが決定 → 仕様をテストとして書く → 実装 → 検収 → コミット
- 実装の約半分はローカル LLM（Strata）の作業員、残りは Claude。作業員の物も Claude が全文を読んで検収し、
  テストを通っていても形が違った物（葉脈が放射状の直線になっていた・稜線角度の判定）は直してテストを足した
- 記録: `docs/MIGRATION.md`（各ツールの精査結果と決定）、`docs/CONVENTIONS.md`（規約と 5.x の罠）

## 7. 実環境 5.2 に残した物

自作ではない、またはスイートの対象外なので触っていない:

- **add_mesh_capsule.py**（作者 David Ludwig）— shapes の「卵形・カプセル」プリセットと機能が一部重なる。外すかどうかはお任せ
- **Step_Loop_Select**（作者 KKS、1 本おきのループ選択）— 重なりなし
- **ModerateWeightReduction**（HoloLab、テクスチャ最適化つきの軽量版モデル作成）— retopo_assistant とは別物
- その他の他者製アドオン・Extension（mira_tools、mifthtools、retopoflow など）

外した旧アドオンは削除せず `5.2\addons_backup_20261010\` に移した（戻すときはフォルダごと `scripts\addons\` へ戻す）。
