"""Model tab panel for Edge Creation."""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_edge_creation(bpy.types.Panel):
    bl_label = "Edge Draw"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        s = context.scene.sts_edge_creation

        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()
        col.prop(s, "target")
        col.prop(s, "depth_mode")
        if s.depth_mode == 'PLANE':
            col.prop(s, "plane_axis")
        col.prop(s, "surface_offset")
        col.prop(s, "drag_interval")
        col.prop(s, "fill_on_close")

        layout.use_property_split = False
        row = layout.row()
        row.scale_y = 1.6
        row.operator("mesh.sts_edge_draw", icon='GREASEPENCIL')

        col = layout.column(align=True)
        for line in ops.HELP_LINES:
            col.label(text=line)

        sub = layout.column()
        sub.enabled = context.mode == 'EDIT_MESH'
        sub.operator("mesh.edge_face_add", text="Fill Face", icon='FACE_MAPS')


classes = (
    VIEW3D_PT_sts_edge_creation,
)
