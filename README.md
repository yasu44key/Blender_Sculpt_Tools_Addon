# Blender Sculpt / Modeling Tools Collection  
# Blender スカルプト / モデリングツール集

---

## Overview  
This is a collection of custom Blender addons designed to accelerate sculpting and modeling workflows.  

Blenderのスカルプトとモデリングのワークフローを高速化することを目的とした、自作アドオンのコレクションです。  

---

## Environment  
- Tested with Blender 4.4  

- Blender 4.4で動作確認済み  

---

## Installation  
It is assumed that you will install each addon `.py` file individually.  

1. Download the `.py` file of the addon you want to use from this repository.  
2. Launch Blender and go to `Edit > Preferences > Add-ons`.  
3. Press the `Install` button and select the downloaded `.py` file.  
4. Enable the installed addon in the list.  

必要なアドオンの`.py`ファイルのみを個別にインストールすることを想定しています。  

1. このリポジトリから、使用したいアドオンの`.py`ファイルをダウンロードします。  
2. Blenderを起動し、`編集 > プリファレンス > アドオン` を開きます。  
3. `インストール`ボタンを押し、ダウンロードした`.py`ファイルを選択します。  
4. インストールされたアドオンにチェックを入れて有効化します。  

---

## Included Addons  
1. [Bezier Draw Tool with Effects](#1-bezier-draw-tool-with-effects)  
2. [Curve Subdivide & Decimate](#2-curve-subdivide--decimate)  
3. [Edge Creation Tool](#3-edge-creation-tool)  
4. [PolyMaker Tool](#4-polymaker-tool)  
5. [Language Switcher](#5-language-switcher)  
6. [Voxel Remesh and Sculpt](#6-voxel-remesh-and-sculpt)  

## 収録アドオン一覧  
1. [Bezier Draw Tool with Effects](#1-bezier-draw-tool-with-effects)  
2. [Curve Subdivide & Decimate](#2-curve-subdivide--decimate)  
3. [Edge Creation Tool](#3-edge-creation-tool)  
4. [PolyMaker Tool](#4-polymaker-tool)  
5. [Language Switcher](#5-language-switcher)  
6. [Voxel Remesh and Sculpt](#6-voxel-remesh-and-sculpt)  

---

## 1. Bezier Draw Tool with Effects  
Draw Bezier curves intuitively in the 3D view and apply various effects.  

3Dビュー上で直感的にベジェ曲線を描画し、多彩なエフェクトを適用できるツールです。  

**Version:** 1.4.5  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

### Features / 主な機能  
- **Drawing:**  
  - `Start Drawing`: Create a new Bezier curve and enter draw mode.  
  - `Finish Drawing`: Exit draw mode and return to object mode.  
- **Edit Mode Effects (apply to selected points):**  
  - `Spiral Points`: Arrange control points in a spiral.  
  - `Scale Variation`: Add variation to point radius.  
  - `Rotate Variation`: Add tilt rotation to points.  
  - `Smooth Points`: Smooth handles and adjust type/scale.  
- **Object Mode Effects (apply to whole curve):**  
  - `Scale Variation (Object Mode)`: Apply global thickness variation.  
  - Includes twist and spiral transformation options.  

---

## 2. Curve Subdivide & Decimate  
Tools to increase (subdivide) or reduce (decimate) curve control points. Works in Edit Mode.  

カーブのポイントを増やしたり（細分化）、減らしたり（間引き）するためのツールです。編集モードで動作します。  

**Version:** 1.0.4  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

### Features / 主な機能  
- **Subdivide Curve:**  
  - Split segments, add control points.  
  - Select specific points or apply to entire curve.  
  - Adjustable `Number of Cuts`.  
- **Decimate Curve:**  
  - Reduce control points while preserving shape.  
  - Uses RDP algorithm with `Error Threshold`.  

---

## 3. Edge Creation Tool  
Quickly create connected edges by clicking in the 3D view, with snapping support.  

3Dビュー上でマウスクリックするだけで、スナップを効かせながら連続した辺を作成できるツールです。  

**Version:** 1.5  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

---

## 4. PolyMaker Tool  
Supports creating and editing polygon meshes.  

ポリゴンメッシュの作成と基本的な編集をサポートするツールです。  

**Version:** 1.2  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

---

## 5. Language Switcher  
Switch Blender UI language quickly between Japanese and English.  

BlenderのUI言語を日本語と英語で素早く切り替えるためのツールです。  

**Version:** 1.1.0  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

---

## 6. Voxel Remesh and Sculpt  
Automates merging objects, remeshing with voxels, and starting sculpt mode.  

複数のオブジェクトを統合し、ボクセルリメッシュをかけてスカルプトを開始するまでの一連の流れを自動化するツールです。  

**Version:** 2.2.3  
**Panel:** 3D View > UI Shelf > Sculpt Tools  

---

## Contribution / 貢献  
Bug reports and feature requests are welcome, but responses may be delayed.  

バグ報告や機能改善の提案は歓迎しますが、すぐに対応できない場合があります。  

---

## License / ライセンス  
This project is released under the MIT License. See `LICENSE` for details.  

このプロジェクトはMITライセンスの下で公開されています。詳細は`LICENSE`ファイルをご覧ください。  

---

## Author / 作者  
- **Yoshiki Yasunaga**  
- X (formerly Twitter): [@YasunagaYoshiki](https://twitter.com/YasunagaYoshiki)  

- **安永ヨシキ**  
- X (旧Twitter): [@YasunagaYoshiki](https://twitter.com/YasunagaYoshiki)  
