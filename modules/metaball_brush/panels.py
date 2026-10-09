"""Sculpt tab panel for Metaball Brush."""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_metaball_brush(bpy.types.Panel):
    bl_label = "Metaball Brush"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        s = context.scene.sts_metaball_brush

        row = layout.row()
        row.scale_y = 1.6
        row.operator("object.sts_metaball_brush", icon='META_BALL')

        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()
        col.prop(s, "depth_mode")
        if s.depth_mode == 'PLANE':
            col.prop(s, "plane_axis")
        col.prop(s, "placement_mode")
        if s.placement_mode == 'TIME':
            col.prop(s, "interval")
        else:
            col.prop(s, "distance_px")
        col.prop(s, "undo_mode")
        col.prop(s, "min_size")
        col.prop(s, "max_size")
        col.prop(s, "pressure_curve")
        col.prop(s, "resolution")
        row = layout.row(align=True)
        row.prop(s, "mirror_x", toggle=True)
        row.prop(s, "mirror_y", toggle=True)
        row.prop(s, "mirror_z", toggle=True)

        layout.use_property_split = False
        col = layout.column(align=True)
        for line in ops.HELP_LINES:
            col.label(text=line)

        if hasattr(bpy.types, "OBJECT_OT_sts_voxel_join_remesh"):
            row = layout.row()
            row.scale_y = 1.3
            row.operator("object.sts_voxel_join_remesh", icon='MOD_REMESH')


classes = (
    VIEW3D_PT_sts_metaball_brush,
)
