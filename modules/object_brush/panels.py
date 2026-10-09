"""Sculpt tab panel for Object Brush."""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_object_brush(bpy.types.Panel):
    bl_label = "Object Brush"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        s = context.scene.sts_object_brush

        row = layout.row()
        row.scale_y = 1.6
        row.operator("object.sts_object_brush", icon='BRUSH_DATA')

        layout.use_property_split = True
        layout.use_property_decorate = False

        box = layout.box()
        col = box.column(align=True)
        col.prop(s, "source", expand=True)
        if s.source == 'OBJECT':
            col.prop(s, "brush_object")
        else:
            col.prop(s, "brush_collection")

        col = box.column(align=True)
        col.prop(s, "use_output_collection")
        if s.use_output_collection:
            col.prop(s, "target_collection")
            col.prop(s, "new_collection_name")

        col = layout.column(align=True)
        col.prop(s, "brush_mode", expand=True)
        if s.brush_mode == 'STROKE':
            col.prop(s, "spacing")
        else:
            col.prop(s, "grid_size")

        col = layout.column(align=True)
        col.prop(s, "base_scale")
        col.prop(s, "use_pressure")
        row = col.row(align=True)
        row.prop(s, "align_to_normal", toggle=True)
        row.prop(s, "align_to_stroke", toggle=True)
        col.prop(s, "jitter_scale", slider=True)
        col.prop(s, "random_rotation", slider=True)
        row = col.row(align=True)
        row.prop(s, "jitter_x")
        row.prop(s, "jitter_y")
        row.prop(s, "jitter_z")

        layout.use_property_split = False
        col = layout.column(align=True)
        for line in ops.HELP_LINES:
            col.label(text=line)


classes = (
    VIEW3D_PT_sts_object_brush,
)
