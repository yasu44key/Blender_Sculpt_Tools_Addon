"""Sculpt tab panel for Thickness Guard."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_thickness_guard(bpy.types.Panel):
    bl_label = "Thickness Guard"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("object.sts_thickness_bake", text="Bake Thickness", icon='NORMALS_FACE')
        col.operator("object.sts_thickness_select", text="Select Thin", icon='MOD_DECIM')
        col.operator("object.sts_thickness_fix", text="Fix Thin", icon='MOD_SOLIDIFY')
        col.operator("object.sts_thickness_to_mask", text="Thickness to Mask", icon='MOD_MASK')
        layout.label(text="Adjust with F9 after running")

        box = layout.box()
        s = context.scene.sts_thickness_brush
        col = box.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(s, "min_thickness")
        col.prop(s, "radius")
        col.prop(s, "strength", slider=True)
        row = box.row()
        row.scale_y = 1.3
        row.operator("object.sts_thickness_guard_brush", icon='BRUSH_DATA')


classes = (
    VIEW3D_PT_sts_thickness_guard,
)
