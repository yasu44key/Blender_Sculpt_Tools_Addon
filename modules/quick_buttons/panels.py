"""Utility tab panel: one-press buttons."""

import math

import bpy

from ...core import tabs

ANGLES = (-90, -45, -30, 30, 45, 90)


class VIEW3D_PT_sts_quick_buttons(bpy.types.Panel):
    bl_label = "Quick Buttons"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.UTILITY

    def draw(self, context):
        layout = self.layout
        ts = context.scene.tool_settings

        if context.mode == 'OBJECT':
            box = layout.box()
            for channel, label, value in (('LOCATION', "Location", "0"), ('ROTATION', "Rotation", "0"),
                                          ('SCALE', "Scale", "1")):
                split = box.split(factor=0.3, align=True)
                split.label(text=label)
                row = split.row(align=True)
                for axis in ("X", "Y", "Z"):
                    op = row.operator("object.sts_quick_reset", text=f"{axis} {value}", translate=False)
                    op.channel, op.axis = channel, axis
                op = row.operator("object.sts_quick_reset", text="All")
                op.channel, op.axis = channel, 'ALL'

        box = layout.box()
        box.label(text="Rotate (global)")
        col = box.column(align=True)
        for axis in ("X", "Y", "Z"):
            row = col.row(align=True)
            for a in ANGLES:
                op = row.operator("view3d.sts_quick_rotate", text=f"{axis}{a:+d}", translate=False)
                op.axis, op.angle = axis, math.radians(a)
        row = box.row(align=True)
        row.label(text="Flatten")
        for axis in ("X", "Y", "Z"):
            row.operator("view3d.sts_quick_flatten", text=axis, translate=False).axis = axis
        row = box.row(align=True)
        row.label(text="Mirror")
        for axis in ("X", "Y", "Z"):
            row.operator("view3d.sts_quick_mirror", text=axis, translate=False).axis = axis
        s = context.scene.sts_quick_buttons
        box.prop(s, "step")
        row = box.row(align=True)
        for axis in ("X", "Y", "Z"):
            for sign in (-1, 1):
                op = row.operator("view3d.sts_quick_step", text=f"{axis}{'+' if sign > 0 else '-'}", translate=False)
                op.axis, op.distance = axis, sign * s.step

        box = layout.box()
        box.label(text="Pivot Point")
        box.row(align=True).prop(ts, "transform_pivot_point", expand=True, icon_only=True)
        box.label(text="Orientation")
        box.row(align=True).prop(context.scene.transform_orientation_slots[0], "type", expand=True)
        if context.mode == 'OBJECT':
            row = box.row(align=True)
            row.label(text="Affect Only")
            row.prop(ts, "use_transform_data_origin", text="Origins", toggle=True)
            row.prop(ts, "use_transform_pivot_point_align", text="Locations", toggle=True)
            row.prop(ts, "use_transform_skip_children", text="Parents", toggle=True)

        box = layout.box()
        box.label(text="3D Cursor")
        row = box.row(align=True)
        row.operator("view3d.snap_cursor_to_center", text="World Origin")
        row.operator("view3d.snap_cursor_to_selected", text="Selection")
        box.operator("view3d.snap_selected_to_cursor", text="Selection to Cursor").use_offset = True
        if context.mode == 'OBJECT':
            row = box.row(align=True)
            row.operator("object.origin_set", text="Origin to Geometry").type = 'ORIGIN_GEOMETRY'
            row.operator("object.origin_set", text="Origin to Cursor").type = 'ORIGIN_CURSOR'


classes = (
    VIEW3D_PT_sts_quick_buttons,
)
