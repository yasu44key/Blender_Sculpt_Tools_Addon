"""Generate tab panel for Wave Surface."""

import bpy

from ...core import nodes, tabs
from . import surface


class VIEW3D_PT_sts_wave_surface(bpy.types.Panel):
    bl_label = "Wave Surface"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.GENERATE

    def draw(self, context):
        layout = self.layout
        if context.mode != 'OBJECT':
            layout.label(text="Object Mode only", icon='INFO')
            return
        obj = context.active_object
        mod = surface.get(obj) if obj is not None and obj.type == 'MESH' else None

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("mesh.sts_wave_surface_add", text="New Grid", icon='MOD_WAVE')
        sub = row.row(align=True)
        sub.enabled = obj is not None and obj.type == 'MESH' and mod is None
        sub.operator("object.sts_wave_surface_assign", icon='ADD')
        if mod is None or mod.node_group is None:
            return

        ng = mod.node_group
        for title, names in surface.input_names():
            box = layout.box()
            box.label(text=title)
            col = box.column(align=True)
            col.use_property_split = True
            col.use_property_decorate = False
            for name in names:
                nodes.draw_modifier_input(col, mod, nodes.socket_identifier(ng, name), name)
            if title == "Wave 3":
                box.operator("object.sts_wave_surface_scatter", icon='STICKY_UVS_DISABLE')

        layout.prop(mod, "show_viewport", text="Show Surface")
        row = layout.row(align=True)
        row.operator("object.modifier_apply", text="Apply (Bake)", icon='CHECKMARK').modifier = mod.name
        row.operator("object.sts_wave_surface_remove", text="Remove", icon='TRASH')


classes = (
    VIEW3D_PT_sts_wave_surface,
)
