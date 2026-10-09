"""Model tab panel and edit-mode menus for Point Smooth."""

import bpy

from ...core import tabs


class VIEW3D_PT_sts_point_smooth(bpy.types.Panel):
    bl_label = "Point Smooth"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        if context.mode not in {'EDIT_MESH', 'EDIT_CURVE', 'EDIT_SURFACE'}:
            layout.label(text="Edit Mode only", icon='INFO')
            return
        row = layout.row()
        row.scale_y = 1.5
        row.operator("object.sts_point_smooth", icon='MOD_SMOOTH')
        layout.label(text="Adjust with F9 after running", icon='INFO')

        box = layout.box()
        box.label(text="Inflate Points", icon='NORMALS_VERTEX')
        box.operator("object.sts_point_inflate", icon='NORMALS_VERTEX')

        box = layout.box()
        box.label(text="Wrap", icon='MOD_SHRINKWRAP')
        box.prop(context.scene.sts_point_smooth, "wrap_target")
        box.operator("object.sts_point_wrap", icon='MOD_SHRINKWRAP')


def menu_mesh(self, _context):
    self.layout.operator("object.sts_point_smooth", text="Point Smooth", icon='MOD_SMOOTH')


def menu_curve(self, _context):
    self.layout.operator("object.sts_point_smooth", text="Point Smooth", icon='MOD_SMOOTH')


classes = (
    VIEW3D_PT_sts_point_smooth,
)
