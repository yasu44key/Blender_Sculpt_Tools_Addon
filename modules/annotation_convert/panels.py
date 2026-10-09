"""Annotation Convert panel (Curve tab)."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_annotation_convert(bpy.types.Panel):
    bl_label = "Annotation Convert"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.CURVE

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("curve.sts_annotation_convert", text="Bezier", icon='CURVE_BEZCURVE').target = 'BEZIER'
        row.operator("curve.sts_annotation_convert", text="Mesh", icon='MESH_DATA').target = 'MESH'
        if context.mode == 'OBJECT':
            layout.label(text="Adjust with F9 after converting")
        else:
            layout.label(text="Object Mode only", icon='INFO')


classes = (
    VIEW3D_PT_sts_annotation_convert,
)
