"""Model tab panel for Smooth Normals."""

import bpy

from ...core import nodes, tabs
from . import normals


class VIEW3D_PT_sts_smooth_normals(bpy.types.Panel):
    bl_label = "Smooth Normals"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            layout.label(text="Select a mesh", icon='INFO')
            return
        if context.mode not in {'OBJECT', 'SCULPT'}:
            layout.label(text="Object Mode only", icon='INFO')
            return
        mod = normals.get(obj)
        if mod is None or mod.node_group is None:
            col = layout.column()
            col.scale_y = 1.2
            col.operator("object.sts_smooth_normals_add", icon='NORMALS_VERTEX')
            return

        ng = mod.node_group
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        ident = nodes.socket_identifier(ng, "Vertex Group")
        props = getattr(mod, "properties", None)
        if props is not None and hasattr(props.inputs, ident):
            # 5.2: a plain RNA string, so it can search the object's groups
            col.prop_search(getattr(props.inputs, ident), "value", obj, "vertex_groups", text="Vertex Group")
        else:
            nodes.draw_modifier_input(col, mod, ident, "Vertex Group")
        col.operator("object.sts_smooth_normals_from_mask", icon='MOD_MASK')
        for name in ("Strength", "Smoothness"):
            nodes.draw_modifier_input(col, mod, nodes.socket_identifier(ng, name), name)
        col.prop(mod, "show_viewport", text="Show Effect")
        row = layout.row(align=True)
        row.operator("object.modifier_apply", text="Apply (Bake)", icon='CHECKMARK').modifier = mod.name
        row.operator("object.sts_smooth_normals_remove", text="Remove", icon='TRASH')


classes = (
    VIEW3D_PT_sts_smooth_normals,
)
