"""Model tab panel for Sujibori (panel lines)."""

import bpy
from bpy.app.translations import pgettext_iface as iface

from ...core import tabs
from . import logic


class VIEW3D_PT_sts_sujibori(bpy.types.Panel):
    bl_label = "Panel Lines"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if obj is not None and obj.type == 'CURVE':
            target = logic.target_of_line(obj)
            if target is not None:
                layout.label(text=iface("Line of") + " " + target.name, icon='CURVE_BEZCURVE',
                             translate=False)
                return

        if obj is None or obj.type != 'MESH':
            layout.label(text="Select the mesh to carve", icon='INFO')
            return
        if context.mode != 'OBJECT':
            layout.label(text="Object Mode only", icon='INFO')
            return

        s = obj.sts_sujibori
        if not logic.is_set_up(obj):
            col = layout.column()
            col.scale_y = 1.3
            col.operator("object.sts_sujibori_setup", text="Set Up (Live)", icon='GEOMETRY_NODES').method = 'LIVE'
            col.operator("object.sts_sujibori_setup", text="Set Up (Boolean)", icon='MOD_BOOLEAN').method = 'BOOLEAN'
            return

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(s, "method")
        layout.prop(s, "width")
        layout.prop(s, "solver")

        mod = obj.modifiers.get(logic.GN_MOD if s.method == 'LIVE' else logic.BOOL_MOD)
        if mod is not None:
            layout.prop(mod, "show_viewport", text="Show Grooves")

        layout.use_property_split = False
        row = layout.row(align=True)
        row.scale_y = 1.3
        if hasattr(bpy.types, "CURVE_OT_sts_draw_start"):
            row.operator("object.sts_sujibori_draw_line", icon='GREASEPENCIL')
        row.operator("object.sts_sujibori_add_lines", icon='ADD')
        if s.method == 'BOOLEAN':
            layout.operator("object.sts_sujibori_update", icon='FILE_REFRESH')
            layout.label(text="Press Update Grooves after editing lines or width", icon='INFO')

        lines = logic.line_curves(s)
        box = layout.box()
        box.label(text=iface("Lines") + f": {len(lines)}", icon='CURVE_BEZCURVE', translate=False)
        col = box.column(align=True)
        for line in lines:
            row = col.row(align=True)
            row.label(text=line.name, translate=False)
            row.operator("object.sts_sujibori_remove_line", text="", icon='X').line = line.name

        row = layout.row(align=True)
        if mod is not None:
            row.operator("object.modifier_apply", text="Apply (Bake)", icon='CHECKMARK').modifier = mod.name
        row.operator("object.sts_sujibori_remove", icon='TRASH')


classes = (
    VIEW3D_PT_sts_sujibori,
)
