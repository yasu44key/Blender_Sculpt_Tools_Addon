"""Sculpt tab panel for Strip Draw."""

import bpy

from ...core import nodes, tabs
from . import strip


class VIEW3D_PT_sts_strip_draw(bpy.types.Panel):
    bl_label = "Strip Draw"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        s = context.scene.sts_strip_draw
        obj = context.active_object

        if context.mode == 'EDIT_CURVE' and strip.get(obj) is not None:
            col = layout.column()
            col.label(text="Draw on the surface (Draw tool)", icon='GREASEPENCIL')
            row = col.row()
            row.scale_y = 1.4
            row.operator("curve.sts_strip_finish", icon='CHECKMARK')
            self._draw_strip(layout, strip.get(obj))
            return
        if context.mode != 'OBJECT':
            layout.label(text="Object Mode only", icon='INFO')
            return

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(s, "target")
        col.prop(s, "style", expand=True)
        col.prop(s, "width")
        col.prop(s, "offset")
        col.prop(s, "thickness")
        if s.style == 'CLAY':
            col.prop(s, "voxel_size")
        col.prop(s, "use_pressure")
        row = layout.row()
        row.scale_y = 1.4
        row.operator("curve.sts_strip_start", icon='GREASEPENCIL')
        layout.operator("object.sts_strip_from_curves", icon='CURVE_DATA')

        mod = strip.get(obj)
        if mod is not None:
            self._draw_strip(layout, mod)
            layout.operator("object.sts_strip_to_mesh", icon='MESH_DATA')

    @staticmethod
    def _draw_strip(layout, mod):
        box = layout.box()
        box.label(text="This strip", icon='MODIFIER')
        col = box.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        for spec in strip.INPUTS:
            name = spec[0]
            nodes.draw_modifier_input(col, mod, nodes.socket_identifier(mod.node_group, name), name)


classes = (
    VIEW3D_PT_sts_strip_draw,
)
