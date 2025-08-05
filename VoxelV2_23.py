bl_info = {
    "name": "Selected Object Voxel Remesh and Sculpt",
    "author": "Yoshiki Yasunaga & ChatGPT",
    "version": (2, 2, 3),
    "blender": (4, 3, 0),
    "location": "View3D > Edit Mesh",
    "description": "Apply voxel remesh, join objects, and create face sets for original objects.",
    "category": "Object"
}

import bpy
import bmesh
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, FloatProperty, EnumProperty

# -----------------------------------------------------
# ✅ すべてのモディファイアを適用するサブルーチン
# -----------------------------------------------------
def apply_all_modifiers(obj):
    """
    指定されたオブジェクトのすべてのモディファイアを適用する。
    """
    if obj.modifiers:
        bpy.ops.object.select_all(action='DESELECT')  # 他のオブジェクトの選択解除
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')  # 確実にオブジェクトモードへ変更
        
        for mod in obj.modifiers[:]:
            bpy.ops.object.modifier_apply(modifier=mod.name)

# -----------------------------------------------------
# ✅ Voxel Remesh を適用するオペレーター
# -----------------------------------------------------

class OBJECT_OT_voxel_remesh_sculpt_v2(Operator):
    """オブジェクトを統合し、Voxel Remesh を適用"""
    bl_idname = "object.voxel_remesh_sculpt_v223"
    bl_label = "Voxel Remesh and Sculpt v223"
    bl_options = {'REGISTER', 'UNDO'}

    # Voxel サイズのプロパティ
    voxel_size: FloatProperty(
        name="Voxel Size",
        default=0.01,
        min=0.005,
        max=1.0,
        description="Set the voxel size for remeshing."
    )

    # 適応度のプロパティ
    adaptivity: FloatProperty(
        name="Adaptivity",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Set adaptivity for remeshing."
    )

    # モディファイアを適用するかのフラグ
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        default=True,
        description="Apply all modifiers before joining"
    )

    # 最終的にスカルプトモードにするか、オブジェクトモードにするか
    final_mode: EnumProperty(
        name="Final Mode",
        items=[('OBJECT', "Object Mode", "End in Object Mode"), 
               ('SCULPT', "Sculpt Mode", "End in Sculpt Mode")],
        default='SCULPT',
        description="Choose whether to end in Object Mode or Sculpt Mode."
    )

    def invoke(self, context, event):
        """UIからの実行時にダイアログを表示する"""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        """Voxel Remesh の適用処理"""

        # 現在のオブジェクトのモードをオブジェクトモードに変更
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 選択されているオブジェクトを取得
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        merged_objects = []  # 統合するオブジェクトのリスト
        skipped_objects = []  # メッシュ化できなかったオブジェクト

        for obj in selected_objects:
            context.view_layer.objects.active = obj
            
            if self.apply_modifiers:
                apply_all_modifiers(obj)  # ✅ すべてのモデファイヤを適用

            # `convert_to_mesh(obj)` を使ってメッシュ化を統一処理
            converted_obj = convert_to_mesh(obj)

            if converted_obj:
                merged_objects.append(converted_obj)
            else:
                skipped_objects.append(obj.name)

        # メッシュ化できなかったオブジェクトの警告
        if skipped_objects:
            self.report({'WARNING'}, f"Some objects could not be converted to mesh: {', '.join(skipped_objects)}")

        # 複数のオブジェクトを統合
        if len(merged_objects) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in merged_objects:
                obj.select_set(True)
            context.view_layer.objects.active = merged_objects[0]
            bpy.ops.object.join()

        # 統合後のアクティブオブジェクトを取得
        active_obj = context.view_layer.objects.active

        # Voxel Remesh モディファイアを追加
        bpy.ops.object.modifier_add(type='REMESH')
        remesh_modifier = active_obj.modifiers[-1]
        remesh_modifier.name = "Voxel Remesh"
        remesh_modifier.mode = 'VOXEL'
        remesh_modifier.voxel_size = self.voxel_size
        remesh_modifier.use_smooth_shade = True
        remesh_modifier.adaptivity = self.adaptivity

        # 指定された最終モードに変更
        bpy.ops.object.mode_set(mode=self.final_mode)

        self.report({'INFO'}, f"Voxel remesh preview applied with voxel size {self.voxel_size}, adaptivity {self.adaptivity}.")
        return {'FINISHED'}

# -----------------------------------------------------
# ✅ スカルプトリメッシュを適用するオペレーター
# -----------------------------------------------------
class OBJECT_OT_apply_voxel_remesh_face_sets(Operator):
    """スカルプトリメッシュを適用"""
    bl_idname = "object.apply_voxel_remesh_face_sets"
    bl_label = "Apply Sculpt Remesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """スカルプトモードで Voxel Remesh を適用"""
        active_obj = context.view_layer.objects.active
        if not active_obj:
            self.report({'WARNING'}, "No active object.")
            return {'CANCELLED'}

        # リメッシュモディファイアを探す
        remesh_mod = None
        for mod in active_obj.modifiers:
            if mod.name == "Voxel Remesh":
                remesh_mod = mod
                break

        if not remesh_mod:
            self.report({'WARNING'}, "Voxel Remesh modifier not found.")
            return {'CANCELLED'}

        # リメッシュパラメータを記録
        rec_voxel_size = remesh_mod.voxel_size
        rec_adaptivity = remesh_mod.adaptivity
        bpy.ops.object.modifier_remove(modifier="Voxel Remesh")  # モディファイアを削除

        # スカルプトモードへ変更
        bpy.ops.object.mode_set(mode='SCULPT')
        active_obj.data.use_remesh_fix_poles = True  # Fix Poles を有効化

        # スカルプトモードのリメッシュを適用
        bpy.context.object.data.remesh_voxel_size = rec_voxel_size
        bpy.context.object.data.remesh_voxel_adaptivity = rec_adaptivity
        bpy.ops.object.voxel_remesh()

        self.report({'INFO'}, f"Applied Sculpt Remesh with Voxel Size: {rec_voxel_size}, Adaptivity: {rec_adaptivity}, Fix Poles: True.")
        return {'FINISHED'}


# -----------------------------------------------------
# ✅ 汎用メッシュ変換ルーチン
# -----------------------------------------------------

def convert_to_mesh(obj):
    """
    オブジェクトをメッシュに変換する共通ルーチン
    - モディファイヤを適用
    - カーブ・メタボール・サーフェス・フォントをメッシュ化
    - メッシュ化できないオブジェクトをリストに記録

    :param obj: 処理対象のオブジェクト
    :return: メッシュ化されたオブジェクト or None（変換不可）
    """
    # 既にメッシュならそのまま返す
    if obj.type == 'MESH':
        return obj

    # モディファイヤが付いている場合、すべて適用
    if obj.modifiers:
        bpy.ops.object.select_all(action='DESELECT')  # 他のオブジェクトを選択解除
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for mod in obj.modifiers[:]:
            bpy.ops.object.modifier_apply(modifier=mod.name)

    # メッシュに変換可能なオブジェクトの場合
    if obj.type in {'CURVE', 'META', 'SURFACE', 'FONT'}:
        bpy.ops.object.select_all(action='DESELECT')  # 他のオブジェクトを選択解除
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')  # 念のためオブジェクトモードへ
        bpy.ops.object.convert(target='MESH')  # メッシュに変換
        return obj  # メッシュ化したオブジェクトを返す

    # メッシュ化できないオブジェクトの場合、None を返す
    return None

# -----------------------------------------------------
# ✅ 面セットを作成するオペレーター
# -----------------------------------------------------

class OBJECT_OT_create_face_sets(Operator):
    """Face Set を作成（カーブ・メタボール・モディファイヤ適用対応）"""
    bl_idname = "object.create_face_sets"
    bl_label = "Create Face Sets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """オブジェクトに Face Set を適用"""
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        processed_objects = []  # メッシュ化されたオブジェクトを保持するリスト
        skipped_objects = []  # メッシュ化できないオブジェクトを記録するリスト

        for obj in selected_objects:
            context.view_layer.objects.active = obj
            
            converted_obj = convert_to_mesh(obj)  # メッシュ化ルーチンを呼び出す

            if converted_obj:
                processed_objects.append(converted_obj)
            else:
                skipped_objects.append(obj.name)

        for obj in processed_objects:
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='SCULPT')  # スカルプトモードに変更

            # オブジェクト全体をマスク
            bpy.ops.paint.mask_flood_fill(mode='VALUE', value=1)

            # マスクから Face Set を作成
            bpy.ops.sculpt.face_sets_create(mode='MASKED')

            # マスクを解除
            bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0)

            bpy.ops.object.mode_set(mode='OBJECT')  # オブジェクトモードに戻る

        # 【追加】メッシュ化できなかったオブジェクトの警告表示
        if skipped_objects:
            self.report({'WARNING'}, f"Some objects could not be converted to mesh: {', '.join(skipped_objects)}")

        self.report({'INFO'}, "Face sets created for selected objects.")
        return {'FINISHED'}
        
# -----------------------------------------------------
# ✅ メッシュ変換オペレーター
# -----------------------------------------------------
class OBJECT_OT_convert_to_mesh(Operator):
    """選択したオブジェクトをメッシュ化"""
    bl_idname = "object.convert_to_mesh"
    bl_label = "Convert to Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """選択されたオブジェクトをメッシュに変換"""
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        skipped_objects = []  # メッシュ化できなかったオブジェクト
        converted_objects = []  # メッシュ化成功したオブジェクト

        for obj in selected_objects:
        
            converted_obj = convert_to_mesh(obj)
            
            if converted_obj:
                converted_objects.append(converted_obj)
            else:
                skipped_objects.append(obj.name)

        if converted_objects:
            self.report({'INFO'}, f"Converted {len(converted_objects)} object(s) to mesh.")
        if skipped_objects:
            self.report({'WARNING'}, f"Some objects could not be converted: {', '.join(skipped_objects)}")

        return {'FINISHED'}

# -----------------------------------------------------
# ✅ 面セットをマスクにするオペレーター
# -----------------------------------------------------
class SCULPT_OT_face_set_to_mask(bpy.types.Operator):
    bl_idname = "sculpt.face_set_to_mask"
    bl_label = "Face Set to Mask"
    bl_options = {'REGISTER', 'UNDO'}

    waiting_for_click: bpy.props.BoolProperty(default=True)

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # マウスクリックされたら処理を実行
            self.execute_mask_process(context)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # 右クリックまたはEscでキャンセル
            self.report({'INFO'}, "Operation canceled")
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "Click on a Face Set to apply the mask")
        return {'RUNNING_MODAL'}

    def execute_mask_process(self, context):
        """マウス位置のFace Setに対してマスクを適用"""
        obj = context.active_object
        if obj and obj.mode == 'SCULPT':
            bpy.ops.sculpt.face_set_change_visibility(mode='HIDE_ACTIVE')  # Face Set を隠す
            bpy.ops.paint.mask_flood_fill(mode='VALUE', value=1)  # 全体をマスク
            bpy.ops.paint.hide_show_all(action='SHOW')  # 隠したFace Setを表示
            bpy.ops.paint.mask_flood_fill(mode='INVERT')  # マスク反転
            self.report({'INFO'}, "Face Set converted to mask successfully")
        else:
            self.report({'WARNING'}, "Active object must be in Sculpt Mode")

# -----------------------------------------------------
# ✅ オブジェクトモードとスカルプトモードを切り替えるオペレーター
# -----------------------------------------------------
class OBJECT_OT_toggle_object_sculpt(Operator):
    """オブジェクトモードとスカルプトモードを切り替える"""
    bl_idname = "object.toggle_object_sculpt"
    bl_label = "Toggle Object/Sculpt Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        """オブジェクトモードとスカルプトモードをトグル"""
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object.")
            return {'CANCELLED'}

        # 現在のモードを取得し、切り替える
        if obj.mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='SCULPT')
            self.report({'INFO'}, "Switched to Sculpt Mode.")
        else:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "Switched to Object Mode.")

        return {'FINISHED'}

# -----------------------------------------------------
# ✅ プロパティパネル（UI）
# -----------------------------------------------------
class OBJECT_PT_voxel_remesh_sculpt_panel(Panel):
    """UIパネルの定義"""
    bl_label = "Voxel Remesh and Sculpt v2.23"
    bl_idname = "OBJECT_PT_voxel_remesh_sculpt_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_voxel_remesh_sculpt_v2.bl_idname, text="Voxel Remesh and Sculpt")
        layout.operator(OBJECT_OT_apply_voxel_remesh_face_sets.bl_idname, text="Apply Sculpt Remesh")
        layout.operator(OBJECT_OT_create_face_sets.bl_idname, text="Create Face Sets")
        layout.operator(OBJECT_OT_convert_to_mesh.bl_idname, text="Curve Convert to Mesh")  # メッシュ変換ボタン
        layout.operator(SCULPT_OT_face_set_to_mask.bl_idname, text="Face Set To Mask") # フェイスセットをマスクにするボタン
        layout.operator(OBJECT_OT_toggle_object_sculpt.bl_idname, text="Toggle Object/Sculpt Mode")  # モード切替ボタン


# -----------------------------------------------------
# ✅ 登録処理
# -----------------------------------------------------
def register():
    bpy.utils.register_class(OBJECT_OT_voxel_remesh_sculpt_v2)
    bpy.utils.register_class(OBJECT_OT_apply_voxel_remesh_face_sets)
    bpy.utils.register_class(OBJECT_OT_create_face_sets)
    bpy.utils.register_class(OBJECT_OT_convert_to_mesh)
    bpy.utils.register_class(SCULPT_OT_face_set_to_mask)
    bpy.utils.register_class(OBJECT_OT_toggle_object_sculpt)
    bpy.utils.register_class(OBJECT_PT_voxel_remesh_sculpt_panel)
    
def unregister():
    bpy.utils.unregister_class(OBJECT_PT_voxel_remesh_sculpt_panel)
    bpy.utils.unregister_class(OBJECT_OT_toggle_object_sculpt)
    bpy.utils.unregister_class(SCULPT_OT_face_set_to_mask)
    bpy.utils.unregister_class(OBJECT_OT_convert_to_mesh)
    bpy.utils.unregister_class(OBJECT_OT_create_face_sets)
    bpy.utils.unregister_class(OBJECT_OT_apply_voxel_remesh_face_sets)
    bpy.utils.unregister_class(OBJECT_OT_voxel_remesh_sculpt_v2)


if __name__ == "__main__":
    register()
