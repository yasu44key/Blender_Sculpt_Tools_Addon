"""Curve tab panel for NURBS Grid."""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_nurbs_grid(bpy.types.Panel):
    bl_label = "NURBS Grid"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.CURVE

    def draw(self, context):
        layout = self.layout
        s = context.scene.sts_nurbs_grid

        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()
        col.prop(s, "u_count")
        col.prop(s, "use_drag")
        if s.use_drag:
            col.prop(s, "drag_interval")
        col.prop(s, "snap")
        col.prop(s, "snap_nurbs_only")
        col.prop(s, "weight")

        layout.use_property_split = False
        row = layout.row()
        row.scale_y = 1.6
        row.enabled = context.mode == 'OBJECT'
        row.operator("surface.sts_nurbs_grid_draw", text="Start Drawing", icon='SURFACE_NSURFACE')

        col = layout.column(align=True)
        for line in ops.HELP_LINES:
            col.label(text=line)

        surfaces = [o for o in context.selected_objects if o.type == 'SURFACE']
        box = layout.box()
        box.label(text="Patchwork", icon='MESH_GRID')
        row = box.row(align=True)
        row.enabled = len(surfaces) >= 2
        row.operator("object.sts_nurbs_join", icon='OUTLINER_OB_SURFACE')
        row = box.row(align=True)
        row.enabled = len(surfaces) >= 1
        row.operator("object.sts_nurbs_flip", icon='NORMALS_FACE')
        box.label(text="After joining: Edit Mode, select border points, F", icon='INFO')

        box = layout.box()
        box.label(text="Loop", icon='CON_FOLLOWPATH')
        obj = context.active_object
        if obj is not None and obj.type == 'SURFACE' and obj.data.splines:
            spline = obj.data.splines[0]
            row = box.row(align=True)
            row.operator("surface.sts_nurbs_cyclic", text="Loop U",
                         depress=spline.use_cyclic_u).axis = 'U'
            row.operator("surface.sts_nurbs_cyclic", text="Loop V",
                         depress=spline.use_cyclic_v).axis = 'V'
        else:
            box.label(text="Select a NURBS surface", icon='INFO')


classes = (
    VIEW3D_PT_sts_nurbs_grid,
)
