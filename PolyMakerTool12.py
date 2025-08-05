bl_info = {
    "name": "PolyMaker Tool",
    "blender": (4, 0, 0),
    "category": "Object",
    "author": "Yoshiki Yasunaga & ChatGPT",
    "version": (1, 2),
    "description": "Create polygon meshes and modify them easily",
}

import bpy

class CreatePolygonMeshOperator(bpy.types.Operator):
    """Create an empty mesh and enter Edit Mode"""
    bl_idname = "mesh.create_polygon_mesh"
    bl_label = "Create Polygon Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # すべてのオブジェクトの選択を解除
        bpy.ops.object.select_all(action='DESELECT')

        # 新しいメッシュオブジェクトを作成
        mesh = bpy.data.meshes.new(name="PolygonMesh")
        obj = bpy.data.objects.new(name="PolygonMesh", object_data=mesh)
        context.collection.objects.link(obj)

        # オブジェクトを選択し、アクティブにする
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # 編集モードに変更
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

class AddSolidifyModifierOperator(bpy.types.Operator):
    """Add a Solidify modifier to the mesh"""
    bl_idname = "object.add_solidify_modifier"
    bl_label = "Add Solidify Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':
            # ソリッドモディファイアを追加
            solidify = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            solidify.thickness = 0.1
            solidify.offset = 0

        return {'FINISHED'}


class ChangePolygonTypeOperator(bpy.types.Operator):
    """Change polygon type to Quads or Triangles"""
    bl_idname = "mesh.change_polygon_type"
    bl_label = "Change Polygon Type"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Polygon Type",
        items=[
            ('QUADS', "Quads", "Convert faces to quads"),
            ('TRIS', "Triangles", "Convert faces to triangles"),
        ],
        default='QUADS',
    )

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        if self.mode == 'QUADS':
            bpy.ops.mesh.tris_convert_to_quads()
        else:
            bpy.ops.mesh.quads_convert_to_tris()

        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


class ToggleObjectEditModeOperator(bpy.types.Operator):
    """Toggle between Object Mode and Edit Mode"""
    bl_idname = "object.toggle_object_edit_mode"
    bl_label = "Toggle Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':
            if obj.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}


class PolyMakerToolPanel(bpy.types.Panel):
    """Creates a Panel in the View3D UI"""
    bl_label = "PolyMaker Tool"
    bl_idname = "VIEW3D_PT_polymaker_tool"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'  # 'PolyMaker' から 'Sculpt Tool' に変更

    def draw(self, context):
        layout = self.layout
        layout.operator("mesh.create_polygon_mesh", text="New Polygon Mesh")
        layout.operator("object.add_solidify_modifier", text="Add Solidify")
        
        col = layout.column()
        col.label(text="Change Polygon Type:")
        col.operator("mesh.change_polygon_type", text="Convert to Quads").mode = 'QUADS'
        col.operator("mesh.change_polygon_type", text="Convert to Triangles").mode = 'TRIS'

        layout.operator("object.toggle_object_edit_mode", text="Toggle Object/Edit Mode")


def register():
    bpy.utils.register_class(CreatePolygonMeshOperator)
    bpy.utils.register_class(AddSolidifyModifierOperator)
    bpy.utils.register_class(ChangePolygonTypeOperator)
    bpy.utils.register_class(ToggleObjectEditModeOperator)
    bpy.utils.register_class(PolyMakerToolPanel)


def unregister():
    bpy.utils.unregister_class(CreatePolygonMeshOperator)
    bpy.utils.unregister_class(AddSolidifyModifierOperator)
    bpy.utils.unregister_class(ChangePolygonTypeOperator)
    bpy.utils.unregister_class(ToggleObjectEditModeOperator)
    bpy.utils.unregister_class(PolyMakerToolPanel)


if __name__ == "__main__":
    register()
