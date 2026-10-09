"""Wear panel (Sculpt tab)."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_wear(bpy.types.Panel):
    bl_label = "Wear"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.3
        row.operator("object.sts_wear", text="Wear", icon='MOD_DISPLACE')
        if context.mode == 'OBJECT':
            layout.label(text="Adjust with F9 after running")
        else:
            layout.label(text="Object Mode only", icon='INFO')


classes = (
    VIEW3D_PT_sts_wear,
)
