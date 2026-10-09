"""Panel Raise panel (Model tab)."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_panel_raise(bpy.types.Panel):
    bl_label = "Panel Raise"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.3
        row.operator("mesh.sts_panel_raise", text="Panel Raise", icon='MOD_SOLIDIFY')
        if context.mode == 'EDIT_MESH':
            layout.label(text="Adjust with F9 after running")
        else:
            layout.label(text="Edit Mode only", icon='INFO')


classes = (
    VIEW3D_PT_sts_panel_raise,
)
