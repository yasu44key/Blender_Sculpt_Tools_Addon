"""Align Tools panel (Model tab)."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_align_tools(bpy.types.Panel):
    bl_label = "Align Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        edit = context.mode == 'EDIT_MESH'
        meshes = [o for o in context.selected_objects if o.type == 'MESH']

        box = layout.box()
        box.label(text="Align to Axis", icon='ORIENTATION_GLOBAL')
        row = box.row()
        row.enabled = edit
        row.scale_y = 1.2
        row.operator("object.sts_align_to_axis", text="Align to Axis")
        if not edit:
            box.label(text="Edit mode only", icon='INFO')

        box = layout.box()
        box.label(text="Origin to Bottom", icon='PIVOT_BOUNDBOX')
        row = box.row()
        row.enabled = bool(meshes)
        row.scale_y = 1.2
        row.operator("object.sts_origin_to_bottom", text="Origin to Bottom")
        if not meshes:
            box.label(text="Select a mesh", icon='INFO')

        box = layout.box()
        box.label(text="Drop to Surface", icon='TRIA_DOWN_BAR')
        row = box.row()
        row.enabled = bool(meshes)
        row.scale_y = 1.2
        row.operator("object.sts_drop_to_surface", text="Drop to Surface")
        if not meshes:
            box.label(text="Select a mesh", icon='INFO')

        box = layout.box()
        box.label(text="Match Cursor", icon='PIVOT_CURSOR')
        row = box.row()
        row.enabled = bool(context.selected_objects)
        row.scale_y = 1.2
        row.operator("object.sts_match_cursor", text="Match Cursor")


classes = (
    VIEW3D_PT_sts_align_tools,
)
