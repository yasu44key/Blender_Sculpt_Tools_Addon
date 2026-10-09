# Sculpt Tools Suite 規約

旧アドオン（`BlenderAddonProject/`）を1本ずつこのパッケージへ移すときの決まり。
人も AI 作業員（Claude / Strata）もこれに従う。**最終的な仕様はテスト**（`tests/`）で、
この文書はその意図の説明。

## 1. 構成

- 1ツール = `modules/<name>/` の1パッケージ。ルート `__init__.py` の `MODULES` に名前を足すと、
  プリファレンスに ON/OFF チェックが自動で出る
- 各モジュールが持つもの
  - `META` … `label` / `description` / `tabs`（表示するタブ名のタプル）/ 任意で `default`
  - `JA` … 日本語訳 `{"英語": "日本語"}`
  - `register()` / `unregister()` … 何度 ON/OFF しても壊れないこと
  - `classes` … 登録するクラスのタプル（ops_*.py / panels.py ごとに `classes` を持ち、`__init__` で連結）
- 2つ以上のモジュールで使う処理は `core/` に置く（例: `core/curve_utils.py`）。モジュール同士で import しない
- docstring の先頭に「Replaces: 旧ファイル名」を書き、どの旧版から来たかを残す
- 旧フォルダ `BlenderAddonProject/` のファイルは**読むだけ**。変更・移動・削除しない

## 2. 命名（旧アドオンと同時に入れても衝突しないため）

- オペレータ: `bl_idname = "<カテゴリ>.sts_<name>"`、クラス名 `<CATEGORY>_OT_sts_<name>`
  - 例: `curve.sts_spiral` / `CURVE_OT_sts_spiral`
- パネル: クラス名 `VIEW3D_PT_sts_<module>_<name>`
- Scene などに足すプロパティ: `sts_<module>`（PointerProperty 1つにまとめる）
- アドオンが作るモディファイア等の名前: `"STS ..."`（例: `STS Mirror`）

## 3. タブ（N パネル）

`bl_category` は必ず `core/tabs.py` の定数を使う（テストで検査）。作業の文脈で分ける。

- `Curve` … カーブを描く・編集する・変換する
- `Sculpt` … スカルプト補助、リメッシュ、フェイスセット、マスク
- `Model` … メッシュ編集、リトポ、整列
- `Generate` … パラメトリックな形状・カーブの生成
- `Utility` … 言語切替など環境まわり

タブ名は Blender 本体の辞書で自動的に訳される（Curve→カーブ、Generate→生成）。本体に訳が無いタブ（Model）は `core/tabs.py` の `JA` に書く。

## 4. UI のきまり

- モジュールごとにメインパネル1つ。モード専用の機能はサブパネルにして `poll` で出し分ける
- 生成系ボタンはモード違いで**隠さず無効化**し、理由をラベルで示す（「オブジェクトモード専用」）
- 設定欄は `use_property_split = True`（ラベル左・値右）。見出しは `box` ＋アイコン付きラベル
- 選択対象の規則: **Edit Mode = 選択したもの、Object Mode = 全体**。パネルに「対象: …」を表示する
- 対象が無いときは `report({'WARNING'}, ...)` して `CANCELLED`（黙って何もしない、をしない）
- オペレータは `bl_options = {'REGISTER', 'UNDO'}`。パラメータは F9（最後の操作を調整）で再調整できる形に。
  シーンに設定値を置いてボタンに渡す方式は使わない
- 角度は `subtype='ANGLE'`、長さは `unit='LENGTH'`（ラジアン生値を見せない）
- **ユーザーのデータを名前で消したり上書きしたりしない**（旧 spiral は既存 "Spiral_Curve" を削除していた）
- 何度押しても複製が増えない（旧 Bezier の Mirror は Finish のたびに複製）。非破壊にできるものはモディファイアで
- 空振りの後始末をする（何も描かずに Finish → 空カーブを削除）

## 5. 言語

- コード中の UI 文字列は英語。日本語は各モジュールの `JA` に書き、Blender の翻訳機構に登録する
  （Preferences > Interface > 言語 に従って切り替わる）
- **Blender 本体の辞書が優先される**。本体に同じ英語があると `JA` は無視される。
  テスト `all JA entries take effect` が衝突を列挙するので、
  - 本体の訳で意味が通る → `JA` から外す（本体の用語に揃う）
  - 意味がずれる → 英語側を言い換える（例: Thickness→「幅」になるので "Curve Thickness"）

## 6. 対応バージョン

- `blender_version_min = "5.1.0"`。5.1 と 5.2 でテストする（このマシンで動くのはこの2つ）
- Extension 形式（`blender_manifest.toml`）。モジュール内の import は相対 import のみ

## 7. テスト

- `tests/test_<module>.py` を作る。`_testlib.check()` で項目を積み、`run([...])` に関数を渡す
- 実行: `bash tests/run_tests.sh`（5.1 と 5.2）／`bash tests/run_tests.sh 5.2`／`TESTS=test_x.py bash tests/run_tests.sh`
  - zip にビルド → 隔離したユーザーフォルダへインストール → バックグラウンド実行
  - **普段の Blender 設定は使わない**（`BLENDER_USER_RESOURCES` で隔離。Blender を呼ぶ全行で）
- 最低限入れる項目: モジュール ON/OFF、タブ定数、JA 衝突、各オペレータの正常系、
  Edit/Object の対象範囲、対象なしで CANCELLED、旧版で見つけた不具合の再発防止
- パネルの描画は GUI でしか走らないので、見た目の確認は GUI 撮影（隔離設定で起動→撮影→自動終了）で行う

## 8. 既知の罠

- プロパティ定義の誤り（存在しない引数など。例: `hard_min=`）は**そのプロパティだけ黙って登録されない**。他は登録されるので気付きにくい。
  範囲は `min=` / `max=`（これが RNA の hard 範囲）と `soft_min=` / `soft_max=`。プロパティが消えたら Blender の生の出力の registration error を見る
- バックグラウンド実行でスカルプト系の標準オペレータ（`sculpt.face_sets_create` など）を呼ぶと Blender が落ちる。テストでは属性の読み書きで確かめる
- サイドバーのボタンから起動したモーダルでは `context.region` はサイドバー。座標は `core/view3d.py` の関数で WINDOW 領域から求める
- Blender 本体の日本語辞書がアドオンの訳より優先される（5. 言語）
- ジオメトリノード・モディファイアの入力値は **5.2 で書き方が変わった**（`mod["Socket_2"] = v` が拒否され、`mod.properties.inputs.Socket_2.value = v`）。`core/nodes.py` の `set_modifier_input` を使う
- 編集モードに入った直後の `obj.matrix_world` は古いことがある（回転が抜けて読める）。ワールド座標で計算する前に `context.view_layer.update()`
- 編集モードの bmesh 頂点に `v.co = ...` と直接代入しても `bmesh.update_edit_mesh` で焼かれないことがある。`bmesh.ops.transform` を使う
- bmesh にカスタムデータ層を足す・消す（`layers.int.new` / `layers.skin.verify()` など）と要素が作り直され、**それ以前に取った BMVert / BMFace の参照がすべて無効**になる
  （`ReferenceError: BMesh data ... has been removed`）。層を先に作ってから要素を集める。途中で必要なら `index` で引き直す
- GN モディファイアの入力を Python から書いても再評価されない（5.1/5.2 とも）。`core/nodes.py` の `set_modifier_input` が `update_tag()` まで行う
- `bmesh.ops.inset_individual` / `inset_region` の戻り値 `faces` は**外周の帯（新しい面）**。内側の面は渡した元の面そのもの。
  帯の頂点を動かすと隣と共有する点まで動く（旧 Aging Toolkit の不具合）
- `extrude_face_region` の後で元の面を消すときは `context='FACES'`。`FACES_ONLY` だと元の面どうしの間の辺が面なしで残る
- 押し出し・ベベルの直後は `BMFace.index` が古い（振り直されていない）。面の見分けは要素そのもの（set）で
- `bmesh.ops.bevel` は隣の面を作り直すので、ベベル前に取った面の参照は無効になりうる（中心と法線などで探し直す）
- アノテーションは 5.x では `scene.annotation`（`scene.grease_pencil` は無い）。アクティブなレイヤーは `layers.active_index`。
  Python から線を足せる（`frame.strokes.new`）のは 5.2 から → 線が要るテストは 5.2 で作った .blend（`tests/data/`）を開く
- `blf.size(font_id, size)` は2引数（3引数は 4.0 で廃止。描画コールバック内で毎回エラーになり文字が出ない）
- Operator に `draw` という名前のメソッドを作らない（予約名・登録エラー）。描画コールバックは `draw_hud` などに
- GN の Named Attribute は**先頭がピリオドの内部属性（`.sculpt_mask` など）を読めない**（値0。5.1/5.2）。Python からは読めるので、頂点グループなどに写して渡す
- Decimate モディファイアの頂点グループは「**重みが高い所から先に間引く**」。守りたい所に重み1を付けたら `invert_vertex_group = True`（旧 Retopo Assistant はここが逆）
- 編集モード中は `obj.data.vertices` が古い（編集の内容は bmesh 側）。メッシュデータを直接書き換えるオペレータは poll でオブジェクトモードに限る

## 9. 作者表記

- manifest の `maintainer` は `"Yoshiki Yasunaga & Claude Code"`。ライセンス MIT
