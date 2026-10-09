"""Mesh Tools — one-click Solidify plus Blender's own conversion buttons.

Replaces: MeshTools_1_3.py (Solidify / conversion panel part)

The old version kept Solidify defaults in the Scene and added a *new*
Solidify modifier on every press. Here the values live on the operator
(adjustable with F9) and a second press updates the existing Solidify
modifier instead of duplicating it. Apply, Tris to Quads and Triangulate
are Blender's own operators, so they act on the user's face selection
instead of selecting everything.
"""

import bpy

from ...core import tabs

META = {
    "label": "Mesh Tools",
    "description": "One-click Solidify and mesh conversion shortcuts",
    "tabs": ("Model",),
}

JA = {
    "Mesh Tools": "メッシュツール",
    "Add Solidify": "ソリッド化を追加",
    "Apply Solidify": "ソリッド化を適用",
    "Select a mesh": "メッシュを選択してください",
    "Object mode only": "オブジェクトモード専用",
    "Edit mode only": "編集モード専用",
}


class OBJECT_OT_sts_add_solidify(bpy.types.Operator):
    """Add a Solidify modifier, or update the values of the existing one"""
    bl_idname = "object.sts_add_solidify"
    bl_label = "Add Solidify"
    bl_options = {'REGISTER', 'UNDO'}

    thickness: bpy.props.FloatProperty(
        name="Thickness",
        description="Solidify thickness",
        default=0.1, min=0.0, unit='LENGTH',
    )
    offset: bpy.props.FloatProperty(
        name="Offset",
        description="Solidify offset",
        default=0.0, min=-1.0, max=1.0,
    )
    use_even_offset: bpy.props.BoolProperty(
        name="Even Thickness",
        description="Solidify even thickness",
        default=False,
    )
    use_rim: bpy.props.BoolProperty(
        name="Fill Rim",
        description="Solidify fill rim",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        mod = next((m for m in obj.modifiers if m.type == 'SOLIDIFY'), None)
        if mod is None:
            mod = obj.modifiers.new("STS Solidify", 'SOLIDIFY')
        mod.thickness = self.thickness
        mod.offset = self.offset
        mod.use_even_offset = self.use_even_offset
        mod.use_rim = self.use_rim
        return {'FINISHED'}


class VIEW3D_PT_sts_mesh_tools(bpy.types.Panel):
    bl_label = "Mesh Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            layout.label(text="Select a mesh")
            return

        box = layout.box()
        box.label(text="Solidify", icon='MOD_SOLIDIFY')
        mod = next((m for m in obj.modifiers if m.type == 'SOLIDIFY'), None)
        if mod is not None:
            box.use_property_split = True
            box.use_property_decorate = False
            col = box.column(align=True)
            col.prop(mod, "thickness")
            col.prop(mod, "offset")
            col.prop(mod, "use_even_offset")
            col.prop(mod, "use_rim")
            row = box.row()
            row.enabled = context.mode == 'OBJECT'
            row.operator("object.modifier_apply", text="Apply Solidify",
                         modifier=mod.name)
            if context.mode != 'OBJECT':
                box.label(text="Object mode only", icon='INFO')
        else:
            row = box.row()
            row.scale_y = 1.3
            row.operator("object.sts_add_solidify", icon='MOD_SOLIDIFY')

        row = layout.row(align=True)
        row.enabled = context.mode == 'EDIT_MESH'
        row.operator("mesh.tris_convert_to_quads", text="Tris to Quads",
                     icon='FACE_MAPS')
        row.operator("mesh.quads_convert_to_tris", text="Triangulate",
                     icon='MOD_TRIANGULATE')
        if context.mode != 'EDIT_MESH':
            layout.label(text="Edit mode only", icon='INFO')


classes = (
    OBJECT_OT_sts_add_solidify,
    VIEW3D_PT_sts_mesh_tools,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
