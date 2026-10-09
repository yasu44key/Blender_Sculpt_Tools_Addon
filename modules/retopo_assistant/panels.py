"""Model tab panel for Retopo Assistant.

The modifier's own values are drawn straight from "STS Decimate" (no Scene
copy). The vertex-count preview reads the evaluated mesh's length — the old
panel copied the whole evaluated mesh on every redraw.
"""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_retopo_assistant(bpy.types.Panel):
    bl_label = "Retopo Assistant"
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
            layout.label(text="Object or Sculpt Mode only", icon='INFO')
            return

        mod = ops.get_mod(obj)
        if mod is None:
            col = layout.column()
            col.scale_y = 1.2
            col.operator("object.sts_retopo_add_decimate", icon='MOD_DECIM')
        else:
            col = layout.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(mod, "decimate_type", text="Type")
            if mod.decimate_type == 'COLLAPSE':
                col.prop(mod, "ratio", slider=True)
                col.prop(mod, "use_collapse_triangulate")
                col.prop(mod, "use_symmetry")
                if mod.use_symmetry:
                    col.prop(mod, "symmetry_axis", text="Axis")
            elif mod.decimate_type == 'UNSUBDIV':
                col.prop(mod, "iterations")
            else:  # DISSOLVE (Planar)
                col.prop(mod, "angle_limit")
                col.prop(mod, "use_dissolve_boundaries")

            dg = context.evaluated_depsgraph_get()
            ev = obj.evaluated_get(dg)
            layout.label(
                text=f"Verts: {len(obj.data.vertices)} -> {len(ev.data.vertices)}",
                icon='INFO',
            )

            box = layout.box()
            box.label(text="Ridge Protection", icon='GROUP_VERTEX')
            row = box.row(align=True)
            row.operator("object.sts_retopo_ridge_from_mask", icon='MOD_MASK')
            row.operator("object.sts_retopo_ridge_from_angle", icon='SNAP_EDGE')
            if obj.vertex_groups.get(ops.RIDGE_GROUP) is not None:
                box.prop_search(mod, "vertex_group", obj, "vertex_groups", text="Group")
                box.prop(mod, "invert_vertex_group")
                box.prop(mod, "vertex_group_factor", slider=True)
            else:
                box.label(text="No Ridge group yet", icon='INFO')

            row = layout.row(align=True)
            row.scale_y = 1.2
            row.operator("object.sts_retopo_apply", icon='CHECKMARK')
            row.operator("object.sts_retopo_remove", icon='TRASH')

        if context.mode == 'SCULPT':
            row = layout.row(align=True)
            row.operator("paint.mask_flood_fill", text="Clear Mask", mode='VALUE', value=0.0)
            row.operator("paint.mask_flood_fill", text="Invert Mask", mode='INVERT')


classes = (
    VIEW3D_PT_sts_retopo_assistant,
)
