# 移植計画と進捗

旧ソース: 手元の `BlenderAddonProject`（非公開・読むだけ）。
各ツールの「最新版」は 2026-10-09 時点の更新日と版番号から判断。移植時に旧版同士の差分も確認する。

状態: ✅ 移植済み / ⏳ 未着手 / ⚠ 要判断

## Curve タブ

- ✅ **bezier_draw**（2026-10-09）
  - 元: `BezierDrawTool/BezierDraw23.py`（v2.3.0）
  - 吸収: `Curve_Subdivide_&_Decimate_1_0_4.py`（同じ処理の旧版）、`spiral/bezier_spiral.py`（Generate の Spiral に）
  - 直した不具合
    - Decimate: 別スプラインまで全体が間引かれていた／cyclic・ハンドル種別が失われていた → その場で点を削除する方式に
    - Object モードの Spiral でハンドルが置き去り → 一緒に移動
    - 平らなカーブで Spiral が1点に潰れる → 「進み方: 点の順番」を追加（既定）
    - Mirror が Finish のたびに複製を増やす → ミラーモディファイア（非破壊・描画中もライブ）
    - Metaball 変換が Edit モードのまま別オブジェクトをアクティブ化／キャンセルでデータが残る
    - 旧 spiral が既存の "Spiral_Curve" を黙って削除
    - 角度がラジアン表示
  - 統合: Edit 用と Object 用で重複していた効果（Spiral / Scale Variation=Radius Profile / Rotate Variation=Twist）を、モードで対象が切り替わる1つずつに
- ✅ **annotation_convert**（2026-10-09・**Strata 作業員が実装**／11分・29ターン・テスト3回で全PASS、Claude が検収）。ユーザー決定: 1つに統合（ベジェ／メッシュの辺・Curve タブ）。
  検収の手直し: 間引き（RDP）が再帰で、数千点の線で RecursionError → 繰り返し版に（5000点の線のテストを追加、元の版で落ちることを確認）。
  仕様 `tests/test_annotation_convert.py`（参照実装で 5.1/5.2 とも 34/34）。テスト用ファイル `tests/data/annotation.blend` は 5.2 で作成
  （`tests/tools/make_annotation_fixture.py`。5.1 でも読める）。罠: `layer.active_frame` はファイルを開いた直後 None のことがある。命令書 `docs/delegation/ORDER_annotation_convert.md`（panel_raise の次に委任）
  - 系統: `AnotationToLine/Annotations_to_Bezier_Curves_14.py`（v1.4・5.0 向け）と `Poly_Line_Tool10.py`（v1.0・4.3 向け。ルートの同名は作者名とタブ名だけ違う）。実環境には入っていない
  - 5.x のアノテーション: `scene.annotation`（型 `Annotation`）。アクティブなレイヤーは `layers.active_index` / `active_note`（レイヤー自体に `active` は無い）。
    点は位置 `co` だけ（筆圧なし）。**Python から線を作る `strokes.new` は 5.2 から**（5.1 には無い → 5.1 のヘッドレステストで線を用意できない）
  - Bezier 版: RDP で間引き＋Catmull-Rom 風ハンドル＋鋭角は VECTOR。**アクティブなレイヤーではなく常に最初のレイヤーを変換**（`layer.active` が存在しない → 先頭に落ちる。5.2 で確認）／
    間引き量に単位なし／他の選択を外さない／1点だけの線（点打ち）は捨てる
  - Polyline 版: **5.x では実行するとエラー**（`scene.grease_pencil` が無い。5.2 で確認）。しかも辺を張る条件が逆（間隔が Step Size より**長い**ときだけ辺を張る）で、
    点の間引きもしていない。実行後に編集モードへ入る
  - どちらにも付いていた Toggle Cyclic（標準 Alt+C）・Toggle Edit Mode（Tab）・Fill Face（F）・アノテーション表示切替（オーバーレイ）は標準の包み直し。
    しかも2本とも `object.toggle_edit_mode` という**同じ bl_idname**
  - 移植済みとの関係: カーブを直接描くのは bezier_draw、辺・ポリゴンを表面に描くのは edge_creation（Draw Polygon 吸収済み）。
    アノテーション変換の利点は「アノテーションツールの手ぶれ補正・配置（表面/ビュー/カーソル）で描いた線を後から形にできる」こと
- ✅ **nurbs_grid**（2026-10-09・**Strata 作業員が実装**／17分半・35ターン・テスト3回で全PASS、GUI 15/15 一発、Claude が検収）。
  検収の手直し: 頂点スナップがマウス移動のたびに全メッシュの全頂点を調べていた（高密度スカルプトで固まる。参照実装も同じ弱点）→ 光線が当たった面の頂点だけ（旧 v6.3 の方式）／
  Join が選択中のメッシュも巻き込む → サーフェスだけ選び直し／ループ切替がスプラインごとに反転 → 全部同じ状態に。GUI テストに頂点スナップを追加（17/17）。
  ユーザー決定: 63 を直して移植（Curve タブ・Strata 委任・GUI 検査つき）、
  v3.5 のウェイトを戻す（Ctrl+ホイール）、ループ U/V 表示・一括法線反転・Join も残す。小物3本は廃止。
  仕様 `tests/test_nurbs_grid.py`（35/35）＋ `tests/gui/gui_nurbs_grid.py`（15/15、サイドバー起動）を参照実装で確認。命令書 `docs/delegation/ORDER_nurbs_grid.md`
  - 以下、精査の記録
  - 系統（12本）: Griod v2.0 → Griod5 v2.3 → nurbs_hud v3.4（HUD・Vtx/Grid/Face スナップ・Ctrl+Z）→ nurbs_hud_w v3.5（**ホイールで点のウェイト**）→
    Auto v4.2（ドラッグで連続配置）→ Patch v5.0（NURBS 頂点スナップ・結合アシスト）→ 61 → 62（法線反転）→ **63 v6.3（ループ U/V）＝最新**。
    63 は実環境 5.1/5.2・`Sculpt_Tools___________/` と同一。マニュアル `NURBS_Grid_Tool_Manual.md/pdf`（参考程度）
  - 取りこぼし: **v3.5 のウェイト調整（ホイール）が v4.2 以降で消えている**（ホイールは視点ズームと取り合う）
  - 小物3本 `4-point-surface.py`（4クリックで 2×2 面）／`simple_click_nurbs.py`（2クリックで直線の4点サーフェスカーブ）／`simple_nurbs_surface.py`（座標指定）:
    グリッドツール（U=2）と標準の 追加 > サーフェス > NURBS カーブ で足りる
  - 不具合（5.2 で確認）
    - **HUD の文字が一切出ない**: `blf.size(id, 24, 72)`（3引数は 4.0 で廃止）が描画のたびにエラー（点と線は描かれる）
    - 作った面の**法線が下向き**になる（左→右・手前→奥に打つと -Z）→ 毎回「法線反転」が要る
    - 法線反転が U 数を独自のカスタムプロパティに頼る（標準の `spline.point_count_u` で取れる）・スキップした物も「反転した数」に数える
  - 要 GUI 確認: パネルの Start Drawing から起動すると `context.region` がサイドバーになる構造（edge_creation で実害が出たのと同じ）
  - その他の弱点: 途中で ↑↓ で U 数を変えると打った点の行の区切りが組み直される／半端な最後の行は黙って捨てる／Grid スナップが 1m 固定／
    ドラッグ間隔 0.5m 固定の既定（単位なし）／設定が Scene（`nurbs_grid_*`）
  - 標準と同じもの: Join（Ctrl+J）・ループ（編集モード Alt+C で U/V 指定）・法線反転（編集モード Switch Direction）。ただしパネルの「ループ U/V の状態表示」と
    オブジェクトモードでの一括反転は便利

## Sculpt タブ

- ✅ **voxel_remesh**（2026-10-09・Claude 実装）
  - 元: `Voxel/VoxelV2_28.py`（旧版 25本・`My_Sculpt_Tools/voxel_remesh.py` を含む）＋ `quick_voxel_remesh_panel_merged.py` ＋ `Fask_Face_set.py`
  - ユーザー決定: 元のオブジェクトは残す（隠す）／既定はオブジェクトモードで、統合結果だけが選択・アクティブ
  - 実機で判明: 旧版の面セット保持フラグ（use_remesh_preserve_face_sets 等）は 5.x に存在せず、hasattr で黙って無効になっていた
    → `use_remesh_preserve_attributes`。オブジェクトモードの `object.voxel_remesh` でも面セットは残る（スカルプトモード経由は不要）。
    `modifier_apply` では消える。Dyntopo では残る。Join は面セット番号を重ならないよう振り直す（1,2,3→1,4,6）
  - 直した不具合: `_` 始まりプロパティの登録エラー／警告判定がアクティブ1個の寸法だけ（ダイアログ内でボクセル数を常時表示）／
    Dyntopo 解像度を毎回上書き（「ボクセルサイズから」の ON/OFF に）／元オブジェクトを壊す Join／モディファイアの二重適用
  - やめたもの: Convert to Mesh・モード切替（標準と同じ）、手動面セット作成（オプションに統合）、Quick Voxel の4ボタン（モディファイア値をパネルに直接表示）、
    Pick Voxel Size（座標混同のバグ。標準 Shift+R をボタンで案内）、5.x に無い Smooth Shading 設定
  - 元を残す方式: bpy.ops の複製ではなく `meshes.new_from_object(評価済み)` で新規メッシュを作る（カーブ・テキスト・メタボール・モディファイア付きも同じ経路）
- ✅ **face_set_tools**（2026-10-09・**Strata 作業員が実装**／9分半・30ターン・テスト2回で全PASS。検収の手直しは訳語と重複定義のみ）
  - 元: `FaceToMask/CFS2.py`・`FaceToMaskTest43.py`（15本の大半は試作・デバッグ用）、`FaceSetDeform/FaceSetDeformer_fixed.py`
  - 直した不具合: 面セット→マスクが「隠す→全体マスク→全表示→反転」で既存マスクと非表示状態を壊していた → `.sculpt_mask` を直接書く（置き換え/足す/引く・反転）
  - 作らなかったもの: FaceSetDeformer（5.x で無い `calc_normals()` で停止、しかも全頂点を変形していた。標準 Mesh Filter と同じ）→ 標準ボタンを配置
  - 罠: バックグラウンド実行で `sculpt.face_sets_create` などスカルプト系標準オペレータを呼ぶと Blender が落ちる（テストは属性の読み書きだけ）
  - GUI 検査 `tests/gui/gui_face_set_tools.py`
- ✅ **metaball_brush**（2026-10-09・**Strata 作業員が実装**／18分・41ターン・テスト5回で全PASS・GUI 9/9 一発。手直しは説明文1か所）
  - ユーザー決定: Esc／右クリック＝ブラシ終了（描いたストロークは残す。edge_creation の「Esc＝破棄」とは別扱い＝ストロークごとに確定済みのため）／ミラーの中心は 3D カーソル（bezier_draw と揃える）／Sculpt タブ
  - 系統: 一本道の27版。最新 `MetaBallTool/MetaballBrushTool_v87.py`（2026-05。同梱のマニュアル PDF/docx は更新されていないので参考程度＝根拠はコード）。
    `Sculpt_Tools___________/` と `My_Sculpt_Tools/metaball_brush.py` は v85〜v86 の旧版
  - **ユーザーの実環境 5.2 の `MetaballBrushTool_v87_b44.py` は中身が v86 で、廃止されたシェーダー名 `2D_UNIFORM_COLOR` を使う**
    → 5.2 ではブラシ円のプレビューが描画のたびにエラー（v87 で修正済み）
  - v87 の不具合
    - `context.region` / `mouse_region_x` を使用＝**サイドバーのボタンから起動すると座標がサイドバー基準**（edge_creation と同じ罠。実機未確認）
    - 描画ハンドラに起動時の `context` を渡して後で使っている（無効になった context を参照しうる。実害は未確認）
    - Snap モードが全可視オブジェクトを1個ずつ ray_cast（オブジェクト数に比例して遅い）→ `scene.ray_cast`＋除外で足りる（edge_creation の `surface_point` と同じ）
    - ボタンを押した瞬間に空の MetaStroke オブジェクトを作る → 時間モードで素早くクリック・サイドバー上のクリックで**空オブジェクトが溜まる**
    - 時間モードでは押した瞬間に1個目が置かれない（interval 待ち）
    - 「視点から一定距離」モード（View Depth 10）は半端な奥行き（edge_creation で廃止したのと同じ）
  - 重複
    - 奥行きの決め方（表面／カーソル／平面）と「サイドバー上は無視」は edge_creation と同じ → `core` に共通化して両方で使う
    - bezier_draw の「点をメタボールに」は入力が違う（カーブの点）ので別機能として残す
    - ストロークのメッシュ化は voxel_remesh の Join & Remesh がメタボールに対応済み → パネルから案内できる
- ✅ **object_brush**（2026-10-09・**Strata 作業員が実装**／12分・30ターン・テスト3回で全PASS・GUI 12/12 一発。手直しなし）
  - ユーザー決定: Sculpt タブ（ブラシ類をまとめる）／Grid は XY だけ格子にそろえ高さは表面のまま／Esc・右クリック・Enter＝終了して残す（metaball_brush と同じ）
  - 系統: 一本道の10版。最新 `ObjectBrash/Object_Brush_Pro_Collection1_15.py`（ユーザーの実環境 5.2 にも入っている）。他ツールとの機能重複なし・標準にも同等機能なし
  - 不具合
    - `context.region` / `mouse_region_x` を使用＝サイドバーのボタンから起動すると座標がサイドバー基準（edge / metaball と同じ罠。実機未確認）
    - **Rotation Z が面の法線まわりにならない**: 法線に合わせた回転のあとオイラー Z に足しているので、斜面ではワールド Z 寄りの変な回転になる
    - **Grid モードが高さ方向も格子に丸める**: 表面から浮く／めり込む
    - `source.copy()` が親子関係・コンストレイントも複製 → ブラシ元に親があると配置位置が親基準でずれる
    - 毎マウス移動で「除外リスト（配置済み全部）」を作り直し、見えている全オブジェクトに1個ずつ ray_cast → 置くほど遅くなる
    - ブラシ内 Ctrl+Z は「コレクションから外すだけ」（オブジェクト本体は残る）。終了時に undo_push と オペレータの UNDO で履歴が2段
    - 角度がラジアン表示、間隔などに単位なし。タブが標準の "Tool" と同名
  - 良い所（残す）: 表面から外れても直前の奥行きを保つ／コレクション指定でランダムに選ぶ／ストローク方向に向ける／ストローク単位のブラシ内 Undo/Redo
  - 共通化: マウスの下の位置・サイドバー判定・間隔判定は core（edge_creation / metaball_brush と同じ）
- ✅ **sujibori**（2026-10-09・Claude 実装・テスト 33/33）
  - ユーザー決定: **Boolean 方式とジオメトリノード方式の両方**を用意して選べる／Model タブ。GN 方式の速さ・シュリンク問題の解消は Claude が実機で検証してから設計を確定
  - 実機検証（2026-10-09・5.1 / 5.2 とも同じ傾向。球 r=1・溝の太さ 0.04・線は表面より 5% 外に描いた状態）
    - GN（コレクションのカーブ→表面に吸着→円で掃引→Mesh Boolean 差分）: 溝の底 r=0.980 ＝ **深さが太さの半分ちょうど（つぶれない）**。
      表面から浮いた線でも彫れる。Boolean 方式（カーブ→管→Boolean）は同じ線で**何も彫れない**（表面に乗せる必要がある）
    - 速さ（線を動かしたときの再計算、MANIFOLD）: 3.2万面 65ms／13万面 0.18秒／52万面 0.65秒。Boolean 方式も同じ条件で 0.05／0.15／0.61秒＝**ほぼ同じ**。
      EXACT は 3.2万面で GN 0.79秒・Boolean 4.2秒 → 既定は MANIFOLD
    - 52万面では1回 0.65秒なので「編集中は溝を隠す」切り替えを付ける
    - 5.2 の API 差: GN モディファイアの入力の書き方が変わった → `core/nodes.py`
  - 作り: 対象メッシュに設定（方式・溝の幅・ソルバー・線コレクション／カッターコレクション／ノードグループへの**ポインタ**）。
    線は対象ごとの「Sujibori Lines (名前)」コレクションのカーブ（太さ無しの中心線）。両方式とも**中心線を表面に吸着してから太さを付ける**
    - ライブ: 対象ごとの GN グループ（Collection Info → 吸着 → 円で掃引 → Mesh Boolean 差分）。線を動かすと即追従
    - ブーリアン: 「溝を更新」で中心線を表面に投影したカッターを作り直し、Boolean（コレクション）で差分
  - 旧版から直したこと: 名前参照（改名で壊れる）→ポインタ／線を表面に乗せないと彫れない→吸着／厚みがつぶれる→中心線を先に吸着／
    線の削除がカーブまで消す→コレクションから外すだけ／太さ無しのカーブで黙って彫れない→線は中心線として扱い幅は設定から／ソルバー既定 MANIFOLD
  - 「線を描く」は Bezier Draw（表面モード）で線コレクションへ直接描く。ユーザーの Bezier Draw 設定は書き換えない
  - 系統: `Sujibori/Sujibori.py` v0.5 の1版（`Sculpt_Tools___________/` と実環境 5.2 にも同一物。`SujiboriBk.py` はタブ名とコメントだけ違う）。
    `Sujibori/BeziierDraw20.py` は線を描くための旧 Bezier（bezier_draw に統合済み）。`Sujibori/CLAUDE.md` に設計方針メモ
  - 仕組み: カーブを複製→メッシュ化→ターゲットに Boolean（差分・EXACT）。Re-edit で Boolean を切ってカーブ編集→Apply で作り直し
  - 不具合・弱点
    - **カーブを直すたびに Apply を押し直す**（カッターは押した時点の写し）。メモの優先課題「リテイク時間を最小化」に反する
    - メモの既知問題「深度を付けたあとシュリンクラップでメッシュに沿わせると厚みがつぶれる」: シュリンクラップがベベル後の形に掛かるため
    - 参照を**名前の文字列**で持つ（ターゲットやカーブを改名すると Re-edit / Delete が効かなくなる）
    - カーブに太さ（ベベル）が無いと面のないカッターになり、**黙って何も彫れない**。端を塞いでいないと EXACT が不安定
    - `bpy.ops.object.duplicate` / `convert` で複製（非表示カーブで失敗、カーブのモディファイアも複製）
    - Delete がユーザーのカーブまで確認なしで消す。コレクション名が "SujiborCutters"（綴り）。コメントのアクティブ/選択の説明が逆
    - ソルバーが EXACT 固定（高密度メッシュで重い。4.5 以降は高速な Manifold がある）
- ✅ **point_smooth** 1回目（スムース）✅（2026-10-09・**Strata 作業員が実装**／22分半・37ターン・テスト3回で全PASS、Claude が検収・手直しなし）。
  2回目（点を膨らませ＋ラップ）✅（**Strata**／23分・55ターン・テスト5回、検収・手直しなし。共通テストのアイコン検査で作業員の `MOD_EXPAND`（5.x に無い）を作業中に検出）。
  設定はオペレータ（F9）、ラップ先だけ `scene.sts_point_smooth.wrap_target`。ラップ先はモディファイア後の形、NURBS の w は不変、方向反転ボタンは廃止（負の値）
  精査の記録: ユーザー決定: 直して移植・Strata に2回で委任（1回目スムース、2回目 膨らませ＋ラップ）・
  ループは「等間隔＋緩和」（大きさは保つ）。モード（自動／ライン）は廃止（直すと同じ動きになり、ラインの独自の働きは面を壊すことだけだった）。Model タブ。
  1回目の仕様 `tests/test_point_smooth.py`（参照実装で 5.1/5.2 とも 35/35）・命令書 `docs/delegation/ORDER_point_smooth.md`（nurbs_grid の次に委任）
  - 以下、精査の記録
  - 系統: point_smooth7 v2.0 → point_smooth v2.2（Inflate）→ rap v2.3（Wrap）→ **rap_all v2.4（サーフェスの Wrap・膨らみ反転）＝最新・上位互換**
    （機能の取りこぼしなし）。実環境 5.1/5.2・`Sculpt_Tools___________/` と同一。マニュアル docx/pdf、作成時の会話ログ `Log.txt`、画像 A〜E.bmp
  - 機能（編集モード・メッシュ／ベジェ・NURBS・Poly 曲線／NURBS サーフェス）:
    スムース（自動: 線→端点を固定して直線上に等間隔・閉じたループ→周長で等間隔・面→ラプラシアン緩和。最外側の固定・接平面に沿う緩和）／
    膨らませ（境界からの距離で sin の重み）／ラップ（対象メッシュの表面へ・オフセット・モディファイア後の形に吸着＝確認済み）
  - 不具合（5.2 で確認）
    - **メッシュでモード「ライン」＋面の選択 → 形が壊れる**（適当な道順を一直線に並べ直す。5×5 格子が崩れた）。サーフェス版は面ならラプラシアンへ切り替えている
    - **離れたループ・線を複数選ぶと1つしか処理しない**（2つ目は移動0）。曲線も、選択が飛び飛び（0,1 と 4,5）だと1本の列として直線化する
    - ループは「今の折れ線に沿って等間隔にするだけ」で形はなめらかにならない（繰り返しても変化なし）
  - 規約との差: UI 文字列が日本語の直書き（英語＋JA にする）／設定が Scene とオペレータの二重持ち（パネルの値を F9 の値が上書きしない）／
    スムースのオペレータに使われない `inflate_amount`／「方向反転」ボタンは値の符号を変えるだけ／アクティブなオブジェクトだけ（複数オブジェクトの編集モード非対応）
  - 標準との重なり: 頂点のスムーズ（`mesh.vertices_smooth`）・カーブのスムーズ（`curve.smooth`、サーフェスにも効く）・拡張 LoopTools（Space / Relax、同梱ではない）。
    ただし「端を固定して直線化／等間隔」「接平面に沿う緩和」「NURBS サーフェスへのラップ」「3種類を1つの操作で」は標準に無い
- ✅ **erosion**（2026-10-09）。ユーザー決定: 経年劣化は (a) 今の方式を直す・パネル系は Raise だけ残す（panel_tools は標準の I / Alt+E / Ctrl+B と同じなので廃止）
  - ✅ **wear**（Sculpt タブ・**Strata 作業員が実装**／25分・28ターン・テスト4回で全PASS、Claude が検収）: aging_toolkit ＋ erosion ＋ edge_damage を統合。
    内側の面だけを沈める（格子点は動かない）・面ごとの大きさに対する比率・メッシュごとにシードから乱数・F9 調整・事前の重さチェック・重力は世界の下向き。
    検収の手直し: 既定値が旧版よりかなり強かった（欠け率0.6・浸食率0.15・深さ0.5/0.4・重力0.5）→ 旧版の効き方に戻した。訳語1つ
  - ✅ **panel_raise**（Model タブ・**Strata 作業員が実装**／10分・28ターン・テスト3回で全PASS、Claude が検収）: F9 で調整・bmesh で構築・
    名前を中身どおりに（余白・溝の幅/深さ・面板の高さ＝元の面から・ベベル・面ごと/まとめて）。複数オブジェクトの編集モード対応。
    検収の手直し: 面を番号（index）で見分けていた（押し出し・ベベル直後は古い）→ 面そのもので／「まとめて」で曲面上の上面を法線で見分けて取りこぼす →
    「頂点がすべて新しい面」で／押し出し後の元面の削除が `FACES_ONLY` で面なしの辺が残る（**命令書の指示ミス**）→ `FACES`。仕様に曲面・面なし辺のテストを追加
  - 以下、精査の記録
  - 中身は2系統。他フォルダに同一物なし。実環境 5.1/5.2 に `aging_toolkit.py`・`panel_raise_addon.py`（手元と同一）・`panel_tools_addon_1.py`（手元と別版）
  - **経年劣化系**: `aging_toolkit.py`（v1.1）＝ `erosion_addon.py`（面の浸食）＋ `edge_damage_addon.py`（エッジ欠け）の統合版で上位互換
    （エッジ影響の広げ方を頂点単位→面単位に改良済み。単体2本は乱数範囲などが少し違うだけ）
    - 仕組み: メッシュ全体を Subdivide → 選んだ面を1枚ずつ Inset して内側へ押し込む。プレビューは複製を作って元を隠し、Apply で元に同じ処理をやり直す
    - 不具合（5.2 で確認）: **Apply でモディファイアが二重になる**（Bevel → Bevel ＋ Bevel.001）／欠けの幅・深さが**絶対値で単位なし**（10cm の立方体だと厚みの 40% まで削れる）／
      「Crumble Edges」は境界辺（開いた縁）だけが対象で**閉じた立体では何もしない**／プレビューが Undo に残らない（元は `hide_viewport` で隠すだけ）／
      安全策のタイムアウトが経過時間なので**同じシードでも結果が変わりうる**／検出結果を捨てている死にコード（`detect_sharp_vert_indices`）／設定は Scene で F9 不可
    - 見た目: 欠けが Inset＋押し込みなので**箱状の穴**になる（実機撮影）
  - **パネル系**: `panel_tools`（Inset A/B・押し出し ▲▼・Bevel を値プリセットのボタンにしたもの＝標準の I / Alt+E / Ctrl+B と同じ。手元は bmesh 版、実環境は bpy.ops 版の別物で同じ bl_idname）／
    `panel_raise` v2.0（それを1押しで「溝の Inset → 溝を沈める → 縁の Inset → 面板を浮かせる → 縁を Bevel」と連続実行するマクロ。5.2 で正常動作を確認）。
    どちらも設定は Scene・単位なし。sujibori（カーブに沿った筋彫り）とは補完関係で重複しない
  - 別案の試作（GN の生きた「ウェア」モディファイア: 細分化 → 鋭い辺からのマスク（Edge Angle → 頂点へ → Blur）＋全体量 → ボロノイのセルで欠け → 法線の逆へ変位）:
    円柱では欠けのまとまりが出たが、立方体では1頂点ずつの点になり、境界も格子状のギザギザ → **品質を詰めるには試作時間が要る**（未解決）
- ✖ **adaptive_remesh** — **廃止**（2026-10-09・ユーザー決定）。代わり: Dyntopo「詳細度で埋める」・QuadriFlow／QRemeshify・voxel_remesh
  - 中身: `PyMeshLab/adaptive_remesh_pymeshlab/`（`__init__.py` 28行＋`adaptive_remesh.py` 82行、zip は同一物）、導入手順 `a.md`・docx（Blender の Python へ pip で入れる版の説明）。
    実環境には入っていない
  - **動かない理由が3つ**: `__init__` が存在しない名前（`MESH_OT_adaptive_remesh`、実体は `*_ext`）を import して登録エラー／
    OBJ の入出力 `export_scene.obj`・`import_scene.obj` は 4.0 で廃止（5.x では `wm.obj_export` / `wm.obj_import`）／外部 Python のパスが `/usr/bin/python3.12` 固定
  - 仕組みの弱点: 選択をまとめて OBJ に書き出し → 外部プロセスで PyMeshLab の isotropic explicit remeshing → 新しいオブジェクトとして読み込み（元は置き換えない・名前や材質が変わる）
  - PyMeshLab: このマシンの Python・Blender 5.1/5.2 の Python のどれにも入っていない。Blender 5.x 用（cp313・win_amd64）の wheel は PyPI にある
    （2025.7.post1・約 55MB・**GPL-3**。スイート本体は MIT → 同梱すると配布物を GPL として扱う必要。Extension の `wheels` で同梱は技術的には可能）
  - 標準との重なり: Dyntopo の「詳細度で埋める」（一定の細かさの三角形で張り直す＝等方的）・ボクセルリメッシュ（スイートの voxel_remesh）・QuadriFlow・
    導入済みの拡張 QRemeshify（四角形）。**曲率に応じて密度を変える「適応的」は標準に無い**

## Model タブ

- ✅ **mesh_tools**（2026-10-09・**Strata 作業員が実装**／16分半・51ターン・テスト7回で全PASS。手直しなし。`hard_min=` を使って1つのプロパティだけ黙って消える罠で3回消費）
  - ユーザー決定: Draw Polygon は edge_creation へ吸収・空メッシュ作成は廃止。PolyMaker は廃止（MeshTools の部分集合）
  - 残したもの: 1クリックの Solidify（2回目は増やさず値を更新）。適用・三角/四角変換は標準ボタン（旧版は全選択して選択を壊していた）
  - 系統: PolyMaker（v1.2/1.3）→ MeshTools（v1.0〜1.3）の一本道。**PolyMaker は MeshTools の完全な部分集合**で独自機能なし。
    同じ bl_idname（`mesh.create_polygon_mesh` / `mesh.change_polygon_type` / `object.toggle_object_edit_mode`）を持つので両方入れると衝突する
  - **MeshTools の Draw Polygon は edge_creation とほぼ同じツール**（クリックで点・表面吸着・カーソル奥行き・編集中メッシュへ追記・ループを閉じる）
    - Draw Polygon にだけある: ドラッグで連続追加（間隔指定）／ワールド平面（XY/XZ/YZ）に置くモード／閉じたら自動で面を張る
    - 旧版の不具合: `context.region` と `mouse_region_x` を使っている（サイドバーのボタンから起動すると領域がサイドバーになる＝edge_creation で作業員がはまったのと同じ罠。実機未確認）／
      外れたときの「視点から10」の半端な奥行き／描画中に全キーを素通し（X や Tab が効いてしまう）
    - Esc の意味が逆: Draw Polygon = 破棄、edge_creation = 確定
  - 残りの小物
    - New Polygon Mesh（空メッシュを原点に作って編集モード）→ edge_creation の「新規オブジェクト」で足りる
    - Solidify 追加/適用（既定値を Scene に保存→追加後はモディファイアの値を直接表示）→ 1クリックの便利機能としては価値あり
    - Change Polygon Type → **全選択してから変換するのでユーザーの選択を壊す**（説明文は「選択面を」）。標準の Alt+J / Ctrl+T と同じ
    - Toggle Edit Mode → 標準の Tab と同じ
- ✅ **edge_creation**（2026-10-09・**Strata 作業員が実装**／35分・37ターンで文脈上限により停止、その時点で仕様テスト60/60。Claude が検収で2か所修正）
  - 元: `Sculpt_Tools___________/Edge_Creation_Tool_4_5.py`（v1.5.1。`Edge_Creation_Tool/` の8版はこの旧版）
  - 直した不具合: 描画中に視点操作できない／何もない所のクリックが「視点から10」の半端な奥行き／1点戻す・ループを閉じる手段がない／
    常に新規オブジェクト（既存メッシュへ足せない）／自分の面に吸着
  - 作らなかったもの: Fill Face（標準 F）・Toggle Edit Mode（標準 Tab）の包み直し。PolyMaker と共有していた親パネルの小細工
  - GUI 検査 `tests/gui/gui_edge_creation.py`（イベント模擬・`bash tests/run_gui_tests.sh`）
  - v2（2026-10-09・**Strata 作業員**／11分・27ターン・テスト2回で全PASS・GUI 16/16 一発）: MeshTools の Draw Polygon を吸収。
    Esc＝破棄（ユーザー決定）／ドラッグで連続追加（間隔指定）／奥行き: 表面・3D カーソル・ワールド平面（XY/XZ/YZ）／ループを閉じたら面を張るオプション
- ✅ **align_tools**（2026-10-09・**Strata 作業員が実装**／33分・53ターン・テスト9回で全PASS、Claude が検収）。ユーザー決定: 4つに統合・Model タブ・Strata 委任
  - 検収の手直し: 親付き物体で回転がずれる（`matrix_basis` → `matrix_world`）／Origin to Bottom を編集モードで押すと変更が消える（poll でオブジェクトモードに限定）・
    メッシュ共有の物体は他の利用者まで動くのでスキップ／Drop の逆向き光線が選択中の物体・非表示物体にも当たっていた＋シーン全頂点を撃っていた
    （高密度スカルプトがあると重い）→ 影の範囲内の頂点だけに絞る
  - 系統: `AlignScripts/`（10オペレータの1パッケージ v1.0）。`souce/` と実環境 5.2 のものは同一。`Transport_Transform_To_Cursor.py`（ルート）も同一。
    `★archive/AlignScripts(old)/` は旧版
  - 重複（10 → 4 に統合できる）
    - 「選択した面/辺の向きを軸に合わせて物体を回す」が4つ: Align Edge to Axis／Align Z- to Face Normal（1面）／
      Align Z- to Average Face Normal（複数面＝1面版の上位互換）／Align Object to Selected Faces（+Z 向き・面の中心で回す版）
    - 「原点を底へ」が2つ: Origin to Bottom ＝ Origin with Offset の割合 0
    - 「下の物に落とす」が3つ: Snap to Ground（Z=0）／Snap to Under Object（真下に1本）／Snap to Surface（6方向・1本）
  - 不具合
    - 回転系3つが `rotation_euler = 差分` で**既存の回転を上書き**（回転を適用していない物体だと向きが狂う）
    - Origin to Bottom 系: `dimensions`（ローカル寸法）で底を出すので**回転した物体で底がずれる**。
      複数選択すると**全員の原点がアクティブ1個の底に**集まる。3D カーソルを動かして戻す回り道
    - Snap to Ground: メッシュ以外を選ぶと停止（`obj.data.vertices`）。モディファイア無視
    - Snap to Under/Surface: 光線1本（物体の中心または箱の角1つ）だけ → 凸凹の上で浮く・めり込む。最初に自分に当たると黙って何もしない
    - Snap to Surface に `bl_options` が無く **Undo できない**。Align Rotation が回転を上書き
    - Transport Transform to Cursor: `matrix_world = カーソル` で**スケールが 1 に戻る**
    - パネルは10個のボタンを平置き。編集モード専用のものもオブジェクトモードで並ぶ。タブ名 "Align Tool"
  - 統合案（4つ）: 向きを軸に合わせる（面の平均法線／辺の向き・±XYZ・回転中心・適用）／原点を底へ（割合・物体ごと・ワールドの高さ）／
    面に落とす（6方向・他の物体 or ワールド平面・複数点で接触判定・自分を除外）／3D カーソルに合わせる（スケール保持）
- ✅ **smooth_normals**（2026-10-09・Claude）。ユーザー: いったん廃止→「実現可能性を検討、安ければ作る」→ 安かったので作成。Model タブ
  - GN モディファイア `STS Smooth Normals`: 法線を頂点で評価してぼかし（Blur Attribute を Evaluate on Domain=Point で包む）→ 正規化 →
    元の法線と「頂点グループの重み×強さ」で混ぜ → Set Mesh Normal（Free・Corner）。形は変えない。適用してもカスタム法線は残る（5.1/5.2 実機確認）
  - 罠: Blur を面の角（corner）のまま評価すると角ごとの平らな法線しか混ざらず効かない／ぼかした法線は打ち消し合って縮むので正規化してから混ぜる
  - 頂点グループが空・存在しない → 全体。追加時にアクティブな頂点グループを入れる。5.2 はパネルで頂点グループを検索選択、5.1 は文字入力
  - 以下、精査の記録
  - **動かない**: 頂点グループがあると `v[active_index]`（BMVert を整数で引く）で即エラー（実機確認）。無くても `BMVert.normal` への代入は
    メッシュに保存されない（4.1 以降、法線は形から計算し直される）。`strength` プロパティは使われていない。numpy 依存
  - 意図（マスクの強さで法線をなめらかに）は標準でできる: 編集モード Mesh > Normals > **Smooth Vectors**（選択頂点・係数）／
    **Weighted Normal** モディファイア（頂点グループ指定可）／**Smooth by Angle**

- ✅ **quad_remesh**（2026-10-10・Claude・新規。旧版なし）。Model タブ。自前 QuadRemesher 構想の第1段階
  - エンジン = QuadWild Bi-MDF（GPL-3.0）。**同梱しない**: インストール済み QRemeshify の `lib_quadwild` / `lib_quadpatches` を、
    別プロセスのバックグラウンド Blender（`worker.py`）から ctypes で呼ぶ。MIT の本体とライセンスを分け、QuadWild 内の `exit(0)` でも本体が落ちない
  - QRemeshify に足したもの: 代理メッシュ（閉じた面 = ボクセル→デシメート、開いた面 = デシメート）／目標の面数（Scale Factor を面積から逆算 → 実数で最大3回補正）／
    別プロセス・進行表示・Esc と中止ボタン／元形状への「STS Fit」（シュリンクラップ・最近接点）／対称の非対称チェック（警告）
  - 実測（頭部スキャン 1,111万三角形・閉多様体）: QRemeshify に直接は終わらない → 49秒で 8,332 面すべて四角形。
    Blender の Decimate だけで 10万へは 192秒、ボクセル（0.75）→デシメートなら 9秒
  - 分かったこと: QRemeshify の「密度」は Scale Factor（**大きいほど粗い**）。QuadWild の Preprocess は入力に関係なく約1.5万三角形へ作り直す＝解像度の上限
    → 使わず（remesh=0）、自前の代理メッシュの密度で決める
  - 罠: **非対称な物に対称を掛けると、ミラー側が実物から浮き、Fit が折れる**（頭部は数度傾いていて最大 7〜10mm）→ 鏡像と面の距離（BVH）の 95% 値が
    クアッド1辺の 25% を超えたら WARNING。頂点どうしの距離で測ると頂点間隔を誤検出する（対称な卵で誤警告した）
  - 長時間処理なので F9 ではなく modal（ダイアログが前回値を覚える）。スクリプト・テストは `blocking=True`
  - **第2段階（2.2.0・2026-10-10）: ガイド線**。表示中のアノテーションレイヤーの線がガイド（レイヤーを隠せば外れる）
    - 「稜線・谷線を検出」（5.2+）: 代理メッシュで折れ角 35° 超の辺（三角形の辺なので破線状）を凸／凹ごとにつなぐ → 2 クアッド以内の端を前方へ橋渡し →
      交点で分けて「ほぼまっすぐ続くものだけ」つなぎ直す（最長経路 1 本だと立方体の 12 辺が 1 本になった）→ 長さで足切り → なめらかに → STS Ridge（赤）/ STS Valley（青）
    - 手動モード: 「表面に描く」= アノテートツール＋配置「サーフェス」＋レイヤー STS Guide。「消しゴム」= アノテート消しゴム
    - 効かせ方 3 種: **誘導（既定）** = QuadWild の交差場 .rosy を線の近く（1.5 クアッド）で接線へ寄せる（4 倍角で混ぜる）／
      誘導＋長い線は辺を乗せる／すべてに辺を乗せる（線の近くを 1 回細分 → 最短経路の辺の列 → 弧長の順を保って線上へ吸着 → .sharp のフィーチャー）
    - 実測（頭部・目標 1 万）: 辺を乗せる＝14,458 面・折り返し 186 → 対策後 0／誘導＝**10,405 面・50 秒・折り返し 0**・目の周りにループ。
      誘導の効き目は控えめで実行ごとに揺れる（卵の斜めの輪で 0.29〜0.62）。辺を乗せる方式は自動検出の断片線だと口角に特異点が集まり形が崩れる → **意図して描いたきれいな線（閉じた輪）向け**
    - 罠と対策: (1) **デシメートは深い溝に薄いヒレ（折り返し）を残す**（頭部で 110）→ 間引き後に折れた所をならしてボクセル面へ戻す `repair_folds`。
      (2) 近すぎる平行線（上下まぶた 1 mm）は細いパッチになり面数の下限も上げる → 長い線優先で 0.8 クアッド以内の部分を削る `_trim_close`。
      (3) 吸着後に近傍をならすと逆に裏返りが増えた（5→17）→ ならさず、裏返った所だけ吸着を戻す。(4) 途中で終わる線の端の先に折れた帯 → 結果のクアッドにも `repair_folds`（143→0）。
      (5) スキャンの「シャープ辺を維持」35° はノイズが 2.7 m 分出て面数が下がらない（短い鎖を捨てても効かない）→ スキャンでは OFF、稜線はガイドで
    - 残り: 密度マップ（C++ の `edgeFactor`）／辺を乗せる方式の端点処理（線の端を特異点にきれいに収める）
  - **第3段階（2.3.0・2026-10-10）: 密度マップ**。スカルプトマスク／カラー属性（明るさ）で塗った所ほどクアッドが小さい（細かさの倍率・既定 2.5）
    - エンジン: QuadWild（ksami/quadwild-bimdf の feature/lib＝QRemeshify の C API）を **MSVC v143 でビルドできた**（CI は ClangCl だが不要だった）。
      ソースはフォーク https://github.com/yasu44key/quadwild-bimdf のブランチ sts/density（commit 1341ea5）。ビルド手順はエンジン同梱の SOURCE.md
    - 改造は1か所: `quadPatches` が `<mesh>.sizing`（頂点ごとの大きさ倍率）を読めばパッチごとの目標辺長 = 基準 × パッチ内の平均倍率。
      ファイルが無ければ従来どおり（QRemeshify と互換）。共有辺は量子化側が両パッチの平均を取るので整合する
    - 配布: **GPL のエンジン用 Extension「STS QuadWild Engine」**（`quadwild-sts/extension/`）。Suite（MIT）は同梱しない。
      `engine.find_engine` は sts_quadwild_engine → qremeshify の順に探し、`lib/sts_engine.json` の density で対応を判定。非対応エンジンで密度を指定 → ERROR
    - 分かったこと: クアッドのパッチは中身が規則格子なので**大きさはパッチの境目でしか変えられない**。卵（上半分を塗る・倍率 2.5）で
      パッチ平均だけだと比 1.38 → **塗り境界（0.5 の等高線）を自動で「辺を乗せる」ガイドに**して 1.64 → さらに alpha 0.005→0.2（規則性より大きさの忠実さ）で 1.79〜1.96。
      密度マップ使用時は alpha 0.2
    - 頭部（目・口を球状に塗る・目標 1 万）: 塗った所の辺長 1.77 → 1.26 mm、塗った所の面数 428 → 868、全体 9,936 面・60 秒・折り返し 0
  - **2.4.0: 詳細を投影**（`detail.py`）。STS Fit の付いた結果に Multires を足し、最上段で「吸着 → (ならす → 吸着)×回数」を焼き込んで普通の Multires にする
    （STS Mirror は先に適用、STS Fit は外す、ほかのモディファイアがあれば止める）。頭部 8,640 面×2 段で 1.0 秒。唇の縁ののこぎり状の段差がほぼ消える
  - 次（第2・第3段階・独立 Extension 予定）: 流れのガイド（.rosy 差し替えで誘導できることは実証済み）／密度マップ（QuadWild の `edgeFactor` はパッチごとのベクトル・C++ 改造）／
    目・口のループ。今は均一サイズなので 8,000 面だと閉じた目は潰れ、口は粗い

## Generate タブ

- ✅ **shapes**（special_object ＋ platonic_solids を統合・2026-10-09・**Strata 作業員が実装**／15分半・34ターン・テスト6回で全PASS、Claude が検収）。
  Generate タブ＋Add > Mesh。Spindle／Egg・Capsule（プリセット5種）／Gear（穴あり可）／Star／正多面体5種＋切頂二十面体。Torus・Pyramid は標準に任せて廃止
  - 検収の手直し: Gear の穴の半径が内径以上だと上下面が裏返る → 内径未満に戻して警告／星の "Points" が本体辞書で「ポイント」→ "Tips"（先端の数）
- 以下 special_object の精査記録（旧 ⏳）
  - 系統: v1.0〜v1.4 → v2.0 が2本。`SpecialObject/special_object_maker_addon.py`（519行＝`Sculpt_Tools___________/` と実環境 5.2 と同一）は
    455行版（`..._addon_.py`）の Capsule を「卵形＋プリセット（卵・球・カプセル・レモン・非対称）」に統合した**上位互換**
  - **実環境 5.2 に `special_object_maker_addon.py` と `special_object_maker_v1_4_full.py` が同時に入っている**（同じ bl_idname を取り合う）
  - 重複
    - Torus ＝ 標準 `primitive_torus_add` をそのまま呼ぶだけ。Pyramid ＝ 標準 Cone（頂点数・上下半径・高さ）と同じ
    - 設定値が Scene と各オペレータの**二重持ち**（ボタンは Scene の値、F9 で変えた値はパネルに戻らない）
    - 正多面体（`Generator/` と `正多面体3Dオブジェクト/` は同一。Add > Mesh に5種）も同じ「形を足す」系 → 1モジュールにまとめられる
  - 不具合・弱点
    - Pyramid の Base Radius が 0 まで入る → 面が作れずエラー
    - Gear / Star の上下面が凹の多角形1枚 → 陰影の乱れ・サブディビジョンやブーリアンで崩れる
    - 卵形の F9 で数値を変えても名前はパネルのプリセット名のまま
    - Add メニューに出ない（パネルからだけ）。長さに単位なし。タブ名 "Special Objects"
  - 統合案: **shapes** モジュール（Generate タブ＋Add > Mesh メニュー）に Spindle・卵形（プリセット）・Gear・Star・正多面体5種
    （＋`正多面体3Dオブジェクト/Models/truncated_icosahedron.py` のサッカーボール型）。Torus / Pyramid は標準に任せる。設定はオペレータだけ（F9）
- ✅ **platonic_solids** — `Generator/platonic_solids_generator.py`（`正多面体3Dオブジェクト/` にも同一物）→ shapes に統合
- ✅ **tessellation**（2026-10-09・Claude）。ユーザー決定: (c) 両方（今の方式を直す＋GN の生きた模様）・Model タブ
  - Tile Faces（一発・F9 調整）: 面ごとではなく「つながった面のまとまり（法線の差が「連続させる角度」以内）」ごとに1つの座標系で敷く
    （座標系はオブジェクトの原点と X 軸に固定 → 離れた同一平面の島でも模様がそろう）。面は自分の三角形（loop triangles）で切り抜き、
    重心座標で元の表面へ戻す → 凹んだ面・曲がった四角でも表面に乗る・UV も引き継ぐ。同じタイルの破片は1面に結合、
    小片はとなりへ結合（既定 10%）、タイル化しなかった面との境は辺を分割して T 字を解消（閉じた立体は閉じたまま）。
    模様: 正方形／レンガ（長さ／高さ・段ずらし）／三角形／六角形／八角形＋正方形（4.8.8）／ボロノイ（ゆらぎ・シード）。回転・ずらし
  - 旧「Custom N-gon」は廃止（正多角形は 3/4/6 以外すき間ができる＝穴の開いたメッシュになっていた）→ 代わりに 4.8.8。
    旧「境界の三角形化」も廃止（必要なら Ctrl+T）。旧「Size Variance / Uniformity」はボロノイの「Randomness」1本に
  - Live Cells（GN モディファイア `STS Cells`・共有ノードグループ）: 細分化 → 三角面化 → 頂点をゆらして表面へ戻す → Dual Mesh。
    入力: 細分化／三角面化／ジッター／シード／ギャップ／セルの厚み／下地を残す／ラティス／支柱の半径。曲面で継ぎ目なし・後から変更可。
    均一なメッシュ（ボクセルリメッシュ後など）向き。UV 球のように極が密なメッシュでは割れた陶片のような見た目になる
  - Skin Lattice: 旧のスキン半径（シーン設定＋リアルタイム更新）を F9 調整のオペレータに。スキンモディファイアも付ける。根は島ごとにちょうど1つ
  - 系統: `Tessellation/cell_tessellation.py` v1.1 の1版（実環境 5.2 と同一）。他ツールとの機能重複なし
  - 仕組み: 対象の面ごとに、その面の平面で2Dタイル（三角／四角／六角／N角／ボロノイ）を敷いて面の形で切り抜き、面を置き換える。
    スキンモディファイア用の頂点半径も書ける
  - 弱点・不具合
    - **面ごとに別々に敷く**ので、隣の面と模様がつながらず、共有する辺の上で頂点がずれる（T字の接続・すき間）。元の辺も残る（`FACES_ONLY` で削除）
    - **曲がった四角形（非平面）**は平面に投影して敷くので表面から浮く。**凹んだ面**は切り抜き（Sutherland–Hodgman）が凸前提なので形が崩れる
    - 面の作成に失敗すると `except: pass` で**黙って捨てる**
    - 設定がシーン側だけでオペレータに無い → F9 で調整できない（やり直しは Undo して再実行）
    - スキン半径を書くだけでスキンモディファイア自体は付けない。タブ名 "Tessellation"
  - 別案: ジオメトリノードの「生きた模様」（三角形化 → Dual Mesh で六角・ボロノイ風）。曲面でも継ぎ目なく、後から密度を変えられる。
    ただし「床タイルを正確な寸法で敷く」用途は今の面ごとの方式が得意
- ✅ **parametric_plane → wave_surface**（2026-10-09・Claude）。ユーザー決定: (b) GN の生きた曲面・Generate タブ
  - GN モディファイア `STS Wave Surface`（共有ノードグループ）: h = 二次曲面（a〜f）＋ 同心円の波×3（振幅・波長・中心 X/Y・速さ[m/s]）。
    使わない項は 0 にするだけ（モード切替なし）。アニメーション ON でシーン時間に合わせて本当に動く／時間のずらしで静止画のポーズ。
    法線に追従 ON で平面以外のメッシュにもかかる。「新しいグリッド」（追加 > メッシュにも・カーソル位置・F9 で大きさと解像度）／「選択に追加」／
    「中心をばらまく」（シード・広がり、旧 Complex のランダム中心の代わり）／適用／外す
  - 以下、精査の記録
  - 系統: `parametric_plane/` の5本（他フォルダに同一物なし）。実環境 5.1 / 5.2 には `Create_Complex_Wave_Plane02.py` だけ入っている
  - 中身は「格子を作って z = f(x, y) で持ち上げる」の3種類だけ
    - 二次曲面 `parametric_plane.py`: z = a·x² + b·y² + c·xy + d·x + e·y + f
    - 同心円の波1つ `create_wave_plane.py`: z = A·sin(2π/λ·r − 速さ·時刻)
    - 同心円の波3つの合成: `Create_Complex_Wave_Plane.py`（中心が毎回ランダム）⊂ `create_wave_plane01.py`（中心を指定）⊂
      `..._Plane02.py`（時刻を現在フレーム/10 から取る）。「Z Scale」は Amplitude と掛けるだけで重複
  - 不具合（5.2 で確認）
    - `create_wave_plane01` と `..._Plane02` が**同じ bl_idname**（`mesh.add_adjustable_wave_plane`）→ 両方入れると後の方が黙って上書き
    - 02 の名前は "Animation" だが**アニメーションしない**（作った瞬間のフレームで固定。フレームを動かしても形は変わらない＝実機確認）
    - 中心の「ランダムな既定値」は**読み込み時に1回だけ**決まる（F9 で振り直せない・再起動で変わる）
    - 3D カーソルに作らない（常に原点）・作った物が**選択もアクティブにもならない**（実機確認）。長さに単位なし。
      Add > Mesh に1項目だけのサブメニューが3つ。wave plane の説明文が "quadratic function"（コピペ）
  - 標準機能との重なり: 格子＋**Wave モディファイア**（同心円の波・アニメーション・重ねがけ可）／Displace。
    任意式の曲面は拡張機能 "Extra Objects" の Z Function Surface（同梱ではない）
  - 案: (a) 一発生成のオペレータ1つにまとめる（二次曲面／波 1〜3 個・中心指定＋シード・カーソル位置・F9）… Strata 可
    (b) ジオメトリノードの「生きた曲面」モディファイア（同じ式・後から変更可・「アニメーション」ON で本当に動く・平面以外のメッシュにも法線方向にかけられる。
    確定したければ適用）… Claude、先に実機検証

## Utility タブ

- ✅ **language_switch**（2026-10-09・**Strata 作業員が実装**／22分・22ターン・テスト2回で全PASS、Claude が検収）
  - 元: `Switch_Jp_En/Switch_Jp_En.py`（`Sculpt_Tools___________/` と `My_Sculpt_Tools/language_switcher.py` も同一内容）
  - 直した不具合: 設定を Scene（.blend 側）に持っていた／「Reports」チェックが無効だった／プリファレンス変更に UNDO／言語を任意文字列で受けていた
  - 追加: 日英トグル（ショートカットやクイックお気に入り向け）。翻訳4項目は Blender のプリファレンスを直接表示

## ★archive（2026-10-09 夜に仕分け）

トップの「空フォルダ」（Armor_Ribbon / BlobBlush / CurveMedering / Dyntopo / PolyMakerTool / Reducer / SmoothNomal / min_thickness_guard /
quick_voxel_remesh / reduction / TestProject）は抜け殻で、中身は `★archive/` に移されていた。実環境 5.1/5.2 で使用中なのは
CrystalStructureMesh・HexagonalMeshGenerator・LeafVenationMeshGenerator4・gridmesh2・quick_voxel_remesh_panel_merged の5本。

- 対応不要（移植済みの旧版・重複・練習）: `AlignScripts(old)/`・`Scripts/` の整列系（＝align_tools）、`Scripts/Face_Set_to_Mask.py`（8行・＝face_set_tools）、
  `PolyMakerTool/` 10・11（廃止済み）、`TestProject/serect.py`（練習のサンプル）、`reduction/reduction.py`（`Reducer/reducer01.py` と同一）、`BlenderDoc/`（資料）
- 対象外: `ScriptToButton-master/`（他者製 RivinHD・GPL-3・拡張として別途導入済み）
- **ユーザー決定: 以下すべて精査して移植**
  - 生成系: 結晶＋四面体充填／葉脈メッシュ（1〜4）／六角メッシュ／ランダム格子（gridmesh 0〜3）
  - スカルプト系: Quick Voxel Remesh（voxel_remesh へ吸収想定）／薄肉ガード一式（5本）／Dyntopo＋リメッシュのループ（6本）／マスク・面セットのスムーズ（3本）
  - その他: アーマーリボン・クレイストリップ（4本）／曲線の接続 G1／シャープを保って削減／Blob ブラシ・Tools for me v2
  - **RetopoAssistant をスイートに統合**（自作拡張 v0.2.0・GPL-2.0-or-later → MIT に揃える必要）

### 移植計画（2026-10-09 夜・ユーザー決定）

1. ✅ **mesh_generators**（新規・Generate タブ＋追加 > メッシュ）: 格子（立方体／四面体・八面体の空間充填＝本当に埋まるもの、頂点共有）・六角グリッド（つながる／すき間）・
   ランダム格子（シード・XYZ 別・中点も）・**葉脈は本物に作り直す**（スペースコロニゼーション法・輪郭はプリセット＋選んだカーブ・辺のメッシュ・シード）
   （Strata 実装・検収。葉脈は作業員版が「引き寄せ点ごとに1本ずつ伸ばす」誤りで根元からの放射状の直線になっていた → 検収時に
   「節点ごとに引く方向の平均へ1歩」へ直し、分岐の次数を見るテストを追加。Skin の太さもパイプモデルで頭打ちに）
2. ✅ **voxel_remesh に吸収**: Quick Voxel Remesh は**同一ファイルが以前に吸収済み**（クリックでサイズを拾うは座標混同のため標準 Shift+R を案内）。
   Dyntopo ループ: スカルプト中の「リメッシュを適用」が Dyntopo を一時的に切って元に戻すように（**以前は切れたまま戻らなかった**＝GUI テストで確認）＋
   スカルプトモードのパネルに Dyntopo の ON/OFF と細かさ・詳細度で埋める。GUI テスト `tests/gui/gui_voxel_dyntopo.py`
3. ✅ **thickness_guard**（新規・Sculpt タブ）: 厚みの計測／薄い所を選ぶ／押し戻して直す／厚み→マスク（**Strata**・13分・31ターン・テスト4回、検収・手直しなし）／
   厚みを保つブラシ（Claude。計測は他と同じ内向きの光線・何回でも塗れる・Esc でセッションごと戻す・スカルプトモードから起動して戻る。GUI テスト `tests/gui/gui_thickness_brush.py`）
4. 既存の拡張: ✅ **smooth_normals** に「スカルプトマスクから」（`.sculpt_mask` を頂点グループ「Sculpt Mask」に写して重みに。GN は内部属性を読めないため）／✅ **face_set_tools** に「面セットをスムーズ」`sculpt.sts_face_set_smooth`（番号指定かクリック・他の面セットとの境目とメッシュの縁は固定・ラプラシアン）
5. ✅ **strip_draw**（新規・Sculpt タブ）: アーマーリボンとクレイストリップを**1つに統合**（描いた線ごとに生きた GN「STS Strip」で帯化・筆圧で幅・後から変更可・クレイ＝厚み＋ボクセルリメッシュ）。
   帯は「接線×面の法線」をカーブ法線にして面に寝かせ、厚みは面から外向き（描く向きに依らない）。旧アーマーは共有グループを作り直して他の帯まで変わっていた → 帯ごとにモディファイア入力で独立。GUI テスト `tests/gui/gui_strip_draw.py`
6. ✅ **bezier_draw** に G1 接続 `curve.sts_connect_g1`（ワールド座標・一番近い開いた端どうし・全スプライン・アクティブ側は動かない・ハンドルの長さは保つ）
7. ✅ **retopo_assistant**（統合・Model タブ。**Strata**・18分・27ターン、検収で1か所修正: 稜線角度が abs(内積) で薄いひれ（ほぼ180°の折り返し）を平らと誤判定 → calc_face_angle に直しテスト追加）: **動く部分だけ**（Decimate ＋スカルプトマスクで稜線保護）＋「シャープを保って削減」を角度による自動保護として吸収。
   作りかけ（GP 描画・穴埋め・投影）は後日。ライセンスは MIT に揃える（作者本人）
8. ✅ Blob ブラシ → **object_brush** で吸収済み（元にする物の種類に制限なし。複製はデータ共有なので同じ系統のメタボールとして溶け合う）
9. ✅ Tools for me → コードは使わず、**自作の一押しボタン `quick_buttons`**（Utility タブ）: 位置・回転・拡大の軸ごとリセット（**選択物すべて**。旧版はアクティブのみ）、
   ±30/45/90°回転・平らに・ミラー・刻み移動（本体の transform 経由＝編集モードでも可・ピボットに従う）、ピボット／座標系／影響の限定、3D カーソル、原点。GUI テスト `tests/gui/gui_quick_buttons.py`

### 精査結果（2026-10-09 夜・コード）

- **生成系**（2024年10月・Add > Mesh）共通の弱点: カーソル位置に作らない・作った物を選択しない・乱数にシードが無い（F9 のたびに変わる）・
  隣り合うセルの頂点が重複（同じ位置に別頂点）・単位なし
  - 結晶 `CrystalStructureMesh`: 立方体を並べるだけ（共有面が二重）。「正四面体」の頂点が正しくない（辺の長さが s と 1.58s）。面の向きがばらばら
  - 四面体充填 `TetrahedralSpace-Filling`: 名前と違い**空間を埋めていない**（正四面体は単独では空間を埋められない。格子状に離して並べるだけ）
  - 葉脈 `LeafVenationMeshGenerator` 1〜4: ランダムに枝分かれする折れ線＋各点に正多角形の面（重なる）。「隙間を埋める」は2頂点の辺を張るだけ。
    交差判定が全点との総当たり。v2〜4 は v1 に機能を足した版（v4 が上位互換）
  - 六角 `HexagonalMeshGenerator`: 六角形を別々の頂点で並べる（隣と辺が重複・つながっていない）。tessellation の六角タイルと重なる
  - ランダム格子 `gridmesh` 1〜3: 格子＋頂点を XYZ 別にずらす。中点にずらしを掛ける処理が `is_boundary`（外周）で選んでいて**中点ではなく外周の頂点が動く**。
    `gridmesh.py`（v0）は8頂点を手入力する別物。標準の Randomize（シード・量・法線方向）と一部重なる
- **Quick Voxel Remesh** v1.1.1（使用中）: Remesh モディファイア（ボクセル・適応度）の追加／更新／適用＋「クリックでボクセルサイズを拾う」。
  拾う処理がワールド座標とローカル座標を混ぜている・半径 0.2m 固定・サイドバー起動の座標問題。標準の Remesh モディファイアのパネルと大半が重なる
- **Dyntopo＋リメッシュのループ**（DyntopoFlow1 v1.2 が最新）: スカルプト中に Dyntopo の ON/OFF、Dyntopo を一時的に切ってボクセルリメッシュ（適応度・極の修正）→ 元に戻す。
  標準のスカルプトのヘッダー（Remesh・Dyntopo）と重なるが「Dyntopo の状態を保ったままリメッシュ」は便利
- **薄肉ガード一式**: 厚みの計測（法線の表裏へ光線）→ 属性 `mtg_thickness`／薄い所を選ぶ・頂点グループ／押し戻して直す／厚み→スカルプトマスク（線形）／
  厚みを保つブラシ（2026-05 の最新・モーダル）。本命 `min_thickness_guard.py` は **`register()` が2回定義され後者が勝つ → マスク系4操作が登録されない**。
  「直す」が 4.1 で廃止の `me.calc_normals()` を呼ぶ（5.x ではエラーのはず・未実機確認）。標準拡張 3D-Print Toolbox は「薄い所を選ぶ」だけで直す機能なし
- **マスク／面セットのスムーズ**: `SmoothNomal` は法線の代入（保存されない）＋マスク属性名違い（実体 `.sculpt_mask`）で効かない。
  `smooth_faceset_modal` は**構文エラーで読み込めない**（DeepSeek との相談ログ付き）。→ smooth_normals に「スカルプトマスクを重みに」、face_set_tools に「クリックした面セットをスムーズ」で実現できる
- **アーマーリボン**: カーブを描く準備（描画ツール・表面に沿う）＋ GN でリボン化。GN グループを毎回 `nodes.clear()` で作り直す共有グループなので
  **設定を変えると過去のリボンも全部変わる**。設定は Scene。**クレイストリップ** v0.2.4: 表面に筆圧つきの帯メッシュを描く＋Solidify＋Remesh
- **曲線の接続 G1**: 2つのカーブの「1つ目の終点」と「2つ目の始点」を合わせて接線をそろえる。ローカル座標どうしを直接代入（**位置や回転が違うとずれる**）・
  先頭スプラインだけ・どちらが1つ目かは選択順で不定
- **シャープを保って削減**: 「30°以上を自動でシャープに」とコメントにあるが実際は**選択中の辺に印を付けるだけ**、しかも Collapse の Decimate は
  シャープの印を見ないので**何も保護されない**。unregister に存在しない名前（無効化でエラー）。→ RetopoAssistant の稜線保護と同じ目的
- **Blob ブラシ**: メタボールを1回クリックで複製して終了。`__init__` の書き方が 4.x 以降の Operator の作法に合わない。object_brush（ドラッグで物を表面に置く）が上位互換
- **Tools for me v2**: **作者は藤田将氏（他者製・ライセンス表記なし）**。位置・回転・拡大のリセット、ピボット・座標系・スナップの切替、カーソル移動などのボタン集
- **RetopoAssistant** v0.2.0（導入済みと同一）: Decimate モディファイアの追加・適用（設定の同期）＋スカルプトマスクで稜線を保護（頂点グループ経由）。
  `gp_setup`・`gp_confirm`（グリースペンシルで線を描いて整える）・`fill_patch`（穴埋め・四角化）・`surface_project` は**ファイルはあるが登録されていない（作りかけ）**。
  仕様作成中に判明: Decimate の頂点グループは「重みが高い所から先に間引く」ので、旧版（反転が既定 OFF）は**稜線保護が逆に効いていた**（5.2 で確認: 辺の頂点 41→8 に減る。反転で 128 残る）

## 対象外・確認待ち

- `RetopoAssistant/`（zip のみ）、`ScriptToButton-master/`（他者製？）
- 中身が空のフォルダ: Armor_Ribbon, BlobBlush, CurveMedering, Dyntopo, PolyMakerTool, Reducer, SmoothNomal, min_thickness_guard, quick_voxel_remesh, reduction, TestProject
- `★archive/`（Armor_Ribbon_Pro / Mesh_Clay_Strip など）
