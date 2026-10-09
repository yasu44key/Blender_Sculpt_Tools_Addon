"""Sculpt tab panel for Voxel Remesh."""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_voxel_remesh(bpy.types.Panel):
    bl_label = "Voxel Remesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.enabled = context.mode == 'OBJECT'
        row = col.row()
        row.scale_y = 1.4
        row.operator("object.sts_voxel_join_remesh", icon='MOD_REMESH')
        if context.mode != 'OBJECT':
            layout.label(text="Join & Remesh: Object Mode only", icon='INFO')

        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return

        box = layout.box()
        box.label(text=obj.name, icon='MESH_DATA', translate=False)
        mod = ops.find_voxel_modifier(obj)
        if mod is not None:
            box.label(text="Voxel Remesh modifier (preview)", icon='MODIFIER')
            col = box.column(align=True)
            col.prop(mod, "voxel_size")
            col.prop(mod, "adaptivity")
        else:
            col = box.column(align=True)
            col.prop(obj.data, "remesh_voxel_size")
            col.prop(obj.data, "remesh_voxel_adaptivity")
        box.operator("object.sts_voxel_apply_remesh", icon='CHECKMARK')
        if context.mode == 'SCULPT':
            box.operator("object.voxel_size_edit", text="Edit Voxel Size (Shift+R)", icon='VIEWZOOM')
            self._draw_dyntopo(context, layout, obj)

    @staticmethod
    def _draw_dyntopo(context, layout, obj):
        """Dyntopo next to the remesh: sculpt detail, then Apply Remesh to even it out."""
        box = layout.box()
        on = obj.use_dynamic_topology_sculpting
        box.operator("sculpt.dynamic_topology_toggle", text="Dyntopo: On" if on else "Dyntopo: Off",
                     icon='CHECKBOX_HLT' if on else 'CHECKBOX_DEHLT', depress=on)
        if not on:
            return
        s = context.tool_settings.sculpt
        col = box.column(align=True)
        col.prop(s, "detail_type_method", text="")
        if s.detail_type_method in {'CONSTANT', 'MANUAL'}:
            row = col.row(align=True)
            row.prop(s, "constant_detail_resolution")
            row.operator("sculpt.detail_flood_fill", text="", icon='BRUSH_DATA')
        elif s.detail_type_method == 'BRUSH':
            col.prop(s, "detail_percent")
        else:
            col.prop(s, "detail_size")
        col.prop(s, "detail_refine_method", text="")
        box.label(text="Apply Remesh keeps Dyntopo on", icon='INFO')


classes = (
    VIEW3D_PT_sts_voxel_remesh,
)
