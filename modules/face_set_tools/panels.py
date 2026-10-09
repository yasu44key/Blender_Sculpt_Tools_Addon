"""Sculpt tab panel for Face Set Tools."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_face_set_tools(bpy.types.Panel):
    bl_label = "Face Sets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.SCULPT

    def draw(self, context):
        layout = self.layout
        if context.mode != 'SCULPT':
            layout.label(text="Sculpt Mode only")
            return

        s = context.scene.sts_face_set_tools
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = layout.column()
        col.prop(s, "mode", expand=True)
        col.prop(s, "invert")

        layout.use_property_split = False
        row = layout.row()
        row.scale_y = 1.6
        row.operator("sculpt.sts_face_set_to_mask", text="Face Set to Mask",
                     icon='MOD_MASK', mode=s.mode, invert=s.invert)

        row = layout.row()
        row.scale_y = 1.3
        row.operator("sculpt.sts_face_set_smooth", text="Smooth Face Set", icon='MOD_SMOOTH')

        col = layout.column(align=True)
        col.operator("sculpt.face_sets_create", text="Face Set from Mask", mode='MASKED')
        col.operator("sculpt.mesh_filter", text="Smooth", type='SMOOTH')
        col.operator("sculpt.mesh_filter", text="Inflate", type='INFLATE')
        col.label(text="Smooth / Inflate: drag in the viewport")


classes = (
    VIEW3D_PT_sts_face_set_tools,
)
